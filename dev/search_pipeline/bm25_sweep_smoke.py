#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.browser import close_browser
from src.search.merge import ACADEMIC, GENERAL, QA, _merge_and_rank
from src.search.result import SearchResult
from src.search.search_web import _query_engines_concurrent, _select_engines

from _bm25_sweep_smoke_report import _build_query_section, _write_report

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "transformer attention mechanism",
    "best espresso machine 2026",
    "python asyncio context manager",
    "kubernetes service mesh comparison",
]

TOP_N = 20
VANILLA_K1 = 1.2

STOPWORDS = frozenset({
    "the", "of", "in", "and", "a", "an", "is", "to", "for", "or", "on", "at",
    "by", "with", "why", "how", "what", "when", "where", "are", "be", "as",
    "from", "that", "this", "it", "was", "not", "has", "but", "have", "been",
    "its", "their", "they", "which", "about", "into", "than", "over", "do",
    "does", "did", "will", "would",
})

BM25_MAIN_GRID = [
    {"b": b, "sw": sw, "repr": dr}
    for b  in [0.0, 0.5, 0.75, 1.0]
    for sw in [True, False]
    for dr in ["title+snippet", "title3x"]
]

BM25_K1_SWEEP = [{"k1": k1} for k1 in [0.5, 1.2, 2.0, 3.0]]


class BM25Uniform(BM25Okapi):
    def _calc_idf(self, nd):
        for word in nd:
            self.idf[word] = 1.0
        self.average_idf = 1.0


# ORCHESTRATOR

async def run_probe() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bm25_sweep_{ts}.md"

    selected, _ = _select_engines(None)
    engine_names = sorted(selected.keys())
    print(f"Engines ({len(selected)}): {', '.join(engine_names)}", file=sys.stderr)
    print(f"Queries:  {len(QUERIES)}", file=sys.stderr)
    print(f"Report:   {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    summaries: list[dict] = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            section, summary = await _run_one_query(qi, query, selected)
            query_sections.append(section)
            summaries.append(summary)
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, summaries, report_path, total_ms, TOP_N)
    print(f"\nReport:     {report_path}", file=sys.stderr)
    print(f"Total wall: {total_ms}ms", file=sys.stderr)


# FUNCTIONS

async def _run_one_query(qi: int, query: str, selected: dict) -> tuple[str, dict]:
    print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)

    t0 = time.perf_counter()
    raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
    fetch_ms = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    hard_slot_ranked, slot_counts = _merge_and_rank(raw_results)
    hard_slot_top = hard_slot_ranked[:TOP_N]
    hardslot_ms = round((time.perf_counter() - t0) * 1000)

    pool = _build_pool(raw_results)

    t0 = time.perf_counter()
    grid_results = _run_main_grid(pool, query)
    k1_results   = _run_k1_sweep(pool, query)
    bm25_total_ms = round((time.perf_counter() - t0) * 1000)

    ok_count = sum(1 for s in engine_stats.values() if s["result_count"] > 0)
    print(
        f"  raw={len(raw_results)}, unique={len(pool)}, ok_engines={ok_count}, "
        f"fetch={fetch_ms}ms, bm25={bm25_total_ms}ms",
        file=sys.stderr,
    )

    return _build_query_section(
        query, pool, hard_slot_top, slot_counts,
        grid_results, k1_results, engine_stats,
        len(raw_results), fetch_ms, hardslot_ms, bm25_total_ms, _classify,
    )


def _build_pool(raw_results: list[SearchResult]) -> list[dict]:
    merged: dict[str, dict] = {}
    for r in raw_results:
        if r.url not in merged:
            merged[r.url] = {
                "url":          r.url,
                "title":        r.title or "",
                "snippet":      r.snippet or "",
                "engines":      [r.engine],
                "snippets":     {r.engine: r.snippet} if r.snippet else {},
                "min_position": r.position,
            }
        else:
            m = merged[r.url]
            if r.engine not in m["engines"]:
                m["engines"].append(r.engine)
            if r.snippet:
                m["snippets"][r.engine] = r.snippet
            m["min_position"] = min(m["min_position"], r.position)
            if not m["title"] and r.title:
                m["title"] = r.title
    return list(merged.values())


def _tokenize(text: str, use_sw: bool) -> list[str]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    return [t for t in tokens if t not in STOPWORDS] if use_sw else tokens


def _doc_repr(m: dict, style: str) -> str:
    t, s = m["title"], m["snippet"]
    return f"{t} {t} {t} {s}" if style == "title3x" else f"{t} {s}"


def _bm25_rank(
    pool: list[dict], query: str, k1: float, b: float, use_sw: bool, repr_style: str
) -> list[tuple[dict, float]]:
    if not pool:
        return []
    corpus = [_tokenize(_doc_repr(m, repr_style), use_sw) for m in pool]
    qtoks  = _tokenize(query, use_sw)
    bm25   = BM25Uniform(corpus, k1=k1, b=b)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = bm25.get_scores(qtoks)
    scores = np.nan_to_num(scores, nan=0.0)
    ranked = sorted(range(len(pool)), key=lambda i: -float(scores[i]))
    return [(pool[i], float(scores[i])) for i in ranked[:TOP_N]]


def _run_main_grid(pool: list[dict], query: str) -> list[dict]:
    results = []
    for cfg in BM25_MAIN_GRID:
        top20 = _bm25_rank(pool, query, k1=VANILLA_K1, b=cfg["b"], use_sw=cfg["sw"], repr_style=cfg["repr"])
        results.append({"cfg": cfg, "top20": top20})
    return results


def _run_k1_sweep(pool: list[dict], query: str) -> list[dict]:
    results = []
    for cfg in BM25_K1_SWEEP:
        top20 = _bm25_rank(pool, query, k1=cfg["k1"], b=0.75, use_sw=True, repr_style="title+snippet")
        results.append({"cfg": cfg, "top20": top20})
    return results


def _classify(engines: list[str]) -> str:
    eng = set(engines)
    if eng & ACADEMIC:
        return "academic"
    if eng & QA:
        return "qa"
    return "general"


if __name__ == "__main__":
    asyncio.run(run_probe())
