#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from _cdp_starvation_probe_instrument import _cdp_ts, SLOW_CB_THRESHOLD_S, _install_asyncio_log_capture

_browser_mod = importlib.import_module("src.search.browser")
_search_mod = importlib.import_module("src.search.search_web")
close_browser = _browser_mod.close_browser
search_web_workflow = _search_mod.search_web_workflow

from _cdp_starvation_probe_canary import _start_probe_clock, _start_canary_monitor, _stop_canary_monitor
from _cdp_starvation_probe_report import _write_report
from _cdp_starvation_probe_findings import _write_findings

SCRIPT_DIR = Path(__file__).parent.parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR = SCRIPT_DIR / "md"
FINDINGS_DIR = SCRIPT_DIR / "md"


# ORCHESTRATOR

async def run_cdp_probe(max_queries: int | None) -> None:
    _start_probe_clock()
    _enable_pattern_a()
    queries = _load_queries(QUERIES_FILE, max_queries)
    query_records = await _execute_queries(queries)
    _write_outputs(query_records)


# FUNCTIONS

def _enable_pattern_a() -> None:
    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = SLOW_CB_THRESHOLD_S
    loop.set_debug(True)
    _install_asyncio_log_capture()


def _load_queries(path: Path, max_queries: int | None) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    qs = [ln.strip() for ln in lines if ln.strip()]
    return qs[:max_queries] if max_queries else qs


async def _execute_queries(queries: list[str]) -> list[dict]:
    print(f"CDP starvation probe | Queries: {len(queries)} | slow_cb_threshold={SLOW_CB_THRESHOLD_S*1000:.0f}ms",
          file=sys.stderr)
    stop_canary, canary_task = await _start_canary_monitor()
    query_records: list[dict] = []
    try:
        for qi, query in enumerate(queries, 1):
            record = await _run_single_query(qi, query, len(queries))
            query_records.append(record)
    finally:
        await _stop_canary_monitor(stop_canary, canary_task)
        await close_browser()
    return query_records


def _write_outputs(query_records: list[dict]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _write_report(query_records, REPORT_DIR)
    findings_path = _write_findings(query_records, report_path, FINDINGS_DIR)
    print(f"\nReport:   {report_path}", file=sys.stderr)
    print(f"Findings: {findings_path}", file=sys.stderr)


async def _run_single_query(qi: int, query: str, total: int) -> dict:
    t_start = time.monotonic()
    _, timings = await search_web_workflow(query, "en", None, None, _with_timings=True)
    t_end = time.monotonic()

    det = timings.get("engine_details", {})
    google_status = det.get("google", {}).get("status", "—")

    all_statuses = {k: v.get("status", "—") for k, v in det.items()}
    all_rate_skip = bool(all_statuses) and all(s == "RATE_SKIP" for s in all_statuses.values())

    cdp_in_query = sum(1 for ts in _cdp_ts if t_start <= ts < t_end)
    dur_s = max(t_end - t_start, 0.001)

    if google_status == "EMPTY":
        category = "empty"
    elif all_rate_skip:
        category = "zero_cascade"
    else:
        category = "normal"

    record = {
        "qi": qi,
        "query": query,
        "t_start": t_start,
        "t_end": t_end,
        "duration_s": dur_s,
        "google_status": google_status,
        "all_statuses": all_statuses,
        "category": category,
        "total_ms": timings.get("total_ms", 0),
        "fanout_ms": timings.get("engine_fanout_ms", 0),
        "cdp_events": cdp_in_query,
        "cdp_rate": cdp_in_query / dur_s,
    }

    flag = "⚡EMPTY" if category == "empty" else ("🚫ZERO" if category == "zero_cascade" else "")
    print(
        f"[{qi}/{total}] {query!r} -> "
        f"google={google_status} cdp={cdp_in_query}({record['cdp_rate']:.0f}/s) "
        f"category={category} {flag}",
        file=sys.stderr,
    )
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CDP starvation probe: Pattern A + B + CDP event counter (20 queries)."
    )
    parser.add_argument("--max-queries", dest="max_queries", type=int, default=None,
                        help="Limit to first N queries (default: all from queries.txt)")
    args = parser.parse_args()
    asyncio.run(run_cdp_probe(args.max_queries))
