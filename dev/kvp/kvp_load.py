# INFRASTRUCTURE
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dev.kvp.kvp_config import ATTRIBUTION_WINDOW_HOURS, UNVERSIONED

SIDECAR_HEADER_PREFIX = "<!-- url:"
SIDECAR_HEADER_SEPARATOR = "\n\n"
SOURCE_LINE_PREFIX = "<!-- source: "
SOURCE_LINE_SUFFIX = " -->"


# FUNCTIONS

def parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_window_bound(value: str | None) -> datetime | None:
    return parse_ts(value) if value else None


def attribution_end(until: datetime | None) -> datetime | None:
    return until + timedelta(hours=ATTRIBUTION_WINDOW_HOURS) if until else None


def load_window(path: Path, since: datetime | None, until: datetime | None) -> list[dict]:
    return [r for r in read_jsonl(path) if in_window(parse_ts(r["ts"]), since, until)]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def in_window(ts: datetime, since: datetime | None, until: datetime | None) -> bool:
    return (since is None or ts >= since) and (until is None or ts <= until)


def load_scrapes(log_path: Path, since: datetime | None, until: datetime | None) -> list[dict]:
    records = load_window(log_path, since, until)
    return [{**r, "body": read_sidecar_body(log_path.parent, r.get("content_path"))} for r in records]


def read_sidecar_body(log_dir: Path, content_path: str | None) -> str:
    if not content_path:
        return ""
    sidecar = log_dir / content_path
    if not sidecar.exists():
        return ""
    text = sidecar.read_text(encoding="utf-8")
    if not text.startswith(SIDECAR_HEADER_PREFIX):
        return text
    return text.split(SIDECAR_HEADER_SEPARATOR, 1)[1] if SIDECAR_HEADER_SEPARATOR in text else ""


def load_collection(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    return [_read_collection_file(path) for path in sorted(directory.glob("*.md"))]


def version_of(record: dict) -> str:
    return record.get("code_version") or UNVERSIONED


def _read_collection_file(path: Path) -> dict:
    body = path.read_text(encoding="utf-8")
    return {
        "name": path.name,
        "source_url": _source_url_of(body),
        "body": body,
        "indexed": path.with_suffix(".json").exists(),
    }


def _source_url_of(body: str) -> str | None:
    first_line = body.split("\n", 1)[0].strip()
    if first_line.startswith(SOURCE_LINE_PREFIX) and first_line.endswith(SOURCE_LINE_SUFFIX):
        return first_line[len(SOURCE_LINE_PREFIX):-len(SOURCE_LINE_SUFFIX)].strip()
    return None
