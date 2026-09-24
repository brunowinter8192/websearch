#!/usr/bin/env python3
"""
Single-Query Pool Dump — capped pool vs Top-N for 4 configs (bead searxng-g82).

Sections: (1) per-engine raw  (2) full capped pool  (3) Top-N per config
          (4) comparison matrix (every pool URL × 4 configs → rank or —)

Hard-stop: google_count == 0 → exit. No fallback.
Services: embedding port 8084 (Qwen3-0.6B) / reranker port 8082 (Qwen3-0.6B)

Usage:
  ./venv/bin/python dev/search_pipeline/single_query_pool_dump.py [--query TEXT] [--output PATH]
"""

# INFRASTRUCTURE
import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from bm25_sweep_smoke import _build_pool, _doc_repr
from _single_query_pool_dump_report import _build_sections, _write_report
from rerank_probe_smoke import (
    EMBEDDING_URL,
    RERANKER_URL,
    embed_batch,
    cross_encoder_rerank,
    cosine_sim,
    _bm25_score,
    _verify_services,
    close_browser,
    _query_engines_concurrent,
    _select_engines,
)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR    = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_QUERY = "postgresql index types btree gin gist performance"
BM25_REPR     = "title+snippet"


# ORCHESTRATOR

async def run_probe(query: str, output_path: Path | None) -> None:
    _verify_services()

    now        = datetime.now()
    ts_slug    = now.strftime("%Y%m%d_%H%M%S")
    ts_display = now.strftime("%Y-%m-%d %H:%M:%S")
    slug       = query[:30].replace(" ", "_").replace("/", "_")
    report_path = output_path or (REPORT_DIR / f"single_query_pool_{slug}_{ts_slug}.md")

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Query:   {query}", file=sys.stderr)
    print(f"Report:  {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    t_wall = time.perf_counter()
    try:
        raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
        fetch_ms = round((time.perf_counter() - t_wall) * 1000)
    finally:
        await close_browser()

    google_count = engine_stats.get("google", {}).get("result_count", 0)
    if google_count == 0:
        sys.exit(
            f"STOP: google_count == 0 for query '{query}'.\n"
            f"Engine results: { {n: s['result_count'] for n, s in engine_stats.items()} }"
        )

    url_engine_pos = _build_url_engine_pos(raw_results, google_count)
    pool            = _build_capped_pool(raw_results, google_count)

    c1_top, c2_scored, c3_scored, c4_scored, c1_ms, c2_ms, c3_ms, c4_ms = _rank_all_configs(query, pool, google_count)

    wall_ms = round((time.perf_counter() - t_wall) * 1000)

    print(
        f"google_count={google_count}  pool={len(pool)}  fetch={fetch_ms}ms  "
        f"C1={c1_ms}ms  C2={c2_ms}ms  C3={c3_ms}ms  C4={c4_ms}ms  wall={wall_ms}ms",
        file=sys.stderr,
    )

    sections = _build_sections(
        query, ts_display, google_count, pool, engine_stats, wall_ms, raw_results, url_engine_pos,
        c1_top, c2_scored, c3_scored, c4_scored, c1_ms, c2_ms, c3_ms, c4_ms,
    )
    _write_report(sections, report_path)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

def _rank_all_configs(query: str, pool: list[dict], google_count: int) -> tuple:
    raw_texts   = [_doc_repr(m, BM25_REPR) for m in pool]
    valid_pairs = [(m, t) for m, t in zip(pool, raw_texts) if t.strip()]
    pool_v      = [m for m, _ in valid_pairs]
    texts_v     = [t for _, t in valid_pairs]

    t0     = time.perf_counter()
    c1_top = _rank_c1(pool, google_count)
    c1_ms  = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c2_scored = _bm25_score(pool, query, google_count)
    c2_ms     = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c3_scored = _ce_top_scored(query, texts_v, pool_v, google_count)
    c3_ms     = round((time.perf_counter() - t0) * 1000)

    t0        = time.perf_counter()
    c4_scored = _embed_top_scored(query, texts_v, pool_v, google_count)
    c4_ms     = round((time.perf_counter() - t0) * 1000)
    return c1_top, c2_scored, c3_scored, c4_scored, c1_ms, c2_ms, c3_ms, c4_ms


# Filter raw_results to position <= google_count; dedup via _build_pool
def _build_capped_pool(raw_results: list, google_count: int) -> list[dict]:
    return _build_pool([r for r in raw_results if r.position <= google_count])


# Build url → {engine: position} lookup for Section 2 engine-position annotations
def _build_url_engine_pos(raw_results: list, google_count: int) -> dict[str, dict[str, int]]:
    lookup: dict[str, dict[str, int]] = {}
    for r in raw_results:
        if r.position <= google_count:
            if r.url not in lookup:
                lookup[r.url] = {}
            lookup[r.url][r.engine] = r.position
    return lookup


# C1: sort pool by (-n_engines, min_position); return top_n
def _rank_c1(pool: list[dict], top_n: int) -> list[dict]:
    return sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))[:top_n]


# C3 cross-encoder rerank; returns [(doc, score), ...], one retry on API error
def _ce_top_scored(
    query: str, texts_v: list[str], pool_v: list[dict], top_n: int
) -> list[tuple[dict, float]]:
    if not texts_v:
        return []
    for attempt in range(2):
        try:
            pairs = cross_encoder_rerank(query, texts_v)
            return [(pool_v[idx], score) for idx, score in sorted(pairs, key=lambda x: -x[1])[:top_n]]
        except Exception as exc:
            print(f"  C3 API error attempt {attempt + 1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return []


# C4 embedding-cosine rerank; returns [(doc, score), ...], one retry on API error
def _embed_top_scored(
    query: str, texts_v: list[str], pool_v: list[dict], top_n: int
) -> list[tuple[dict, float]]:
    if not texts_v:
        return []
    for attempt in range(2):
        try:
            embs       = embed_batch([query] + texts_v)
            cos_scores = [cosine_sim(embs[0], e) for e in embs[1:]]
            ranked     = sorted(range(len(pool_v)), key=lambda i: -cos_scores[i])[:top_n]
            return [(pool_v[i], cos_scores[i]) for i in ranked]
        except Exception as exc:
            print(f"  C4 API error attempt {attempt + 1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Single-query pool dump — capped pool vs 4 config Top-N side-by-side"
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Query string to run (default: Q14)")
    parser.add_argument("--output", default=None, help="Custom report output path")
    args   = parser.parse_args()
    output = Path(args.output) if args.output else None
    asyncio.run(run_probe(args.query, output))
