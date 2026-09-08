# INFRASTRUCTURE
import asyncio
import json
import logging
from urllib.parse import urlparse

from src.search.browser import new_tab, kill_tab
from src.search.document_status import attach_document_status, start_document_status_capture
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

SEARCH_URL = "https://yandex.com/search/?text={}"
BLOCK_URL_MARKERS = ("showcaptcha", "checkcaptcha", "/captcha")
SELF_DOMAIN_LABEL = "yandex"
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

_JS_WAIT = "return document.querySelectorAll('li.serp-item').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('li.serp-item');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a.OrganicTitle-Link');
    var _snip = _c.querySelector('.OrganicText .OrganicTextContentSpan') || _c.querySelector('.OrganicText');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _a.textContent.trim(),
        snippet: _snip ? _snip.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = ['captcha', 'confirm you are not a robot', 'unusual activity',
               'smartcaptcha', 'подтвердите, что запросы', 'подозрительн', 'ты робот'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
return JSON.stringify({marker: hit, url: window.location.href, ready_state: document.readyState, title: document.title});
"""

_limiters["yandex"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

class YandexEngine(BaseEngine):
    name = "yandex"

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None, dict | None]:
        logger.info("Yandex search: %s", query)
        tab = await new_tab()
        try:
            status_chain = await start_document_status_capture(tab)
            await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
            current_url = await tab.current_url
            if _is_block_url(current_url):
                logger.warning("Yandex CAPTCHA redirect detected for: %s", query)
                diag = await _diagnose(tab)
                diag["containers_found"] = None
                return [], None, attach_document_status(diag, status_chain)
            if not await _wait_for_results(tab):
                diag = await _diagnose(tab)
                diag["containers_found"] = False
                logger.debug("Yandex empty for: %s", query)
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
            logger.error("Yandex search failed: %s", e)
            return []


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


def _is_block_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(marker in lowered for marker in BLOCK_URL_MARKERS)


def _is_self_referential(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return SELF_DOMAIN_LABEL in host.split(".")


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
    for item in items:
        if len(results) >= max_results:
            break
        url = item.get("url", "")
        if not url or _is_self_referential(url):
            continue
        results.append(SearchResult(
            url=url, title=item.get("title", ""), snippet=item.get("snippet", ""),
            engine="yandex", position=len(results) + 1,
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
    diag = {"marker": None, "url": "", "ready_state": "", "title": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag
