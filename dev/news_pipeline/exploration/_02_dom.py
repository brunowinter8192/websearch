# INFRASTRUCTURE
import asyncio
import re  # DATE_RE
from pathlib import Path

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
OUTPUT_DIR = Path(__file__).parent / "02_output"
REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)
POLL_INTERVAL = 0.5
POLL_MAX = 40          # 20s max wait per click

DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')

# Extract feed article URLs — excludes aside/nav/footer/sidebar noise (mirrored from discover.py)
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
        results.push(href);
    }
    return results;
})();
"""

# Dismiss OneTrust cookie consent overlay (removes the DOM node so pointer events are unblocked)
_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
})();
"""

# Scroll "More stories" button into view and JS-click it; return true if found + clicked
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

# Return descriptor of "More stories" button: {found, disabled, text} or {found: false}
_JS_BTN_STATE = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            return {found: true, disabled: candidates[i].disabled || false, text: t.slice(0, 60)};
        }
    }
    return {found: false};
})();
"""

# Count feed-scoped article URLs (fast poll)
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


# FUNCTIONS

# Evaluate _JS_EXTRACT; return list of article href strings
async def extract_articles(page) -> list[str]:
    result = await page.evaluate(_JS_EXTRACT)
    return result if isinstance(result, list) else []


# Poll feed-scoped count until it grows past prev_count; return new count
async def wait_for_new_articles(page, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        count = await page.evaluate(_JS_COUNT)
        if isinstance(count, int) and count > prev_count:
            return count
    return prev_count


# Parse oldest date string (YYYY-MM-DD) from a collection of CoinDesk article URLs
def compute_oldest(urls) -> str:
    dates = []
    for url in urls:
        m = DATE_RE.search(url)
        if m:
            dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not dates:
        return "(none)"
    y, mo, d = min(dates)
    return f"{y:04d}-{mo:02d}-{d:02d}"
