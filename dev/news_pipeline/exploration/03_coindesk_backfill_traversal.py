#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydoll.browser import Chrome

sys.path.insert(0, str(Path(__file__).parent))
from _03_capture import (  # noqa: E402
    DISABLED_RETRY_MAX,
    _JS_DISMISS_COOKIE,
    _extract_value,
    check_btn_state,
    click_button,
    extract_articles,
    get_free_port,
    kill_chrome_on_port,
    launch_background_chrome,
    retry_disabled_check,
    wait_for_new_articles,
    wait_for_ws_url,
)
from _03_log import write_log_header, write_log_line  # noqa: E402
from _03_report import write_run_report  # noqa: E402

TARGET_URL = "https://www.coindesk.com/latest-crypto-news"
OUTPUT_DIR = Path(__file__).parent / "03_output"

STAGE_A_CAP = 400        # bounded sanity run ceiling; None = uncapped Stage B
PLATEAU_TOLERANCE = 3    # consecutive no-growth clicks before declaring feed end
CHECKPOINT_EVERY = 50    # overwrite checkpoint_urls.json every N clicks

DATE_RE = re.compile(r'/(\d{4})/(\d{2})/(\d{2})/')


# ORCHESTRATOR

# Paginate CoinDesk feed without date/round caps; write live log, periodic checkpoints, and final URL set.
async def backfill_workflow(stage_a_cap: int | None = STAGE_A_CAP) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run = prepare_backfill_run(stage_a_cap)
    log_fh = run["log_fh"]
    run_start = time.monotonic()

    port = None
    session_dir = None
    chrome = None
    tab = None
    state = {
        "all_urls": {},
        "oldest": "(none)",
        "click_times": [],
        "plateau_count": 0,
        "disabled_retry_hits": 0,
        "stop_reason": "interrupted",
    }
    click_n = 0

    try:
        port = get_free_port()
        session_dir = tempfile.mkdtemp(prefix="coindesk_backfill_")
        print(f"Launching Chrome on port {port} …", file=sys.stderr)
        launch_background_chrome(port, session_dir)
        ws_url = wait_for_ws_url(port)
        print(f"Connected: {ws_url}", file=sys.stderr)

        chrome = Chrome()
        tab = await chrome.connect(ws_url)

        await load_initial_feed(tab, state, log_fh)

        click_n = await run_click_loop(tab, state, log_fh, run["checkpoint_path"], stage_a_cap)

        print(f"Stop: {state['stop_reason']} | total={len(state['all_urls'])} | oldest={state['oldest']}", file=sys.stderr)

    finally:
        await teardown_backfill_session(state, run["checkpoint_path"], tab, chrome, port, session_dir, log_fh)

    write_final_output(state["all_urls"], run["final_path"])

    run_elapsed = time.monotonic() - run_start
    write_run_report(run["report_path"], run["ts"], run_elapsed, click_n, len(state["all_urls"]), state["oldest"],
                      state["stop_reason"], state["click_times"], stage_a_cap, state["disabled_retry_hits"])
    print(f"Report → {run['report_path']}")


# FUNCTIONS
def write_final_output(all_urls: dict, final_path: Path) -> None:
    entries = build_entries(all_urls)
    entries, n_filtered = filter_live_blogs(entries)
    if n_filtered:
        print(f"Filtered {n_filtered} live-blog URLs", file=sys.stderr)
    final_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Final output → {final_path} ({len(entries)} entries)", file=sys.stderr)


def prepare_backfill_run(stage_a_cap: int | None) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = OUTPUT_DIR / f"progress_{ts}.log"
    checkpoint_path = OUTPUT_DIR / "checkpoint_urls.json"
    final_path = OUTPUT_DIR / f"urls_{ts}.json"
    report_path = OUTPUT_DIR / f"report_stage_a_{ts}.md"
    cap_label = str(stage_a_cap) if stage_a_cap is not None else "UNCAPPED"

    print(f"Log        → {log_path}", file=sys.stderr)
    print(f"Checkpoint → {checkpoint_path}  (every {CHECKPOINT_EVERY} clicks + on exit)", file=sys.stderr)
    print(f"Stage cap  : {cap_label} clicks", file=sys.stderr)

    log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
    write_log_header(log_fh, ts, cap_label)

    return {
        "ts": ts,
        "log_path": log_path,
        "checkpoint_path": checkpoint_path,
        "final_path": final_path,
        "report_path": report_path,
        "cap_label": cap_label,
        "log_fh": log_fh,
    }


