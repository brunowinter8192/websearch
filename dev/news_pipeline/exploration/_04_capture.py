# INFRASTRUCTURE
import asyncio
import json
import socket
import subprocess
import sys
import time
import urllib.request

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"
CLICKS_TO_TRIGGER = 8

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
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read())
                return data["webSocketDebuggerUrl"]
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(f"Chrome did not start on port {port} within {timeout}s (last error: {last_error!r})")


def kill_chrome_on_port(port: int) -> None:
    try:
        subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)
    except Exception as e:
        print(f"pkill (non-fatal): {e}", file=sys.stderr)


async def run_capture_phase(tab) -> dict | None:
    print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
    await tab.go_to(TARGET_URL, timeout=60)
    await asyncio.sleep(3.0)

    raw = await tab.execute_script(_JS_DISMISS_COOKIE)
    print(f"Cookie consent: {_extract_value(raw)}", file=sys.stderr)
    await asyncio.sleep(0.5)

    print(f"HAR-recording {CLICKS_TO_TRIGGER} clicks to trigger Timeline API …", file=sys.stderr)
    return await capture_timeline_request(tab, CLICKS_TO_TRIGGER)


async def capture_timeline_request(tab, n_clicks: int) -> dict | None:
    async with tab.request.record() as capture:
        for i in range(n_clicks):
            raw = await tab.execute_script(_JS_CLICK_BTN)
            clicked = bool(_extract_value(raw))
            print(f"  click {i + 1}/{n_clicks}: {'OK' if clicked else 'no-button'}", file=sys.stderr)
            await asyncio.sleep(2.5)

    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


def _extract_value(raw):
    return raw["result"]["result"]["value"]
