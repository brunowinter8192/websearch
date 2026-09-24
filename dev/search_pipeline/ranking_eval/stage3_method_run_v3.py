#!/usr/bin/env python3
"""
Stage 3 v3 — 12-Method Run (Phase 13 eval).

Reads *_pool.json (v3 schema, with positions field) from pool_dir, applies
filter_pool(drop_engines={'google','semantic_scholar'}), then runs 12 methods
per pair. Writes per-pair {mode}_{slug}_methods_v3.json to pool_dir.

Methods:
  M1  C1 Overlap-Count (no GPU)
  M2  RRF post-bucket using positions field (no GPU)
  M3  Structural URL Features — penalty scoring (no GPU)
  M4  C2 BM25 vanilla on pool_full (no GPU)
  M5  C2' BM25-Capped on pool (no GPU)
  M6  C3 Cross-Encoder vanilla — also saves c3_scores for M8/M10
  M7  C3 + Instruction-Prefix (same reranker model, new query prefix)
  M8  RRF + C3 Hybrid — 0.5*norm(c3_scores) + 0.5*norm(rrf_scores), NO new GPU call
  M9  SPLADE standalone — dot product on sparse vectors
  M10 SPLADE + C3 Hybrid — 0.5*norm(c3_scores) + 0.5*norm(splade_scores), NO new GPU call
  M11 Two-Stage C3 + LLM-Filter — C3 top-20 → generator-4b filter → top-10
  M12 LLM-as-Selector direct — full filtered pool → generator-4b → top-10

Execution order: M1-M5 (cheap), M6-M8 (reranker warm), M9-M10 (SPLADE warm), M11-M12 (generator).
Per-GPU model group: pre-flight warmup on first query only; cold_ms tracked separately.

Requires:
  - reranker-0.6b running (M6, M7, M8, M10, M11): rag-cli server start reranker-0.6b
  - splade running (M9, M10):                      rag-cli server start splade
  - generator-4b running (M11, M12):               rag-cli server start generator-4b

Usage:
  ./venv/bin/python dev/search_pipeline/stage3_method_run_v3.py \\
      --pool-dir dev/search_pipeline/runs/value_eval_v3_<ts> \\
      [--smoke]
"""

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

# From clean_pool.py: engine filter
from clean_pool import filter_pool

# RAG server manager — dynamic service URLs
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
    # Resolve service URLs (fail fast if missing)
    reranker_url, splade_url, generator_url = _init_services()

    pool_files = sorted(pool_dir.glob("*_pool.json"))
    if smoke:
        pool_files = [f for f in pool_files if f.name.startswith("general_")][:1]

    n = len(pool_files)
    print(f"Pools: {n} | pool_dir: {pool_dir}", file=sys.stderr)
    print(file=sys.stderr)

    for i, pool_file in enumerate(pool_files, 1):
        stem      = pool_file.stem           # e.g. "general_transformer_attention_mechan_pool"
        name      = stem[:-5]                # strip "_pool"
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


# Resolve and verify GPU service endpoints; return (reranker_url, splade_url, generator_url)
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


# Run all 12 methods on one pair; save methods_v3.json; return timing metadata dict
def _run_one_pair(
    pool_dir: Path, mode: str, slug: str, query: str, pool_data: dict,
    reranker_url: str, splade_url: str, generator_url: str,
) -> dict:
    raw_pool      = pool_data["pool"]
    raw_pool_full = pool_data.get("pool_full", raw_pool)

    # Apply engine filter at method input
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
    # --- Cheap methods (no GPU) ---
    m1_urls, m1_ms = _apply_m1(pool)
    m2_urls, m2_ms, rrf_scores = _apply_m2(pool)
    m3_urls, m3_ms = _apply_m3(pool)
    m4_urls, m4_ms = _apply_m4(pool_full, query)
    m5_urls, m5_ms = _apply_m5(pool, query)

    return {
        # M1
        "m1": m1_urls, "m1_ms": m1_ms,
        # M2
        "m2": m2_urls, "m2_ms": m2_ms,
        # M3
        "m3": m3_urls, "m3_ms": m3_ms,
        # M4
        "m4": m4_urls, "m4_ms": m4_ms,
        # M5
        "m5": m5_urls, "m5_ms": m5_ms,
    }, rrf_scores


def _run_gpu_methods(
    pool: list[dict], query: str, rrf_scores: dict,
    reranker_url: str, splade_url: str, generator_url: str,
) -> dict:
    # --- Reranker methods (M6 saves c3_scores; M7 saves c3_instr_scores; M8 reuses M6) ---
    m6_urls, m6_ms, c3_scores      = _apply_m6(pool, query, reranker_url)
    m7_urls, m7_ms, c3_instr_scores = _apply_m7(pool, query, reranker_url)
    m8_urls, m8_ms                 = _apply_m8(pool, c3_scores, rrf_scores)

    # --- SPLADE methods (M9 saves splade_scores; M10 reuses M6 + M9) ---
    m9_urls, m9_ms, splade_scores = _apply_m9(pool, query, splade_url)
    m10_urls, m10_ms              = _apply_m10(pool, c3_scores, splade_scores)

    # --- LLM methods (M11 reuses c3_scores for top-20 pre-filter) ---
    m11_urls, m11_ms, m11_tokens = _apply_m11(pool, query, c3_scores, generator_url)
    m12_urls, m12_ms, m12_tokens = _apply_m12(pool, query, generator_url)

    return {
        # M6
        "m6": m6_urls, "m6_ms": m6_ms,
        # M7
        "m7": m7_urls, "m7_ms": m7_ms,
        # M8
        "m8": m8_urls, "m8_ms": m8_ms,
        # M9
        "m9": m9_urls, "m9_ms": m9_ms,
        # M10
        "m10": m10_urls, "m10_ms": m10_ms,
        # M11
        "m11": m11_urls, "m11_ms": m11_ms,
        "m11_tokens_in": m11_tokens[0], "m11_tokens_out": m11_tokens[1],
        # M12
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
