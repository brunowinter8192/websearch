# INFRASTRUCTURE
from src.config import PROJECT_ROOT
from src.news.platform import ScrapeConfig

SCRAPE_CONFIG = ScrapeConfig()

TIMELINE_BASE = "https://www.coindesk.com/api/v1/articles/timeline"
COINDESK_BASE = "https://www.coindesk.com"
TARGET_URL    = "https://www.coindesk.com/latest-crypto-news"

CALL_DELAY           = 0.3
REWARM_EVERY         = 240.0
CLICKS_WARMUP        = 8
CLICKS_REWARM        = 7
MAX_CURSOR_FALLBACKS = 3
CHECKPOINT_EVERY     = 50
DEFAULT_DELTA_DAYS   = 30
FULL_MODE_FLOOR      = "2018-01-01"

DISCOVER_DIR = PROJECT_ROOT / "data" / "news" / "coindesk" / "discover"

SKIP_HEADERS = frozenset({
    ":authority", ":method", ":path", ":scheme",
    "host", "content-length", "content-encoding", "transfer-encoding",
})
