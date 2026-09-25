# INFRASTRUCTURE
import asyncio
import http.server
import json
import logging
import subprocess
import threading
import time
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.managers import BrowserProcessManager
from pydoll.commands import PageCommands

logger = logging.getLogger(__name__)

PROBE_PROFILE_ROOT = Path.home() / ".websearch" / "browser-posture-probe"

BACKGROUNDING_FLAGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

WINDOW_ARGS = ["--window-position=200,200", "--window-size=900,700"]

PROBE_HTML = """<!doctype html>
<html><head><title>browser-posture-probe</title></head>
<body>
<p id="marker">PROBE_PAGE_READY</p>
<script>
window.__ticks = [];
(function() {
  var n = 0;
  var iv = setInterval(function() {
    window.__ticks.push(Date.now());
    n++;
    if (n >= 40) { clearInterval(iv); }
  }, 100);
})();
</script>
</body></html>
"""

ARTIFACT_HTML = """<!doctype html>
<html><head><title>artifact-test</title></head>
<body>
<a id="plain-link" href="#">link</a>
<div id="active-text" style="color: ActiveText">x</div>
<div id="link-text" style="color: LinkText">x</div>
<div id="visited-text" style="color: VisitedText">x</div>
</body></html>
"""


# FUNCTIONS

def start_probe_server() -> tuple[http.server.ThreadingHTTPServer, threading.Thread, int]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


def stop_probe_server(server: http.server.ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)


def profile_dir(name: str) -> str:
    return str(PROBE_PROFILE_ROOT / name)


def count_processes_for(profile: str) -> int:
    result = subprocess.run(["pgrep", "-f", f"user-data-dir={profile}"], capture_output=True, text=True)
    return len([line for line in result.stdout.splitlines() if line.strip()])


async def launch_chrome(
    profile: str, headless: bool, extra_flags: list[str], backgrounded: bool
) -> tuple[Chrome, object, float, float]:
    kill_by_profile(profile)
    time.sleep(0.3)
    options = build_options(profile, headless, extra_flags, window_args=backgrounded)
    browser = Chrome(options)
    if backgrounded:
        browser._browser_process_manager = BrowserProcessManager(process_creator=open_background_process_creator)
    t0 = time.monotonic()
    tab = await browser.start()
    t_tab = time.monotonic() - t0
    await tab.execute_script("1+1")
    t_drivable = time.monotonic() - t0
    return browser, tab, t_tab, t_drivable


async def stop_chrome(browser, profile: str) -> None:
    if browser is not None:
        try:
            await browser.stop()
        except Exception as e:
            logger.warning("browser.stop() failed (expected to fall through to pkill): %s", e)
    kill_by_profile(profile)


def spawn_plain_chrome(profile: str, window_args: list[str] | None = None) -> None:
    kill_by_profile(profile)
    time.sleep(0.3)
    args = ["open", "-g", "-n", "-a", "Google Chrome", "--args", f"--user-data-dir={profile}"]
    if window_args:
        args += window_args
    subprocess.run(args)


async def read_visibility_state(tab) -> dict:
    raw = await tab.execute_script(
        "return JSON.stringify({visibilityState: document.visibilityState, hidden: document.hidden})"
    )
    value = extract_value(raw)
    return json.loads(value) if value else {"visibilityState": None, "hidden": None}


async def read_tick_stats(tab) -> dict:
    raw = await tab.execute_script("return JSON.stringify(window.__ticks || [])")
    value = extract_value(raw)
    ticks = json.loads(value) if value else []
    if len(ticks) < 2:
        return {"count": len(ticks), "mean_interval_ms": None, "max_gap_ms": None}
    intervals = [ticks[i + 1] - ticks[i] for i in range(len(ticks) - 1)]
    return {
        "count": len(ticks),
        "mean_interval_ms": round(sum(intervals) / len(intervals), 1),
        "max_gap_ms": max(intervals),
    }


def stats_ms(values: list[float]) -> dict:
    ms = sorted(round(v * 1000) for v in values)
    n = len(ms)
    if n == 0:
        return {"n": 0, "min": None, "median": None, "max": None}
    median = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) // 2
    return {"n": n, "min": ms[0], "median": median, "max": ms[-1]}


async def inject_before_navigation(tab, source: str) -> None:
    if not source:
        return
    await tab._execute_command(
        PageCommands.add_script_to_evaluate_on_new_document(source=source, run_immediately=True)
    )


async def read_system_colors(tab) -> dict:
    raw = await tab.execute_script(
        "return JSON.stringify({"
        "plainLink: getComputedStyle(document.getElementById('plain-link')).color,"
        "activeText: getComputedStyle(document.getElementById('active-text')).color,"
        "linkText: getComputedStyle(document.getElementById('link-text')).color,"
        "visitedText: getComputedStyle(document.getElementById('visited-text')).color"
        "})"
    )
    value = extract_value(raw)
    return json.loads(value) if value else {}


async def read_screen_window_props(tab) -> dict:
    raw = await tab.execute_script(
        "return JSON.stringify({"
        "screenWidth: screen.width, screenHeight: screen.height,"
        "availWidth: screen.availWidth, availHeight: screen.availHeight,"
        "colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,"
        "devicePixelRatio: window.devicePixelRatio,"
        "innerWidth: window.innerWidth, innerHeight: window.innerHeight,"
        "outerWidth: window.outerWidth, outerHeight: window.outerHeight"
        "})"
    )
    value = extract_value(raw)
    return json.loads(value) if value else {}


async def wait_for_stable_content(tab, js_expr: str, interval: float = 2.0, max_wait: float = 25.0, stable_reads: int = 2) -> tuple:
    start = time.monotonic()
    prev = None
    stable_count = 0
    while time.monotonic() - start < max_wait:
        raw = await tab.execute_script(f"return {js_expr}")
        cur = extract_value(raw)
        if cur == prev:
            stable_count += 1
            if stable_count >= stable_reads:
                return cur, True
        else:
            stable_count = 0
        prev = cur
        await asyncio.sleep(interval)
    return prev, False


def get_frontmost_app() -> str:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


class _ProbeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (ARTIFACT_HTML if self.path.startswith("/artifact") else PROBE_HTML).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def kill_by_profile(profile: str) -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={profile}"], capture_output=True)


def build_options(profile: str, headless: bool, extra_flags: list[str], window_args: bool) -> ChromiumOptions:
    options = ChromiumOptions()
    options.headless = headless
    options.add_argument(f"--user-data-dir={profile}")
    options.block_popups = True
    options.block_notifications = True
    for flag in extra_flags:
        options.add_argument(flag)
    if window_args:
        for arg in WINDOW_ARGS:
            options.add_argument(arg)
    return options


def open_background_process_creator(command: list[str]) -> subprocess.Popen:
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", "Google Chrome", "--args", *args]
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None
