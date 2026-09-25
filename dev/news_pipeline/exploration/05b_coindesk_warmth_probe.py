#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydoll.browser import Chrome

sys.path.insert(0, str(Path(__file__).parent))
from _05b_report import write_warmth_report

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
TIMELINE_API_PATH = "/api/v1/articles/timeline"
OUTPUT_DIR = Path(__file__).parent / "05b_output"
STATE_FILE = OUTPUT_DIR / "state.json"

WARMTH_INTERVALS = [0, 10, 20, 30, 60, 120, 180, 300]

CLICKS_TO_TRIGGER = 8

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


# ORCHESTRATOR

async def warmth_probe_workflow() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = _compute_report_path(ts)

    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_warmth_")
    captured = await _capture_state(port, session_dir)
    if captured is None:
        return
    test_url, test_headers, baseline_status = captured

    if test_url is None or test_headers is None:
        print("ERROR: State not captured — aborting.", file=sys.stderr)
        return

    ladder_results = run_warmth_ladder(test_url, test_headers, WARMTH_INTERVALS)

    feedpage_result, subprocess_result = run_phase_c(test_url, test_headers, ladder_results)

    write_warmth_report(
        report_path, ts, TARGET_URL, test_url, baseline_status,
        WARMTH_INTERVALS, ladder_results, feedpage_result, subprocess_result,
    )
    _print_warmth_report(report_path)


# FUNCTIONS

