#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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

from _rerank_probe_smoke_config import (
    BM25_B,
    BM25_K1,
    BM25_REPR,
    BM25_SW,
    EMBEDDING_URL,
    QUERY_CATEGORIES,
    RERANKER_URL,
    RETRIEVE_N,
    TOP_N,
)
from _rerank_probe_smoke_gpu import _verify_services, cosine_sim, cross_encoder_rerank, embed_batch
from _rerank_probe_smoke_rank import (
    _bm25_score,
    _filter_search_pages,
    _retrieve_candidates,
    _run_bm25_only,
    _run_capped,
    _run_ce_rerank,
    _run_embed_rerank,
    is_search_results_url,
)
from _rerank_probe_smoke_report import _build_query_section, _write_report

QUERIES = [
    "bert fine-tuning natural language processing",
    "knowledge graph embedding relational learning",
    "contrastive learning self-supervised representations",
    "variational autoencoder latent space generative model",
    "graph neural network node classification",
    "best espresso machine under 500 2026",
    "mechanical keyboard switches comparison tactile linear",
    "best noise cancelling headphones 2026",
    "standing desk ergonomics home office",
    "air fryer vs convection oven cooking",
    "python asyncio event loop concurrency",
    "rust ownership borrowing lifetime explained",
    "docker compose network bridge host mode",
    "postgresql index types btree gin gist performance",
    "react useEffect cleanup subscription pattern",
    "transformer attention mechanism",
    "neural network activation functions comparison",
    "gradient descent optimization methods stochastic",
    "protein structure prediction alphafold deep learning",
    "convolutional neural network image classification tutorial",
]

REPORT_DIR = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = SCRIPT_DIR / "jsonl"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ORCHESTRATOR

async def run_probe() -> None:
    _verify_services()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"rerank_probe_{ts}.md"
    probe_log_path = DATA_DIR / f"rerank_probe_{ts}.queries.jsonl"
    os.environ["SEARXNG_QUERY_LOG_PATH"] = str(probe_log_path)

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    summaries: list[dict]     = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)
            section, summary = await _run_one_query(query, selected)
            query_sections.append(section)
            summaries.append(summary)
            print(
                f"  fetch={summary['fetch_ms']}ms  hardslot={summary['hardslot_ms']}ms  "
                f"bm25={summary['bm25_ms']}ms  embed={summary['embed_ms']}ms  "
                f"rerank={summary['rerank_ms']}ms  "
                f"filtered_out={summary['removed_by_filter']}  "
                f"unique={summary['unique_after_dedup']}",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)
    _write_report(query_sections, summaries, report_path, total_ms)
    print(f"\nReport:     {report_path}", file=sys.stderr)
    print(f"Total wall: {total_ms}ms", file=sys.stderr)

# FUNCTIONS

async def _run_one_query(query: str, selected: dict) -> tuple[str, dict]:
    fs = await _fetch_and_filter(query, selected)
    cf = _run_configs(query, fs)

    section = _build_query_section(query, fs, cf)

    return section, _query_summary(query, fs, cf)


async def _fetch_and_filter(query: str, selected: dict) -> dict:
    t0 = time.perf_counter()
    raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
    fetch_ms = round((time.perf_counter() - t0) * 1000)

    raw_count = len(raw_results)

    filtered_raw, filtered_count, pattern_hist = _filter_search_pages(raw_results)
    removed_count   = raw_count - filtered_count

    pool          = _build_pool(filtered_raw)
    unique_count  = len(pool)

    return {
        "raw_results": raw_results, "engine_stats": engine_stats, "fetch_ms": fetch_ms,
        "raw_count": raw_count, "filtered_count": filtered_count, "removed_count": removed_count,
        "pattern_hist": pattern_hist, "pool": pool, "unique_count": unique_count,
    }


def _run_configs(query: str, fs: dict) -> dict:
    pool = fs["pool"]

    hs_top, slot_counts, hardslot_ms = _run_hardslot(fs["raw_results"])

    bm25_top, bm25_ms = _run_bm25_only(pool, query)

    bm25_candidates, retrieve_ms, cand_docs, cand_texts = _retrieve_candidates(pool, query)
    bm25_ms += retrieve_ms

    embed_top, embed_ms = _run_embed_rerank(query, cand_docs, cand_texts)

    ce_top, rerank_ms = _run_ce_rerank(query, cand_docs, cand_texts)

    K, capped_pool, capped_top, capped_ms = _run_capped(fs["raw_results"], fs["engine_stats"], query)

    return {
        "hs_top": hs_top, "slot_counts": slot_counts, "hardslot_ms": hardslot_ms,
        "bm25_top": bm25_top, "bm25_ms": bm25_ms, "bm25_candidates": bm25_candidates,
        "embed_top": embed_top, "embed_ms": embed_ms, "ce_top": ce_top, "rerank_ms": rerank_ms,
        "K": K, "capped_pool": capped_pool, "capped_top": capped_top, "capped_ms": capped_ms,
    }


def _run_hardslot(raw_results: list) -> tuple[list[dict], dict, int]:
    t0 = time.perf_counter()
    hs_ranked, slot_counts = _merge_and_rank(raw_results)
    hs_top = [{"url": r.url, "engines": r.engines or [r.engine], "score": None} for r in hs_ranked[:TOP_N]]
    hardslot_ms = round((time.perf_counter() - t0) * 1000)
    return hs_top, slot_counts, hardslot_ms


def _query_summary(query: str, fs: dict, cf: dict) -> dict:
    return {
        "query":            query,
        "fetch_ms":         fs["fetch_ms"],
        "hardslot_ms":      cf["hardslot_ms"],
        "bm25_ms":          cf["bm25_ms"],
        "embed_ms":         cf["embed_ms"],
        "rerank_ms":        cf["rerank_ms"],
        "capped_ms":        cf["capped_ms"],
        "removed_by_filter": fs["removed_count"],
        "unique_after_dedup": fs["unique_count"],
    }


if __name__ == "__main__":
    asyncio.run(run_probe())
