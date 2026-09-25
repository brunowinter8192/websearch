#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from _06_capture import TARGET_URL, browser_load_feed
from _06_progress import OUTPUT_DIR, log, log_checkpoint, save_checkpoint
from _06_report import write_report

TIMELINE_BASE = "https://www.coindesk.com/api/v1/articles/timeline"
COINDESK_BASE = "https://www.coindesk.com"
URLS_DIR = OUTPUT_DIR / "urls"

STOP_DATE = "2017-01-01"
CALL_DELAY = 0.3
CHECKPOINT_EVERY = 50
REWARM_EVERY = 240.0
CLICKS_WARMUP = 8
CLICKS_REWARM = 7
MAX_CURSOR_FALLBACKS = 3


# ORCHESTRATOR

def full_discovery() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    URLS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = _compute_log_path(ts)

    completed = _discover_into_log(log_path, ts)
    if completed:
        _print_log(log_path)


# FUNCTIONS

def _compute_log_path(ts):
    log_path = OUTPUT_DIR / f"progress_{ts}.log"
    return log_path


def _discover_into_log(log_path, ts) -> bool:
    with open(log_path, "w", encoding="utf-8", buffering=1) as log_fh:
        return _discover(log_fh, ts)


def _print_log(log_path):
    print(f"Log → {log_path}")


def _discover(log_fh, ts) -> bool:
    _log_start(log_fh, ts)
    log(log_fh, "Browser warmup …")
    headers, start_url, first_body = asyncio.run(browser_load_feed(CLICKS_WARMUP, log_fh))
    if first_body is None:
        log(log_fh, "FATAL: browser warmup failed — aborting.")
        return False
    _log_warmup_done(log_fh, start_url)
    results = cursor_loop(headers, start_url, first_body, log_fh)
    write_report(_discovery_report_path(ts), results, ts, STOP_DATE)
    log(log_fh, "Report written.")
    _log_done(log_fh, results)
    return True


def _log_start(log_fh, ts) -> None:
    log(log_fh, f"=== CoinDesk Full Discovery start {ts} ===")
    log(log_fh, f"Stop date: {STOP_DATE} | Delay: {CALL_DELAY}s | Rewarm every: {REWARM_EVERY}s")


def _log_warmup_done(log_fh, start_url) -> None:
    log(log_fh, f"Warmup done. First URL: {start_url}")


def cursor_loop(headers: dict, start_url: str, first_body: bytes, log_fh) -> dict:
    year_files: dict = {}
    seen_ids: set = set()
    state = {
        "year_counts": defaultdict(int),
        "total_articles": 0,
        "ok_calls": 0,
        "fallback_count": 0,
        "rewarm_count": 0,
        "httpx_rewarm_confirmed": None,
        "oldest_date": None,
        "last_rewarm_t": time.monotonic(),
        "body": first_body,
        "last_id": "",
        "last_date": "",
        "headers": headers,
        "elapsed_vals": [],
        "t_start": time.monotonic(),
    }

    try:
        while not run_cursor_iteration(state, year_files, seen_ids, log_fh):
            pass
    finally:
        for fh in year_files.values():
            try:
                fh.close()
            except OSError as e:
                print(f"year file close error (non-fatal): {e}", file=sys.stderr)
        save_checkpoint(state["ok_calls"], state["last_id"], state["last_date"],
                         state["year_counts"], state["total_articles"])

    elapsed_vals = state["elapsed_vals"]
    avg_elapsed = round(sum(elapsed_vals) / len(elapsed_vals), 3) if elapsed_vals else None
    return {
        "ok_calls": state["ok_calls"],
        "total_articles": state["total_articles"],
        "year_counts": dict(state["year_counts"]),
        "oldest_date": state["oldest_date"],
        "fallback_count": state["fallback_count"],
        "rewarm_count": state["rewarm_count"],
        "httpx_rewarm_confirmed": state["httpx_rewarm_confirmed"],
        "avg_elapsed": avg_elapsed,
        "wall_seconds": round(time.monotonic() - state["t_start"], 0),
    }


def _discovery_report_path(ts) -> Path:
    return OUTPUT_DIR / f"discovery_{ts}.md"


def _log_done(log_fh, results) -> None:
    log(log_fh, (
        f"=== DONE | calls={results['ok_calls']} articles={results['total_articles']}"
        f" oldest={results['oldest_date']} rewarms={results['rewarm_count']}"
        f" fallbacks={results['fallback_count']} ==="
    ))


