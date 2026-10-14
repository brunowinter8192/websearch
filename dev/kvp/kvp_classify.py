# INFRASTRUCTURE
import hashlib
import re
from typing import NamedTuple
from urllib.parse import urlparse

from dev.kvp.kvp_config import (
    COLLAPSE_BLOCKED,
    COLLAPSE_CONNECT_FAILED,
    COLLAPSE_LOCAL_NETWORK,
    COLLAPSE_MIXED,
    COLLAPSE_SLOW_NAVIGATION,
    COLLECTION_DUPLICATE,
    COLLECTION_PLACEHOLDER,
    COLLECTION_TITLE_ONLY,
    ENGINE_BLOCKED,
    ENGINE_EMPTY_NO_SIGNAL,
    ENGINE_OK,
    ENGINE_OTHER,
    ENGINE_RATE_SKIP,
    ENGINE_TRANSPORT_ERROR,
    SCRAPE_BLOCKED,
    SCRAPE_CHALLENGE,
    SCRAPE_FILTERED_TO_NOTHING,
    SCRAPE_HTTP_ERROR_PAGE,
    SCRAPE_LOGIN_WALL,
    SCRAPE_NO_CONTENT,
    SCRAPE_USABLE,
)

BLOCK_STATUSES = frozenset({401, 403, 429, 503})
HTTP_ERROR_PAGE_STATUSES = frozenset({404, 410})
BLOCK_BODY_MAX_BYTES = 2000
INTERSTITIAL_BODY_MAX_BYTES = 1000
FILTERED_TO_NOTHING_MAX_BYTES = 1
ANTI_BOT_MARKERS = (
    "sicherheitsüberprüfung",
    "sicherheitsprüfung",
    "access denied",
    "verification required",
    "klicke auf die schaltfläche",
)
LOGIN_URL_PATTERN = re.compile(r"(?<![a-z])(idp|saml|login|signin|sso|auth)(?![a-z])", re.IGNORECASE)
ENGINE_BLOCK_HTTP_STATUSES = frozenset({403, 429})
ENGINE_BLOCK_URL_MARKER = "showcaptcha"
PLACEHOLDER_LINE_PATTERN = re.compile(r"^Loading\.*$")
PLACEHOLDER_MIN_LINES = 5
TITLE_ONLY_MAX_BYTES = 100
CONNECT_FAILED_MARKER = "Failed to get browser ws address"
CONNECTION_REFUSED_MARKER = "ERR_CONNECTION_REFUSED"
LOCAL_NETWORK_MIN_REFUSED = 3
SLOW_NAVIGATION_MIN_TIMEOUTS = 3
BLOCKED_MIN_ENGINES = 2
SOURCE_LINE_PATTERN = re.compile(r"^<!-- source: .*? -->\n?")


class Verdict(NamedTuple):
    label: str
    evidence: str


# FUNCTIONS

def classify_scrape(record: dict, body: str) -> Verdict:
    return (
        _no_content(record)
        or _filtered_to_nothing(record)
        or _http_error_page(record)
        or _login_wall(record)
        or _blocked(record)
        or _challenge_or_interstitial(record, body)
        or Verdict(SCRAPE_USABLE, "")
    )


def classify_pipe_record(record: dict) -> Verdict:
    status = record.get("http_status")
    if record.get("error"):
        return Verdict(SCRAPE_NO_CONTENT, f"error={record['error']}")
    if not record.get("bytes"):
        return Verdict(SCRAPE_NO_CONTENT, "bytes=0")
    if status is not None and status >= 400:
        return Verdict(SCRAPE_HTTP_ERROR_PAGE, f"http_status={status}")
    return Verdict(SCRAPE_USABLE, "")


def classify_engine_run(stats: dict) -> Verdict:
    status = stats.get("status", "")
    if status == "OK":
        return Verdict(ENGINE_OK, "")
    if status.startswith(("ERROR_", "TIMEOUT_")):
        return Verdict(ENGINE_TRANSPORT_ERROR, status)
    if status == "RATE_SKIP":
        return Verdict(ENGINE_RATE_SKIP, status)
    if status == "EMPTY":
        return _classify_empty_run(stats)
    return Verdict(ENGINE_OTHER, status)


def classify_collapse(engines: dict) -> Verdict:
    return (
        _connect_failed(engines)
        or _local_network(engines)
        or _slow_navigation(engines)
        or _blocked_majority(engines)
        or Verdict(COLLAPSE_MIXED, "")
    )


def classify_collection_file(body: str) -> Verdict | None:
    content = strip_source_line(body)
    placeholder_lines = sum(1 for line in content.splitlines() if PLACEHOLDER_LINE_PATTERN.match(line.strip()))
    if placeholder_lines >= PLACEHOLDER_MIN_LINES:
        return Verdict(COLLECTION_PLACEHOLDER, f"{placeholder_lines} bare Loading lines")
    size = len(content.strip().encode("utf-8"))
    if size <= TITLE_ONLY_MAX_BYTES:
        return Verdict(COLLECTION_TITLE_ONLY, f"{size} B after source line")
    return None


def find_duplicate_files(files: list[dict]) -> dict[str, Verdict]:
    first_by_hash: dict[str, str] = {}
    duplicates: dict[str, Verdict] = {}
    for file in sorted(files, key=lambda f: f["name"]):
        digest = hashlib.sha256(strip_source_line(file["body"]).strip().encode("utf-8")).hexdigest()
        if digest in first_by_hash:
            duplicates[file["name"]] = Verdict(COLLECTION_DUPLICATE, f"same body as {first_by_hash[digest]}")
        else:
            first_by_hash[digest] = file["name"]
    return duplicates


