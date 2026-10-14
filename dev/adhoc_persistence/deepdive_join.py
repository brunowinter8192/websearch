# INFRASTRUCTURE
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from dev.adhoc_persistence.deepdive_config import JOIN_SLACK_SECONDS
from dev.kvp.kvp_load import parse_ts


# FUNCTIONS

def join_scrapes_to_calls(records: list[dict], calls: list[dict]) -> list[dict]:
    windows = [call_window(call) for call in calls]
    wanted_sets = [{normalize_url(u) for u in call["urls"] if is_parseable(u)} for call in calls]
    return [{**record, "call": best_call(record, calls, windows, wanted_sets)} for record in records]


def call_window(call: dict) -> tuple[datetime, datetime] | None:
    if not call["end"]:
        return None
    slack = timedelta(seconds=JOIN_SLACK_SECONDS)
    return parse_ts(call["start"]) - slack, parse_ts(call["end"]) + slack


def best_call(record: dict, calls: list[dict], windows: list, wanted_sets: list) -> dict | None:
    scraped_at = parse_ts(record["ts"])
    wanted = normalize_url(record["url"])
    matches = [
        call for call, window, urls in zip(calls, windows, wanted_sets)
        if window and window[0] <= scraped_at <= window[1] and wanted in urls
    ]
    if not matches:
        return None
    return min(matches, key=lambda call: abs((parse_ts(call["start"]) - scraped_at).total_seconds()))


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = f"?{parts.query}" if parts.query else ""
    return f"{host}{parts.path.rstrip('/')}{query}"


def is_parseable(url: str) -> bool:
    try:
        urlsplit(url)
    except ValueError:
        return False
    return True
