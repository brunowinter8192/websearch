# INFRASTRUCTURE
import asyncio
import json
import logging
import re
from urllib.parse import quote_plus, urlparse, parse_qs

from src.search.browser import new_tab, kill_tab
from src.search.document_status import attach_document_status, start_document_status_capture
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

SEARCH_URL = "https://html.duckduckgo.com/html/?q={}&kl=wt-wt"
CAPTCHA_SELECTOR = "form#challenge-form"
MAX_WAIT_CYCLES = 3
WAIT_INTERVAL = 0.2

_JS_WAIT = "return document.querySelectorAll('#links > div.web-result').length"

_JS_DIAGNOSE = f"""
return JSON.stringify({{
    challenge_form_count: document.querySelectorAll('{CAPTCHA_SELECTOR}').length,
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState
}});
"""

_JS_PARSE = """
var _cs = document.querySelectorAll('#links > div.web-result');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('h2 a');
    var _snip = _c.querySelector('a.result__snippet');
    var _extras = _c.querySelector('.result__extras__url');
    var _dateSpan = _extras ? _extras.querySelector('span:not(.result__icon)') : null;
    if (!_a) continue;
    _out.push({
        href: _a.href,
        title: _a.textContent.trim(),
        snippet: _snip ? _snip.textContent.trim() : '',
        date_raw: _dateSpan ? _dateSpan.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_limiters["duckduckgo"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

class DuckDuckGoEngine(BaseEngine):
    name = "duckduckgo"

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None, dict | None]:
        logger.info("DuckDuckGo search: %s", query)
        tab = await new_tab()
        search_url = _build_url(query)
        try:
            status_chain = await start_document_status_capture(tab)
            await tab.go_to(search_url, timeout=3.0)
            diag = await _diagnose(tab)
            if diag["challenge_form"]:
                logger.warning("DuckDuckGo CAPTCHA detected for: %s", query)
                diag["containers_found"] = None
                return [], None, attach_document_status(diag, status_chain)
            if not await _wait_for_results(tab):
                diag = await _diagnose(tab)
                diag["containers_found"] = False
                logger.debug("DuckDuckGo empty for: %s", query)
                return [], None, attach_document_status(diag, status_chain)
            results = await _parse_results(tab, max_results)
            if results:
                return results, None, attach_document_status({}, status_chain)
            diag = await _diagnose(tab)
            diag["containers_found"] = True
            return results, None, attach_document_status(diag, status_chain)
        finally:
            await kill_tab(tab)


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


def _build_url(query: str) -> str:
    return SEARCH_URL.format(quote_plus(query))


async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


def _clean_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    uddg = qs.get("uddg", [None])[0]
    if uddg:
        return uddg
    return href


async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    items = json.loads(value)
    results = []
    for i, item in enumerate(items[:max_results]):
        url = _clean_url(item.get("href", ""))
        if not url:
            continue
        results.append(SearchResult(
            url=url,
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            engine="duckduckgo",
            position=i + 1,
            date=_extract_date(item.get("date_raw", "")),
        ))
    return results


def _extract_date(date_raw: str) -> str | None:
    text = (date_raw or "").replace("\xa0", " ").strip()
    date_part = text[:10]
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
        return date_part
    return None


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    parsed = {"challenge_form_count": 0, "title": "", "url": "", "ready_state": ""}
    if val:
        try:
            parsed.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "marker": None,
        "challenge_form": bool(parsed.get("challenge_form_count", 0)),
        "title": parsed["title"],
        "url": parsed["url"],
        "ready_state": parsed["ready_state"],
    }