def run_cursor_iteration(state: dict, year_files: dict, seen_ids: set, log_fh) -> bool:
    batch = process_batch(state["body"], year_files, seen_ids, state["year_counts"],
                           state["oldest_date"], log_fh)
    state["oldest_date"] = batch["oldest_date"]
    state["total_articles"] += batch["added"]
    if batch["stop"]:
        return True

    if state["httpx_rewarm_confirmed"] and time.monotonic() - state["last_rewarm_t"] >= REWARM_EVERY:
        fp = fetch_feedpage(state["headers"])
        log(log_fh, f"[proactive rewarm] httpx feedpage → {fp}")
        state["last_rewarm_t"] = time.monotonic()
        state["rewarm_count"] += 1

    step = get_next_body(batch["articles"], state["headers"], log_fh, state["ok_calls"])
    if step["stop"]:
        return True

    state["headers"], state["body"] = step["headers"], step["body"]
    state["last_id"], state["last_date"] = step["last_id"], step["last_date"]
    apply_cursor_step(step, state)

    if state["ok_calls"] % CHECKPOINT_EVERY == 0:
        log_checkpoint(log_fh, state["ok_calls"], state["total_articles"], state["oldest_date"],
                        state["last_date"], state["t_start"], state["elapsed_vals"],
                        state["rewarm_count"], state["fallback_count"])
        save_checkpoint(state["ok_calls"], state["last_id"], state["last_date"],
                         state["year_counts"], state["total_articles"])

    return False


def process_batch(body: bytes, year_files: dict, seen_ids: set, year_counts: defaultdict,
                   oldest_date, log_fh) -> dict:
    articles = parse_articles(body)
    if not articles:
        log(log_fh, "Empty response — reached API bottom. Stopping.")
        return {"stop": True, "articles": None, "oldest_date": oldest_date, "added": 0}

    added, batch_oldest = write_batch_articles(articles, year_files, seen_ids, year_counts)
    if batch_oldest and (oldest_date is None or batch_oldest < oldest_date):
        oldest_date = batch_oldest

    oldest_in_batch = (articles[-1].get("displayDate") or "")[:10]
    if oldest_in_batch and oldest_in_batch < STOP_DATE:
        log(log_fh, f"Reached stop date floor at {oldest_in_batch}. Stopping.")
        return {"stop": True, "articles": articles, "oldest_date": oldest_date, "added": added}

    return {"stop": False, "articles": articles, "oldest_date": oldest_date, "added": added}


def get_next_body(articles: list, headers: dict, log_fh, ok_calls: int) -> dict:
    result = advance_cursor(articles, headers, log_fh, ok_calls)
    next_body = result["next_body"]
    next_url = result["next_url"]
    last_id, last_date = result["last_id"], result["last_date"]
    rewarm_method = None

    if next_body is None and next_url:
        outcome = resolve_cursor_exhaustion(next_url, headers, log_fh)
        if outcome["fatal"]:
            return {"stop": True}
        headers = outcome["headers"]
        next_body = outcome["body"]
        rewarm_method = outcome["method"]

    if next_body is None:
        log(log_fh, "Cursor exhausted with no body. Stopping.")
        return {"stop": True}

    return {
        "stop": False, "body": next_body, "headers": headers,
        "last_id": last_id, "last_date": last_date,
        "elapsed": result["elapsed"], "fb_used": result["fb_used"], "rewarm_method": rewarm_method,
    }


def apply_cursor_step(step: dict, state: dict) -> None:
    if step["rewarm_method"] is None:
        state["ok_calls"] += 1
        state["elapsed_vals"].append(step["elapsed"])
        if step["fb_used"]:
            state["fallback_count"] += 1
    else:
        state["rewarm_count"] += 1
        state["last_rewarm_t"] = time.monotonic()
        state["ok_calls"] += 1
        if step["rewarm_method"] == "httpx" and state["httpx_rewarm_confirmed"] is None:
            state["httpx_rewarm_confirmed"] = True
        elif step["rewarm_method"] == "browser" and state["httpx_rewarm_confirmed"] is None:
            state["httpx_rewarm_confirmed"] = False


def parse_articles(body: bytes) -> list:
    data = json.loads(body)
    articles = data if isinstance(data, list) else None
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                articles = v
                break
    if not articles:
        return []
    result = []
    for a in articles:
        ad = a.get("articleDates") or {}
        result.append({
            "_id": a.get("_id") or a.get("id"),
            "storyType": a.get("storyType"),
            "pathname": a.get("pathname"),
            "displayDate": (
                ad.get("displayDate") or ad.get("publishedAt")
                or a.get("displayDate") or a.get("publishedAt") or a.get("date")
            ),
        })
    return result


def write_batch_articles(articles: list, year_files: dict, seen_ids: set, year_counts: defaultdict) -> tuple:
    added = 0
    batch_oldest = None
    for a in articles:
        if write_article(a, year_files, seen_ids):
            d = (a.get("displayDate") or "")[:10]
            year_counts[d[:4]] += 1
            added += 1
            if d and (batch_oldest is None or d < batch_oldest):
                batch_oldest = d
    return added, batch_oldest


