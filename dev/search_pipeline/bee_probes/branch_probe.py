#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from _branch_probe_instrument import _acq_events, _pre_snapshots

_browser_mod = importlib.import_module("src.search.browser")
_search_mod = importlib.import_module("src.search.search_web")
close_browser = _browser_mod.close_browser
search_web_workflow = _search_mod.search_web_workflow

from _branch_probe_canary import _start_probe_clock, _start_canary_monitor, _stop_canary_monitor
from _branch_probe_analysis import (
    _load_queries, _snapshot_limiters, _build_engine_detail, _query_discriminator, _dump_smoke,
)
from _branch_probe_report import _write_report
from _branch_probe_findings import _write_findings

SCRIPT_DIR = Path(__file__).parent.parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR = SCRIPT_DIR / "md"
FINDINGS_DIR = SCRIPT_DIR / "md"

BACKOFF_IMMUNE = frozenset({"crossref", "openalex", "stack_exchange", "open_library"})


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sleep-branch discriminator probe — Phase 3 (backoff vs tokencap)."
    )
    parser.add_argument("--max-queries", dest="max_queries", type=int, default=None,
                        help="Limit to first N queries (default: all from queries.txt)")
    parser.add_argument("--smoke", action="store_true",
                        help="4-query dry-run: verify instrumentation, no report written")
    args = parser.parse_args()
    if args.smoke and args.max_queries is None:
        args.max_queries = 4
    asyncio.run(run_branch_probe(args.max_queries, args.smoke))


# FUNCTIONS

async def run_branch_probe(max_queries: int | None, smoke: bool) -> None:
    _start_probe_clock()
    queries = _load_queries(QUERIES_FILE, max_queries)
    query_records = await _execute_queries(queries, smoke)
    zero_n, min_expected, cascade_ok = _cascade_result(query_records, smoke)
    if smoke:
        _report_smoke_ok()
        return
    if not cascade_ok:
        _write_stop_note(query_records, zero_n, min_expected)
        return
    _write_outputs(query_records, cascade_ok, zero_n)


async def _execute_queries(queries: list[str], smoke: bool) -> list[dict]:
    print(f"branch probe | queries={len(queries)} smoke={smoke}", file=sys.stderr)
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


def _cascade_result(query_records: list[dict], smoke: bool) -> tuple[int, int, bool]:
    zero_n = sum(1 for r in query_records if r["category"] == "zero_cascade")
    min_expected = max(3, len(query_records) // 4) if not smoke else 0
    cascade_ok = zero_n >= min_expected
    print(
        f"\nzero_cascade={zero_n}/{len(query_records)}  cascade_reproduced={cascade_ok}",
        file=sys.stderr,
    )
    return zero_n, min_expected, cascade_ok


def _report_smoke_ok() -> None:
    print("Smoke OK — re-run without --smoke for full 20-query run.", file=sys.stderr)


def _write_stop_note(query_records: list[dict], zero_n: int, min_expected: int) -> None:
    print(
        "\n🛑 STOP: cascade did not reproduce "
        f"({zero_n}/{len(query_records)} zero_cascade < min {min_expected}). "
        "Instrumentation may be interfering. Data INVALID — do not proceed.",
        file=sys.stderr,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    stop_path = REPORT_DIR / f"branch_probe_{ts_str}_STOP.md"
    stop_path.write_text(
        f"# Branch Probe STOP — {ts_str}\n\n"
        f"Cascade did not reproduce: {zero_n}/{len(query_records)} zero_cascade "
        f"(min expected {min_expected}). Instrumentation interference suspected.\n",
        encoding="utf-8",
    )
    print(f"STOP note: {stop_path}", file=sys.stderr)


def _write_outputs(query_records: list[dict], cascade_ok: bool, zero_n: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    rp = _write_report(query_records, cascade_ok, zero_n, REPORT_DIR, BACKOFF_IMMUNE)
    fp = _write_findings(query_records, rp, cascade_ok, zero_n, FINDINGS_DIR, BACKOFF_IMMUNE)
    print(f"\nReport:   {rp}", file=sys.stderr)
    print(f"Findings: {fp}", file=sys.stderr)


async def _run_single_query(qi: int, query: str, total: int, smoke: bool) -> dict:
    n_before = len(_acq_events)
    snap = _snapshot_limiters(qi)
    _pre_snapshots.append(snap)

    t_start = time.monotonic()
    _, timings = await search_web_workflow(query, "en", None, None, _with_timings=True)
    t_end = time.monotonic()

    det = timings.get("engine_details", {})
    google_status = det.get("google", {}).get("status", "—")
    all_statuses = {k: v.get("status", "—") for k, v in det.items()}
    all_rate_skip = bool(all_statuses) and all(s == "RATE_SKIP" for s in all_statuses.values())
    category = (
        "empty" if google_status == "EMPTY"
        else "zero_cascade" if all_rate_skip
        else "normal"
    )

    new_events = _acq_events[n_before:]
    eng_detail = _build_engine_detail(new_events, all_statuses, snap)
    disc = _query_discriminator(eng_detail)

    record = {
        "qi": qi, "query": query, "t_start": t_start, "t_end": t_end,
        "duration_s": t_end - t_start, "google_status": google_status,
        "all_statuses": all_statuses, "category": category,
        "total_ms": timings.get("total_ms", 0),
        "eng_detail": eng_detail, "disc": disc, "snap": snap,
    }

    flag = {"empty": "⚡", "zero_cascade": "🚫", "normal": ""}[category]
    print(
        f"[{qi:2}/{total}] {query[:48]!r:50} "
        f"cat={category:<12} disc={disc:<24} ev={len(new_events)} {flag}",
        file=sys.stderr,
    )
    if smoke:
        _dump_smoke(new_events, eng_detail, snap, BACKOFF_IMMUNE)
    return record


if __name__ == "__main__":
    main()
