# INFRASTRUCTURE
import asyncio
import base64
import json
import logging
import re
import time
from urllib.parse import urlparse, parse_qs

from src.search.browser import new_tab, kill_tab
from src.cdp_value import extract_value
from src.search.document_status import attach_document_status, start_document_status_capture, update_partial
from src.search.selector_hits import collect_selector_hits
from src.search.result import SearchResult

logger = logging.getLogger(__name__)

name = "bing"

SEARCH_URL = "https://www.bing.com/search?q={}"
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

_JS_WAIT = "return document.querySelectorAll('li.b_algo').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('li.b_algo');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _h2a = _c.querySelector('h2 a');
    var _sel = {};
    var _cap = _c.querySelector('.b_caption p');
    if (_cap) { _sel.caption = 0; }
    else {
        _cap = _c.querySelector('.b_caption');
        if (_cap) { _sel.caption = 1; }
    }
    var _dt = _c.querySelector('span.news_dt');
    if (!_h2a || !_h2a.href) continue;
    _out.push({
        url: _h2a.href,
        title: _h2a.textContent.trim(),
        snippet: _cap ? _cap.textContent.trim() : '',
        date_raw: _dt ? _dt.textContent.trim() : '',
        sel: _sel
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = ['captcha', 'unusual traffic', 'verify you are human', 'are you a robot',
               'access denied', 'automated queries', 'ungewöhnlichen datenverkehr',
               'roboter', 'bestätigen sie, dass sie ein mensch'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
return JSON.stringify({marker: hit, url: window.location.href, ready_state: document.readyState, title: document.title});
"""

_DE_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DE_DATE_RE = re.compile(r'^(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})$')
_EN_DATE_RE = re.compile(r'^([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})$')


# ORCHESTRATOR

async def search_with_reason(query: str, language: str = "en", max_results: int = 10, partial: dict | None = None) -> tuple[list[SearchResult], str | None, dict | None]:
    t0 = time.perf_counter()
    logger.info("Bing search: %s", query)
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
    await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
    if not await _wait_for_results(tab, status_chain, t0, partial):
        diag = await _diagnose(tab)
        diag["containers_found"] = False
        logger.debug("Bing empty for: %s", query)
        return [], None, attach_document_status(diag, status_chain)
    results, selector_hits = await _parse_results(tab, max_results)
    if results:
        return results, None, attach_document_status({"selector_hits": selector_hits}, status_chain)
    diag = await _diagnose(tab)
    diag["containers_found"] = True
    return results, None, attach_document_status(diag, status_chain)


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
    diag = {"marker": None, "url": "", "ready_state": "", "title": ""}
    if val:
        diag.update(json.loads(val))
    return diag


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
            url=url, title=item.get("title", ""), snippet=item.get("snippet", ""),
            engine="bing", position=i + 1,
            date=_extract_date(item.get("date_raw", "")),
        ))
    return results


def _clean_url(href: str) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)
    u = qs.get("u", [None])[0]
    if not u:
        return href
    payload = u[2:] if len(u) > 2 else u
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")


def _extract_date(news_dt_text: str) -> str | None:
    text = (news_dt_text or "").strip()
    if not text:
        return None
    m = _DE_DATE_RE.match(text)
    if m:
        day, month_name, year = m.groups()
        month = _DE_MONTHS.get(month_name.lower())
        return f"{int(year):04d}-{month:02d}-{int(day):02d}" if month else None
    m = _EN_DATE_RE.match(text)
    if m:
        month_name, day, year = m.groups()
        month = _EN_MONTHS.get(month_name.lower())
        return f"{int(year):04d}-{month:02d}-{int(day):02d}" if month else None
    return None
