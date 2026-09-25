#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.search_web import search_web_workflow
from src.search.browser import close_browser

REPORT_DIR = SCRIPT_DIR / "md"

LOG_PATH = PROJECT_ROOT / "src" / "logs" / "query_log.jsonl"

QUERIES = [
    "python asyncio concurrent programming",
    "machine learning gradient descent optimization",
    "docker kubernetes container orchestration",
    "REST API authentication JWT OAuth",
    "database indexing B-tree performance",
]


# ORCHESTRATOR

async def run_smoke() -> None:
    _configure_logging()
    _prepare_report_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = _compute_report_path(ts)

    _print_smoke_with_google(report_path)
    print(file=sys.stderr)

    log_line_before = _count_log_lines()

    records = await _run_queries()

    log_lines_written = _compute_log_lines_written(log_line_before)
    _write_report(records, report_path, log_lines_written)
    pass_count = _compute_pass_count(records)
    _print_result_checks_passed(pass_count, records, report_path)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _prepare_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _compute_report_path(ts):
    report_path = REPORT_DIR / f"with_google_decoupling_{ts}.md"
    return report_path


def _print_smoke_with_google(report_path):
    print(f"Smoke: with-Google default set, {len(QUERIES)} queries", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)


async def _run_queries():
    records = []
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)
            t0 = time.perf_counter()
            await search_web_workflow(query, engines=None)
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            log_entry = _read_last_log_entry()
            result = _verify_log_entry(log_entry, query)
            result["elapsed_ms"] = elapsed_ms
            records.append(result)
            status_symbol = "OK" if result["pass"] else "FAIL"
            print(f"  → {status_symbol} | scholar_in_requested={result['scholar_in_requested']} | excluded_correct={result['excluded_correct']} | {elapsed_ms}ms", file=sys.stderr)
    finally:
        await close_browser()
    return records


def _compute_log_lines_written(log_line_before):
    log_lines_written = _count_log_lines() - log_line_before
    return log_lines_written


def _write_report(records: list[dict], path: Path, log_lines_written: int) -> None:
    ts = path.stem.replace("with_google_decoupling_", "")
    pass_count = sum(1 for r in records if r["pass"])
    fail_count = len(records) - pass_count

    lines = [
        f"# With-Google Decoupling Smoke — {ts}",
        "",
        f"**Queries:** {len(records)}  ",
        f"**Pass:** {pass_count}  ",
        f"**Fail:** {fail_count}  ",
        f"**Log lines written:** {log_lines_written}",
        "",
        "## Invariants Checked (per query)",
        "",
        "1. `google_scholar` NOT in `engines_requested`",
        "2. `google` IS in `engines_requested`",
        "3. `engines_excluded[\"google_scholar\"] == \"decoupled_from_google\"`",
        "4. `engines_excluded` field present in log entry",
        "",
        "## Results",
        "",
        "| # | Query | Pass | Scholar absent | Google present | Excluded correct | engines count |",
        "|---|-------|------|----------------|----------------|-----------------|---------------|",
    ]

    for i, r in enumerate(records, 1):
        q = r["query"][:50].replace("|", "\\|")
        p = "✓" if r["pass"] else "✗"
        sa = "✓" if not r["scholar_in_requested"] else "✗"
        gp = "✓" if r["google_in_requested"] else "✗"
        ec = "✓" if r["excluded_correct"] else "✗"
        n = r["engines_requested_count"]
        lines.append(f"| {i} | {q} | {p} | {sa} | {gp} | {ec} | {n} |")

    if fail_count > 0:
        lines += _render_failures(records)

    path.write_text("\n".join(lines), encoding="utf-8")


def _compute_pass_count(records):
    pass_count = sum(1 for r in records if r["pass"])
    return pass_count


def _print_result_checks_passed(pass_count, records, report_path):
    print(f"\nResult: {pass_count}/{len(records)} checks passed", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)


def _count_log_lines() -> int:
    if not LOG_PATH.exists():
        return 0
    return sum(1 for _ in LOG_PATH.open(encoding="utf-8"))


def _read_last_log_entry() -> dict:
    if not LOG_PATH.exists():
        return {}
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1]) if lines else {}


def _verify_log_entry(entry: dict, query: str) -> dict:
    engines_requested = entry.get("engines_requested", [])
    engines_excluded = entry.get("engines_excluded", {})

    scholar_in_requested = "google_scholar" in engines_requested
    google_in_requested = "google" in engines_requested
    excluded_correct = engines_excluded.get("google_scholar") == "decoupled_from_google"
    has_excluded_field = "engines_excluded" in entry

    passed = (
        not scholar_in_requested
        and google_in_requested
        and excluded_correct
        and has_excluded_field
    )

    return {
        "query": query,
        "pass": passed,
        "scholar_in_requested": scholar_in_requested,
        "google_in_requested": google_in_requested,
        "excluded_correct": excluded_correct,
        "has_excluded_field": has_excluded_field,
        "engines_requested_count": len(engines_requested),
        "engines_excluded_raw": engines_excluded,
    }


def _render_failures(records: list[dict]) -> list[str]:
    lines = ["", "## Failures", ""]
    for r in records:
        if not r["pass"]:
            lines += [
                f"### {r['query'][:80]}",
                "",
                f"- scholar_in_requested: {r['scholar_in_requested']}",
                f"- google_in_requested: {r['google_in_requested']}",
                f"- excluded_correct: {r['excluded_correct']}",
                f"- has_excluded_field: {r['has_excluded_field']}",
                f"- engines_excluded (raw): {r['engines_excluded_raw']}",
                "",
            ]
    return lines


if __name__ == "__main__":
    asyncio.run(run_smoke())
