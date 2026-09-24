#!/usr/bin/env python3
"""
BM25 IDF vs Engine-Weighting probe — 5 configs, top-10, 4 queries.

Tests IDF and engine-count-inverse-weighting as separate and combined axes
relative to the Vanilla BM25 baseline.

Config matrix:
  1. Hard-Slot         — _merge_and_rank baseline (12 General / 6 Academic / 2 QA)
  2. Vanilla BM25      — BM25Uniform (no IDF, no weighting), b=0.75, k1=1.2
  3. BM25 + IDF        — BM25Okapi (standard per-pool IDF), same params
  4. BM25 + Weighting  — BM25Uniform × engine-count-inverse weight per URL
  5. BM25+IDF+Weighting— BM25Okapi × engine-count-inverse weight per URL

Engine-count-inverse weight for URL u:
  wt(u) = sum(1.0 / engine_counts[e] for e in u.engines)
  engine_counts[e] = number of raw results from engine e this query.
  Multi-engine URLs accumulate summed weights; high-volume engines
  (crossref=200, openalex=200) are naturally discounted vs low-volume
  (google~11, mojeek~10). Weighted score = bm25_score × wt.

Weighting applied to full pool (not truncated to 20 first) so re-ordering
by weighting does not miss candidates outside vanilla top-20.

Imports: QUERIES, VANILLA_K1, STOPWORDS, _build_pool, _tokenize, _doc_repr,
BM25Uniform from bm25_sweep_smoke.py (same directory).
"""

# INFRASTRUCTURE
import asyncio
import sys
import time
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from bm25_sweep_smoke import (
    BM25Uniform,
    QUERIES,
    STOPWORDS,
    VANILLA_K1,
    _build_pool,
    _doc_repr,
    _tokenize,
)
from src.search.browser import close_browser
from src.search.merge import _merge_and_rank
from src.search.search_web import _query_engines_concurrent, _select_engines

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N     = 10
BM25_K1   = VANILLA_K1   # 1.2
BM25_B    = 0.75
BM25_SW   = True
BM25_REPR = "title+snippet"

COMPARE_CONFIGS = [
    {"name": "Hard-Slot",            "type": "hardslot"},
    {"name": "Vanilla BM25",          "type": "uniform"},
    {"name": "BM25 + IDF",            "type": "okapi"},
    {"name": "BM25 + Weighting",      "type": "uniform_wt"},
    {"name": "BM25 + IDF + Weighting","type": "okapi_wt"},
]


# ORCHESTRATOR

async def run_probe() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bm25_idf_engine_{ts}.md"

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)

            t0 = time.perf_counter()
            raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
            fetch_ms = round((time.perf_counter() - t0) * 1000)

            pool          = _build_pool(raw_results)
            engine_counts = _compute_engine_counts(raw_results)

            t0 = time.perf_counter()
            config_tops = _rank_all_configs(raw_results, pool, query, engine_counts)
            rank_ms = round((time.perf_counter() - t0) * 1000)

            ok_count = sum(1 for s in engine_stats.values() if s["result_count"] > 0)
            print(
                f"  raw={len(raw_results)}, unique={len(pool)}, ok_engines={ok_count}, "
                f"fetch={fetch_ms}ms, rank={rank_ms}ms",
                file=sys.stderr,
            )
            query_sections.append(_build_query_section(
                query, config_tops, engine_stats, engine_counts,
                len(raw_results), len(pool), fetch_ms, rank_ms,
            ))
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, report_path, total_ms)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Total:  {total_ms}ms", file=sys.stderr)


# FUNCTIONS

# Count raw results per engine for this query
def _compute_engine_counts(raw_results) -> dict[str, int]:
    return dict(Counter(r.engine for r in raw_results))


# BM25 score full pool (no top-N truncation); return [(doc, score), ...] sorted desc
def _score_pool(pool: list[dict], query: str, use_okapi: bool) -> list[tuple[dict, float]]:
    if not pool:
        return []
    corpus = [_tokenize(_doc_repr(m, BM25_REPR), BM25_SW) for m in pool]
    qtoks  = _tokenize(query, BM25_SW)
    bm25   = BM25Okapi(corpus, k1=BM25_K1, b=BM25_B) if use_okapi else BM25Uniform(corpus, k1=BM25_K1, b=BM25_B)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = bm25.get_scores(qtoks)
    scores = np.nan_to_num(scores, nan=0.0)
    ranked = sorted(range(len(pool)), key=lambda i: -float(scores[i]))
    return [(pool[i], float(scores[i])) for i in ranked]


