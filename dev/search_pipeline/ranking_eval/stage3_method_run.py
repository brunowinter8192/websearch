#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RAG_SRC      = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/src")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAG_SRC))

from bm25_sweep_smoke import _doc_repr, _tokenize, BM25Uniform, VANILLA_K1

from rerank_probe_smoke import _bm25_score

from rag.server_manager import ensure_ready, find_server_url

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

TOP_N     = 10
BM25_REPR = "title+snippet"

RERANKER_URL: str = ""

MODES = ["general", "pdf", "books", "docs"]

QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]


# ORCHESTRATOR

def run_method_run(ts_dir: Path, smoke: bool) -> None:
    global RERANKER_URL
    print("Initialising reranker …", file=sys.stderr)
    ensure_ready("reranker")
    base_url = find_server_url("reranker")
    if base_url is None:
        sys.exit(
            "ERROR: Reranker not reachable after ensure_ready.\n"
            "Start manually: rag-cli server start reranker-0.6b"
        )
    RERANKER_URL = f"{base_url}/v1/rerank"
    print(f"  Reranker OK: {RERANKER_URL}", file=sys.stderr)
    print(file=sys.stderr)

    pool_files = sorted(ts_dir.glob("*_pool.json"))
    if smoke:
        pool_files = [f for f in pool_files if f.name.startswith("general_")][:1]

    n = len(pool_files)
    print(f"Pools: {n} | ts_dir: {ts_dir}", file=sys.stderr)
    print(file=sys.stderr)

    for i, pool_file in enumerate(pool_files, 1):
        stem      = pool_file.stem
        name      = stem[:-5]
        mode, slug = name.split("_", 1)
        data      = json.loads(pool_file.read_text())
        query     = data["query"]
        print(f"[{i}/{n}] mode={mode} | {query}", file=sys.stderr)
        meta = _run_one_pair(ts_dir, mode, slug, query, data)
        print(
            f"  c1={meta['c1_ms']}ms  c2={meta['c2_ms']}ms"
            f"  c2p={meta['c2p_ms']}ms  c3={meta['c3_ms']}ms",
            file=sys.stderr,
        )

    print(f"\nDone — methods.json written to {ts_dir}", file=sys.stderr)


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _apply_c1(pool: list[dict], top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    ranked = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:top_n]], ms


def _apply_c2(pool_full: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(pool_full, query, top_n)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms


def _apply_c2p(pool: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(pool, query, top_n)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms


def _cross_encoder_rerank(query: str, documents: list[str]) -> list[tuple[int, float]]:
    r = httpx.post(RERANKER_URL, json={"query": query, "documents": documents}, timeout=60.0)
    r.raise_for_status()
    return [(item["index"], item["relevance_score"]) for item in r.json().get("results", [])]


def _apply_c3(pool: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    if not pool:
        return [], 0
    valid = [(m, _doc_repr(m, BM25_REPR)) for m in pool if _doc_repr(m, BM25_REPR).strip()]
    if not valid:
        return [], 0
    docs_v  = [m for m, _ in valid]
    texts_v = [t for _, t in valid]
    t0 = time.perf_counter()
    try:
        pairs  = _cross_encoder_rerank(query, texts_v)
        ranked = sorted(pairs, key=lambda x: -x[1])[:top_n]
        ms     = round((time.perf_counter() - t0) * 1000)
        return [docs_v[idx]["url"] for idx, _ in ranked], ms
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000)
        print(f"  C3 error: {exc}", file=sys.stderr)
        return [], ms


def _run_one_pair(ts_dir: Path, mode: str, slug: str, query: str, pool_data: dict) -> dict:
    pool      = pool_data["pool"]
    pool_full = pool_data.get("pool_full", pool)

    c1_urls,  c1_ms  = _apply_c1(pool,      TOP_N)
    c2_urls,  c2_ms  = _apply_c2(pool_full, query, TOP_N)
    c2p_urls, c2p_ms = _apply_c2p(pool,     query, TOP_N)
    c3_urls,  c3_ms  = _apply_c3(pool,      query, TOP_N)

    ps = pool_data.get("pool_sizes", {})
    data = {
        "mode":                      mode,
        "query":                     query,
        "google_count":              pool_data.get("google_count", 0),
        "pool_size":                 ps.get("raw", 0),
        "capped_pool_size":          ps.get("capped", 0),
        "filtered_pool_size":        ps.get("filtered", len(pool_full)),
        "filtered_capped_pool_size": ps.get("filtered_capped", len(pool)),
        "oracle_pool_size":          len(pool),
        "c1":    c1_urls,   "c1_ms":  c1_ms,
        "c2":    c2_urls,   "c2_ms":  c2_ms,
        "c2p":   c2p_urls,  "c2p_ms": c2p_ms,
        "c3":    c3_urls,   "c3_ms":  c3_ms,
        "method_pool_sizes": {
            "c1": len(pool), "c2": len(pool_full), "c2p": len(pool), "c3": len(pool),
        },
    }
    (ts_dir / f"{mode}_{slug}_methods.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"c1_ms": c1_ms, "c2_ms": c2_ms, "c2p_ms": c2p_ms, "c3_ms": c3_ms}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 3 — Method Run (value_eval_v2)")
    parser.add_argument("--ts-dir", required=True, help="Directory with *_pool.json from Stage 1")
    parser.add_argument("--smoke",  action="store_true", help="Process first general pool only")
    args   = parser.parse_args()
    ts_dir = Path(args.ts_dir)
    if not ts_dir.exists():
        sys.exit(f"ERROR: ts_dir does not exist: {ts_dir}")
    run_method_run(ts_dir=ts_dir, smoke=args.smoke)
