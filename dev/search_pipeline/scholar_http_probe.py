#!/usr/bin/env python3

# INFRASTRUCTURE
import logging
from urllib.parse import quote_plus

import httpx
from lxml import html as lhtml

from src.search.rate_limiter import RateLimiter
from src.search.result import SearchResult
logger = logging.getLogger(__name__)

SEARCH_URL = "https://scholar.google.com/scholar?q={}&hl={}&num={}&as_sdt=2007&as_vis=0"

_BLOCK = "BLOCK"
_NO_RESULTS = "NO_RESULTS"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.7680.154 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

_COOKIES = {"CONSENT": "YES+"}

_TIMEOUT = 6.0


# ORCHESTRATOR

class ScholarHTTPProbe:
    name = "scholar_http"

    def __init__(self) -> None:
        self._limiter = RateLimiter(max_requests=20, window_seconds=60)

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None]:
        logger.info("ScholarHTTPProbe search: %s", query)
        url = _build_url(query, language, max_results)
        try:
            r = await _fetch(url)
        except httpx.TimeoutException as e:
            logger.warning("ScholarHTTPProbe timeout: %s", e)
            raise
        except httpx.HTTPError as e:
            logger.warning("ScholarHTTPProbe http error: %s", e)
            raise

        if r.status_code in (301, 302, 303, 307, 308):
            location = r.headers.get("Location", "")
            logger.warning("ScholarHTTPProbe redirect → %s", location)
            self._limiter.backoff()
            return [], _BLOCK

        r.raise_for_status()

        results, reason = _parse_response(r.text, max_results)
        if reason == _BLOCK:
            self._limiter.backoff()
        else:
            self._limiter.reset_backoff()
        return results, reason


# FUNCTIONS

def _build_url(query: str, language: str, max_results: int) -> str:
    return SEARCH_URL.format(quote_plus(query), language, max_results)


async def _fetch(url: str) -> httpx.Response:
    async with httpx.AsyncClient(
        headers=_HEADERS,
        cookies=_COOKIES,
        follow_redirects=False,
        timeout=_TIMEOUT,
    ) as client:
        return await client.get(url)


def _parse_response(body: str, max_results: int) -> tuple[list[SearchResult], str | None]:
    dom = lhtml.fromstring(body)
    if dom.xpath("//form[@id='gs_captcha_f']"):
        logger.warning("ScholarHTTPProbe inline captcha form detected")
        return [], _BLOCK
    results = _extract_results(dom, max_results)
    if not results:
        return [], _NO_RESULTS
    return results, None


def _extract_results(dom, max_results: int) -> list[SearchResult]:
    results = []
    for i, block in enumerate(dom.xpath("//div[@data-rp]")):
        if i >= max_results:
            break
        title_nodes = block.xpath(".//h3[1]//a")
        if not title_nodes:
            continue
        title = title_nodes[0].text_content().strip()
        url = title_nodes[0].get("href", "")
        if not url or not title:
            continue
        snippet_nodes = block.xpath(".//div[@class='gs_rs']")
        snippet = snippet_nodes[0].text_content().strip() if snippet_nodes else ""
        results.append(SearchResult(
            url=url,
            title=title,
            snippet=snippet,
            engine="scholar_http",
            position=i + 1,
        ))
    return results
