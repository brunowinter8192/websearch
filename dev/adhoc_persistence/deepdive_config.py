# INFRASTRUCTURE
from pathlib import Path

MAIN_CHECKOUT = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch")
RAG_CLI_ROOT = Path("/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli")

LOG_DIR = MAIN_CHECKOUT / "src" / "logs"
SCRAPE_LOG_NAME = "scrape_log.jsonl"
PIPE_LOG_NAME = "pipe_scrape_log.jsonl"
RAG_SEARCH_LOG = RAG_CLI_ROOT / "src" / "rag" / "logs" / "search.jsonl"
COLLECTION_DIR = RAG_CLI_ROOT / "data" / "documents" / "websearch-pages"
COLLECTION_NAME = "websearch-pages"
TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"

HERE = Path(__file__).parent
REPORT_DIR = HERE / "md"
LABELS_PATH = HERE / "deepdive_labels.json"

JOIN_SLACK_SECONDS = 30
OFFER_WINDOW_HOURS = 3
MIN_PAGES = 2
STRONG_MIN_PAGES = 3
DOMAIN_SCALE_MIN_URLS = 30
DEV_PROJECT_MARKER = "cli-websearch"
WEB_RESEARCH_SKILL = "websearch-web-research"
TOP_LEVEL_TRANSCRIPT_GLOB = "*/*.jsonl"
MEASURING_PROJECT_SUFFIX = "worktrees-deepdive51"

LIST_QUALIFIES = "qualifies"
LIST_EXCLUDED = "excluded"
LIST_SILENT = "list_silent"
QUALIFYING_TYPES = frozenset({"docs", "vendor_manual"})
EXCLUDED_TYPES = frozenset({"blog", "news", "forum", "product", "changelog", "release_feed"})

ERAS = (
    ("E0", None, "2026-09-20T19:47:04Z", "capture is the default, ad hoc scrape only on explicit user request; no domain rule"),
    ("E1", "2026-09-20T19:47:04Z", "2026-09-24T18:46:25Z", "deep dive hangs on domain type, never on need; propose to the user at the smallest suspicion"),
    ("E2", "2026-09-24T18:46:25Z", "2026-10-11T11:58:39Z", "deep dive when other URLs of the domain could be relevant; propose to the user"),
    ("E3", "2026-10-11T11:58:39Z", "2026-10-14T16:37:27Z", "same trigger, proposal line dropped; workflow section still asks the user"),
    ("E4", "2026-10-14T16:37:27Z", None, "same trigger, worker-only workflow with INFO_NEED, no user step"),
)

SKILL_TEXT_MARKERS = (
    ("E0", "Permanent Capture Workflow"),
    ("E1", "hängt am Typ der Domain"),
    ("E4", "Starte einen Deep Dive"),
    ("E2_E3", "Mache einen Deep Dive wenn"),
)
PROPOSAL_MARKER = "Schlage dem User proaktiv einen Deep Dive vor"
