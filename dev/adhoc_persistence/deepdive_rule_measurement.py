# INFRASTRUCTURE
from datetime import datetime, timezone
from pathlib import Path

from dev.adhoc_persistence.deepdive_assessment import annotate_groups, load_labels
from dev.adhoc_persistence.deepdive_candidates import add_recurrence, build_groups, classify_records, load_drilldowns, mark_offered
from dev.adhoc_persistence.deepdive_config import (
    COLLECTION_DIR,
    LABELS_PATH,
    LOG_DIR,
    PIPE_LOG_NAME,
    RAG_SEARCH_LOG,
    REPORT_DIR,
    SCRAPE_LOG_NAME,
    TRANSCRIPT_ROOT,
)
from dev.adhoc_persistence.deepdive_deepdives import build_runs
from dev.adhoc_persistence.deepdive_join import join_scrapes_to_calls
from dev.adhoc_persistence.deepdive_render import render_report
from dev.adhoc_persistence.deepdive_report_data import build_report_data
from dev.adhoc_persistence.deepdive_transcripts import load_transcript_facts
from dev.kvp.kvp_load import load_scrapes, read_jsonl

QUERY_LOG_NAME = "query_log.jsonl"


# ORCHESTRATOR

def main() -> None:
    labels = load_labels(LABELS_PATH)
    scrapes = classify_records(load_scrapes(LOG_DIR / SCRAPE_LOG_NAME, None, None))
    drilldowns = load_drilldowns(LOG_DIR / QUERY_LOG_NAME)
    facts = load_transcript_facts(TRANSCRIPT_ROOT)
    joined = mark_offered(join_scrapes_to_calls(scrapes, facts["calls"]["scrape"]), drilldowns)
    groups = annotate_groups(add_recurrence(build_groups(joined, facts["sessions"])), labels)
    rag_searches = read_jsonl(RAG_SEARCH_LOG)
    runs = build_runs(read_jsonl(LOG_DIR / PIPE_LOG_NAME), COLLECTION_DIR, rag_searches, labels)
    data = build_report_data(joined, groups, facts, runs, labels, rag_searches)
    print(write_report(render_report(data), REPORT_DIR))


# FUNCTIONS

def write_report(report: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = report_dir / f"deepdive_rule_measurement_{stamp}.md"
    path.write_text(report, encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
