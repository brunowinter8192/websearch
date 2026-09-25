# INFRASTRUCTURE
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "src" / "logs"

CDP_PORT_WAIT_TIMEOUT_S = 10.0
FOCUS_STEAL_POLL_INTERVAL_S = 0.25

BACKFILL_TOTAL = 61_000
XML_MARKERS = (b"<?xml", b"<sitemapindex", b"<urlset", b"<sitemap>")
PROXY_LIST_FETCH_TIMEOUT = 15.0
PROXY_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

REGWALL_SIGNALS: list[str] = [
    "from_regwall",
    "Create a FREE account to continue reading",
    "You've reached your monthly limit",
]

RAW_SUBDIR = "raw"
DELAY_BEFORE_HTML = 0.5
FAIL_THRESHOLD = 2
