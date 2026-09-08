# INFRASTRUCTURE
import re
from urllib.parse import urljoin

import httpx

from src.crawler.seed_feeders_constants import HTTP_TIMEOUT_S, USER_AGENT

_DIRECTIVE_RE = re.compile(r'^\s*(allow|disallow|sitemap)\s*:\s*(.+?)\s*$', re.IGNORECASE)


# FUNCTIONS

async def fetch_robots_txt(client: httpx.AsyncClient, base_url: str) -> str | None:
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        response = await client.get(robots_url, timeout=HTTP_TIMEOUT_S,
                                    headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.text


def parse_robots_directives(text: str, base_url: str) -> dict:
    paths = []
    sitemaps = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        match = _DIRECTIVE_RE.match(line)
        if not match:
            continue
        directive, value = match.group(1).lower(), match.group(2).strip()
        if not value:
            continue
        if directive == "sitemap":
            sitemaps.append(urljoin(base_url, value))
        else:
            paths.append(urljoin(base_url, value))
    return {"paths": paths, "sitemaps": sitemaps}
