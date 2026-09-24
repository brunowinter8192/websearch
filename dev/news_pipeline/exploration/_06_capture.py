# INFRASTRUCTURE
import asyncio
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

import httpx
from pydoll.browser import Chrome

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"

SKIP_HEADERS = frozenset({
    ":authority", ":method", ":path", ":scheme",
    "host", "content-length", "content-encoding", "transfer-encoding",
})

REAL_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

_JS_DISMISS_COOKIE = """
(function() {
    var btn = document.querySelector('#onetrust-accept-btn-handler');
    if (btn) { btn.click(); return 'clicked-accept'; }
    var sdk = document.getElementById('onetrust-consent-sdk');
    if (sdk) { sdk.remove(); return 'removed-sdk'; }
    return 'not-found';
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

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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


def wait_for_ws_url(port: int, timeout: float = 30.0) -> str:
    url = f"http://localhost:{port}/json/version"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return json.loads(r.read())["webSocketDebuggerUrl"]
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome not ready on port {port}")


def kill_chrome_on_port(port: int) -> None:
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)


def _extract_value(raw):
    return raw["result"]["result"]["value"]


async def capture_timeline_request(tab, n_clicks: int) -> dict | None:
    async with tab.request.record() as capture:
        for i in range(n_clicks):
            raw = await tab.execute_script(_JS_CLICK_BTN)
            print(f"  click {i + 1}/{n_clicks}: {'OK' if _extract_value(raw) else 'miss'}", flush=True)
            await asyncio.sleep(2.5)
    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


def filter_headers(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


def _log(log_fh, msg: str) -> None:
    if log_fh is None:
        return
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    log_fh.write(f"[{ts}] {msg}\n")
    log_fh.flush()


async def browser_load_feed(n_clicks: int, log_fh=None) -> tuple:
    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_disc_")
    chrome = None
    tab = None
    try:
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        await tab.go_to(TARGET_URL, timeout=60)
        await asyncio.sleep(3.0)
        await tab.execute_script(_JS_DISMISS_COOKIE)
        await asyncio.sleep(0.5)

        entry = await capture_timeline_request(tab, n_clicks)
        if entry is None:
            return {}, "", None

        api_url = entry["request"]["url"]
        raw_hdrs = {h["name"]: h["value"] for h in entry["request"]["headers"]}
        headers = filter_headers(raw_hdrs)

        resp = httpx.get(api_url, headers=headers, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            _log(log_fh, f"browser_load_feed: first replay → {resp.status_code}")
            return headers, api_url, None

        return headers, api_url, resp.content

    finally:
        if tab is not None:
            try:
                await tab.close()
            except Exception as e:
                print(f"tab.close (non-fatal): {e}", file=sys.stderr)
        if chrome is not None:
            try:
                await chrome.close()
            except Exception as e:
                print(f"chrome.close (non-fatal): {e}", file=sys.stderr)
        kill_chrome_on_port(port)
        shutil.rmtree(session_dir, ignore_errors=True)
