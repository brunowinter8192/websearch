#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import shutil
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydoll.browser import Chrome

sys.path.insert(0, str(Path(__file__).parent))
from _05_capture import (
    filter_headers,
    get_free_port,
    kill_chrome_on_port,
    launch_background_chrome,
    run_capture_phase,
    wait_for_ws_url,
)
from _05_fixed import fixed_cursor_loop
from _05_parse import build_cursor_url, extract_cursor_std, parse_articles
from _05_report import write_fixed_report, write_walk_report

OUTPUT_DIR = Path(__file__).parent / "05_data"

TARGET_ID = "cc8f264d-ebd5-4749-ba09-63d771ba1df4"
CALL_DELAY = 0.3


# ORCHESTRATOR

async def cursor_probe_workflow(
    mode: str,
    n: int,
    invalid_types: frozenset,
    delay: float,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    port = get_free_port()
    session_dir = tempfile.mkdtemp(prefix="coindesk_cursor_")
    chrome = None
    tab = None

    try:
        print(f"[{mode}] Launching Chrome on port {port} …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        timeline_entry = await run_capture_phase(tab, mode)
        if timeline_entry is None:
            print("ERROR: Timeline API not found in HAR.", file=sys.stderr)
            return

        api_url, headers, first_body = replay_first_call(timeline_entry, mode)
        if first_body is None:
            return

        run_mode(mode, api_url, headers, first_body, ts, n, delay, invalid_types)

    finally:
        await teardown_chrome_session(tab, chrome, port, session_dir, mode)


# FUNCTIONS
def replay_first_call(timeline_entry: dict, mode: str) -> tuple:
    api_url = timeline_entry["request"]["url"]
    raw_hdrs = {h["name"]: h["value"] for h in timeline_entry["request"]["headers"]}
    headers = filter_headers(raw_hdrs)
    print(f"[{mode}] Captured URL: {api_url}", file=sys.stderr)

    first = httpx.get(api_url, headers=headers, follow_redirects=True, timeout=30)
    if first.status_code != 200:
        print(f"ERROR: First replay → {first.status_code}", file=sys.stderr)
        return api_url, headers, None

    print(f"[{mode}] First replay → 200 ({len(first.content)} bytes)", file=sys.stderr)
    return api_url, headers, first.content


def run_mode(mode: str, api_url: str, headers: dict, first_body: bytes, ts: str,
             n: int, delay: float, invalid_types: frozenset) -> None:
    if mode == "walk":
        results = storytype_walk(api_url, headers, first_body, n=n, delay=delay)
        rpath = OUTPUT_DIR / f"walk_{ts}.md"
        jpath = OUTPUT_DIR / f"walk_{ts}_articles.json"
        write_walk_report(rpath, jpath, ts, api_url, n, results)
        print(f"Walk report    → {rpath}")
        print(f"Articles JSON  → {jpath}")
    else:
        results = fixed_cursor_loop(
            api_url, headers, first_body,
            n=n, delay=delay, invalid_types=invalid_types,
        )
        rpath = OUTPUT_DIR / f"fixed_{ts}.md"
        write_fixed_report(rpath, ts, api_url, n, invalid_types, results)
        print(f"Fixed report   → {rpath}")


async def teardown_chrome_session(tab, chrome, port: int, session_dir: str, mode: str) -> None:
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
    print(f"[{mode}] Cleanup done.", file=sys.stderr)


def record_walk_batch(articles: list, call_num: int, call_log: list) -> dict | None:
    target_article = None
    for a in articles:
        if a.get("_id") == TARGET_ID:
            target_article = a

    call_log.append({
        "call": call_num,
        "status": 200,
        "count": len(articles),
        "newest": (articles[0].get("displayDate") or "")[:19],
        "oldest": (articles[-1].get("displayDate") or "")[:19],
        "target_in_call": any(a.get("_id") == TARGET_ID for a in articles),
    })
    return target_article


def advance_walk_cursor(articles: list, headers: dict, delay: float, call_num: int, call_log: list) -> bytes | None:
    last_id, last_date = extract_cursor_std(articles)
    if not last_id or not last_date:
        call_log.append({"call": call_num + 1, "error": "cursor extraction failed"})
        return None

    next_url = build_cursor_url(last_id, last_date)
    time.sleep(delay)

    t0 = time.monotonic()
    resp = httpx.get(next_url, headers=headers, follow_redirects=True, timeout=30)
    elapsed = round(time.monotonic() - t0, 2)

    print(
        f"  call {call_num + 1}: {resp.status_code} ({elapsed}s)"
        f" pivot={last_date[:10]} storyType={articles[-1].get('storyType')}",
        file=sys.stderr,
    )

    if resp.status_code != 200:
        last_art = articles[-1]
        call_log.append({
            "call": call_num + 1,
            "status": resp.status_code,
            "url": next_url,
            "elapsed": elapsed,
            "cursor_source": {
                "_id": last_art.get("_id"),
                "storyType": last_art.get("storyType"),
                "displayDate": last_art.get("displayDate"),
                "title": last_art.get("title"),
                "pathname": last_art.get("pathname"),
            },
            "body_snippet": resp.content[:400].decode("utf-8", errors="replace"),
        })
        return None

    return resp.content


def storytype_walk(first_url: str, headers: dict, first_body: bytes, n: int, delay: float) -> dict:
    all_articles: list = []
    call_log: list = []
    body = first_body
    target_article = None

    for call_num in range(n + 1):
        articles = parse_articles(body)
        if not articles:
            call_log.append({"call": call_num, "error": "no articles parsed from body"})
            break

        found = record_walk_batch(articles, call_num, call_log)
        if found:
            target_article = found
        all_articles.extend(articles)

        if call_num >= n:
            break

        body = advance_walk_cursor(articles, headers, delay, call_num, call_log)
        if body is None:
            break

    type_dist = dict(Counter(
        a.get("storyType") or "NULL" for a in all_articles
    ).most_common())

    return {
        "call_log": call_log,
        "all_articles": all_articles,
        "type_distribution": type_dist,
        "total_articles": len(all_articles),
        "target_article": target_article,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CoinDesk cursor storyType probe")
    parser.add_argument(
        "--mode", choices=["walk", "fixed"], default="walk",
        help="walk: log all storyTypes; fixed: use fixed cursor skipping invalid types",
    )
    parser.add_argument(
        "--n", type=int, default=25,
        help="number of paginated calls (default: 25 for walk, increase for fixed/deep)",
    )
    parser.add_argument(
        "--invalid-types", type=str, default="",
        metavar="T1,T2,...",
        help="comma-separated storyTypes to skip as cursor anchor (fixed mode only)",
    )
    parser.add_argument(
        "--delay", type=float, default=CALL_DELAY,
        help=f"seconds between cursor calls (default: {CALL_DELAY})",
    )
    args = parser.parse_args()

    invalid = frozenset(t.strip() for t in args.invalid_types.split(",") if t.strip())
    asyncio.run(cursor_probe_workflow(mode=args.mode, n=args.n, invalid_types=invalid, delay=args.delay))
