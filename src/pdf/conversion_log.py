# INFRASTRUCTURE
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import LOG_DIR
from src.pdf.report import WorkflowError
from src.scraper.scrape_logger import utc_timestamp

CONVERSION_LOG_PATH = LOG_DIR / "conversions.jsonl"
CONVERSION_LOG_ENV = "WEBSEARCH_CONVERSION_LOG_PATH"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
RUN_ID_LENGTH = 12


# FUNCTIONS
def log_path() -> Path:
    override = os.environ.get(CONVERSION_LOG_ENV)
    return Path(override) if override else CONVERSION_LOG_PATH


def new_run_id() -> str:
    return uuid.uuid4().hex[:RUN_ID_LENGTH]


def append_record(record: dict) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_records() -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def count_earlier_attempts(pdf_sha256: str) -> int:
    return sum(
        1 for record in read_records()
        if record["record_type"] == "start" and record["pdf_sha256"] == pdf_sha256
    )


def parse_timestamp(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def build_end_record(run_id: str, ts_start: str, outcome: str, failure_class: str | None, **fields) -> dict:
    ts_end = utc_timestamp()
    wall_s = (parse_timestamp(ts_end) - parse_timestamp(ts_start)).total_seconds()
    return {
        "record_type": "end",
        "run_id": run_id,
        "ts_end": ts_end,
        "outcome": outcome,
        "failure_class": failure_class,
        "wall_s": round(wall_s, 1),
        **fields,
    }


def log_failure(run_id: str, ts_start: str, error: Exception, default_class: str) -> str:
    failure_class = error.failure_class if isinstance(error, WorkflowError) else default_class
    append_record(build_end_record(run_id, ts_start, "failed", failure_class, error=str(error)))
    return failure_class
