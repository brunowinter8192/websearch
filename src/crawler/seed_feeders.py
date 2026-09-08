# INFRASTRUCTURE
from urllib.parse import urljoin, urlparse

import httpx

from src.crawler.seed_feeders_constants import CONVENTIONAL_SITEMAP_PATHS
from src.crawler.seed_feeders_scope import FeederResult, scope_and_dedup, require_host
from src.crawler.seed_feeders_robots import fetch_robots_txt, parse_robots_directives
from src.crawler.seed_feeders_sitemap import resolve_sitemap_urls
from src.crawler.seed_feeders_navtree import resolve_navigation_tree


# ORCHESTRATOR

async def robots_feeder_workflow(seed_url: str) -> FeederResult:
    try:
        seed_host = require_host(seed_url)
        base_url = _base_url(seed_url)
        async with httpx.AsyncClient() as client:
            text = await fetch_robots_txt(client, base_url)
        paths = parse_robots_directives(text, base_url)["paths"] if text else []
        return FeederResult(urls=scope_and_dedup(paths, seed_host), ok=True, source="robots")
    except Exception as exc:
        return FeederResult(urls=[], ok=False, error=str(exc))


async def sitemap_feeder_workflow(seed_url: str) -> FeederResult:
    try:
        seed_host = require_host(seed_url)
        base_url = _base_url(seed_url)
        async with httpx.AsyncClient() as client:
            text = await fetch_robots_txt(client, base_url)
            declared_sitemaps = parse_robots_directives(text, base_url)["sitemaps"] if text else []
            sitemap_urls = declared_sitemaps or [urljoin(base_url, p) for p in CONVENTIONAL_SITEMAP_PATHS]
            loc_urls = await resolve_sitemap_urls(client, sitemap_urls)
        return FeederResult(urls=scope_and_dedup(loc_urls, seed_host), ok=True, source="sitemap")
    except Exception as exc:
        return FeederResult(urls=[], ok=False, error=str(exc))


async def navtree_feeder_workflow(seed_url: str) -> FeederResult:
    try:
        seed_host = require_host(seed_url)
        async with httpx.AsyncClient() as client:
            raw_urls, tier, version_keys = await resolve_navigation_tree(client, seed_url)
        return FeederResult(urls=scope_and_dedup(raw_urls, seed_host), ok=True,
                            source=f"navtree_{tier}", version_keys=version_keys)
    except Exception as exc:
        return FeederResult(urls=[], ok=False, error=str(exc))


# FUNCTIONS

def _base_url(seed_url: str) -> str:
    parsed = urlparse(seed_url)
    return f"{parsed.scheme}://{parsed.netloc}/"
