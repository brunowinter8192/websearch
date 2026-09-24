#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydoll.browser import Chrome

sys.path.insert(0, str(Path(__file__).parent))
from _04_capture import (
    get_free_port,
    kill_chrome_on_port,
    launch_background_chrome,
    run_capture_phase,
    wait_for_ws_url,
)
from _04_replay import (
    CALL_DELAY,
    cursor_loop,
    extract_json_sample,
    filter_replay_headers,
    replay_curl_cffi,
    replay_httpx,
)
from _04_report import write_report

OUTPUT_DIR = Path(__file__).parent / "04_output"

CURSOR_LOOP_CALLS = 3


# ORCHESTRATOR

async def timeline_replay_workflow(loop: int = CURSOR_LOOP_CALLS, delay: float = CALL_DELAY, rate_test: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = OUTPUT_DIR / f"report_{ts}.md"

    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_replay_")
    chrome = None
    tab = None

    try:
        print(f"Launching Chrome on port {port} …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        print(f"Connected: {ws_url}", file=sys.stderr)

        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        timeline_entry = await run_capture_phase(tab)

        if timeline_entry is None:
            print("ERROR: Timeline API not captured — no matching HAR entry.", file=sys.stderr)
            write_report(report_path, ts, None, {}, {}, {}, None, None)
            return

        replay = extract_and_replay(timeline_entry)
        first_json_sample, cursor_results, cursor_results_rate = run_cursor_phase(
            replay["api_url"], replay["replay_headers"], replay["body_200"], loop, delay, rate_test,
        )

        write_report(
            report_path, ts, replay["api_url"], replay["raw_headers"], replay["replay_headers"],
            replay["replay_results"], first_json_sample, cursor_results, cursor_results_rate,
        )
        print(f"Report → {report_path}")

    finally:
        await teardown_replay_session(tab, chrome, port, session_dir)


# FUNCTIONS
def extract_and_replay(timeline_entry: dict) -> dict:
    api_url = timeline_entry["request"]["url"]
    raw_headers = {h["name"]: h["value"] for h in timeline_entry["request"]["headers"]}
    replay_headers = filter_replay_headers(raw_headers)
    print(f"Captured: {api_url}", file=sys.stderr)
    print(f"Headers: raw={len(raw_headers)} replay={len(replay_headers)}", file=sys.stderr)

    status_httpx, body_httpx, _, err_httpx = replay_httpx(api_url, replay_headers)
    status_curl, body_curl, _, err_curl = replay_curl_cffi(api_url, replay_headers)
    print(f"httpx → {status_httpx}  |  curl_cffi → {status_curl}", file=sys.stderr)

    body_200 = None
    if status_httpx == 200:
        body_200 = body_httpx
    elif status_curl == 200:
        body_200 = body_curl

    return {
        "api_url": api_url,
        "raw_headers": raw_headers,
        "replay_headers": replay_headers,
        "replay_results": {"httpx": (status_httpx, err_httpx), "curl_cffi": (status_curl, err_curl)},
        "body_200": body_200,
    }


def run_cursor_phase(api_url: str, replay_headers: dict, body_200: bytes | None,
                      loop: int, delay: float, rate_test: bool) -> tuple:
    if body_200 is None:
        return None, None, None

    first_json_sample = extract_json_sample(body_200)
    print(f"Running cursor loop: {loop} calls, {delay}s delay …", file=sys.stderr)
    cursor_results = cursor_loop(api_url, replay_headers, body_200, n=loop, delay=delay)

    cursor_results_rate = None
    if rate_test:
        print("Rate-test: re-running loop with 2.0s delay …", file=sys.stderr)
        cursor_results_rate = cursor_loop(api_url, replay_headers, body_200, n=loop, delay=2.0)

    return first_json_sample, cursor_results, cursor_results_rate


async def teardown_replay_session(tab, chrome, port: int, session_dir: str) -> None:
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
    print("Cleanup complete.", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CoinDesk Timeline API HTTP replay probe")
    parser.add_argument("--loop", type=int, default=CURSOR_LOOP_CALLS, metavar="N",
                        help=f"cursor-loop calls after initial capture (default: {CURSOR_LOOP_CALLS})")
    parser.add_argument("--delay", type=float, default=CALL_DELAY, metavar="S",
                        help=f"seconds between cursor calls (default: {CALL_DELAY})")
    parser.add_argument("--rate-test", action="store_true",
                        help="after the main loop, rerun with 2s delay to distinguish time- vs count-limit")
    args = parser.parse_args()
    asyncio.run(timeline_replay_workflow(loop=args.loop, delay=args.delay, rate_test=args.rate_test))