def advance_cursor(articles: list, headers: dict, log_fh, ok_calls: int) -> dict:
    next_body = None
    next_url = ""
    last_id = last_date = ""
    elapsed = None
    fb_used = None
    for fb in range(min(MAX_CURSOR_FALLBACKS, len(articles))):
        anchor = articles[-(1 + fb)]
        last_id = anchor.get("_id") or ""
        last_date = anchor.get("displayDate") or ""
        if not last_id or not last_date:
            continue
        next_url = build_cursor_url(last_id, last_date)

        time.sleep(CALL_DELAY)
        t0 = time.monotonic()
        resp = httpx.get(next_url, headers=headers, follow_redirects=True, timeout=30)
        elapsed = round(time.monotonic() - t0, 2)

        if resp.status_code == 200:
            if fb > 0:
                log(log_fh, f"  call {ok_calls + 1}: 200 FALLBACK-{fb} anchor={last_id[:8]} pivot={last_date[:10]}")
            next_body = resp.content
            fb_used = fb
            break

        snippet = resp.content[:80].decode("utf-8", errors="replace")
        print(f"  call {ok_calls + 1}: {resp.status_code} fb={fb} pivot={last_date[:10]} {snippet}", flush=True)

    return {
        "next_body": next_body,
        "next_url": next_url,
        "last_id": last_id,
        "last_date": last_date,
        "elapsed": elapsed,
        "fb_used": fb_used,
    }


def resolve_cursor_exhaustion(next_url: str, headers: dict, log_fh) -> dict:
    new_headers, rewarm_body, method = try_rewarm(next_url, headers, log_fh)
    if method == "fatal" or rewarm_body is None:
        log(log_fh, "FATAL: re-warm failed. Stopping.")
        return {"fatal": True}
    return {"fatal": False, "headers": new_headers, "body": rewarm_body, "method": method}


def write_article(a: dict, year_files: dict, seen_ids: set) -> bool:
    art_id = a.get("_id")
    pathname = a.get("pathname") or ""
    date_str = (a.get("displayDate") or "")[:10]
    if not art_id or not pathname or len(date_str) < 10:
        return False
    if art_id in seen_ids:
        return False
    seen_ids.add(art_id)
    year = date_str[:4]
    if year not in year_files:
        p = URLS_DIR / f"coindesk_{year}.txt"
        year_files[year] = open(p, "w", encoding="utf-8", buffering=1)
    year_files[year].write(f"{date_str}\t{COINDESK_BASE}{pathname}\n")
    return True


def build_cursor_url(last_id: str, last_date: str) -> str:
    return f"{TIMELINE_BASE}?size=16&lastId={last_id}&lastDisplayDate={last_date}&lang=en"


def try_rewarm(failing_url: str, headers: dict, log_fh) -> tuple:
    log(log_fh, "[rewarm] Attempting httpx feedpage re-warm …")
    fp_status = fetch_feedpage(headers)
    log(log_fh, f"[rewarm] httpx feedpage GET → {fp_status}")
    time.sleep(1.0)

    resp = httpx.get(failing_url, headers=headers, follow_redirects=True, timeout=30)
    if resp.status_code == 200:
        log(log_fh, "[rewarm] httpx feedpage re-warm SUCCESS ✅")
        return headers, resp.content, "httpx"

    log(log_fh, f"[rewarm] httpx re-warm failed ({resp.status_code}) → browser re-warm …")
    new_headers, _, _ = asyncio.run(browser_load_feed(CLICKS_REWARM, log_fh))
    if not new_headers:
        log(log_fh, "[rewarm] browser re-warm produced no headers — fatal")
        return headers, None, "fatal"

    resp2 = httpx.get(failing_url, headers=new_headers, follow_redirects=True, timeout=30)
    if resp2.status_code == 200:
        log(log_fh, "[rewarm] browser re-warm SUCCESS ✅ (httpx feedpage was insufficient)")
        return new_headers, resp2.content, "browser"

    log(log_fh, f"[rewarm] browser re-warm also failed ({resp2.status_code}) — fatal")
    return headers, None, "fatal"


def fetch_feedpage(headers: dict) -> int:
    feed_hdrs = {k: v for k, v in headers.items() if k.lower() in {"user-agent", "accept-language", "accept"}}
    try:
        resp = httpx.get(TARGET_URL, headers=feed_hdrs, follow_redirects=True, timeout=30)
        return resp.status_code
    except OSError as e:
        print(f"fetch_feedpage error: {e}", file=sys.stderr)
        return -1


if __name__ == "__main__":
    full_discovery()