async def run_click_loop(tab, state: dict, log_fh, checkpoint_path: Path, stage_a_cap: int | None) -> int:
    max_clicks = stage_a_cap if stage_a_cap is not None else 10_000_000
    click_n = 0

    for click_n in range(1, max_clicks + 1):
        should_stop = await run_backfill_click(tab, click_n, state, log_fh, checkpoint_path)
        if should_stop:
            break
    else:
        if stage_a_cap is not None:
            state["stop_reason"] = f"stage-A cap ({stage_a_cap} clicks)"
        else:
            state["stop_reason"] = "loop exhausted (internal max reached)"

    return click_n


async def load_initial_feed(tab, state: dict, log_fh) -> None:
    print(f"Navigating to {TARGET_URL} …", file=sys.stderr)
    await tab.go_to(TARGET_URL, timeout=60)
    await asyncio.sleep(3.0)

    raw_cookie = await tab.execute_script(_JS_DISMISS_COOKIE)
    cookie_result = _extract_value(raw_cookie)
    print(f"Cookie consent: {cookie_result}", file=sys.stderr)
    await asyncio.sleep(0.5)

    initial = await extract_articles(tab)
    state["all_urls"] = {a["url"]: a for a in initial}
    state["oldest"] = compute_oldest(state["all_urls"])
    print(f"Batch 0: {len(state['all_urls'])} initial | oldest={state['oldest']}", file=sys.stderr)
    write_log_line(log_fh, 0, len(state["all_urls"]), state["oldest"], len(state["all_urls"]), "initial", 0.0)


async def check_stop_conditions(tab, click_n: int, state: dict, log_fh) -> bool:
    btn = await check_btn_state(tab)
    if not btn["found"]:
        state["stop_reason"] = "button GONE"
        write_log_line(log_fh, click_n, len(state["all_urls"]), state["oldest"], 0, "GONE", 0.0)
        print(f"Click {click_n}: button GONE — end of feed", file=sys.stderr)
        return True
    if btn["disabled"]:
        recovered = await retry_disabled_check(tab, click_n)
        if not recovered:
            state["stop_reason"] = f"button DISABLED (persistent after {DISABLED_RETRY_MAX} retries)"
            write_log_line(log_fh, click_n, len(state["all_urls"]), state["oldest"], 0, "DISABLED-PERSIST", 0.0)
            print(f"Click {click_n}: {state['stop_reason']}", file=sys.stderr)
            return True
        state["disabled_retry_hits"] += 1
        print(f"Click {click_n}: disabled recovered — continuing", file=sys.stderr)
    return False


def record_click_result(click_n: int, state: dict, new_this: int, cycle_elapsed: float,
                         log_fh, checkpoint_path: Path) -> bool:
    if new_this == 0:
        state["plateau_count"] += 1
        btn_label = f"plateau({state['plateau_count']}/{PLATEAU_TOLERANCE})"
        if state["plateau_count"] >= PLATEAU_TOLERANCE:
            state["stop_reason"] = f"plateau ({PLATEAU_TOLERANCE} consecutive no-growth clicks)"
            write_log_line(log_fh, click_n, len(state["all_urls"]), state["oldest"], 0, "PLATEAU-STOP", cycle_elapsed)
            print(f"Click {click_n}: {state['stop_reason']}", file=sys.stderr)
            return True
    else:
        state["plateau_count"] = 0
        btn_label = "active"

    write_log_line(log_fh, click_n, len(state["all_urls"]), state["oldest"], new_this, btn_label, cycle_elapsed)

    if click_n % CHECKPOINT_EVERY == 0:
        save_checkpoint(state["all_urls"], checkpoint_path)
        print(f"  [checkpoint] {len(state['all_urls'])} URLs at click {click_n}", file=sys.stderr)

    return False


