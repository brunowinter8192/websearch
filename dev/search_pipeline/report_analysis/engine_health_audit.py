"""Engine-health audit over src/logs/query_log.jsonl.

Aggregates per-engine OK/EMPTY/TIMEOUT/ERROR/RATE_SKIP counts and classifies
each engine into one of: BROKEN / DEGRADED / SLOW / RATE_LIMITED / INSUFFICIENT / OK.

Usage:
    ./venv/bin/python dev/search_pipeline/engine_health_audit.py --last 100
    ./venv/bin/python dev/search_pipeline/engine_health_audit.py --last 50 --since 2026-05-08T00:00
    ./venv/bin/python dev/search_pipeline/engine_health_audit.py --engine google_scholar
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("src/logs/query_log.jsonl")
REPORT_DIR = Path("dev/search_pipeline/md")

SUCCESS_BROKEN: float = 0.50
SUCCESS_DEGRADED: float = 0.80
SFAIL_SLOW: float = 0.30
MIN_SAMPLES: int = 5


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    records = load_records(LOG_PATH, args.last, args.since, args.engine)
    if not records:
        print("No records matched the given filters.", file=sys.stderr)
        sys.exit(1)
    stats = aggregate_engine_stats(records)
    table_str = format_table(stats, n_records=len(records), last_n=args.last, since=args.since, engine_filter=args.engine)
    print(table_str)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = write_report(table_str, REPORT_DIR, ts)
    print(f"\nReport written → {report_path}")


# FUNCTIONS

# Parse CLI args: --last N, --since ISO_TIMESTAMP, --engine NAME
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Engine health audit over query_log.jsonl")
    ap.add_argument("--last", type=int, default=100, help="Analyse last N query records (default 100)")
    ap.add_argument("--since", type=str, default=None, help="Only records at or after ISO timestamp, e.g. 2026-05-08T00:00")
    ap.add_argument("--engine", type=str, default=None, help="Filter to a single engine name")
    return ap.parse_args()


# Load, slice, and filter records from the JSONL log
def load_records(log_path: Path, last_n: int, since: str | None, engine_filter: str | None) -> list[dict]:
    if not log_path.exists():
        print(f"Log not found: {log_path}", file=sys.stderr)
        sys.exit(1)
    records = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    records = records[-last_n:]
    if since:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
        records = [r for r in records if _parse_ts(r["ts"]) >= since_dt]
    if engine_filter:
        records = [r for r in records if engine_filter in r.get("engines", {})]
    return records


# Parse log ts field (Z-suffix UTC) to aware datetime
def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# Build per-engine aggregate stats dict from a list of query records
def aggregate_engine_stats(records: list[dict]) -> dict[str, dict]:
    counts: dict[str, Counter] = defaultdict(Counter)
    ok_ms: dict[str, list[int]] = defaultdict(list)
    ok_results: dict[str, list[int]] = defaultdict(list)

    for r in records:
        for eng, d in r.get("engines", {}).items():
            status = d.get("status", "UNKNOWN")
            counts[eng][status] += 1
            if status == "OK":
                ok_ms[eng].append(d.get("search_ms", 0))
                rc = d.get("result_count", 0)
                if rc:
                    ok_results[eng].append(rc)

    stats = {}
    for eng, c in counts.items():
        total = sum(c.values())
        ok = c.get("OK", 0)
        # Sum all sub-statuses per bucket (tolerates EMPTY_*, TIMEOUT_*, ERROR_* sub-statuses)
        empty_count   = sum(v for k, v in c.items() if k.startswith("EMPTY"))
        timeout_count = sum(v for k, v in c.items() if k.startswith("TIMEOUT"))
        error_count   = sum(v for k, v in c.items() if k.startswith("ERROR"))
        rate_skip_count = c.get("RATE_SKIP", 0)
        silent = total - ok
        avg_ms = int(sum(ok_ms[eng]) / len(ok_ms[eng])) if ok_ms[eng] else 0
        avg_res = round(sum(ok_results[eng]) / len(ok_results[eng]), 1) if ok_results[eng] else 0.0
        buckets = {"EMPTY": empty_count, "TIMEOUT": timeout_count, "ERROR": error_count, "RATE_SKIP": rate_skip_count}
        dom_fail = max(buckets, key=buckets.get) if silent > 0 else None
        stats[eng] = {
            "total": total,
            "ok": ok,
            "empty": empty_count,
            "timeout": timeout_count,
            "error": error_count,
            "rate_skip": rate_skip_count,
            "success_rate": ok / total if total else 0.0,
            "silent_fail_rate": silent / total if total else 0.0,
            "dom_fail": dom_fail,
            "avg_ms": avg_ms,
            "avg_results": avg_res,
            "status_counts": dict(c),  # raw per-sub-status counter for classify_health
        }
    return stats


# Classify a single engine's stats into (emoji, label) health flag
def classify_health(s: dict) -> tuple[str, str]:
    if s["total"] < MIN_SAMPLES:
        return "⚪", "INSUFFICIENT"
    sc = s.get("status_counts", {})

    # Sub-status-aware EMPTY rules (EMPTY_NO_CONTAINER/EMPTY_BLOCK/EMPTY_NO_RESULTS) were removed
    # along with the query log's guessed-verdict sub-statuses — every empty result now logs a bare
    # "EMPTY" carrying its own diagnosis snapshot instead, so no sub-status breakdown remains to
    # bucket on here; see src/search/DOCS.md's diagnosis Gotcha for what replaced the distinction.

    # TIMEOUT sub-status: PYDOLL-CANCEL-LEAK flag
    timeout_total = s["timeout"]
    if timeout_total >= 3:
        noncoop = sc.get("TIMEOUT_NONCOOP", 0)
        if noncoop / timeout_total > 0.10:
            return "⚠️", "FLAG (PYDOLL-CANCEL-LEAK)"

    # Coarse success-rate rules (unchanged)
    if s["success_rate"] < SUCCESS_BROKEN:
        return "🔴", "BROKEN"
    if s["success_rate"] < SUCCESS_DEGRADED:
        if s["silent_fail_rate"] > SFAIL_SLOW and s["dom_fail"] == "TIMEOUT":
            return "🟡", "DEGRADED (⏱️ SLOW)"
        if s["silent_fail_rate"] > SFAIL_SLOW and s["dom_fail"] == "RATE_SKIP":
            return "🟡", "DEGRADED (🚫 RATE_LIMITED)"
        return "🟡", "DEGRADED"
    if s["silent_fail_rate"] > SFAIL_SLOW and s["dom_fail"] == "TIMEOUT":
        return "⏱️", "SLOW"
    if s["silent_fail_rate"] > SFAIL_SLOW and s["dom_fail"] == "RATE_SKIP":
        return "🚫", "RATE_LIMITED"
    return "✅", "OK"


# Build human-readable table string with per-engine rows and legend
def format_table(stats: dict[str, dict], n_records: int, last_n: int, since: str | None, engine_filter: str | None) -> str:
    lines = []
    scope = f"last {n_records} records"
    if since:
        scope += f" since {since}"
    if engine_filter:
        scope += f", engine={engine_filter}"
    lines.append(f"# Engine Health Audit — {scope}")
    lines.append(f"Thresholds: BROKEN<{int(SUCCESS_BROKEN*100)}%  DEGRADED<{int(SUCCESS_DEGRADED*100)}%  SLOW/RL sfail>{int(SFAIL_SLOW*100)}%  MIN_SAMPLES={MIN_SAMPLES}")
    lines.append("")

    # Header
    col = f"{'Engine':<25}  {'Flag':<28}  {'OK':>4}  {'EMPTY':>5}  {'TO':>5}  {'ERR':>5}  {'RSKP':>5}  {'total':>5}  {'succ%':>6}  {'sfail%':>7}  {'avg_ms':>7}  {'avg_res':>8}"
    lines.append(col)
    lines.append("-" * len(col))

    # Sort: worst first (BROKEN/INSUFFICIENT at top), then alphabetical within group
    def sort_key(item: tuple[str, dict]) -> tuple[int, str]:
        eng, s = item
        emoji, label = classify_health(s)
        order = {"🔴": 0, "⚪": 1, "🟡": 2, "⏱️": 3, "🚫": 4, "✅": 5}
        return order.get(emoji, 9), eng

    for eng, s in sorted(stats.items(), key=sort_key):
        emoji, label = classify_health(s)
        flag_col = f"{emoji} {label}"
        avg_res_str = f"{s['avg_results']:>8.1f}" if s["avg_results"] else f"{'—':>8}"
        avg_ms_str = f"{s['avg_ms']:>7}" if s["avg_ms"] else f"{'—':>7}"
        lines.append(
            f"{eng:<25}  {flag_col:<28}  {s['ok']:>4}  {s['empty']:>5}  {s['timeout']:>5}  {s['error']:>5}  {s['rate_skip']:>5}  {s['total']:>5}  {s['success_rate']*100:>5.0f}%  {s['silent_fail_rate']*100:>6.0f}%  {avg_ms_str}  {avg_res_str}"
        )

    lines.append("")
    lines.append("Legend: BROKEN<50% success | DEGRADED<80% | SLOW/RL sfail>30% | INSUFFICIENT<5 samples")
    return "\n".join(lines)


# Write report MD to md/ with timestamp; returns the path written
def write_report(table_str: str, report_dir: Path, timestamp: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"engine_health_{timestamp}.md"
    path.write_text(f"```\n{table_str}\n```\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
