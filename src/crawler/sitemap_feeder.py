# INFRASTRUCTURE
from urllib.parse import urljoin

import httpx

from src.crawler.seed_feeders_constants import CONVENTIONAL_SITEMAP_PATHS
from src.crawler.seed_feeders_robots import fetch_robots_txt, parse_robots_directives
from src.crawler.seed_feeders_scope import FeederResult, base_url, require_host, run_guarded, scope_and_dedup
from src.crawler.seed_feeders_sitemap import resolve_sitemap_urls


# ORCHESTRATOR

async def sitemap_feeder_workflow(seed_url: str) -> FeederResult:
    return await run_guarded(_collect_sitemap, seed_url)


# FUNCTIONS

async def _collect_sitemap(seed_url: str) -> FeederResult:
    seed_host = require_host(seed_url)
    root_url = base_url(seed_url)
    async with httpx.AsyncClient() as client:
        text = await fetch_robots_txt(client, root_url)
        declared_sitemaps = parse_robots_directives(text, root_url)["sitemaps"] if text else []
        sitemap_urls = declared_sitemaps or [urljoin(root_url, p) for p in CONVENTIONAL_SITEMAP_PATHS]
        source = "sitemap_declared" if declared_sitemaps else "sitemap_conventional"
        loc_urls = await resolve_sitemap_urls(client, sitemap_urls)
    urls, dropped = scope_and_dedup(loc_urls, seed_host)
    return FeederResult(urls=urls, ok=True, source=source, dropped=dropped)
