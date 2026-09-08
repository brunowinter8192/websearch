# INFRASTRUCTURE
import asyncio
import json
import logging

from src.search.browser import new_tab, kill_tab
from src.search.document_status import attach_document_status, start_document_status_capture
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.brave.com/search?q={}"
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

_JS_WAIT = "return document.querySelectorAll('div[data-type=\"web\"]').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div[data-type="web"]');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a[href^="http"]');
    var _title = _c.querySelector('.search-snippet-title');
    var _snip = _c.querySelector('.snippet-content .content') || _c.querySelector('.generic-snippet .content');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _title ? _title.textContent.trim() : (_a.textContent || '').trim(),
        snippet: _snip ? _snip.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var powLink = document.querySelector('a[href*="pow-captcha"]');
var markers = ['captcha', 'schieberegler ziehen', 'drag the slider', 'proof of work', 'checking your browser'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
return JSON.stringify({
    marker: hit,
    pow_link: !!powLink,
    url: window.location.href,
    ready_state: document.readyState,
    title: document.title
});
"""

_limiters["brave"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

class BraveEngine(BaseEngine):
    name = "brave"

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None, dict | None]:
        logger.info("Brave search: %s", query)
        tab = await new_tab()
        try:
            status_chain = await start_document_status_capture(tab)
            await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
            await asyncio.sleep(1.5)
            diag = await _diagnose(tab)
            if diag["marker"] or diag["pow_link"]:
                logger.warning("Brave PoW/CAPTCHA detected for: %s", query)
                diag["containers_found"] = None
                return [], None, attach_document_status(diag, status_chain)
            if not await _wait_for_results(tab):
                diag["containers_found"] = False
                logger.debug("Brave empty for: %s", query)
                return [], None, attach_document_status(diag, status_chain)
            results = await _parse_results(tab, max_results)
            if results:
                return results, None, attach_document_status({}, status_chain)
            diag = await _diagnose(tab)
            diag["containers_found"] = True
            return results, None, attach_document_status(diag, status_chain)
        finally:
            await kill_tab(tab)

    async def search(self, query: str, language: str = "en", max_results: int = 10) -> list[SearchResult]:
        try:
            results, _, _ = await self.search_with_reason(query, language, max_results)
            return results
        except Exception as e:
            logger.error("Brave search failed: %s", e)
            return []


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


def _build_results(items: list[dict], max_results: int) -> list[SearchResult]:
    results = []
    for i, item in enumerate(items[:max_results]):
        url = item.get("url", "")
        if not url:
            continue
        results.append(SearchResult(
            url=url, title=item.get("title", ""), snippet=item.get("snippet", ""),
            engine="brave", position=i + 1,
        ))
    return results


async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return _build_results(items, max_results)


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "pow_link": False, "url": "", "ready_state": "", "title": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag
