# INFRASTRUCTURE
from pathlib import Path

MAIN_CHECKOUT = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch")
RAG_CLI_ROOT = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli")

DEFAULT_LOG_DIR = MAIN_CHECKOUT / "src" / "logs"
DEFAULT_RAG_SEARCH_LOG = RAG_CLI_ROOT / "src" / "rag" / "logs" / "search.jsonl"
DEFAULT_COLLECTION_DIR = RAG_CLI_ROOT / "data" / "documents" / "websearch-pages"
COLLECTION_NAME = "websearch-pages"
REPORT_DIR = Path(__file__).parent / "md"

QUERY_LOG_NAME = "query_log.jsonl"
SCRAPE_LOG_NAME = "scrape_log.jsonl"
PIPE_LOG_NAME = "pipe_scrape_log.jsonl"

UNVERSIONED = "unversioned"
ATTRIBUTION_WINDOW_HOURS = 3
MIN_ENGINES_OK = 3

SCRAPE_USABLE = "usable"
SCRAPE_NO_CONTENT = "no_content"
SCRAPE_FILTERED_TO_NOTHING = "filtered_to_nothing"
SCRAPE_HTTP_ERROR_PAGE = "http_error_page"
SCRAPE_LOGIN_WALL = "login_wall"
SCRAPE_BLOCKED = "blocked"
SCRAPE_CHALLENGE = "challenge_or_interstitial"
SILENT_SCRAPE_LABELS = (
    SCRAPE_FILTERED_TO_NOTHING,
    SCRAPE_HTTP_ERROR_PAGE,
    SCRAPE_LOGIN_WALL,
    SCRAPE_BLOCKED,
    SCRAPE_CHALLENGE,
)

ENGINE_OK = "ok"
ENGINE_BLOCKED = "blocked"
ENGINE_EMPTY_NO_SIGNAL = "empty_no_signal"
ENGINE_TRANSPORT_ERROR = "transport_error"
ENGINE_RATE_SKIP = "rate_skip"
ENGINE_OTHER = "other"

COLLECTION_PLACEHOLDER = "placeholder"
COLLECTION_TITLE_ONLY = "title_only"
COLLECTION_DUPLICATE = "duplicate"
