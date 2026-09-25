# INFRASTRUCTURE
import httpx

from src.crawler.seed_feeders_navtree import resolve_navigation_tree
from src.crawler.seed_feeders_scope import FeederResult, require_host, run_guarded, scope_and_dedup


# ORCHESTRATOR

async def navtree_feeder_workflow(seed_url: str) -> FeederResult:
    return await run_guarded(_collect_navtree, seed_url)


# FUNCTIONS

async def _collect_navtree(seed_url: str) -> FeederResult:
    seed_host = require_host(seed_url)
    async with httpx.AsyncClient() as client:
        raw_urls, tier, version_keys = await resolve_navigation_tree(client, seed_url)
    urls, dropped = scope_and_dedup(raw_urls, seed_host)
    return FeederResult(urls=urls, ok=True, source=f"navtree_{tier}",
                        version_keys=version_keys, dropped=dropped)
