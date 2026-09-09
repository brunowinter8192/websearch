# INFRASTRUCTURE

import asyncio
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path

from src.news.engine.proxy_riding.cooldown import RidingCooldownManager
from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool
from src.news.engine.proxy_riding.rider import run_riding_pool
from src.news.engine.proxy_riding.state import RiderState

BROWSER_ELIGIBLE_PROTOS: frozenset[str] = frozenset({"http", "socks5"})


@dataclass
class RidingScrapeConfig:
    burn_threshold:  int   = 2
    n_slots:         int   = 64
    n_browsers:      int   = 4
    page_timeout_ms: int   = 8_000
    stall_timeout_s: float = 300.0
    cooldown_policy: str   = "fixed"


# ORCHESTRATOR

async def scrape_entries_riding(
    entries:    list[dict],
    output_dir: Path,
    riding_cfg: RidingScrapeConfig,
    job_dir:    Path,
) -> tuple[list[dict], RiderState]:
    output_dir.mkdir(parents=True, exist_ok=True)

    urls        = [e["url"] for e in entries]
    url_to_hash = {url: hashlib.sha256(url.encode()).hexdigest()[:12] for url in urls}

    url_queue = asyncio.Queue()
    for url in urls:
        url_queue.put_nowait(url)

    proxy_pool = await _pool_provider()
    cm         = RidingCooldownManager(policy=riding_cfg.cooldown_policy)

    state = await run_riding_pool(
        url_queue=url_queue,
        proxy_pool=proxy_pool,
        cooldown_mgr=cm,
        output_dir=output_dir,
        job_dir=job_dir,
        target_urls=frozenset(urls),
        burn_threshold=riding_cfg.burn_threshold,
        n_slots=riding_cfg.n_slots,
        page_timeout_ms=riding_cfg.page_timeout_ms,
        n_browsers=riding_cfg.n_browsers,
        stall_timeout_s=riding_cfg.stall_timeout_s,
        pool_provider=_pool_provider,
    )

    return _build_manifest(entries, url_to_hash, state), state


# FUNCTIONS

async def _pool_provider() -> list[tuple[str, str]]:
    loop       = asyncio.get_running_loop()
    raw_pool, _ = await loop.run_in_executor(None, load_backfill_pool)
    pool       = [(p, hp) for p, hp in raw_pool if p in BROWSER_ELIGIBLE_PROTOS]
    random.shuffle(pool)
    return pool

def _build_manifest(
    entries:     list[dict],
    url_to_hash: dict[str, str],
    state:       RiderState,
) -> list[dict]:
    url_ok_file:    dict[str, str] = {}
    url_char_count: dict[str, int] = {}
    last_error:     dict[str, str | None] = {}

    for job in state.job_records:
        last_error[job.url] = job.error
        if job.status == "ok" and job.file:
            url_ok_file[job.url]    = job.file
            if job.char_count is not None:
                url_char_count[job.url] = job.char_count

    manifest = []
    for entry in entries:
        url = entry["url"]
        h   = url_to_hash[url]
        if url in url_ok_file:
            manifest.append({
                "url": url, "hash": h, "status": "ok",
                "file": url_ok_file[url],
                "char_count": url_char_count.get(url),
                "error": None,
            })
        else:
            manifest.append({
                "url": url, "hash": h, "status": "failed",
                "file": None, "char_count": None,
                "error": last_error.get(url) or "not fetched",
            })
    return manifest
