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

import httpx
from pydoll.browser import Chrome

from src.cdp_value import extract_value
from src.news.platforms.coindesk.config import (
    TARGET_URL,
    CLICKS_REWARM,
    SKIP_HEADERS,
)

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


# ORCHESTRATOR

async def browser_load_feed(n_clicks: int) -> tuple[dict, str, bytes | None]:
    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_disc_")
    return await _load_feed_and_cleanup(port, session_dir, n_clicks)


# FUNCTIONS

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _load_feed_and_cleanup(port: int, session_dir: str, n_clicks: int) -> tuple[dict, str, bytes | None]:
    handles = {"chrome": None, "tab": None}
    try:
        return await _load_feed(port, session_dir, n_clicks, handles)
    finally:
        await _cleanup_session(handles, port, session_dir)


async def _load_feed(port: int, session_dir: str, n_clicks: int, handles: dict) -> tuple[dict, str, bytes | None]:
    launch_background_chrome(port, session_dir)
    ws_url = wait_for_ws_url(port)
    handles["chrome"] = Chrome()
    handles["tab"] = await handles["chrome"].connect(ws_url)
    tab = handles["tab"]

    await _open_feed_page(tab)

    entry = await capture_timeline_request(tab, n_clicks)
    return _replay_timeline_request(entry)


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
    raise TimeoutError(f"Chrome not ready on port {port} within {timeout}s")


async def _open_feed_page(tab) -> None:
    await tab.go_to(TARGET_URL, timeout=60)
    await asyncio.sleep(3.0)
    await tab.execute_script(_JS_DISMISS_COOKIE)
    await asyncio.sleep(0.5)


async def capture_timeline_request(tab, n_clicks: int) -> dict | None:
    async with tab.request.record() as capture:
        for i in range(n_clicks):
            raw = await tab.execute_script(_JS_CLICK_BTN)
            print(f"  click {i + 1}/{n_clicks}: {'OK' if extract_value(raw) else 'miss'}", flush=True)
            await asyncio.sleep(2.5)
    for entry in capture.entries:
        if "/api/v1/articles/timeline" in entry["request"]["url"]:
            return entry
    return None


def _replay_timeline_request(entry: dict | None) -> tuple[dict, str, bytes | None]:
    if entry is None:
        return {}, "", None

    api_url = entry["request"]["url"]
    raw_hdrs = {h["name"]: h["value"] for h in entry["request"]["headers"]}
    headers = filter_headers(raw_hdrs)

    resp = httpx.get(api_url, headers=headers, follow_redirects=True, timeout=30)
    if resp.status_code != 200:
        print(f"[coindesk] browser_load_feed: first replay → {resp.status_code}", file=sys.stderr)
        return headers, api_url, None

    return headers, api_url, resp.content


def filter_headers(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


async def _cleanup_session(handles: dict, port: int, session_dir: str) -> None:
    if handles["tab"] is not None:
        await _close_non_fatal("tab.close", handles["tab"])
    if handles["chrome"] is not None:
        await _close_non_fatal("chrome.close", handles["chrome"])
    kill_chrome_on_port(port)
    shutil.rmtree(session_dir, ignore_errors=True)


async def _close_non_fatal(label: str, target) -> None:
    try:
        await target.close()
    except Exception as e:
        print(f"{label} (non-fatal): {e}", file=sys.stderr)


def kill_chrome_on_port(port: int) -> None:
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)
