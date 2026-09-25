# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from urllib.parse import quote_plus, urlparse, parse_qs

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException, Timeout
from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

from src.search.browser import new_tab, kill_tab
from src.cdp_value import extract_value
from src.search.document_status import attach_document_status, start_document_status_capture, update_partial
from src.search.selector_hits import collect_selector_hits
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

name = "google"

SEARCH_URL = "https://www.google.com/search?q={}&hl={}&num={}"
CAPTCHA_PATH = "/sorry/"
MAX_WAIT_CYCLES = 3
WAIT_INTERVAL = 0.2
SOCS_NAME = "SOCS"
SOCS_VALUE = "CAISHAgCEhJnd3NfMjAyNjA0MDctMCAgIBgEIAEaBgiA_fC8Bg"
SOCS_DOMAIN = ".google.com"
GOTO_RESOLVE_TIMEOUT_S = 1.5

_JS_WAIT = "return document.querySelectorAll('div.MjjYud').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div.MjjYud');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = null;
    var _sel = {};
    var _title = '';
    var _h3 = _c.querySelector('h3');
    var _lc = _c.querySelector('.LC20lb');
    if (_h3) {
        _title = _h3.textContent.trim();
        _a = _h3.closest('a[href^="/goto?url="]');
        if (_a) { _sel.anchor = 0; }
        else {
            _a = _h3.parentElement.querySelector('a[href^="/goto?url="]');
            if (_a) { _sel.anchor = 1; }
        }
    }
    if (!_a && _lc) {
        if (!_title) { _title = _lc.textContent.trim(); }
        _a = _lc.closest('a[href^="/goto?url="]');
        if (_a) { _sel.anchor = 2; }
        else {
            _a = _lc.parentElement.querySelector('a[href^="/goto?url="]');
            if (_a) { _sel.anchor = 3; }
        }
    }
    if (!_a) {
        _a = _c.querySelector('a[href^="/goto?url="]');
        if (_a) { _sel.anchor = 4; }
    }
    if (!_title && _a) { _title = _a.textContent.trim(); }
    if (!_a || !_title) continue;
    var _snip = _c.querySelector('.VwiC3b');
    if (_snip) { _sel.snippet = 0; }
    else {
        _snip = _c.querySelector('[data-sncf]');
        if (_snip) { _sel.snippet = 1; }
        else {
            _snip = _c.querySelector('.lEBKkf');
            if (_snip) { _sel.snippet = 2; }
        }
    }
    var _date = null;
    var _snipText = '';
    if (_snip) {
        var _dateEl = _snip.querySelector('.YrbPuc');
        if (_dateEl) {
            _date = _dateEl.textContent.replace(/[\\s\\u2014-]+$/, '').trim();
            _snipText = _snip.textContent.replace(_dateEl.textContent, '').trim();
        } else {
            _snipText = _snip.textContent.trim();
        }
    }
    _out.push({url: _a.href, title: _title, snippet: _snipText, date: _date, sel: _sel});
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState
});
"""


# ORCHESTRATOR

async def search_with_reason(query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
    t0 = time.perf_counter()
    logger.info("Google search: %s", query)
    tab = await new_tab()
    await _inject_socs_cookie(tab)
    search_url = _build_url(query, language, max_results)
    return await _search_and_close(tab, query, max_results, partial, t0, search_url)


# FUNCTIONS

async def _search_and_close(tab, query: str, max_results: int, partial: dict | None, t0: float, search_url: str) -> tuple[list[SearchResult], str | None, dict | None]:
    try:
        return await _search_in_tab(tab, query, max_results, partial, t0, search_url)
    finally:
        await kill_tab(tab)


async def _search_in_tab(tab, query: str, max_results: int, partial: dict | None, t0: float, search_url: str) -> tuple[list[SearchResult], str | None, dict | None]:
    status_chain = await start_document_status_capture(tab)
    await tab.go_to(search_url, timeout=3.0)
    current = await tab.current_url
    if CAPTCHA_PATH in current:
        logger.warning("Google CAPTCHA detected for: %s", query)
        diag = await _diagnose(tab)
        diag["containers_found"] = None
        return [], None, attach_document_status(diag, status_chain)
    if not await _wait_for_results(tab, status_chain, t0, partial):
        diag = await _diagnose(tab)
        diag["containers_found"] = False
        logger.debug("Google empty for: %s", query)
        return [], None, attach_document_status(diag, status_chain)
    results, selector_hits = await _parse_results(tab, max_results)
    results, resolution = await _resolve_urls(results)
    _log_drops(resolution)
    if results:
        return results, None, attach_document_status({"goto_resolution": resolution, "selector_hits": selector_hits}, status_chain)
    diag = await _diagnose(tab)
    diag["containers_found"] = True
    diag["goto_resolution"] = resolution
    return results, None, attach_document_status(diag, status_chain)


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


async def _wait_for_results(tab, status_chain: list[int], t0: float, partial: dict | None) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = extract_value(raw)
        update_partial(partial, status_chain, t0, {"containers_found": False})
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


async def _parse_results(tab, max_results: int) -> tuple[list[SearchResult], dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = extract_value(raw)
    if not value:
        return [], {}
    items = json.loads(value)
    return _build_results(items, max_results), collect_selector_hits(items[:max_results])


def _build_results(items: list[dict], max_results: int) -> list[SearchResult]:
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
            date=item.get("date"),
        ))
    return results


def _clean_url(href: str) -> str:
    if not href:
        return ""
    if "/url?" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        return qs.get("q", [href])[0]
    return href


async def _resolve_urls(results: list[SearchResult]) -> tuple[list[SearchResult], dict]:
    async with AsyncSession(impersonate="chrome") as session:
        outcomes = await asyncio.gather(*[_resolve_one(session, r) for r in results])
    reasons = [reason for _, reason in outcomes if reason]
    deduped, duplicates = _dedupe_resolved([r for r, _ in outcomes if r is not None])
    reasons.extend(["duplicate_destination"] * duplicates)
    return deduped, _build_resolution_stats(len(results), len(deduped), reasons)


def _dedupe_resolved(resolved: list[SearchResult]) -> tuple[list[SearchResult], int]:
    seen: set[str] = set()
    deduped = []
    for r in resolved:
        if r.url in seen:
            continue
        seen.add(r.url)
        deduped.append(r)
    for i, r in enumerate(deduped):
        r.position = i + 1
    return deduped, len(resolved) - len(deduped)


def _build_resolution_stats(found: int, resolved: int, reasons: list[str]) -> dict:
    counts: dict[str, int] = {}
    for reason in reasons:
        counts[reason] = counts.get(reason, 0) + 1
    return {"found": found, "resolved": resolved, "dropped": found - resolved, "reasons": counts}


def _log_drops(resolution: dict) -> None:
    if not resolution["dropped"]:
        return
    logger.warning(
        "Google goto resolution dropped %d of %d results: %s",
        resolution["dropped"], resolution["found"], resolution["reasons"],
    )


async def _resolve_one(session: AsyncSession, result: SearchResult) -> tuple[SearchResult | None, str | None]:
    try:
        resp = await session.get(
            result.url, allow_redirects=False, timeout=GOTO_RESOLVE_TIMEOUT_S,
        )
    except Timeout as e:
        logger.debug("Google goto resolution timed out for %s: %s", result.url, e)
        return None, "timeout"
    except RequestException as e:
        logger.debug("Google goto resolution failed for %s: %s", result.url, e)
        return None, "request_error"
    if resp.status_code != 302:
        return None, f"non_302_{resp.status_code}"
    location = resp.headers.get("location")
    if not location:
        return None, "no_location"
    if not _is_absolute_http_url(location):
        return None, "relative_location"
    return SearchResult(
        url=location, title=result.title, snippet=result.snippet,
        engine="google", position=result.position, date=result.date,
    ), None


def _is_absolute_http_url(location: str) -> bool:
    parsed = urlparse(location)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = extract_value(raw)
    diag = {"title": "", "url": "", "ready_state": ""}
    if val:
        diag.update(json.loads(val))
    diag["marker"] = None
    return diag
