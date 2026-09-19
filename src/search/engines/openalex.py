# INFRASTRUCTURE
import html
import logging
import os

import httpx

from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

API_URL = "https://api.openalex.org/works"
MAX_PER_PAGE = 100

_limiters["openalex"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

class OpenAlexEngine(BaseEngine):
    name = "openalex"

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
        logger.info("OpenAlex search: %s", query)
        status_code, works = await _fetch_results(query, max_results)
        if status_code == 429:
            logger.warning("OpenAlex rate limited: 429")
            return [], None, {"http_status": status_code}
        if works is None:
            return [], None, {"http_status": status_code}
        results = _parse_results(works)
        if results:
            return results, None, None
        return results, None, {"http_status": status_code}


# FUNCTIONS

def _deep_unescape(s: str) -> str:
    while True:
        new = html.unescape(s)
        if new == s:
            return new
        s = new


async def _fetch_results(query: str, max_results: int) -> tuple[int, list[dict] | None]:
    params: dict = {"search": query, "per_page": min(max_results, MAX_PER_PAGE)}
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    async with httpx.AsyncClient(timeout=3.6) as client:
        response = await client.get(API_URL, params=params)
    if response.status_code in (429, 403):
        logger.warning("OpenAlex rate limited: %d", response.status_code)
        return response.status_code, None
    response.raise_for_status()
    return response.status_code, response.json().get("results", [])


def _parse_results(works: list[dict]) -> list[SearchResult]:
    results = []
    for i, work in enumerate(works):
        title = _deep_unescape(work.get("title") or "")
        if not title:
            continue
        url = _pick_url(work)
        if not url:
            continue
        snippet = _reconstruct_abstract(work.get("abstract_inverted_index"))
        cited = work.get("cited_by_count", 0)
        if cited > 50:
            snippet = f"{snippet} (Cited {cited}×)"
        results.append(SearchResult(
            url=url,
            title=title,
            snippet=snippet,
            engine="openalex",
            position=i + 1,
            date=_extract_date(work),
            pdf_url=_extract_pdf_url(work),
        ))
    return results


def _extract_pdf_url(work: dict) -> str | None:
    location = work.get("best_oa_location")
    if not location:
        return None
    return location.get("pdf_url")


def _extract_date(work: dict) -> str | None:
    pub_date = work.get("publication_date")
    if pub_date:
        return pub_date
    pub_year = work.get("publication_year")
    if pub_year:
        return str(pub_year)
    return None


def _reconstruct_abstract(aii: dict | None) -> str:
    if not aii:
        return ""
    pos_word: dict[int, str] = {}
    for word, positions in aii.items():
        for pos in positions:
            pos_word[pos] = word
    return html.unescape(" ".join(html.unescape(pos_word[p]) for p in sorted(pos_word)))


def _pick_url(work: dict) -> str:
    ids = work.get("ids") or {}
    arxiv = ids.get("arxiv")
    if arxiv:
        return arxiv
    doi = work.get("doi")
    if doi:
        return doi
    return work.get("id", "")
