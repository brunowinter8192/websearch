# INFRASTRUCTURE
import httpx

from src.crawler.seed_feeders_robots import fetch_robots_txt, parse_robots_directives
from src.crawler.seed_feeders_scope import FeederResult, base_url, require_host, run_guarded, scope_and_dedup


# ORCHESTRATOR

async def robots_feeder_workflow(seed_url: str) -> FeederResult:
    return await run_guarded(_collect_robots, seed_url)


# FUNCTIONS

async def _collect_robots(seed_url: str) -> FeederResult:
    seed_host = require_host(seed_url)
    root_url = base_url(seed_url)
    async with httpx.AsyncClient() as client:
        text = await fetch_robots_txt(client, root_url)
    paths = parse_robots_directives(text, root_url)["paths"] if text else []
    urls, dropped = scope_and_dedup(paths, seed_host)
    return FeederResult(urls=urls, ok=True, source="robots", dropped=dropped)