def _compute_report_path(ts):
    report_path = OUTPUT_DIR / f"warmth_{ts}.md"
    return report_path


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _capture_state(port: int, session_dir: str):
    chrome = None
    tab = None
    try:
        print("Phase W: launching Chrome …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        timeline_entry = await run_capture_phase(tab)
        if timeline_entry is None:
            print("ERROR: Timeline API not found in HAR.", file=sys.stderr)
            return None
        return save_baseline_state(timeline_entry)
    finally:
        await teardown_chrome_session(tab, chrome, port, session_dir)


def run_warmth_ladder(url: str, headers: dict, intervals: list) -> list:
    results = []
    elapsed_total = 0.0

    for target_t in intervals:
        delta = target_t - elapsed_total
        if delta > 0.5:
            print(f"  sleeping {round(delta, 1)}s → T={target_t}s …", file=sys.stderr)
            time.sleep(delta)
        elapsed_total = target_t

        t0 = time.monotonic()
        try:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
            call_elapsed = round(time.monotonic() - t0, 2)
            elapsed_total += call_elapsed
            results.append({
                "t_seconds": target_t,
                "status": resp.status_code,
                "call_elapsed": call_elapsed,
                "body_snippet": resp.content[:200].decode("utf-8", errors="replace")
                if resp.status_code != 200 else None,
            })
        except Exception as e:
            call_elapsed = round(time.monotonic() - t0, 2)
            elapsed_total += call_elapsed
            results.append({"t_seconds": target_t, "status": -1, "error": str(e)})

        print(f"  T={target_t}s → {results[-1]['status']}", file=sys.stderr)

    return results


def run_phase_c(test_url: str, test_headers: dict, ladder_results: list) -> tuple:
    first_403 = next((r for r in ladder_results if r["status"] != 200), None)
    if first_403 is None:
        print(
            f"Phase C: skipped — no 403 in {WARMTH_INTERVALS[-1]}s ladder.",
            file=sys.stderr,
        )
        return None, None

    print("Phase C: feedpage rewarm test …", file=sys.stderr)
    feedpage_status, feedpage_bytes = fetch_feedpage(test_headers)
    print(f"Phase C: feedpage GET → {feedpage_status} ({feedpage_bytes} bytes)", file=sys.stderr)

    time.sleep(1.0)
    rewarm = httpx.get(test_url, headers=test_headers, follow_redirects=True, timeout=30)
    print(f"Phase C: API after feedpage GET → {rewarm.status_code}", file=sys.stderr)
    feedpage_result = {
        "feedpage_status": feedpage_status,
        "feedpage_bytes": feedpage_bytes,
        "api_after_feedpage": rewarm.status_code,
        "api_after_feedpage_snippet": rewarm.content[:200].decode("utf-8", errors="replace")
        if rewarm.status_code != 200 else None,
    }

    print("Phase C: subprocess cold test …", file=sys.stderr)
    subprocess_result = subprocess_cold_test(STATE_FILE)
    print(f"Phase C: subprocess result: {subprocess_result}", file=sys.stderr)

    return feedpage_result, subprocess_result


def _print_warmth_report(report_path):
    print(f"Warmth report → {report_path}")


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
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Chrome not ready on port {port}")


async def run_capture_phase(tab) -> dict | None:
    print(f"Phase W: navigating to {TARGET_URL} …", file=sys.stderr)
    await tab.go_to(TARGET_URL, timeout=60)
    await asyncio.sleep(3.0)

    raw = await tab.execute_script(_JS_DISMISS_COOKIE)
    print(f"Phase W: cookie consent: {_extract_value(raw)}", file=sys.stderr)
    await asyncio.sleep(0.5)

    print(f"Phase W: capturing timeline request ({CLICKS_TO_TRIGGER} clicks) …", file=sys.stderr)
    return await capture_timeline_request(tab, CLICKS_TO_TRIGGER)


def save_baseline_state(timeline_entry: dict) -> tuple:
    test_url = timeline_entry["request"]["url"]
    raw_hdrs = {h["name"]: h["value"] for h in timeline_entry["request"]["headers"]}
    test_headers = filter_headers(raw_hdrs)
    print(f"Phase W: captured URL: {test_url}", file=sys.stderr)

    baseline = httpx.get(test_url, headers=test_headers, follow_redirects=True, timeout=30)
    baseline_status = baseline.status_code
    print(f"Phase W: baseline (Chrome open) → {baseline_status}", file=sys.stderr)

    state = {"url": test_url, "headers": test_headers}
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Phase W: state saved → {STATE_FILE}", file=sys.stderr)

    return test_url, test_headers, baseline_status


async def teardown_chrome_session(tab, chrome, port: int, session_dir: str) -> None:
    if tab:
        try:
            await tab.close()
        except Exception as e:
            print(f"tab.close (non-fatal): {e}", file=sys.stderr)
    if chrome:
        try:
            await chrome.close()
        except Exception as e:
            print(f"chrome.close (non-fatal): {e}", file=sys.stderr)
    kill_chrome_on_port(port)
    shutil.rmtree(session_dir, ignore_errors=True)
    print("Phase W: Chrome closed — timing ladder starts now.", file=sys.stderr)


def fetch_feedpage(api_headers: dict) -> tuple:
    feed_headers = {
        k: v for k, v in api_headers.items()
        if k.lower() in {"user-agent", "accept-language", "accept"}
    }
    try:
        resp = httpx.get(TARGET_URL, headers=feed_headers, follow_redirects=True, timeout=30)
        return resp.status_code, len(resp.content)
    except Exception as e:
        return -1, 0


def subprocess_cold_test(state_file: Path) -> dict:
    script_lines = [
        "import json, httpx, sys",
        f"state = json.loads(open({json.dumps(str(state_file))}).read())",
        "try:",
        "    r = httpx.get(state['url'], headers=state['headers'], follow_redirects=True, timeout=30)",
        "    print(r.status_code)",
        "except Exception as e:",
        "    print(f'ERROR:{e}', file=sys.stderr)",
        "    print(-1)",
    ]
    script = "\n".join(script_lines)

    tmp_script = None
    try:
        fd, tmp_script = tempfile.mkstemp(suffix=".py", prefix="cd_cold_")
        os.close(fd)
        Path(tmp_script).write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, tmp_script],
            capture_output=True, text=True, timeout=60,
        )
        return {
            "status": proc.stdout.strip(),
            "stderr": proc.stderr.strip()[:300],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "status": "?"}
    except Exception as e:
        return {"error": str(e), "status": "?"}
    finally:
        if tmp_script and os.path.exists(tmp_script):
            os.unlink(tmp_script)


async def capture_timeline_request(tab, n_clicks: int) -> dict | None:
    async with tab.request.record() as capture:
        for i in range(n_clicks):
            raw = await tab.execute_script(_JS_CLICK_BTN)
            clicked = bool(_extract_value(raw))
            print(f"  click {i + 1}/{n_clicks}: {'OK' if clicked else 'miss'}", file=sys.stderr)
            await asyncio.sleep(2.5)
    for entry in capture.entries:
        if TIMELINE_API_PATH in entry["request"]["url"]:
            return entry
    return None


def filter_headers(raw: dict) -> dict:
    return {k: v for k, v in raw.items() if k.lower() not in SKIP_HEADERS}


def kill_chrome_on_port(port: int) -> None:
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port}"], check=False)


def _extract_value(raw):
    return raw["result"]["result"]["value"]


if __name__ == "__main__":
    asyncio.run(warmth_probe_workflow())
