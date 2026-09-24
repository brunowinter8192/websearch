#!/usr/bin/env python3
"""
BM25 per-engine top-K cap probe — 3 configs, top-10, 4 queries.

Tests whether capping each engine's contribution to top-K URLs (where
K = google result count for this query) before building the dedup pool
improves BM25 result quality vs the uncapped full pool.

Rationale: crossref/openalex return 200 results each — keyword-matched
but often irrelevant. Google returns ~11 highly-curated results. Capping
all engines to K~11 equalises engine contribution and removes the long
tail of low-quality academic matches before BM25 scoring.

Config matrix:
  1. Hard-Slot   — _merge_and_rank baseline (12/6/2 slots)
  2. BM25 UNCAPPED — BM25Uniform on full dedup pool
  3. BM25 CAPPED   — BM25Uniform on pool built from top-K per engine
     K = engine_stats['google']['result_count'] for this query;
     fallback K=10 if google absent or returned 0.

Report header per query shows:
  raw=N, K=K, capped_pre_dedup=C, unique_capped=U, unique_full=F

Imports: QUERIES, VANILLA_K1, STOPWORDS, _build_pool, _tokenize, _doc_repr,
BM25Uniform from bm25_sweep_smoke.py (same directory).
"""

# INFRASTRUCTURE
import asyncio
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

SCRIPT_DIR   = Path(__file__).parent.parent
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
    {"name": "Hard-Slot",          "type": "hardslot"},
    {"name": "Vanilla BM25 UNCAPPED", "type": "bm25_uncapped"},
    {"name": "Vanilla BM25 CAPPED",   "type": "bm25_capped"},
]


# ORCHESTRATOR

async def run_probe() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"bm25_capped_{ts}.md"

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

            t0 = time.perf_counter()
            config_tops, K, capped_pre_dedup, unique_capped, unique_full = _rank_all_configs(
                raw_results, engine_stats, query
            )
            rank_ms = round((time.perf_counter() - t0) * 1000)

            ok_count = sum(1 for s in engine_stats.values() if s["result_count"] > 0)
            print(
                f"  raw={len(raw_results)}, K={K}, capped_pre={capped_pre_dedup}, "
                f"unique_capped={unique_capped}, unique_full={unique_full}, "
                f"fetch={fetch_ms}ms, rank={rank_ms}ms",
                file=sys.stderr,
            )
            query_sections.append(_build_query_section(
                query, config_tops, engine_stats, K,
                len(raw_results), capped_pre_dedup, unique_capped, unique_full,
                fetch_ms, rank_ms,
            ))
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, report_path, total_ms)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Total:  {total_ms}ms", file=sys.stderr)


# FUNCTIONS

# K = google result count; fallback 10 if absent or zero
def _compute_K(engine_stats: dict) -> int:
    K = engine_stats.get("google", {}).get("result_count", 0)
    return K if K > 0 else 10


# Keep only results within top-K per-engine position
def _cap_raw_results(raw_results, K: int) -> list:
    return [r for r in raw_results if r.position <= K]


# BM25Uniform score full pool; return [(doc, score), ...] sorted desc (no truncation)
def _score_bm25(pool: list[dict], query: str) -> list[tuple[dict, float]]:
    if not pool:
        return []
    corpus = [_tokenize(_doc_repr(m, BM25_REPR), BM25_SW) for m in pool]
    qtoks  = _tokenize(query, BM25_SW)
    bm25   = BM25Uniform(corpus, k1=BM25_K1, b=BM25_B)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = bm25.get_scores(qtoks)
    scores = np.nan_to_num(scores, nan=0.0)
    ranked = sorted(range(len(pool)), key=lambda i: -float(scores[i]))
    return [(pool[i], float(scores[i])) for i in ranked]


# Run all 3 configs; return (config_tops, K, capped_pre_dedup, unique_capped, unique_full)
def _rank_all_configs(raw_results, engine_stats: dict, query: str) -> tuple:
    K           = _compute_K(engine_stats)
    capped_raw  = _cap_raw_results(raw_results, K)
    full_pool   = _build_pool(raw_results)
    capped_pool = _build_pool(capped_raw)

    results = []
    for cfg in COMPARE_CONFIGS:
        t = cfg["type"]
        if t == "hardslot":
            ranked, _ = _merge_and_rank(raw_results)
            top10 = [
                {"url": r.url, "engines": r.engines or [r.engine], "score": None}
                for r in ranked[:TOP_N]
            ]
        elif t == "bm25_uncapped":
            pairs = _score_bm25(full_pool, query)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        elif t == "bm25_capped":
            pairs = _score_bm25(capped_pool, query)
            top10 = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in pairs[:TOP_N]]
        results.append({"name": cfg["name"], "cfg": cfg, "top10": top10})

    return results, K, len(capped_raw), len(capped_pool), len(full_pool)


# Build markdown section: metadata + 3 stacked top-10 tables
def _build_query_section(
    query: str,
    config_tops: list[dict],
    engine_stats: dict,
    K: int,
    total_raw: int,
    capped_pre_dedup: int,
    unique_capped: int,
    unique_full: int,
    fetch_ms: int,
    rank_ms: int,
) -> str:
    ok_engines  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    engine_line = ", ".join(f"{n}={c}" for n, c in ok_engines)

    lines = [
        f"## {query}",
        "",
        f"**Raw:** {total_raw} | **K (google count):** {K} | "
        f"**Capped pre-dedup:** {capped_pre_dedup} | **Unique capped:** {unique_capped} | **Unique full:** {unique_full}  ",
        f"**Engines ({len(ok_engines)}):** {engine_line}  ",
        f"**Timing:** fetch={fetch_ms}ms, rank={rank_ms}ms",
        "",
    ]

    for ct in config_tops:
        t = ct["cfg"]["type"]
        if t == "hardslot":
            label = "Hard-Slot baseline (12 General / 6 Academic / 2 QA)"
        elif t == "bm25_uncapped":
            label = f"BM25Uniform — k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR} [full pool, N={unique_full}]"
        elif t == "bm25_capped":
            label = f"BM25Uniform — k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR} [capped pool K={K}, N={unique_capped}]"

        lines += [
            f"#### {ct['name']} — {label}",
            "",
            "| # | Score | Engines | URL |",
            "|---|-------|---------|-----|",
        ]
        for i, item in enumerate(ct["top10"], 1):
            score_str = f"{item['score']:.4f}" if item["score"] is not None else "—"
            lines.append(f"| {i} | {score_str} | {', '.join(item['engines'])} | {item['url'][:90]} |")
        lines.append("")

    return "\n".join(lines)


# Write report: header + per-query sections
def _write_report(sections: list[str], path: Path, total_ms: int) -> None:
    ts = path.stem.replace("bm25_capped_", "")
    header = "\n".join([
        f"# BM25 Per-Engine Top-K Cap Probe — {ts}",
        "",
        f"**Queries:** {len(sections)}  ",
        f"**Configs:** Hard-Slot / BM25 Uncapped / BM25 Capped  ",
        f"**BM25 params:** k1={BM25_K1}, b={BM25_B}, sw=on, repr={BM25_REPR}  ",
        f"**Cap rule:** K = google result count for this query (fallback K=10)  ",
        f"**Total wallclock:** {total_ms}ms",
    ])
    path.write_text("\n\n---\n\n".join([header] + sections), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(run_probe())
