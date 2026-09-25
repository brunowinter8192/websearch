# INFRASTRUCTURE
import asyncio
import json
import logging
import time

from src.search.browser import new_tab, kill_tab
from src.cdp_value import extract_value
from src.search.document_status import attach_document_status, start_document_status_capture, update_partial
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

name = "startpage"

HOME_URL = "https://www.startpage.com/"
EXPECTED_RESULT_PATH = "/sp/search"
MAX_WAIT_CYCLES = 25
WAIT_INTERVAL = 0.3

_JS_WAIT = "return document.querySelectorAll('div.result').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div.result');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a.result-title');
    var _h2 = _c.querySelector('h2.wgl-title');
    var _desc = _c.querySelector('p.description');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _h2 ? _h2.textContent.trim() : (_a.textContent || '').trim(),
        snippet: _desc ? _desc.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = ['captcha', 'unusual traffic', 'verify you are human', 'are you a robot',
               'access denied', 'checking your browser', 'temporarily blocked',
               'too many requests', 'rate limit exceeded', 'automated queries'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
var iframeChallenge = document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="challenge"]');
return JSON.stringify({
    marker: hit,
    iframe_challenge: !!iframeChallenge,
    url: window.location.href,
    ready_state: document.readyState,
    title: document.title
});
"""


# ORCHESTRATOR

async def search_with_reason(query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
    t0 = time.perf_counter()
    logger.info("Startpage search: %s", query)
    tab = await new_tab()
    return await _search_and_close(tab, query, max_results, partial, t0)


# FUNCTIONS

async def _search_and_close(tab, query: str, max_results: int, partial: dict | None, t0: float) -> tuple[list[SearchResult], str | None, dict | None]:
    try:
        return await _search_in_tab(tab, query, max_results, partial, t0)
    finally:
        await kill_tab(tab)


async def _search_in_tab(tab, query: str, max_results: int, partial: dict | None, t0: float) -> tuple[list[SearchResult], str | None, dict | None]:
    status_chain = await start_document_status_capture(tab)
    await _submit_search(tab, query)
    if not await _wait_for_results(tab, status_chain, t0, partial):
        diag = await _diagnose(tab)
        diag["containers_found"] = False
        logger.debug("Startpage empty for: %s", query)
        return [], None, attach_document_status(diag, status_chain)
    results = await _parse_results(tab, max_results)
    if results:
        return results, None, attach_document_status({}, status_chain)
    diag = await _diagnose(tab)
    diag["containers_found"] = True
    return results, None, attach_document_status(diag, status_chain)


async def _submit_search(tab, query: str) -> None:
    await tab.go_to(HOME_URL, timeout=10.0)
    await asyncio.sleep(1.5)
    await tab.execute_script(_js_set_query(query))
    await asyncio.sleep(0.3)
    await tab.execute_script("document.querySelector('button.search-btn').click();")


def _js_set_query(query: str) -> str:
    return f"""
    var inp = document.querySelector('#q');
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(inp, {json.dumps(query)});
    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
    """


async def _wait_for_results(tab, status_chain: list[int], t0: float, partial: dict | None) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = extract_value(raw)
        update_partial(partial, status_chain, t0, {"containers_found": False})
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = extract_value(raw)
    diag = {"marker": None, "iframe_challenge": False, "url": "", "ready_state": "", "title": ""}
    if val:
        diag.update(json.loads(val))
    return diag


async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = extract_value(raw)
    if not value:
        return []
    items = json.loads(value)
    return _build_results(items, max_results)


def _build_results(items: list[dict], max_results: int) -> list[SearchResult]:
    results = []
    for i, item in enumerate(items[:max_results]):
        url = item.get("url", "")
        if not url:
            continue
        results.append(SearchResult(
            url=url, title=item.get("title", ""), snippet=item.get("snippet", ""),
            engine="startpage", position=i + 1,
        ))
    return results
