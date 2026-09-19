# INFRASTRUCTURE
import asyncio
import json
import logging
import time

from src.search.browser import new_tab, kill_tab
from src.search.document_status import attach_document_status, start_document_status_capture, update_partial
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.brave.com/search?q={}"
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3
POW_LINK_GRACE_CYCLES = 2

_JS_DEEP_BUTTONS = """
function _deepButtons(root) {
    var _direct = root.querySelectorAll('button, [role="button"]');
    var _out = [];
    for (var _i = 0; _i < _direct.length; _i++) { _out.push(_direct[_i]); }
    var _all = root.querySelectorAll('*');
    for (var _j = 0; _j < _all.length; _j++) {
        if (_all[_j].shadowRoot) { _out = _out.concat(_deepButtons(_all[_j].shadowRoot)); }
    }
    return _out;
}
var _CHALLENGE_BUTTON_TEXTS = ['verifizieren', 'verify', "i'm not a robot", 'i am not a robot'];
"""

_JS_POLL = _JS_DEEP_BUTTONS + """
var _btns = _deepButtons(document);
var _matched = false;
for (var _k = 0; _k < _btns.length && !_matched; _k++) {
    var _text = (_btns[_k].textContent || '').trim().toLowerCase();
    for (var _m = 0; _m < _CHALLENGE_BUTTON_TEXTS.length; _m++) {
        if (_text.indexOf(_CHALLENGE_BUTTON_TEXTS[_m]) !== -1) { _matched = true; break; }
    }
}
return JSON.stringify({
    count: document.querySelectorAll('div[data-type="web"]').length,
    pow_link: !!document.querySelector('a[href*="pow-captcha"]'),
    button_present: _btns.length > 0,
    button_matched: _matched
});
"""

_JS_CLICK_CHALLENGE = _JS_DEEP_BUTTONS + """
var _btns = _deepButtons(document);
for (var _k = 0; _k < _btns.length; _k++) {
    var _text = (_btns[_k].textContent || '').trim().toLowerCase();
    for (var _m = 0; _m < _CHALLENGE_BUTTON_TEXTS.length; _m++) {
        if (_text.indexOf(_CHALLENGE_BUTTON_TEXTS[_m]) !== -1) {
            try {
                _btns[_k].click();
                return JSON.stringify({clicked: true});
            } catch (e) {
                return JSON.stringify({clicked: false});
            }
        }
    }
}
return JSON.stringify({clicked: false});
"""

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

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
        t0 = time.perf_counter()
        logger.info("Brave search: %s", query)
        tab = await new_tab()
        try:
            status_chain = await start_document_status_capture(tab)
            await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
            found, challenge_triggered, button_present = await _wait_for_results(tab, status_chain, t0, partial)
            if not found:
                diag = await _diagnose(tab)
                diag["containers_found"] = False
                diag["challenge_triggered"] = challenge_triggered
                diag["button_present"] = button_present
                _log_empty_result(query, diag)
                return [], None, attach_document_status(diag, status_chain)
            results = await _parse_results(tab, max_results)
            if results:
                diag = {"challenge_triggered": challenge_triggered}
                return results, None, attach_document_status(diag, status_chain)
            diag = await _diagnose(tab)
            diag["containers_found"] = True
            diag["challenge_triggered"] = challenge_triggered
            diag["button_present"] = button_present
            return results, None, attach_document_status(diag, status_chain)
        finally:
            await kill_tab(tab)


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def _wait_for_results(tab, status_chain: list[int], t0: float, partial: dict | None) -> tuple[bool, bool, bool]:
    challenge_triggered = False
    button_present = False
    pow_link_idle_cycles = 0
    for _ in range(MAX_WAIT_CYCLES):
        state = await _poll_state(tab)
        if state["button_present"]:
            button_present = True
        update_partial(partial, status_chain, t0, {
            "containers_found": False,
            "pow_link": state["pow_link"],
            "button_present": button_present,
            "challenge_triggered": challenge_triggered,
        })
        if state["count"] > 0:
            return True, challenge_triggered, button_present
        if state["button_matched"] and not challenge_triggered:
            challenge_triggered = await _click_challenge_button(tab)
        elif state["pow_link"] and not challenge_triggered and not button_present:
            pow_link_idle_cycles += 1
            if pow_link_idle_cycles >= POW_LINK_GRACE_CYCLES:
                return False, challenge_triggered, button_present
        await asyncio.sleep(WAIT_INTERVAL)
    return False, challenge_triggered, button_present


async def _poll_state(tab) -> dict:
    raw = await tab.execute_script(_JS_POLL)
    val = _extract_value(raw)
    state = {"count": 0, "pow_link": False, "button_present": False, "button_matched": False}
    if val:
        try:
            state.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return state


async def _click_challenge_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_CHALLENGE)
    val = _extract_value(raw)
    if not val:
        return False
    try:
        return bool(json.loads(val).get("clicked"))
    except (json.JSONDecodeError, TypeError):
        return False


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


def _log_empty_result(query: str, diag: dict) -> None:
    if diag["button_present"] and not diag["challenge_triggered"]:
        logger.warning("Brave challenge candidate seen but not clicked for: %s", query)
    elif diag["challenge_triggered"]:
        logger.warning("Brave challenge attempted but unresolved for: %s", query)
    elif diag["marker"] or diag["pow_link"]:
        logger.warning("Brave PoW/CAPTCHA detected for: %s", query)
    else:
        logger.debug("Brave empty for: %s", query)


async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
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
            engine="brave", position=i + 1,
        ))
    return results
