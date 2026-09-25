# INFRASTRUCTURE
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "src" / "logs"
NEWS_DATA_ROOT = PROJECT_ROOT / "data" / "news"

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
RIDING_PAGE_TIMEOUT_MS = 8_000
RIDING_STALL_TIMEOUT_S = 3_600.0
RIDING_POOL_REFRESH_INTERVAL_S = 1_800.0

PROXY_POOL_BUFFER_SIZE = 1280
PROXY_POOL_CONCURRENCY = 128
MONOSANS_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json"

TOTAL_SCRAPE_BUDGET_S = 242.8
SCRAPE_LOG_PATH = LOG_DIR / "scrape_log.jsonl"
MAX_SNIPPET_LEN = 500
