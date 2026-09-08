# INFRASTRUCTURE
import json
import logging
import os
import re
from pathlib import Path

from src.log_janitor import maybe_prune_jsonl, maybe_prune_sidecars

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "scrape_log.jsonl"


# FUNCTIONS

def _sanitize_ts(ts: str) -> str:
    return ts.replace(":", "-")


def _url_slug(url: str) -> str:
    slug = re.sub(r'^https?://', '', url)
    slug = re.sub(r'[^a-zA-Z0-9]', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:80]


def write_sidecar(url: str, ts: str, content: str, mode: str, engine: str) -> str | None:
    if not content:
        return None
    env = os.environ.get("WEBSEARCH_SCRAPE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    sidecar_dir = log_path.parent / "scrape_content"
    filename = f"{_sanitize_ts(ts)}_{_url_slug(url)}.md"
    header = (
        f"<!-- url: {url} -->\n"
        f"<!-- ts: {ts} -->\n"
        f"<!-- bytes: {len(content.encode('utf-8'))} -->\n"
        f"<!-- mode: {mode} -->\n"
        f"<!-- engine: {engine} -->\n"
    )
    try:
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        (sidecar_dir / filename).write_text(header + "\n" + content, encoding="utf-8")
        maybe_prune_sidecars(sidecar_dir)
        return f"scrape_content/{filename}"
    except Exception as e:
        logger.warning("scrape_logger sidecar write failed: %s", e)
        return None


def log_scrape(record: dict) -> None:
    env = os.environ.get("WEBSEARCH_SCRAPE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        maybe_prune_jsonl(log_path)
    except Exception as e:
        logger.warning("scrape_log write failed: %s", e)
