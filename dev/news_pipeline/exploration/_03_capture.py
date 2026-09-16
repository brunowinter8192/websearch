# INFRASTRUCTURE
import asyncio
import json
import socket
import subprocess
import sys
import time
import urllib.request

DISABLED_RETRY_MAX = 3   # retries before declaring persistent disabled (real end)
DISABLED_RETRY_WAIT = 2.0  # seconds between disabled retries

POLL_INTERVAL = 0.5
POLL_MAX = 40            # 20s max wait per click

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

# Extract feed article URLs + title; excludes aside/nav/footer/sidebar noise (mirrors discover.py)
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
        results.push({url: href, timeLabel: timeLabel, title: a.textContent.trim()});
    }
    return JSON.stringify(results);
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

# Scroll "More stories" button into view and click it; return true if found
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

# Button state — returns JSON string {found, disabled} for pydoll CDP unwrapping via _extract_value
_JS_BTN_STATE_JSON = """
(function() {
    var candidates = Array.from(document.querySelectorAll('button, a[role="button"], [role="button"]'));
    for (var i = 0; i < candidates.length; i++) {
        var t = candidates[i].textContent.trim();
        if (/more\\s+stories|load\\s+more|show\\s+more/i.test(t)) {
            return JSON.stringify({found: true, disabled: candidates[i].disabled || false});
        }
    }
    return JSON.stringify({found: false, disabled: false});
})();
"""

# Dismiss OneTrust cookie consent overlay so pointer events reach the feed
_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
})();
"""


# FUNCTIONS

# Bind to port 0 to get a free OS-assigned port
def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Launch Chrome in background via open -gna (new instance, no foreground)
def launch_background_chrome(port: int, session_dir: str) -> None:
    subprocess.run(
        [
            "open", "-gna", "Google Chrome", "--args",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={session_dir}",
            f"--user-agent={REAL_UA}",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        check=True,
    )


# Poll /json/version until Chrome responds; return webSocketDebuggerUrl
def wait_for_ws_url(port: int, timeout: float = 30.0) -> str:
    url = f"http://localhost:{port}/json/version"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read())
                return data["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome did not start on port {port} within {timeout}s")


# Kill the Chrome process bound to this debug port
def kill_chrome_on_port(port: int) -> None:
    try:
        subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)
    except Exception as e:
        print(f"pkill (non-fatal): {e}", file=sys.stderr)


# Unpack CDP execute_script result dict
def _extract_value(raw):
    try:
        return raw["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Run extract JS + decode JSON response into list of article dicts
async def extract_articles(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_EXTRACT)
    val = _extract_value(raw)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


# Click "More stories" button via JS; return True if clicked
async def click_button(tab) -> bool:
    raw = await tab.execute_script(_JS_CLICK_BTN)
    return bool(_extract_value(raw))


# Poll feed-scoped count up to POLL_MAX × POLL_INTERVAL; return when it grows
async def wait_for_new_articles(tab, prev_count: int) -> int:
    for _ in range(POLL_MAX):
        await asyncio.sleep(POLL_INTERVAL)
        raw = await tab.execute_script(_JS_COUNT)
        count = _extract_value(raw)
        if count is not None and int(count) > prev_count:
            return int(count)
    return prev_count


# Query button presence and disabled state via CDP; return {found, disabled}
async def check_btn_state(tab) -> dict:
    raw = await tab.execute_script(_JS_BTN_STATE_JSON)
    val = _extract_value(raw)
    if not val:
        return {"found": False, "disabled": False}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {"found": False, "disabled": False}


# Retry a seen-disabled button up to DISABLED_RETRY_MAX times with scroll nudge; return True if recovered
async def retry_disabled_check(tab, click_n: int) -> bool:
    for attempt in range(1, DISABLED_RETRY_MAX + 1):
        print(f"  [disabled-retry {attempt}/{DISABLED_RETRY_MAX}] click={click_n} waiting {DISABLED_RETRY_WAIT}s …", file=sys.stderr)
        await asyncio.sleep(DISABLED_RETRY_WAIT)
        await tab.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
        await asyncio.sleep(0.3)
        btn = await check_btn_state(tab)
        if not btn.get("disabled"):
            print(f"  [disabled-retry {attempt}/{DISABLED_RETRY_MAX}] recovered → active", file=sys.stderr)
            return True
        print(f"  [disabled-retry {attempt}/{DISABLED_RETRY_MAX}] still disabled", file=sys.stderr)
    return False
