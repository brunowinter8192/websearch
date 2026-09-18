#!/usr/bin/env python3
"""RateLimiter.acquire() instrumentation probe — Phase 2 bee investigation.

Discriminates three hypotheses for zero_cascade queries (all 9+ engines RATE_SKIP):
  B:       enter=N                  — Task never scheduled by asyncio
  A-lock:  enter=Y, lg=N, ~5000ms  — entered acquire() but blocked waiting for the lock
  A-sleep: enter=Y, lg=Y, ~5000ms  — got lock, blocked on asyncio.sleep(backoff_s)
  C:       enter=Y, exit_ok        — acquire() innocent, bug elsewhere

Phase 1 REFUTED CDP starvation (event loop p99=1.4ms, 0 CDP events during cascade).
New hypothesis: Python 3.14 asyncio.Lock non-release under CancelledError causes
stale lock that blocks subsequent queries on same engine.

Usage:
    ./venv/bin/python3 dev/search_pipeline/acquire_probe.py [--max-queries N] [--smoke]

    --smoke: 4-query dry-run, prints per-engine event detail to stderr, no report written.
             Run first to verify instrumentation is live before full 20-query run.

Output (full run only):
    dev/search_pipeline/md/acquire_probe_<ts>.md
"""

# INFRASTRUCTURE
import argparse
import asyncio
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from _acquire_probe_instrument import _acq_events

_browser_mod = importlib.import_module("src.search.browser")
_search_mod = importlib.import_module("src.search.search_web")
close_browser = _browser_mod.close_browser
search_web_workflow = _search_mod.search_web_workflow

from _acquire_probe_canary import _start_probe_clock, _start_canary_monitor, _stop_canary_monitor
from _acquire_probe_analysis import _load_queries, _build_engine_summary, _discriminator, _dump_smoke
from _acquire_probe_report import _write_report
from _acquire_probe_findings import _write_findings

SCRIPT_DIR = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR = SCRIPT_DIR / "md"
FINDINGS_DIR = SCRIPT_DIR / "md"


# ORCHESTRATOR

async def run_acquire_probe(max_queries: int | None, smoke: bool) -> None:
    _start_probe_clock()
    queries = _load_queries(QUERIES_FILE, max_queries)
    query_records = await _execute_queries(queries, smoke)
    zero_n, cascade_ok = _cascade_result(query_records, smoke)
    if smoke:
        _report_smoke_ok()
        return
    if not cascade_ok:
        _report_cascade_warning()
    _write_outputs(query_records, cascade_ok, zero_n)


# FUNCTIONS

async def _execute_queries(queries: list[str], smoke: bool) -> list[dict]:
    print(f"acquire probe | queries={len(queries)} smoke={smoke}", file=sys.stderr)
    stop_canary, canary_task = await _start_canary_monitor()
    query_records: list[dict] = []
    try:
        for qi, query in enumerate(queries, 1):
            record = await _run_single_query(qi, query, len(queries), smoke)
            query_records.append(record)
    finally:
        await _stop_canary_monitor(stop_canary, canary_task)
        await close_browser()
    return query_records


async def _run_single_query(qi: int, query: str, total: int, smoke: bool) -> dict:
    n_before = len(_acq_events)
    t_start = time.monotonic()
    _, timings = await search_web_workflow(query, "en", None, None, _with_timings=True)
    t_end = time.monotonic()

    det = timings.get("engine_details", {})
    google_status = det.get("google", {}).get("status", "—")
    all_statuses = {k: v.get("status", "—") for k, v in det.items()}
    all_rate_skip = bool(all_statuses) and all(s == "RATE_SKIP" for s in all_statuses.values())
    # "captcha" (keyed on the removed EMPTY_BLOCK verdict) renamed to "empty" — the
    # guessed-verdict-removal milestone collapsed EMPTY_BLOCK into bare "EMPTY", and
    # engine_details (status+ms only) carries no diagnosis to reconstruct which kind of
    # empty this was; an honest narrower label beats a familiar wrong one.
    category = (
        "empty" if google_status == "EMPTY"
        else "zero_cascade" if all_rate_skip
        else "normal"
    )

    new_events = _acq_events[n_before:]
    eng_summary = _build_engine_summary(new_events, all_statuses)
    disc = _discriminator(eng_summary)

    record = {
        "qi": qi, "query": query, "t_start": t_start, "t_end": t_end,
        "duration_s": t_end - t_start, "google_status": google_status,
        "all_statuses": all_statuses, "category": category,
        "total_ms": timings.get("total_ms", 0),
        "eng_summary": eng_summary, "disc": disc,
    }

    flag = {"empty": "⚡", "zero_cascade": "🚫", "normal": ""}[category]
    print(
        f"[{qi:2}/{total}] {query[:48]!r:50} "
        f"cat={category:<12} disc={disc:<8} ev={len(new_events)} {flag}",
        file=sys.stderr,
    )
    if smoke:
        _dump_smoke(new_events, eng_summary)
    return record


def _cascade_result(query_records: list[dict], smoke: bool) -> tuple[int, bool]:
    zero_n = sum(1 for r in query_records if r["category"] == "zero_cascade")
    # Cascade expected: ≥5/20 based on Phase 1 baseline; for shorter smoke: 0 OK
    min_expected = max(3, len(query_records) // 4) if not smoke else 0
    cascade_ok = zero_n >= min_expected
    print(
        f"\nzero_cascade={zero_n}/{len(query_records)}  cascade_reproduced={cascade_ok}",
        file=sys.stderr,
    )
    return zero_n, cascade_ok


def _report_smoke_ok() -> None:
    print("Smoke OK — re-run without --smoke for full 20-query run.", file=sys.stderr)


def _report_cascade_warning() -> None:
    print(
        "WARNING: cascade did not reproduce — instrumentation may be interfering. "
        "Data may be invalid.",
        file=sys.stderr,
    )


def _write_outputs(query_records: list[dict], cascade_ok: bool, zero_n: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    rp = _write_report(query_records, cascade_ok, zero_n, REPORT_DIR)
    fp = _write_findings(query_records, rp, cascade_ok, zero_n, FINDINGS_DIR)
    print(f"\nReport:   {rp}", file=sys.stderr)
    print(f"Findings: {fp}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RateLimiter.acquire() instrumentation probe — Phase 2 bee."
    )
    parser.add_argument("--max-queries", dest="max_queries", type=int, default=None,
                        help="Limit to first N queries (default: all from queries.txt)")
    parser.add_argument("--smoke", action="store_true",
                        help="4-query dry-run: verify instrumentation live, no report written")
    args = parser.parse_args()
    if args.smoke and args.max_queries is None:
        args.max_queries = 4
    asyncio.run(run_acquire_probe(args.max_queries, args.smoke))
