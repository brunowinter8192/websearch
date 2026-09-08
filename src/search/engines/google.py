# INFRASTRUCTURE
import asyncio
import json
import logging
from urllib.parse import quote_plus, urlparse, parse_qs

from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

from src.search.browser import new_tab, kill_tab
from src.search.document_status import attach_document_status, start_document_status_capture
from src.search.engines.base import BaseEngine
from src.search.rate_limiter import RateLimiter, _limiters
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.google.com/search?q={}&hl={}&num={}"
CONSENT_DOMAIN = "consent.google.com"
CAPTCHA_PATH = "/sorry/"
MAX_WAIT_CYCLES = 3
WAIT_INTERVAL = 0.2
SOCS_NAME = "SOCS"
SOCS_VALUE = "CAISHAgCEhJnd3NfMjAyNjA0MDctMCAgIBgEIAEaBgiA_fC8Bg"
SOCS_DOMAIN = ".google.com"

_JS_WAIT = "return document.querySelectorAll('div.MjjYud').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div.MjjYud');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = null;
    var _title = '';
    var _h3 = _c.querySelector('h3');
    var _lc = _c.querySelector('.LC20lb');
    if (_h3) {
        _title = _h3.textContent.trim();
        _a = _h3.closest('a[href^="http"]') || _h3.parentElement.querySelector('a[href^="http"]');
    }
    if (!_a && _lc) {
        if (!_title) { _title = _lc.textContent.trim(); }
        _a = _lc.closest('a[href^="http"]') || _lc.parentElement.querySelector('a[href^="http"]');
    }
    if (!_a) { _a = _c.querySelector('a[href^="http"]'); }
    if (!_title && _a) { _title = _a.textContent.trim(); }
    if (!_a || !_title) continue;
    var _snip = _c.querySelector('.wHYlTd') || _c.querySelector('.VwiC3b') || _c.querySelector('[data-sncf]') || _c.querySelector('.lEBKkf');
    _out.push({url: _a.href, title: _title, snippet: _snip ? _snip.textContent.trim() : ''});
}
return JSON.stringify(_out);
"""

_JS_CONSENT = """
var btn = document.querySelector('button[jsname="b3VHJd"]') ||
           document.querySelector('.lssxud') ||
           document.querySelector('form[action*="consent"] button[type="submit"]') ||
           document.querySelector('button[aria-label*="Accept"]');
if (btn) { btn.click(); return true; }
return false;
"""

_JS_DIAGNOSE = """
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState
});
"""

_limiters["google"] = RateLimiter(max_requests=4, window_seconds=60)


# ORCHESTRATOR

class GoogleEngine(BaseEngine):
    name = "google"

    async def search_with_reason(self, query: str, language: str = "en", max_results: int = 10) -> tuple[list[SearchResult], str | None, dict | None]:
        logger.info("Google search: %s", query)
        tab = await new_tab()
        await _inject_socs_cookie(tab)
        search_url = _build_url(query, language, max_results)
        try:
            status_chain = await start_document_status_capture(tab)
            await tab.go_to(search_url, timeout=3.0)
            current = await tab.current_url
            if CONSENT_DOMAIN in current or await _has_inline_consent(tab):
                await _handle_consent(tab)
                await tab.go_to(search_url, timeout=3.0)
                current = await tab.current_url
            if CAPTCHA_PATH in current:
                logger.warning("Google CAPTCHA detected for: %s", query)
                diag = await _diagnose(tab)
                diag["containers_found"] = None
                return [], None, attach_document_status(diag, status_chain)
            if not await _wait_for_results(tab):
                diag = await _diagnose(tab)
                diag["containers_found"] = False
                logger.debug("Google empty for: %s", query)
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
            logger.error("Google search failed: %s", e)
            return []


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


def _build_url(query: str, language: str, max_results: int) -> str:
    return SEARCH_URL.format(quote_plus(query), language, max_results)


async def _inject_socs_cookie(tab) -> None:
    await tab._execute_command(NetworkCommands.set_cookie(
        name=SOCS_NAME,
        value=SOCS_VALUE,
        domain=SOCS_DOMAIN,
        path="/",
        secure=True,
        same_site=CookieSameSite.LAX,
    ))


async def _has_inline_consent(tab) -> bool:
    js = "var body = document.body ? document.body.innerText : ''; return body.indexOf('Before you continue') !== -1 || body.indexOf('cookies and data') !== -1;"
    raw = await tab.execute_script(js)
    val = _extract_value(raw)
    return bool(val)


async def _handle_consent(tab) -> None:
    logger.info("Google consent page detected — clicking accept")
    await tab.execute_script(_JS_CONSENT)


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
    if "/url?" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        return qs.get("q", [href])[0]
    return href


async def _parse_results(tab, max_results: int) -> list[SearchResult]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    results = []
    for i, item in enumerate(items[:max_results]):
        url = _clean_url(item.get("url", ""))
        if not url:
            continue
        results.append(SearchResult(
            url=url,
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
            engine="google",
            position=i + 1,
        ))
    return results


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"title": "", "url": "", "ready_state": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    diag["marker"] = None
    return diag
