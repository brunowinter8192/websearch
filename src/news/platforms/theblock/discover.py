# INFRASTRUCTURE
import logging
import re
import sys
from datetime import datetime, timezone

import httpx

from src.config import XML_MARKERS
from src.news.engine.proxy_pool.fetch import fetch_url
from src.news.engine.proxy_pool.pool_loaders import load_backfill_pool
from src.news.platforms.theblock.config import SITEMAP_INDEX, DIRECT_TIMEOUT

logger = logging.getLogger(__name__)

_INDEX_LOC_RE = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_URL_BLOCK_RE = re.compile(rb"<url>(.*?)</url>", re.DOTALL)
_LOC_RE       = re.compile(rb"<loc>(https?://[^<]+)</loc>")
_MOD_RE       = re.compile(rb"<lastmod>([^<]+)</lastmod>")
_NUM_RE       = re.compile(r"_(\d+)\.xml$")


# ORCHESTRATOR

async def discover(timeframe: str = "delta", acquire_logger=None) -> list[dict]:
    pool_cache: list = []

    index_content = _fetch_xml(SITEMAP_INDEX, pool_cache, acquire_logger)
    if index_content is None:
        raise RuntimeError("theblock sitemap index fetch failed (direct + proxy exhausted)")
    post_subs = _parse_post_sub_urls(index_content)
    if not post_subs:
        raise RuntimeError("No post_type_post sub-sitemaps found in theblock sitemap index")
    print(f"[theblock] {len(post_subs)} post_type_post sub-sitemaps", file=sys.stderr)

    target_subs = _resolve_target_subs(timeframe, post_subs)
    print(f"[theblock] Fetching {len(target_subs)} sub-sitemap(s) …", file=sys.stderr)

    entries = []
    for sub_url in target_subs:
        content = _fetch_xml(sub_url, pool_cache, acquire_logger)
        if content is None:
            raise RuntimeError(f"theblock sub-sitemap fetch failed (direct + proxy exhausted): {sub_url}")
        for url, lastmod in _parse_url_blocks(content):
            entries.append({"url": url, "lastmod": lastmod.isoformat()})

    print(f"[theblock] discover → {len(entries)} entries (timeframe={timeframe!r})", file=sys.stderr)
    return entries


# FUNCTIONS

def _resolve_target_subs(timeframe: str, post_subs: list[str]) -> list[str]:
    if timeframe == "full":
        return post_subs
    if timeframe == "delta":
        return _top_n_subs(post_subs, 2)
    if timeframe.startswith("sub:"):
        spec = timeframe[4:]
        if "-" in spec:
            parts = spec.split("-", 1)
            try:
                a, b = int(parts[0]), int(parts[1])
            except ValueError:
                raise RuntimeError(
                    f"Invalid sub:A-B timeframe: {timeframe!r} — expected two integers, e.g. 'sub:24-27'"
                )
            if a > b:
                raise RuntimeError(
                    f"Invalid sub:A-B timeframe: {timeframe!r} — A ({a}) must be ≤ B ({b})"
                )
            return _subs_in_range(post_subs, a, b)
        try:
            n = int(spec)
        except ValueError:
            raise RuntimeError(f"Invalid sub:N timeframe: {timeframe!r} — expected 'sub:<integer>'")
        return [_sub_by_index(post_subs, n)]
    raise RuntimeError(
        f"Unknown timeframe: {timeframe!r} — expected 'full', 'delta', 'sub:N', or 'sub:A-B'"
    )


def _fetch_xml(url: str, pool_cache: list, acquire_logger=None) -> bytes | None:
    content = _fetch_direct(url)
    if content is not None:
        logger.info("theblock sitemap served direct: %s", url)
        return content
    if not pool_cache:
        print("[theblock] Loading proxy pool for sitemap fallback …", file=sys.stderr)
        pool, _ = load_backfill_pool()
        pool_cache.extend(pool)
    for proto, hp in pool_cache:
        status, content, reason = fetch_url(proto, hp, url, "xml")
        if acquire_logger is not None:
            acquire_logger.record_attempt(proto, hp, url, status == "ok", reason)
        if status == "ok":
            logger.info("theblock sitemap served via proxy %s://%s: %s", proto, hp.split("@")[-1], url)
            return content
    return None


def _fetch_direct(url: str) -> bytes | None:
    r = httpx.get(url, timeout=DIRECT_TIMEOUT, follow_redirects=True)
    head = r.content[:500]
    if r.status_code == 200 and any(m in head for m in XML_MARKERS):
        return r.content
    logger.warning("theblock direct sitemap fetch failed: status=%s xml_marker=%s url=%s",
                   r.status_code, any(m in head for m in XML_MARKERS), url)
    return None


def _parse_post_sub_urls(content: bytes) -> list[str]:
    return [
        m.group(1).decode().strip()
        for m in _INDEX_LOC_RE.finditer(content)
        if b"post_type_post" in m.group(1)
    ]


def _top_n_subs(urls: list[str], n: int) -> list[str]:
    def _num(u: str) -> int:
        m = _NUM_RE.search(u)
        return int(m.group(1)) if m else -1
    return sorted(urls, key=_num, reverse=True)[:n]


def _sub_by_index(urls: list[str], n: int) -> str:
    for u in urls:
        m = _NUM_RE.search(u)
        if m and int(m.group(1)) == n:
            return u
    raise RuntimeError(f"sub:{n} not found among {len(urls)} post_type_post sub-sitemaps")


def _subs_in_range(urls: list[str], a: int, b: int) -> list[str]:
    def _num(u: str) -> int:
        m = _NUM_RE.search(u)
        return int(m.group(1)) if m else -1
    matched = [u for u in urls if a <= _num(u) <= b]
    if not matched:
        raise RuntimeError(
            f"sub:{a}-{b} matched no post_type_post sub-sitemaps (range [{a}, {b}] not found)"
        )
    return sorted(matched, key=_num, reverse=True)


def _parse_url_blocks(content: bytes) -> list[tuple[str, datetime]]:
    results = []
    for block in _URL_BLOCK_RE.finditer(content):
        body  = block.group(1)
        loc_m = _LOC_RE.search(body)
        mod_m = _MOD_RE.search(body)
        if not loc_m or not mod_m:
            continue
        url     = loc_m.group(1).decode().strip()
        mod_raw = mod_m.group(1).decode().strip().replace("Z", "+00:00")
        mod = datetime.fromisoformat(mod_raw)
        if mod.tzinfo is None:
            mod = mod.replace(tzinfo=timezone.utc)
        results.append((url, mod))
    return results
