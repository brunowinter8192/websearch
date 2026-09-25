# INFRASTRUCTURE
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

DEFAULT_LOG_PATH = Path("src/logs/query_log.jsonl")


# ORCHESTRATOR

def main() -> None:
    args = _parse_args()

    log_path = _resolve_log_path(args.log_path)
    if not log_path.exists():
        _print_no_log_file(log_path)
        sys.exit(1)

    all_records = _compute_all_records(log_path)

    engine_run_records = _compute_engine_run_records(all_records)
    workflow_records = _compute_workflow_records(all_records)

    _print_log(log_path, all_records, engine_run_records, workflow_records)

    records = _compute_records(all_records, args, workflow_records)
    if args.tail:
        records = _compute_tail_records(records, args)

    if not records:
        print("No records to display (try --all-types for a probe log).")
        return

    _print_timing_summary(records)
    _print_status_hits(records)
    _print_last_record(records)


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Inspect query_log.jsonl")
    ap.add_argument("--tail", type=int, default=None, help="Only consider last N records (after type filter)")
    ap.add_argument("--log-path", default=None, help="Path to JSONL log file (overrides env var and default)")
    ap.add_argument("--all-types", action="store_true", help="Include engine_run records in output (default: skip)")
    return ap.parse_args()


def _resolve_log_path(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("SEARXNG_QUERY_LOG_PATH")
    if env:
        return Path(env)
    return DEFAULT_LOG_PATH


def _print_no_log_file(log_path):
    print(f"No log file at {log_path}", file=sys.stderr)


def _compute_all_records(log_path):
    all_records = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    return all_records


def _compute_engine_run_records(all_records):
    engine_run_records    = [r for r in all_records if r.get("record_type") == "engine_run"]
    return engine_run_records


def _compute_workflow_records(all_records):
    workflow_records      = [r for r in all_records if r.get("record_type", "workflow_summary") != "engine_run"]
    return workflow_records


def _print_log(log_path, all_records, engine_run_records, workflow_records):
    print(f"Log          : {log_path}")
    print(f"Total lines  : {len(all_records)}  "
          f"(engine_run={len(engine_run_records)}, workflow_summary/old={len(workflow_records)})")


def _compute_records(all_records, args, workflow_records):
    records = all_records if args.all_types else workflow_records
    return records


def _compute_tail_records(records, args):
    records = records[-args.tail:]
    return records


def _print_timing_summary(records: list[dict]) -> None:
    summary_records = [r for r in records if r.get("record_type", "workflow_summary") != "engine_run"]
    if summary_records:
        total_wall = [r["total_wall_ms"] for r in summary_records]
        bottlenecks = Counter(r.get("bottleneck_engine") for r in summary_records if r.get("bottleneck_engine"))
        print(f"\nWorkflow summary records: {len(summary_records)}")
        print(f"Wall ms      : min={min(total_wall)}  mean={sum(total_wall)//len(total_wall)}  max={max(total_wall)}")
        print(f"Bottlenecks  : {dict(bottlenecks.most_common(5))}")


def _print_status_hits(records: list[dict]) -> None:
    timeouts: Counter = Counter()
    rate_skips: Counter = Counter()
    for r in records:
        for eng, d in r.get("engines", {}).items():
            if d.get("status") == "TIMEOUT":
                timeouts[eng] += 1
            if d.get("status") == "RATE_SKIP":
                rate_skips[eng] += 1
    print(f"TIMEOUT hits : {dict(timeouts.most_common(5))}")
    print(f"RATE_SKIP    : {dict(rate_skips.most_common(5))}")


def _print_last_record(records: list[dict]) -> None:
    prev = records[-1]
    rtype = prev.get("record_type", "old-style")
    print(f"\nLast record  : [{rtype}]  query={prev.get('query')}  ts={prev.get('ts')}")
    for eng, d in prev.get("engines", {}).items():
        print(f"  {eng:20s}  rate_wait={d['rate_wait_ms']:5d}ms  search={d['search_ms']:5d}ms  {d['status']}")
    pv = prev.get("preview")
    if pv:
        print(f"  preview: {pv.get('urls_succeeded')}/{pv.get('urls_attempted')} ok, "
              f"{pv.get('url_timeouts')} timeouts, {pv.get('total_ms')}ms total")


if __name__ == "__main__":
    main()