async def run_backfill_click(tab, click_n: int, state: dict, log_fh, checkpoint_path: Path) -> bool:
    cycle_start = time.monotonic()

    if await check_stop_conditions(tab, click_n, state, log_fh):
        return True

    prev_count = len(state["all_urls"])
    clicked = await click_button(tab)
    if not clicked:
        state["stop_reason"] = "button GONE (mid-click)"
        write_log_line(log_fh, click_n, len(state["all_urls"]), state["oldest"], 0, "GONE-MID", 0.0)
        print(f"Click {click_n}: button vanished mid-click", file=sys.stderr)
        return True

    await asyncio.sleep(2.0)
    await wait_for_new_articles(tab, prev_count)

    fresh = await extract_articles(tab)
    added = {a["url"]: a for a in fresh if a["url"] not in state["all_urls"]}
    state["all_urls"].update(added)
    state["oldest"] = compute_oldest(state["all_urls"])
    new_this = len(added)

    cycle_elapsed = time.monotonic() - cycle_start
    state["click_times"].append(cycle_elapsed)

    return record_click_result(click_n, state, new_this, cycle_elapsed, log_fh, checkpoint_path)


async def teardown_backfill_session(state: dict, checkpoint_path: Path, tab, chrome, port, session_dir, log_fh) -> None:
    if state["all_urls"]:
        save_checkpoint(state["all_urls"], checkpoint_path)
        print(f"Final checkpoint: {len(state['all_urls'])} URLs → {checkpoint_path}", file=sys.stderr)
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
    if port is not None:
        kill_chrome_on_port(port)
    if session_dir is not None:
        shutil.rmtree(session_dir, ignore_errors=True)
    print("Cleanup complete.", file=sys.stderr)
    log_fh.close()


# Parse date from CoinDesk URL path (/YYYY/MM/DD/) → UTC midnight datetime
def parse_url_date(url: str) -> datetime | None:
    m = DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


# Return YYYY-MM-DD of oldest article URL in all_urls; "(none)" if no parseable dates
def compute_oldest(all_urls: dict) -> str:
    dates = []
    for url in all_urls:
        dt = parse_url_date(url)
        if dt:
            dates.append(dt.date())
    if not dates:
        return "(none)"
    return min(dates).strftime("%Y-%m-%d")


# Convert URL date to ISO-8601 string (UTC midnight)
def _url_to_iso(url: str) -> str:
    dt = parse_url_date(url)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# Extract first path segment as section (e.g. /markets/2026/... → markets)
def _extract_section(url: str) -> str:
    try:
        path = url.split("coindesk.com", 1)[1]
        return path.strip("/").split("/")[0]
    except (IndexError, ValueError):
        return "unknown"


# Build sorted output entry list from all_urls dict
def build_entries(all_urls: dict) -> list[dict]:
    entries = []
    for url, article in all_urls.items():
        iso = _url_to_iso(url)
        entries.append({
            "url": url,
            "lastmod": iso,
            "publication_date": iso,
            "title": article.get("title", ""),
            "section": _extract_section(url),
        })
    entries.sort(key=lambda e: e["lastmod"], reverse=True)
    return entries


# Return True if URL is a CoinDesk live-blog (slug starts with "live-")
def _is_live_blog(url: str) -> bool:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.startswith("live-")


# Remove live-blog URLs; return (filtered_list, count_removed)
def filter_live_blogs(entries: list[dict]) -> tuple[list[dict], int]:
    kept = [e for e in entries if not _is_live_blog(e["url"])]
    return kept, len(entries) - len(kept)


# Build live-blog-filtered entry list and overwrite path (crash-safe periodic save)
def save_checkpoint(all_urls: dict, path: Path) -> None:
    entries = build_entries(all_urls)
    entries, _ = filter_live_blogs(entries)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CoinDesk backfill traversal — stage A (capped) or stage B (uncapped)")
    parser.add_argument("--full", action="store_true", help="Stage B: uncapped run (no click limit)")
    parser.add_argument("--cap", type=int, default=None, metavar="N", help="Override click cap (default: STAGE_A_CAP=400)")
    args = parser.parse_args()
    if args.full:
        cap = None
    elif args.cap is not None:
        cap = args.cap
    else:
        cap = STAGE_A_CAP
    asyncio.run(backfill_workflow(stage_a_cap=cap))
