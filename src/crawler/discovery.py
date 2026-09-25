# INFRASTRUCTURE
import asyncio
import time
from dataclasses import dataclass, field

from src.crawler.navtree_feeder import navtree_feeder_workflow
from src.crawler.robots_feeder import robots_feeder_workflow
from src.crawler.sitemap_feeder import sitemap_feeder_workflow
from src.crawler.seed_feeders_scope import normalize_url, require_host

_FEEDER_WORKFLOWS = (
    ("robots", robots_feeder_workflow),
    ("sitemap", sitemap_feeder_workflow),
    ("navtree", navtree_feeder_workflow),
)


@dataclass
class DiscoveredURL:
    url: str
    source: str


@dataclass
class DiscoveryResult:
    urls: list = field(default_factory=list)
    ok: bool = True
    wall_s: float = 0.0
    failed_feeders: dict = field(default_factory=dict)
    dropped: int = 0
    error: str | None = None


# ORCHESTRATOR

async def discover_urls_workflow(seed_url: str) -> DiscoveryResult:
    t0 = time.time()
    try:
        require_host(seed_url)
    except Exception as exc:
        return DiscoveryResult(ok=False, error=str(exc), wall_s=time.time() - t0)

    feeder_results = await _run_feeders(seed_url)
    seeds, failed_feeders = _assemble_seeds(seed_url, feeder_results)
    urls = [DiscoveredURL(url=url, source=source) for url, source in seeds.items()]
    dropped = _total_dropped(feeder_results)
    return DiscoveryResult(urls=urls, ok=True, wall_s=time.time() - t0,
                           failed_feeders=failed_feeders, dropped=dropped)


# FUNCTIONS

async def _run_feeders(seed_url: str) -> dict:
    results = await asyncio.gather(*[workflow(seed_url) for _, workflow in _FEEDER_WORKFLOWS])
    return {name: result for (name, _), result in zip(_FEEDER_WORKFLOWS, results)}


def _assemble_seeds(seed_url: str, feeder_results: dict) -> tuple:
    seeds = {normalize_url(seed_url): "seed"}
    failed_feeders = {}
    for name, result in feeder_results.items():
        if not result.ok:
            failed_feeders[name] = result.error
            continue
        for url in result.urls:
            if url not in seeds:
                seeds[url] = result.source
    return seeds, failed_feeders


def _total_dropped(feeder_results: dict) -> int:
    return sum(result.dropped for result in feeder_results.values() if result.ok)
