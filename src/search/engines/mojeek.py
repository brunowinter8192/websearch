# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from urllib.parse import quote_plus

from src.search.browser import new_tab, kill_tab
from src.cdp_value import extract_value
from src.search.document_status import attach_document_status, start_document_status_capture, update_partial
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

name = "mojeek"

SEARCH_URL = "https://www.mojeek.com/search?q={}&safe=1"

MOJEEK_BUDGET_S = 4.5
NAV_TIMEOUT_S = 3.0
WAIT_INTERVAL = 0.2
PAGE_RESULT_COUNT = 10

_JS_POLL = """
var _w = document.querySelector('altcha-widget');
var _note = document.querySelector('#captcha-note');
var _state = null;
try { _state = (_w && typeof _w.getState === 'function') ? _w.getState() : null; } catch (e) { _state = null; }
return JSON.stringify({
    links: document.querySelectorAll('ul.results-standard > li > a.ob').length,
    challenge_widget: !!_w,
    verify_ready: !!_w && typeof _w.verify === 'function',
    challenge_state: _state,
    captcha_note: _note ? _note.textContent : null
});
"""

_JS_VERIFY = """
var _w = document.querySelector('altcha-widget');
if (!_w || typeof _w.verify !== 'function') return JSON.stringify({fired: false});
_w.verify();
return JSON.stringify({fired: true});
"""

_JS_PARSE = """
var _cs = document.querySelectorAll('ul.results-standard > li > a.ob');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _a = _cs[_i];
    var _li = _a.closest('li');
    var _h2a = _li ? _li.querySelector('h2 a') : null;
    var _ps = _li ? _li.querySelector('p.s') : null;
    if (!_a.href) continue;
    _out.push({url: _a.href, title: _h2a ? _h2a.textContent.trim() : '', snippet: _ps ? _ps.textContent.trim() : ''});
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var _w = document.querySelector('altcha-widget');
var _note = document.querySelector('#captcha-note');
var _state = null;
try { _state = (_w && typeof _w.getState === 'function') ? _w.getState() : null; } catch (e) { _state = null; }
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState,
    challenge_widget: !!_w,
    challenge_state: _state,
    captcha_note: _note ? _note.textContent : null
});
"""


# ORCHESTRATOR

async def search_with_reason(query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
    t0 = time.perf_counter()
    deadline = _budget_deadline()
    logger.info("Mojeek search: %s", query)
    tab = await new_tab()
    return await _search_and_close(tab, query, max_results, partial, t0, deadline)


# FUNCTIONS

def _budget_deadline() -> float:
    return time.monotonic() + MOJEEK_BUDGET_S


async def _search_and_close(tab, query: str, max_results: int, partial: dict | None, t0: float, deadline: float) -> tuple[list[SearchResult], str | None, dict | None]:
    try:
        return await _search_in_tab(tab, query, max_results, partial, t0, deadline)
    finally:
        await kill_tab(tab)


async def _search_in_tab(tab, query: str, max_results: int, partial: dict | None, t0: float, deadline: float) -> tuple[list[SearchResult], str | None, dict | None]:
    status_chain = await start_document_status_capture(tab)
    await tab.go_to(_build_url(query), timeout=NAV_TIMEOUT_S)
    trace = await _await_results(tab, deadline, _parse_target(max_results), status_chain, t0, partial)
    if not trace["ready"]:
        diag = await _diagnose(tab, trace)
        diag["containers_found"] = False
        logger.debug("Mojeek empty for: %s", query)
        return [], None, attach_document_status(diag, status_chain)
    results = await _parse_results(tab, max_results)
    if results:
        return results, None, attach_document_status({}, status_chain)
    diag = await _diagnose(tab, trace)
    diag["containers_found"] = True
    return results, None, attach_document_status(diag, status_chain)


def _build_url(query: str) -> str:
    return SEARCH_URL.format(quote_plus(query))


async def _await_results(tab, deadline: float, target: int, status_chain: list[int], t0: float, partial: dict | None) -> dict:
    trace = {"ready": False, "link_count": 0, "challenge_triggered": False, "poll_count": 0}
    previous = -1
    while time.monotonic() < deadline:
        facts = await _poll_facts(tab)
        trace["poll_count"] += 1
        count = facts.get("links", 0)
        trace["link_count"] = count
        update_partial(partial, status_chain, t0, {
            "containers_found": trace["ready"], "challenge_triggered": trace["challenge_triggered"],
        })
        if _is_ready_to_parse(count, previous, target):
            trace["ready"] = True
            return trace
        if _should_fire_verify(facts, trace["challenge_triggered"]):
            await _fire_verify(tab)
            trace["challenge_triggered"] = True
            logger.info("Mojeek ALTCHA challenge detected, verify() dispatched")
        previous = count
        await asyncio.sleep(WAIT_INTERVAL)
    return trace


async def _poll_facts(tab) -> dict:
    raw = await tab.execute_script(_JS_POLL)
    value = extract_value(raw)
    if not value:
        return {}
    return json.loads(value)


def _is_ready_to_parse(count: int, previous: int, target: int) -> bool:
    if count <= 0:
        return False
    if count >= target:
        return True
    return count == previous


def _should_fire_verify(facts: dict, already_triggered: bool) -> bool:
    if already_triggered:
        return False
    return bool(facts.get("challenge_widget")) and bool(facts.get("verify_ready"))


async def _fire_verify(tab) -> None:
    await tab.execute_script(_JS_VERIFY)


def _parse_target(max_results: int) -> int:
    return min(max_results, PAGE_RESULT_COUNT)


async def _diagnose(tab, trace: dict) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = extract_value(raw)
    diag = {
        "marker": None, "title": "", "url": "", "ready_state": "",
        "challenge_widget": False, "challenge_state": None, "captcha_note": None,
    }
    if val:
        diag.update(json.loads(val))
    diag["challenge_triggered"] = trace.get("challenge_triggered", False)
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
    for item in items[:max_results]:
        url = item.get("url", "")
        if not url:
            continue
        results.append(SearchResult(
            url=url, title=item.get("title", ""), snippet=item.get("snippet", ""),
            engine="mojeek", position=len(results) + 1,
        ))
    return results
