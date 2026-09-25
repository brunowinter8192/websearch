#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines import openalex as openalex_engine

QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR = SCRIPT_DIR / "md"


# ORCHESTRATOR

async def run_smoke_test() -> None:
    _configure_logging()
    queries = load_queries(QUERIES_FILE)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    engine = openalex_engine

    records = await _run_queries(queries, engine)

    report_path = write_report(records, REPORT_DIR)
    ok_count = _compute_ok_count(records)
    _print_report(report_path, ok_count, records)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def load_queries(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


async def _run_queries(queries, engine):
    records = []
    for qi, query in enumerate(queries):
        print(f"[{qi + 1}/{len(queries)}] {query}", file=sys.stderr)
        t0 = time.monotonic()
        record = await run_query(engine, query)
        elapsed = time.monotonic() - t0
        record["elapsed_ms"] = int(elapsed * 1000)
        records.append(record)
        print(
            f"  → {record['status']} | {record['count']} results | {elapsed:.1f}s",
            file=sys.stderr,
        )
    return records


def write_report(records: list[dict], report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"openalex_smoke_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    lines = [
        f"# OpenAlex Smoke Test — {ts}",
        "",
        f"**Queries:** {len(records)}  ",
        f"**OK:** {ok_count}  ",
        f"**Non-OK:** {len(records) - ok_count}",
        "",
        "## Overview",
        "",
        "| # | Query | Status | Count | Elapsed ms | Sample-URL |",
        "|---|-------|--------|-------|------------|------------|",
    ]

    for i, r in enumerate(records, 1):
        query = r["query"][:50].replace("|", "\\|")
        sample = r["sample_urls"][0] if r["sample_urls"] else ""
        lines.append(
            f"| {i} | {query} | {r['status']} | {r['count']} | {r['elapsed_ms']} | {sample} |"
        )

    non_ok = [r for r in records if r["status"] != "OK"]
    if non_ok:
        lines += ["", "## Non-OK Details", ""]
        for r in non_ok:
            lines += [
                f"### [{r['status']}] {r['query'][:80]}",
                "",
                f"- **Status:** {r['status']}",
                f"- **Count:** {r['count']}",
            ]
            if r.get("error"):
                lines.append(f"- **Error:** {r['error']}")
            for url in r.get("sample_urls", []):
                lines.append(f"- {url}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _compute_ok_count(records):
    ok_count = sum(1 for r in records if r["status"] == "OK")
    return ok_count


def _print_report(report_path, ok_count, records):
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/30 OK, {len(records) - ok_count}/30 non-OK",
        file=sys.stderr,
    )


async def run_query(engine, query: str) -> dict:
    record: dict = {"query": query, "count": 0, "sample_urls": [], "status": "EMPTY", "elapsed_ms": 0}
    try:
        results = (await engine.search_with_reason(query))[0]
        record["count"] = len(results)
        record["sample_urls"] = [r.url for r in results[:3]]
        record["status"] = "OK" if results else "EMPTY"
    except Exception as e:
        record["status"] = "RATE_LIMITED" if "429" in str(e) or "rate" in str(e).lower() else "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:80]}"
    return record


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
