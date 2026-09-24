#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RAG_SRC      = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/src")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAG_SRC))

from bm25_sweep_smoke import _tokenize, BM25Uniform, VANILLA_K1

from clean_pool import filter_pool

from rag.server_manager import ensure_ready, find_server_url

from _stage3_method_run_v3_cheap import _apply_m1, _apply_m2, _apply_m3, _apply_m4, _apply_m5
from _stage3_method_run_v3_gpu import (
    _apply_m6, _apply_m7, _apply_m8, _apply_m9, _apply_m10, _apply_m11, _apply_m12,
)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

DROP_ENGINES = {"google", "semantic_scholar"}

MODES = ["general", "pdf", "books", "docs"]
QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]


# ORCHESTRATOR

def run_method_run_v3(pool_dir: Path, smoke: bool) -> None:
    reranker_url, splade_url, generator_url = _init_services()

    pool_files = sorted(pool_dir.glob("*_pool.json"))
    if smoke:
        pool_files = [f for f in pool_files if f.name.startswith("general_")][:1]

    n = len(pool_files)
    print(f"Pools: {n} | pool_dir: {pool_dir}", file=sys.stderr)
    print(file=sys.stderr)

    for i, pool_file in enumerate(pool_files, 1):
        stem      = pool_file.stem
        name      = stem[:-5]
        mode, slug = name.split("_", 1)
        data      = json.loads(pool_file.read_text())
        query     = data["query"]
        print(f"[{i}/{n}] mode={mode} | {query}", file=sys.stderr)
        meta = _run_one_pair(pool_dir, mode, slug, query, data, reranker_url, splade_url, generator_url)
        print(
            f"  M1={meta['m1_ms']}ms M2={meta['m2_ms']}ms M3={meta['m3_ms']}ms"
            f"  M4={meta['m4_ms']}ms M5={meta['m5_ms']}ms M6={meta['m6_ms']}ms"
            f"  M7={meta['m7_ms']}ms M8={meta['m8_ms']}ms M9={meta['m9_ms']}ms"
            f"  M10={meta['m10_ms']}ms M11={meta['m11_ms']}ms M12={meta['m12_ms']}ms",
            file=sys.stderr,
        )

    print(f"\nDone — methods_v3.json written to {pool_dir}", file=sys.stderr)


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _init_services() -> tuple[str, str, str]:
    print("Initialising GPU services …", file=sys.stderr)

    print("  reranker …", file=sys.stderr)
    ensure_ready("reranker")
    reranker_base = find_server_url("reranker")
    if not reranker_base:
        sys.exit("ERROR: reranker not reachable. Run: rag-cli server start reranker-0.6b")
    reranker_url = f"{reranker_base}/v1/rerank"
    print(f"  reranker OK: {reranker_url}", file=sys.stderr)

    print("  splade …", file=sys.stderr)
    ensure_ready("splade")
    splade_base = find_server_url("splade")
    if not splade_base:
        sys.exit("ERROR: splade not reachable. Run: rag-cli server start splade")
    splade_url = f"{splade_base}/v1/sparse-embeddings"
    print(f"  splade OK: {splade_url}", file=sys.stderr)

    print("  generator-4b …", file=sys.stderr)
    ensure_ready("generator-4b")
    gen_base = find_server_url("generator-4b")
    if not gen_base:
        sys.exit("ERROR: generator-4b not reachable. Run: rag-cli server start generator-4b")
    generator_url = f"{gen_base}/v1/chat/completions"
    print(f"  generator OK: {generator_url}", file=sys.stderr)

    print(file=sys.stderr)
    return reranker_url, splade_url, generator_url


def _run_one_pair(
    pool_dir: Path, mode: str, slug: str, query: str, pool_data: dict,
    reranker_url: str, splade_url: str, generator_url: str,
) -> dict:
    raw_pool      = pool_data["pool"]
    raw_pool_full = pool_data.get("pool_full", raw_pool)

    pool      = filter_pool(raw_pool,      DROP_ENGINES)
    pool_full = filter_pool(raw_pool_full, DROP_ENGINES)

    data = {
        "mode":  mode,
        "query": query,
        "pool_size_before_filter": len(raw_pool),
        "pool_size_after_filter":  len(pool),
        **_run_methods(pool, pool_full, query, reranker_url, splade_url, generator_url),
    }
    (pool_dir / f"{mode}_{slug}_methods_v3.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {f"m{i}_ms": data[f"m{i}_ms"] for i in range(1, 13)}


def _run_methods(
    pool: list[dict], pool_full: list[dict], query: str,
    reranker_url: str, splade_url: str, generator_url: str,
) -> dict:
    cheap, rrf_scores = _run_cheap_methods(pool, pool_full, query)
    return {**cheap, **_run_gpu_methods(pool, query, rrf_scores, reranker_url, splade_url, generator_url)}


def _run_cheap_methods(pool: list[dict], pool_full: list[dict], query: str) -> tuple[dict, dict]:
    m1_urls, m1_ms = _apply_m1(pool)
    m2_urls, m2_ms, rrf_scores = _apply_m2(pool)
    m3_urls, m3_ms = _apply_m3(pool)
    m4_urls, m4_ms = _apply_m4(pool_full, query)
    m5_urls, m5_ms = _apply_m5(pool, query)

    return {
        "m1": m1_urls, "m1_ms": m1_ms,
        "m2": m2_urls, "m2_ms": m2_ms,
        "m3": m3_urls, "m3_ms": m3_ms,
        "m4": m4_urls, "m4_ms": m4_ms,
        "m5": m5_urls, "m5_ms": m5_ms,
    }, rrf_scores


def _run_gpu_methods(
    pool: list[dict], query: str, rrf_scores: dict,
    reranker_url: str, splade_url: str, generator_url: str,
) -> dict:
    m6_urls, m6_ms, c3_scores      = _apply_m6(pool, query, reranker_url)
    m7_urls, m7_ms, c3_instr_scores = _apply_m7(pool, query, reranker_url)
    m8_urls, m8_ms                 = _apply_m8(pool, c3_scores, rrf_scores)

    m9_urls, m9_ms, splade_scores = _apply_m9(pool, query, splade_url)
    m10_urls, m10_ms              = _apply_m10(pool, c3_scores, splade_scores)

    m11_urls, m11_ms, m11_tokens = _apply_m11(pool, query, c3_scores, generator_url)
    m12_urls, m12_ms, m12_tokens = _apply_m12(pool, query, generator_url)

    return {
        "m6": m6_urls, "m6_ms": m6_ms,
        "m7": m7_urls, "m7_ms": m7_ms,
        "m8": m8_urls, "m8_ms": m8_ms,
        "m9": m9_urls, "m9_ms": m9_ms,
        "m10": m10_urls, "m10_ms": m10_ms,
        "m11": m11_urls, "m11_ms": m11_ms,
        "m11_tokens_in": m11_tokens[0], "m11_tokens_out": m11_tokens[1],
        "m12": m12_urls, "m12_ms": m12_ms,
        "m12_tokens_in": m12_tokens[0], "m12_tokens_out": m12_tokens[1],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 3 v3 — 12-Method Run (Phase 13)")
    parser.add_argument("--pool-dir", required=True, help="Directory with *_pool.json from Stage 1 v3")
    parser.add_argument("--smoke",    action="store_true", help="Process first general pool only")
    args     = parser.parse_args()
    pool_dir = Path(args.pool_dir)
    if not pool_dir.exists():
        sys.exit(f"ERROR: pool_dir does not exist: {pool_dir}")
    run_method_run_v3(pool_dir=pool_dir, smoke=args.smoke)