def strip_source_line(body: str) -> str:
    return SOURCE_LINE_PATTERN.sub("", body, count=1)


def _connect_failed(engines: dict) -> Verdict | None:
    failed = [name for name, stats in engines.items() if CONNECT_FAILED_MARKER in (stats.get("drop_reason") or "")]
    if failed:
        return Verdict(COLLAPSE_CONNECT_FAILED, f"{len(failed)} engines: {CONNECT_FAILED_MARKER}")
    return None


def _local_network(engines: dict) -> Verdict | None:
    refused = [name for name, stats in engines.items() if CONNECTION_REFUSED_MARKER in (stats.get("drop_reason") or "")]
    if len(refused) < LOCAL_NETWORK_MIN_REFUSED:
        return None
    http_errors = [name for name, stats in engines.items() if stats.get("status") == "ERROR_HTTP"]
    suffix = f", HTTP errors from {', '.join(http_errors)}" if http_errors else ""
    return Verdict(COLLAPSE_LOCAL_NETWORK, f"{len(refused)} engines {CONNECTION_REFUSED_MARKER}{suffix}")


def _slow_navigation(engines: dict) -> Verdict | None:
    timed_out = [stats for stats in engines.values() if stats.get("status") == "TIMEOUT_WATCHDOG"]
    if len(timed_out) < SLOW_NAVIGATION_MIN_TIMEOUTS:
        return None
    still_navigating = sum(1 for stats in timed_out if not stats.get("diagnosis"))
    return Verdict(COLLAPSE_SLOW_NAVIGATION, f"{len(timed_out)} watchdog timeouts, {still_navigating} without diagnosis")


def _blocked_majority(engines: dict) -> Verdict | None:
    blocked = [name for name, stats in engines.items() if classify_engine_run(stats).label == ENGINE_BLOCKED]
    if len(blocked) < BLOCKED_MIN_ENGINES:
        return None
    return Verdict(COLLAPSE_BLOCKED, f"blocked: {', '.join(blocked)}")


def _no_content(record: dict) -> Verdict | None:
    if record.get("acquisition_error"):
        return Verdict(SCRAPE_NO_CONTENT, f"acquisition_error={record['acquisition_error']}")
    if not record.get("bytes_returned"):
        return Verdict(SCRAPE_NO_CONTENT, "bytes_returned=0")
    return None


def _filtered_to_nothing(record: dict) -> Verdict | None:
    returned = record["bytes_returned"]
    raw = record.get("bytes_raw_markdown") or 0
    if returned <= FILTERED_TO_NOTHING_MAX_BYTES and raw > returned:
        return Verdict(SCRAPE_FILTERED_TO_NOTHING, f"returned {returned} B of {raw} B raw")
    return None


def _http_error_page(record: dict) -> Verdict | None:
    status = record.get("http_status")
    if status in HTTP_ERROR_PAGE_STATUSES:
        return Verdict(SCRAPE_HTTP_ERROR_PAGE, f"http_status={status}")
    return None


def _login_wall(record: dict) -> Verdict | None:
    landed = record.get("landed_url")
    if not landed or _location_of(landed) == _location_of(record["url"]):
        return None
    if LOGIN_URL_PATTERN.search(_host_and_path(landed)) and not LOGIN_URL_PATTERN.search(_host_and_path(record["url"])):
        return Verdict(SCRAPE_LOGIN_WALL, f"landed on {_host_and_path(landed)}")
    return None


def _blocked(record: dict) -> Verdict | None:
    status = record.get("http_status")
    if status in BLOCK_STATUSES and record["bytes_returned"] < BLOCK_BODY_MAX_BYTES:
        return Verdict(SCRAPE_BLOCKED, f"http_status={status} with {record['bytes_returned']} B")
    return None


def _challenge_or_interstitial(record: dict, body: str) -> Verdict | None:
    if record["bytes_returned"] >= INTERSTITIAL_BODY_MAX_BYTES:
        return None
    lowered = body.lower()
    for marker in ANTI_BOT_MARKERS:
        if marker in lowered:
            return Verdict(SCRAPE_CHALLENGE, f"marker '{marker}' in {record['bytes_returned']} B body")
    return None


def _classify_empty_run(stats: dict) -> Verdict:
    signals = _block_signals(stats.get("diagnosis") or {})
    if signals:
        return Verdict(ENGINE_BLOCKED, ", ".join(signals))
    return Verdict(ENGINE_EMPTY_NO_SIGNAL, "")


def _block_signals(diagnosis: dict) -> list[str]:
    signals = []
    if diagnosis.get("marker"):
        signals.append(f"marker={diagnosis['marker']}")
    for key in ("challenge_triggered", "challenge_widget", "pow_link"):
        if diagnosis.get(key):
            signals.append(key)
    if diagnosis.get("http_status") in ENGINE_BLOCK_HTTP_STATUSES:
        signals.append(f"http_status={diagnosis['http_status']}")
    if ENGINE_BLOCK_URL_MARKER in (diagnosis.get("url") or ""):
        signals.append(ENGINE_BLOCK_URL_MARKER)
    return signals


def _location_of(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return (parsed.hostname or "").removeprefix("www."), parsed.path.rstrip("/")


def _host_and_path(url: str) -> str:
    host, path = _location_of(url)
    return host + path
