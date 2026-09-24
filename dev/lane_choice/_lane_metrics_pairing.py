# INFRASTRUCTURE
import json
from pathlib import Path

PROD_SCRAPE_LOG_PATH = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch/src/logs/scrape_log.jsonl"
)


# FUNCTIONS

def _latest_ok_records_by_url_engine(log_path: Path) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("acquisition_error") or not record.get("bytes_returned"):
                continue
            if not record.get("content_path"):
                continue
            key = (record["url"], record.get("engine"))
            if key not in latest or record["ts"] > latest[key]["ts"]:
                latest[key] = record
    return latest


def _resolve_content_path(log_path: Path, record: dict) -> Path:
    return log_path.parent / record["content_path"]


def collect_pairs_from_scrape_log() -> list[dict]:
    latest = _latest_ok_records_by_url_engine(PROD_SCRAPE_LOG_PATH)

    seen_urls: list[str] = []
    seen_set: set[str] = set()
    for url, _engine in latest:
        if url not in seen_set:
            seen_set.add(url)
            seen_urls.append(url)

    pairs = []
    for url in seen_urls:
        chromium_record = latest.get((url, "chromium"))
        camoufox_record = latest.get((url, "camoufox"))
        if chromium_record is None or camoufox_record is None:
            continue
        pairs.append({
            "url": url,
            "chromium_path": _resolve_content_path(PROD_SCRAPE_LOG_PATH, chromium_record),
            "camoufox_path": _resolve_content_path(PROD_SCRAPE_LOG_PATH, camoufox_record),
        })
    return pairs
