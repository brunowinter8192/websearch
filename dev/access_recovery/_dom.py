# INFRASTRUCTURE
import asyncio
import json
import sys
from urllib.parse import urlparse, parse_qs

from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

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

_JS_INLINE_CONSENT_CHECK = (
    "var body = document.body ? document.body.innerText : ''; "
    "return body.indexOf('Before you continue') !== -1 || body.indexOf('cookies and data') !== -1;"
)

_JS_DIAGNOSTIC = """
var _cs = document.querySelectorAll('div.MjjYud');
var _samples = [];
var _n = Math.min(_cs.length, 5);
for (var _i = 0; _i < _n; _i++) {
    var _c = _cs[_i];
    var _h3 = _c.querySelector('h3');
    var _lc = _c.querySelector('.LC20lb');
    var _httpAnchors = _c.querySelectorAll('a[href^="http"]');
    var _allAnchors = _c.querySelectorAll('a');
    var _childTags = [];
    for (var _j = 0; _j < _c.children.length; _j++) {
        var _el = _c.children[_j];
        var _cls = _el.className && typeof _el.className === 'string' ? '.' + _el.className.trim().split(/\\s+/).join('.') : '';
        _childTags.push(_el.tagName + _cls);
    }
    _samples.push({
        index: _i,
        has_h3: !!_h3,
        has_lc20lb: !!_lc,
        http_anchor_count: _httpAnchors.length,
        total_anchor_count: _allAnchors.length,
        child_tags: _childTags.join(' | '),
        outer_html_sample: _c.outerHTML.slice(0, 800)
    });
}
return JSON.stringify({
    container_count: _cs.length,
    page_wide_h3_count: document.querySelectorAll('h3').length,
    page_wide_http_anchor_count: document.querySelectorAll('a[href^="http"]').length,
    samples: _samples
});
"""

_JS_DIAGNOSE = """
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState
});
"""


# FUNCTIONS

async def inject_socs_cookie(tab) -> None:
    await tab._execute_command(NetworkCommands.set_cookie(
        name=SOCS_NAME, value=SOCS_VALUE, domain=SOCS_DOMAIN, path="/",
        secure=True, same_site=CookieSameSite.LAX,
    ))


async def has_inline_consent(tab) -> bool:
    raw = await tab.execute_script(_JS_INLINE_CONSENT_CHECK)
    return bool(extract_value(raw))


async def accept_consent(tab) -> None:
    await tab.execute_script(_JS_CONSENT)


async def wait_for_results(tab) -> tuple[bool, int]:
    count = 0
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        val = extract_value(raw)
        count = int(val) if val else 0
        if count > 0:
            return True, count
        await asyncio.sleep(WAIT_INTERVAL)
    return False, count


async def parse_results(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = extract_value(raw)
    if not value:
        return []
    items = json.loads(value)
    out = []
    for item in items:
        url = _clean_url(item.get("url", ""))
        if not url:
            continue
        out.append({"url": url, "title": item.get("title", ""), "snippet": item.get("snippet", "")})
    return out


async def diagnostic_scan(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSTIC)
    val = extract_value(raw)
    if not val:
        return {}
    return json.loads(val)


async def diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = extract_value(raw)
    diag = {"title": "", "url": "", "ready_state": ""}
    if val:
        diag.update(json.loads(val))
    return diag


def extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError) as exc:
        print(f"extract_value: dropped {type(exc).__name__} for result {str(result)[:200]}", file=sys.stderr)
        return None


def _clean_url(href: str) -> str:
    if not href:
        return ""
    if "/url?" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        return qs.get("q", [href])[0]
    return href
