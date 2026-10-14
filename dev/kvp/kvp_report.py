# INFRASTRUCTURE
import argparse
from datetime import datetime, timezone
from pathlib import Path

from dev.kvp.kvp_config import (
    DEFAULT_COLLECTION_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_RAG_SEARCH_LOG,
    PIPE_LOG_NAME,
    QUERY_LOG_NAME,
    REPORT_DIR,
    SCRAPE_LOG_NAME,
)
from dev.kvp.kvp_indicators import (
    classify_collection,
    classify_pipe_records,
    classify_scrapes,
    classify_searches,
    compute_report_data,
    scrape_counter_check,
)
from dev.kvp.kvp_load import attribution_end, load_collection, load_scrapes, load_window, parse_window_bound
from dev.kvp.kvp_render import render_report


# ORCHESTRATOR

def main() -> None:
    args = parse_args()
    since, until = parse_window_bound(args.since), parse_window_bound(args.until)
    log_dir = Path(args.log_dir)
    query_records = load_window(log_dir / QUERY_LOG_NAME, since, until)
    scrape_records = load_scrapes(log_dir / SCRAPE_LOG_NAME, since, until)
    attribution_scrapes = load_scrapes(log_dir / SCRAPE_LOG_NAME, since, attribution_end(until))
    pipe_records = load_window(log_dir / PIPE_LOG_NAME, since, until)
    rag_searches = load_window(Path(args.rag_search_log), since, until)
    collection_files = load_collection(Path(args.collection_dir))
    summaries = [r for r in query_records if r["record_type"] == "workflow_summary"]
    drilldowns = [r for r in query_records if r["record_type"] == "drilldown"]
    searches = classify_searches(summaries)
    scrapes = classify_scrapes(scrape_records)
    collection_items = classify_collection(collection_files)
    data = compute_report_data(
        searches, scrapes, drilldowns, attribution_scrapes,
        classify_pipe_records(pipe_records), collection_items, rag_searches,
    )
    meta = build_meta(args, log_dir, summaries, drilldowns, scrape_records, pipe_records, rag_searches, collection_files)
    report = render_report(meta, data, searches, scrapes, collection_items, scrape_counter_check(scrapes))
    path = write_report(report, REPORT_DIR, args.since, args.until)
    print(path)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="KVP report over the websearch logs")
    ap.add_argument("--since", type=str, default=None, help="Window start, ISO date or timestamp, UTC if no zone is given")
    ap.add_argument("--until", type=str, default=None, help="Window end, ISO date or timestamp, UTC if no zone is given")
    ap.add_argument("--log-dir", type=str, default=str(DEFAULT_LOG_DIR))
    ap.add_argument("--rag-search-log", type=str, default=str(DEFAULT_RAG_SEARCH_LOG))
    ap.add_argument("--collection-dir", type=str, default=str(DEFAULT_COLLECTION_DIR))
    return ap.parse_args()


def build_meta(
    args: argparse.Namespace, log_dir: Path, summaries: list[dict], drilldowns: list[dict],
    scrape_records: list[dict], pipe_records: list[dict], rag_searches: list[dict], collection_files: list[dict],
) -> dict:
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since": args.since,
        "until": args.until,
        "log_dir": str(log_dir),
        "counts": {
            "searches": len(summaries), "drilldowns": len(drilldowns), "scrapes": len(scrape_records),
            "pipe URLs": len(pipe_records), "rag-cli searches": len(rag_searches), "collection files (unwindowed)": len(collection_files),
        },
    }


def write_report(report: str, report_dir: Path, since: str | None, until: str | None) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    window = f"{_slug(since) or 'start'}_{_slug(until) or 'now'}"
    path = report_dir / f"kvp_report_{window}_{stamp}.md"
    path.write_text(report, encoding="utf-8")
    return path


def _slug(value: str | None) -> str:
    return "".join(c if c.isalnum() else "-" for c in value) if value else ""


if __name__ == "__main__":
    main()
