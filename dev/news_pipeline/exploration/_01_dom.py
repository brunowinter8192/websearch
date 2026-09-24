# INFRASTRUCTURE
import asyncio
import json

from pydoll.browser.options import ChromiumOptions

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
POLL_INTERVAL = 0.5
POLL_MAX = 40

_JS_INSPECT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var scopes = [
        {name: 'global', sel: 'a[href]'},
        {name: 'main a', sel: 'main a[href]'},
        {name: 'article a', sel: 'article a[href]'},
        {name: 'aside a', sel: 'aside a[href]'},
        {name: 'nav a', sel: 'nav a[href]'},
        {name: 'footer a', sel: 'footer a[href]'},
    ];
    var counts = {};
    scopes.forEach(function(s) {
        counts[s.name] = Array.from(document.querySelectorAll(s.sel)).filter(function(a) {
            return dateRe.test(a.href);
        }).length;
    });
    var chains = [];
    var seen = {};
    var mains = document.querySelectorAll('main a[href]');
    for (var i = 0; i < mains.length && chains.length < 3; i++) {
        var href = mains[i].href;
        if (!dateRe.test(href) || seen[href]) continue;
        seen[href] = true;
        var chain = [];
        var node = mains[i];
        for (var d = 0; d < 6; d++) {
            node = node.parentElement;
            if (!node || node === document.body) break;
            var cls = node.className ? node.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
            chain.push(node.tagName + (cls ? '.' + cls : ''));
        }
        chains.push({url: href.slice(22, 90), chain: chain});
    }
    return JSON.stringify({counts: counts, sample_chains: chains});
})();
"""

_JS_EXTRACT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var links = document.querySelectorAll('a[href]');
    var results = [];
    var seen = {};
    for (var i = 0; i < links.length; i++) {
        var a = links[i];
        var href = a.href;
        if (!dateRe.test(href) || seen[href]) continue;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (skip) continue;
        seen[href] = true;
        var timeLabel = '';
        node = a;
        for (var d = 0; d < 10; d++) {
            node = node.parentElement;
            if (!node) break;
            var te = node.querySelector('time');
            if (te) { timeLabel = te.getAttribute('datetime') || te.textContent.trim(); break; }
            var kids = node.querySelectorAll('span, p, div');
            for (var j = 0; j < kids.length; j++) {
                var t = kids[j].textContent.trim();
                if (t.length < 40 && /\\d+\\s*(min|hour|hr|day|h|m)\\s*(ago|s)?|just now/i.test(t)) {
                    timeLabel = t; break;
                }
            }
            if (timeLabel) break;
        }
        results.push({url: href, timeLabel: timeLabel});
    }
    return JSON.stringify(results);
})();
"""

_JS_COUNT = """
(function() {
    var dateRe = /\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//;
    var skipTags = {ASIDE: 1, NAV: 1, FOOTER: 1, HEADER: 1};
    var skipCls = /related|recommendation|popular|trending|sidebar/i;
    var seen = {};
    var count = 0;
    document.querySelectorAll('a[href]').forEach(function(a) {
        if (!dateRe.test(a.href) || seen[a.href]) return;
        var skip = false;
        var node = a.parentElement;
        while (node && node !== document.body) {
            if (skipTags[node.tagName]) { skip = true; break; }
            if (node.className && skipCls.test(node.className)) { skip = true; break; }
            node = node.parentElement;
        }
        if (!skip) { seen[a.href] = true; count++; }
    });
    return count;
})();
"""

_JS_FIND_BTN = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        var t = el.textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            var r = el.getBoundingClientRect();
            var attrs = {};
            Array.from(el.attributes).filter(function(a) { return a.name.startsWith('data-'); })
                .forEach(function(a) { attrs[a.name] = a.value; });
            return JSON.stringify({
                found: true,
                text: t.slice(0, 80),
                tagName: el.tagName,
                id: el.id,
                className: el.className.trim().split(/\\s+/).slice(0, 5).join(' '),
                dataAttrs: attrs,
                rect: {top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height)},
                scrollY: Math.round(window.scrollY)
            });
        }
    }
    return JSON.stringify({found: false});
})();
"""

_JS_CLICK_BTN = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            candidates[i].scrollIntoView({block: 'center', behavior: 'smooth'});
            candidates[i].click();
            return true;
        }
    }
    return false;
})();
"""


# FUNCTIONS

def build_options(headless: bool, session_dir: str) -> ChromiumOptions:
    opts = ChromiumOptions()
    opts.headless = headless
    opts.add_argument(f"--user-data-dir={session_dir}")
    opts.add_argument(f"--user-agent={REAL_UA}")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.block_popups = True
    opts.block_notifications = True
    return opts


def _extract_value(raw):
    try:
        return raw["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def inspect_containers(tab) -> dict:
    raw = await tab.execute_script(_JS_INSPECT)
    val = _extract_value(raw)
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


async def extract_articles(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_EXTRACT)
    val = _extract_value(raw)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


async def wait_for_new_articles(tab, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        raw = await tab.execute_script(_JS_COUNT)
        count = _extract_value(raw)
        if count is not None and int(count) > prev_count:
            return int(count)
    return prev_count


async def find_button(tab) -> dict | None:
    raw = await tab.execute_script(_JS_FIND_BTN)
    val = _extract_value(raw)
    if not val:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


async def click_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_BTN)
    return bool(_extract_value(raw))
