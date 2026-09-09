# INFRASTRUCTURE

import hashlib
from pathlib import Path

from src.news.engine.proxy_pool.cooldown import PersistentCooldownManager
from src.news.engine.proxy_pool.logger import AcquireLogger
from src.news.engine.proxy_pool.loop import run_loop
from src.news.platform import ProxyScrapeConfig


# ORCHESTRATOR

def scrape_entries_proxy(
    entries: list[dict],
    output_dir: Path,
    proxy_cfg: ProxyScrapeConfig,
    logger: AcquireLogger,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)

    target_urls = [e["url"] for e in entries]
    url_to_hash = {
        url: hashlib.sha256(url.encode()).hexdigest()[:12]
        for url in target_urls
    }
    fetched: dict[str, dict] = {}

    def content_handler(url: str, content: bytes) -> None:
        url_hash  = url_to_hash[url]
        text      = content.decode("utf-8", errors="replace")
        file_path = output_dir / f"{url_hash}.md"
        file_path.write_text(text, encoding="utf-8")
        fetched[url] = {"file": str(file_path), "char_count": len(text)}

    cm = PersistentCooldownManager()

    done, dead, gap = run_loop(
        proxy_cfg.pool_provider,
        target_urls,
        proxy_cfg.content_type,
        logger,
        cm,
        concurrency=proxy_cfg.concurrency,
        buffer_size=proxy_cfg.buffer_size,
        content_handler=content_handler,
    )

    return _build_manifest(entries, url_to_hash, fetched, set(done), set(dead))


# FUNCTIONS

def _build_manifest(
    entries: list[dict],
    url_to_hash: dict[str, str],
    fetched: dict[str, dict],
    done: set[str],
    dead: set[str],
) -> list[dict]:
    manifest = []
    for entry in entries:
        url      = entry["url"]
        url_hash = url_to_hash[url]
        if url in done:
            r = fetched.get(url, {})
            manifest.append({
                "url": url, "hash": url_hash, "status": "ok",
                "file": r.get("file"), "char_count": r.get("char_count"), "error": None,
            })
        elif url in dead:
            manifest.append({
                "url": url, "hash": url_hash, "status": "dead",
                "file": None, "char_count": None, "error": None,
            })
        else:
            manifest.append({
                "url": url, "hash": url_hash, "status": "failed",
                "file": None, "char_count": None, "error": "not fetched",
            })
    return manifest
