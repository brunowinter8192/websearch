# INFRASTRUCTURE
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.scraper.scrape_logger import DEFAULT_LOG_PATH, _url_slug
from src.crawler.pipe_scraper_acquisition import _url_to_filename

RAG_CLI_COLLECTIONS_ROOT = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents"
)


@dataclass
class IndexOutcome:
    url: str
    status: str
    detail: str
    byte_count: int | None = None


@dataclass
class IndexScrapesResult:
    ok: bool
    error: str | None
    outcomes: list[IndexOutcome]


# ORCHESTRATOR

def index_scrapes_workflow(collection: str, urls: list[str]) -> IndexScrapesResult:
    collection_dir = _resolve_collection_dir(collection)
    if not collection_dir.is_dir():
        return IndexScrapesResult(False, f"collection directory not found: {collection_dir}", [])
    sidecar_dir = _resolve_sidecar_dir()
    outcomes = [_index_one(url, sidecar_dir, collection, collection_dir) for url in urls]
    return IndexScrapesResult(True, None, outcomes)


# FUNCTIONS

def _resolve_collection_dir(collection: str) -> Path:
    return RAG_CLI_COLLECTIONS_ROOT / collection


def _resolve_sidecar_dir() -> Path:
    env = os.environ.get("WEBSEARCH_SCRAPE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    return log_path.parent / "scrape_content"


def _index_one(url: str, sidecar_dir: Path, collection: str, collection_dir: Path) -> IndexOutcome:
    try:
        sidecar_path = _find_sidecar(url, sidecar_dir)
        if sidecar_path is None:
            return IndexOutcome(url, "no_sidecar", "")
        content = _sidecar_content(sidecar_path)
        filename = _url_to_filename(url)
        byte_count = _write_collection_file(collection_dir, filename, url, content)
        ok, detail = _run_rag_cli_index(collection, filename)
        if ok:
            return IndexOutcome(url, "indexed", filename, byte_count)
        return IndexOutcome(url, "failed", detail)
    except Exception as e:
        return IndexOutcome(url, "failed", str(e))


def _find_sidecar(url: str, sidecar_dir: Path) -> Path | None:
    slug = _url_slug(url)
    matches = sorted(sidecar_dir.glob(f"*_{slug}.md"))
    return matches[-1] if matches else None


def _sidecar_content(sidecar_path: Path) -> str:
    return sidecar_path.read_text(encoding="utf-8").split("\n\n", 1)[1]


def _write_collection_file(collection_dir: Path, filename: str, url: str, content: str) -> int:
    text = f"<!-- source: {url} -->\n\n{content}"
    (collection_dir / filename).write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def _run_rag_cli_index(collection: str, filename: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ["rag-cli", "index", "--collection", collection, "--document", filename],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()
    return True, ""
