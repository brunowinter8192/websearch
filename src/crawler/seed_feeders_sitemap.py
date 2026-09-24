# INFRASTRUCTURE
import asyncio
import gzip
from xml.etree import ElementTree

import httpx

from src.crawler.seed_feeders_constants import ABSENT_STATUSES, HTTP_TIMEOUT_S, USER_AGENT, SITEMAP_FETCH_CONCURRENCY


# FUNCTIONS

async def fetch_sitemap(client: httpx.AsyncClient, url: str) -> bytes | None:
    response = await client.get(url, timeout=HTTP_TIMEOUT_S,
                                headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    if response.status_code in ABSENT_STATUSES:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"unexpected status {response.status_code} for {url}")
    content = response.content
    if url.endswith(".gz"):
        content = gzip.decompress(content)
    return content


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(parent, local_name: str) -> str | None:
    for child in parent:
        if _local_name(child.tag) == local_name:
            return (child.text or "").strip()
    return None


def parse_sitemap_xml(content: bytes) -> tuple:
    root = ElementTree.fromstring(content)
    root_tag = _local_name(root.tag)
    if root_tag == "sitemapindex":
        locs = [_child_text(entry, "loc") for entry in root]
        return ("index", [loc for loc in locs if loc])
    if root_tag == "urlset":
        locs = [_child_text(entry, "loc") for entry in root]
        return ("urlset", [loc for loc in locs if loc])
    return ("unknown", [])


async def resolve_sitemap_urls(client: httpx.AsyncClient, sitemap_urls: list, seen: set | None = None) -> list:
    seen = seen if seen is not None else set()
    semaphore = asyncio.Semaphore(SITEMAP_FETCH_CONCURRENCY)
    loc_urls = []

    async def _resolve_one(url: str) -> None:
        if url in seen:
            return
        seen.add(url)
        async with semaphore:
            content = await fetch_sitemap(client, url)
        if content is None:
            return
        kind, entries = parse_sitemap_xml(content)
        if kind == "urlset":
            loc_urls.extend(entries)
        elif kind == "index":
            await asyncio.gather(*[_resolve_one(sub) for sub in entries])

    await asyncio.gather(*[_resolve_one(u) for u in sitemap_urls])
    return loc_urls