# Multiply each score by engine-count-inverse weight; re-sort descending
def _apply_engine_weighting(
    scored: list[tuple[dict, float]], engine_counts: dict[str, int]
) -> list[tuple[dict, float]]:
    weighted = [
        (doc, score * sum(1.0 / engine_counts.get(e, 1) for e in doc["engines"]))
        for doc, score in scored
    ]
    weighted.sort(key=lambda x: -x[1])
    return weighted


# Run all 5 configs; return list of {name, cfg, top10}
def _rank_all_configs(raw_results, pool: list[dict], query: str, engine_counts: dict) -> list[dict]:
    results = []
    for cfg in COMPARE_CONFIGS:
        t = cfg["type"]
        if t == "hardslot":
            ranked, _ = _merge_and_rank(raw_results)
            top10 = [
                {"url": r.url, "engines": r.engines or [r.engine], "score": None}
                for r in ranked[:TOP_N]
            ]
        elif t == "uniform":
            pairs = _score_pool(pool, query, use_okapi=False)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        elif t == "okapi":
            pairs = _score_pool(pool, query, use_okapi=True)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        elif t == "uniform_wt":
            pairs = _apply_engine_weighting(_score_pool(pool, query, use_okapi=False), engine_counts)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        elif t == "okapi_wt":
            pairs = _apply_engine_weighting(_score_pool(pool, query, use_okapi=True), engine_counts)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        results.append({"name": cfg["name"], "cfg": cfg, "top10": top10})
    return results


# Build markdown section for one query: metadata + engine-weight line + 5 stacked tables
def _build_query_section(
    query: str,
    config_tops: list[dict],
    engine_stats: dict,
    engine_counts: dict[str, int],
    total_raw: int,
    unique: int,
    fetch_ms: int,
    rank_ms: int,
) -> str:
    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)
    weight_line = ", ".join(
        f"{e}→{1.0/c:.4f}"
        for e, c in sorted(engine_counts.items(), key=lambda x: -x[1])
    )

    lines = [
        f"## {query}",
        "",
        f"**Raw:** {total_raw} | **Unique:** {unique} | **Engines ({len(ok_engines)}):** {engine_line}  ",
        f"**Engine weights (1/count):** {weight_line}  ",
        f"**Timing:** fetch={fetch_ms}ms, rank={rank_ms}ms",
        "",
    ]

    for ct in config_tops:
        lines += _render_config_table(ct)

    return "\n".join(lines)


def _render_config_table(ct: dict) -> list[str]:
    t = ct["cfg"]["type"]
    if t == "hardslot":
        label = "Hard-Slot baseline (12 General / 6 Academic / 2 QA)"
    elif t == "uniform":
        label = f"BM25Uniform — k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR} [no IDF]"
    elif t == "okapi":
        label = f"BM25Okapi   — k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR} [per-pool IDF]"
    elif t == "uniform_wt":
        label = f"BM25Uniform × engine-inv-wt — k1={BM25_K1}, b={BM25_B}, sw=on [no IDF + wt]"
    elif t == "okapi_wt":
        label = f"BM25Okapi   × engine-inv-wt — k1={BM25_K1}, b={BM25_B}, sw=on [IDF + wt]"

    lines = [
        f"#### {ct['name']} — {label}",
        "",
        "| # | Score | Engines | URL |",
        "|---|-------|---------|-----|",
    ]
    for i, item in enumerate(ct["top10"], 1):
        score_str = f"{item['score']:.5f}" if item["score"] is not None else "—"
        lines.append(f"| {i} | {score_str} | {', '.join(item['engines'])} | {item['url'][:90]} |")
    lines.append("")
    return lines


# Write report: header + per-query sections
def _write_report(sections: list[str], path: Path, total_ms: int) -> None:
    ts = path.stem.replace("bm25_idf_engine_", "")
    header = "\n".join([
        f"# BM25 IDF vs Engine-Weighting Probe — {ts}",
        "",
        f"**Queries:** {len(sections)}  ",
        f"**Configs:** Hard-Slot / BM25 / BM25+IDF / BM25+Wt / BM25+IDF+Wt  ",
        f"**BM25 params:** k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR}  ",
        f"**Engine weight:** wt(u) = sum(1/engine_count[e] for e in u.engines)  ",
        f"**Total wallclock:** {total_ms}ms",
    ])
    path.write_text("\n\n---\n\n".join([header] + sections), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(run_probe())
