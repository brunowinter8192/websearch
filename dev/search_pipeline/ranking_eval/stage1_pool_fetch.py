#!/usr/bin/env python3

# INFRASTRUCTURE
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from rerank_probe_smoke import close_browser, _query_engines_concurrent, _select_engines

from bm25_sweep_smoke import _build_pool

from _stage1_pool_fetch_report import _save_engine_report, _save_engine_summary
from _stage1_pool_fetch_config import MODES

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "runs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]

SMOKE_MODE  = "general"
SMOKE_QUERY = "transformer attention mechanism"

_MODE_ENGINES = frozenset({"google", "duckduckgo"})


# ORCHESTRATOR

async def run_pool_fetch(smoke: bool, ts_dir_arg: Path | None) -> Path:
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = ts_dir_arg or (REPORT_DIR / f"value_eval_v3_{ts}")
    ts_dir.mkdir(parents=True, exist_ok=True)

    pairs   = [(SMOKE_MODE, SMOKE_QUERY)] if smoke else [(m, q) for m in MODES for q in QUERIES]
    n_pairs = len(pairs)

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Pairs: {n_pairs} | Output: {ts_dir}", file=sys.stderr)
    print(file=sys.stderr)

    summary_rows: list[dict] = []
    try:
        for i, (mode, query) in enumerate(pairs, 1):
            print(f"[{i}/{n_pairs}] mode={mode} | {query}", file=sys.stderr)
            meta = await _run_one_pair(ts_dir, mode, query, selected)
            print(
                f"  raw={meta['raw_count']}  capped={meta['capped_count']}"
                f"  oracle={meta['oracle_count']}"
                f"  fetch={meta['fetch_ms']}ms",
                file=sys.stderr,
            )
            summary_rows.append(meta)
    finally:
        await close_browser()

    _save_engine_summary(ts_dir, summary_rows, ts)
    print(f"\nOutput dir: {ts_dir}", file=sys.stderr)
    return ts_dir


# FUNCTIONS

def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _modifier_map(mode: str) -> dict | None:
    if mode == "books": return {e: (lambda q: f"{q} book")          for e in _MODE_ENGINES}
    if mode == "pdf":   return {e: (lambda q: f"{q} pdf")           for e in _MODE_ENGINES}
    if mode == "docs":  return {e: (lambda q: f"{q} documentation") for e in _MODE_ENGINES}
    return None


def _build_capped_pool(raw_results: list, K: int) -> list[dict]:
    return _build_pool([r for r in raw_results if r.position <= K])


def _attach_positions(raw_results: list, pool: list[dict]) -> None:
    pos_map: dict[str, dict[str, int]] = {}
    for r in raw_results:
        if r.url not in pos_map:
            pos_map[r.url] = {}
        eng = pos_map[r.url]
        eng[r.engine] = min(eng.get(r.engine, 999), r.position)
    for m in pool:
        m["positions"] = pos_map.get(m["url"], {})


async def _run_one_pair(ts_dir: Path, mode: str, query: str, selected: dict) -> dict:
    qmm = _modifier_map(mode)

    t0 = time.perf_counter()
    raw_results, engine_stats = await _query_engines_concurrent(
        query, "en", 10, selected, query_modifier_map=qmm
    )
    fetch_ms   = round((time.perf_counter() - t0) * 1000)
    fetched_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    google_count = engine_stats.get("google", {}).get("result_count", 0)
    K            = google_count if google_count > 0 else 10

    full_pool   = _build_pool(raw_results)
    capped_raw  = [r for r in raw_results if r.position <= K]
    capped_pool = _build_pool(capped_raw)
    _attach_positions(raw_results, full_pool)
    _attach_positions(capped_raw, capped_pool)
    oracle_pool = sorted(capped_pool, key=lambda m: m["url"])

    slug = _query_slug(query)
    _save_pool_json(
        ts_dir, mode, slug, query, fetched_ts, google_count,
        oracle_pool, full_pool, len(raw_results), len(capped_pool),
    )
    _save_engine_report(
        ts_dir, mode, slug, query, fetched_ts, engine_stats, oracle_pool,
        len(raw_results), len(capped_pool),
    )

    return {
        "mode":         mode,
        "query":        query,
        "slug":         slug,
        "raw_count":    len(raw_results),
        "capped_count": len(capped_pool),
        "oracle_count": len(oracle_pool),
        "fetch_ms":     fetch_ms,
        "engine_stats": engine_stats,
    }


def _save_pool_json(
    ts_dir: Path, mode: str, slug: str, query: str, fetched_ts: str,
    google_count: int, oracle_pool: list[dict], full_pool: list[dict],
    raw_count: int, capped_count: int,
) -> None:
    def _item(m: dict) -> dict:
        return {
            "url":          m["url"],
            "title":        (m.get("title") or "").strip(),
            "snippet":      (m.get("snippet") or "").strip(),
            "engines":      m.get("engines", []),
            "min_position": m.get("min_position", 999),
            "positions":    m.get("positions", {}),
        }

    data = {
        "mode":         mode,
        "query":        query,
        "fetched_ts":   fetched_ts,
        "google_count": google_count,
        "pool_sizes": {
            "raw":             raw_count,
            "capped":          capped_count,
            "filtered_capped": len(oracle_pool),
        },
        "pool":      [_item(m) for m in oracle_pool],
        "pool_full": [_item(m) for m in sorted(full_pool, key=lambda m: m["url"])],
    }
    (ts_dir / f"{mode}_{slug}_pool.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1 — Pool Fetch (value_eval_v2)")
    parser.add_argument("--smoke",  action="store_true", help="One pair only (general × Q1)")
    parser.add_argument("--ts-dir", default=None,        help="Output directory override")
    args       = parser.parse_args()
    ts_dir_arg = Path(args.ts_dir) if args.ts_dir else None
    ts_dir     = asyncio.run(run_pool_fetch(smoke=args.smoke, ts_dir_arg=ts_dir_arg))
    print(ts_dir)
