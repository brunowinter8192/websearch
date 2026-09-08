# INFRASTRUCTURE
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.news.platforms.coindesk.config import (
    COINDESK_BASE,
    CALL_DELAY,
    REWARM_EVERY,
    CLICKS_WARMUP,
    MAX_CURSOR_FALLBACKS,
    CHECKPOINT_EVERY,
    DEFAULT_DELTA_DAYS,
    FULL_MODE_FLOOR,
    DISCOVER_DIR,
)
# From browser.py: browser_load_feed(n_clicks) -> (headers, api_url, body)
from src.news.platforms.coindesk.browser import browser_load_feed
# From timeline.py: timeline-API access + session re-warm
from src.news.platforms.coindesk.timeline import parse_articles, build_cursor_url, fetch_feedpage, try_rewarm
# From shards.py: per-year discover shard storage
from src.news.platforms.coindesk.shards import _append_to_shard, load_discover


# ORCHESTRATOR

# Browser warmup → httpx cursor loop → incremental discover write → entry list.
async def discover(timeframe: str = "30") -> list[dict]:
    stop_date = _parse_stop_date(timeframe)
    print(f"[coindesk] discover timeframe={timeframe!r} stop_date={stop_date}", file=sys.stderr)

    print("[coindesk] Browser warmup …", file=sys.stderr)
    headers, start_url, first_body = await browser_load_feed(CLICKS_WARMUP)
    if first_body is None:
        raise RuntimeError("CoinDesk browser warmup failed — could not capture timeline API response")

    print(f"[coindesk] Warmup done. First URL: {start_url}", file=sys.stderr)

    DISCOVER_DIR.mkdir(parents=True, exist_ok=True)
    seen_urls = load_discover(DISCOVER_DIR)
    print(f"[coindesk] Discover loaded: {len(seen_urls)} existing URLs", file=sys.stderr)

    entries = await cursor_loop(headers, start_url, first_body, stop_date, seen_urls, DISCOVER_DIR)

    new_count = sum(1 for e in entries if e.get("_new"))
    print(
        f"[coindesk] discover → {len(entries)} entries total, {new_count} new to discover",
        file=sys.stderr,
    )
    return [{k: v for k, v in e.items() if k != "_new"} for e in entries]


# FUNCTIONS

# Compute stop-date string from timeframe specifier
def _parse_stop_date(timeframe: str) -> str:
    if timeframe == "full":
        return FULL_MODE_FLOOR
    try:
        n = int(timeframe)
    except ValueError:
        n = DEFAULT_DELTA_DAYS
    floor = datetime.now(timezone.utc).date() - timedelta(days=n)
    return floor.isoformat()


# Run-wide cursor_loop accumulators — mirrors the per-ride scratch dataclass pattern in rider.py.
@dataclass
class _CursorLoopStats:
    ok_calls:               int  = 0
    fallback_count:         int  = 0
    rewarm_count:           int  = 0
    httpx_rewarm_confirmed: bool | None = None
    oldest_date:            str | None  = None
    last_rewarm_t:          float = field(default_factory=time.monotonic)


# Cursor loop: pages backward to stop_date; writes new URLs incrementally to discover shards.
async def cursor_loop(
    headers: dict,
    start_url: str,
    first_body: bytes,
    stop_date: str,
    seen_urls: set,
    discover_dir: Path,
) -> list[dict]:
    year_files: dict[str, object] = {}
    all_entries: list[dict] = []
    stats = _CursorLoopStats()
    t_start = time.monotonic()
    body = first_body
    last_date = ""

    try:
        while True:
            articles = parse_articles(body)
            if not articles:
                print("[coindesk] Empty response — reached API bottom or parse failure. Stopping.", file=sys.stderr)
                break

            _process_batch(articles, seen_urls, year_files, discover_dir, all_entries, stats)

            oldest_in_batch = (articles[-1].get("displayDate") or "")[:10]
            if oldest_in_batch and oldest_in_batch < stop_date:
                print(f"[coindesk] Reached stop_date floor at {oldest_in_batch}. Stopping.", file=sys.stderr)
                break

            _maybe_proactive_rewarm(headers, stats)

            headers, body, last_date, should_stop = await _advance_cursor(articles, headers, stats)
            if should_stop:
                break

            _maybe_log_checkpoint(stats, all_entries, last_date, t_start)

    finally:
        _close_year_files(year_files)

    _log_cursor_loop_summary(stats, all_entries, t_start)
    return all_entries


# Process and incrementally write this batch: build entries, filter live-blogs, dedup, track oldest_date.
def _process_batch(
    articles:     list[dict],
    seen_urls:    set,
    year_files:   dict,
    discover_dir: Path,
    all_entries:  list[dict],
    stats:        _CursorLoopStats,
) -> None:
    for a in articles:
        entry = _build_entry(a)
        if entry is None:
            continue
        if _is_live_blog(entry["url"]):
            continue
        is_new = entry["url"] not in seen_urls
        if is_new:
            seen_urls.add(entry["url"])
            _append_to_shard(entry, year_files, discover_dir)
        all_entries.append({**entry, "_new": is_new})
        d = entry["publication_date"][:10] if entry["publication_date"] else ""
        if d and (stats.oldest_date is None or d < stats.oldest_date):
            stats.oldest_date = d


# Proactive keep-alive re-warm once httpx re-warm is confirmed working, throttled to REWARM_EVERY.
def _maybe_proactive_rewarm(headers: dict, stats: _CursorLoopStats) -> None:
    if not (stats.httpx_rewarm_confirmed and time.monotonic() - stats.last_rewarm_t >= REWARM_EVERY):
        return
    fp = fetch_feedpage(headers)
    print(f"[coindesk] [proactive rewarm] httpx feedpage → {fp}", file=sys.stderr)
    stats.last_rewarm_t = time.monotonic()
    stats.rewarm_count += 1


# Advance to the next page, handling cursor exhaustion/re-warm. Return (headers, body, last_date, should_stop).
async def _advance_cursor(
    articles: list[dict], headers: dict, stats: _CursorLoopStats,
) -> tuple[dict, bytes | None, str, bool]:
    next_body, next_url, last_id, last_date = _fetch_next_page(articles, headers, stats)

    if next_body is None and next_url:
        headers, next_body, fatal = await _handle_cursor_exhaustion(next_url, headers, stats)
        if fatal:
            return headers, None, last_date, True

    if next_body is None:
        print("[coindesk] Cursor exhausted with no body. Stopping.", file=sys.stderr)
        return headers, None, last_date, True

    return headers, next_body, last_date, False


# Build next cursor; fall back to N-1, N-2 articles on 403. Return (body, url, last_id, last_date).
def _fetch_next_page(
    articles: list[dict], headers: dict, stats: _CursorLoopStats,
) -> tuple[bytes | None, str, str, str]:
    next_body = None
    next_url = ""
    last_id = last_date = ""
    for fb in range(min(MAX_CURSOR_FALLBACKS, len(articles))):
        anchor = articles[-(1 + fb)]
        last_id = anchor.get("_id") or ""
        last_date = anchor.get("displayDate") or ""
        if not last_id or not last_date:
            continue
        next_url = build_cursor_url(last_id, last_date)

        time.sleep(CALL_DELAY)
        resp = httpx.get(next_url, headers=headers, follow_redirects=True, timeout=30)

        if resp.status_code == 200:
            if fb > 0:
                stats.fallback_count += 1
                print(
                    f"[coindesk]   call {stats.ok_calls + 1}: 200 FALLBACK-{fb} "
                    f"anchor={last_id[:8]} pivot={last_date[:10]}",
                    file=sys.stderr,
                )
            next_body = resp.content
            stats.ok_calls += 1
            break

        snippet = resp.content[:80].decode("utf-8", errors="replace")
        print(
            f"[coindesk]   call {stats.ok_calls + 1}: {resp.status_code} fb={fb} "
            f"pivot={last_date[:10]} {snippet}",
            file=sys.stderr,
        )

    return next_body, next_url, last_id, last_date


# All cursor fallbacks exhausted → try re-warm. Return (headers, body, fatal) — fatal=True means stop.
async def _handle_cursor_exhaustion(
    next_url: str, headers: dict, stats: _CursorLoopStats,
) -> tuple[dict, bytes | None, bool]:
    new_headers, rewarm_body, method = await try_rewarm(next_url, headers)
    if method == "fatal" or rewarm_body is None:
        print("[coindesk] FATAL: re-warm failed. Stopping.", file=sys.stderr)
        return headers, None, True
    stats.rewarm_count += 1
    stats.last_rewarm_t = time.monotonic()
    stats.ok_calls += 1
    if method == "httpx" and stats.httpx_rewarm_confirmed is None:
        stats.httpx_rewarm_confirmed = True
    elif method == "browser" and stats.httpx_rewarm_confirmed is None:
        stats.httpx_rewarm_confirmed = False
    return new_headers, rewarm_body, False


# Periodic progress log every CHECKPOINT_EVERY successful calls.
def _maybe_log_checkpoint(stats: _CursorLoopStats, all_entries: list[dict], last_date: str, t_start: float) -> None:
    if stats.ok_calls % CHECKPOINT_EVERY != 0:
        return
    wall = int(time.monotonic() - t_start)
    new_in_run = sum(1 for e in all_entries if e.get("_new"))
    print(
        f"[coindesk] checkpoint call={stats.ok_calls} total={len(all_entries)} "
        f"new={new_in_run} oldest={stats.oldest_date} pivot={last_date[:10]} "
        f"wall={wall}s rewarms={stats.rewarm_count} fallbacks={stats.fallback_count}",
        file=sys.stderr,
    )


# Close all open year-shard file handles; log (non-fatal) on close error.
def _close_year_files(year_files: dict) -> None:
    for fh in year_files.values():
        try:
            fh.close()
        except OSError as e:
            print(f"[coindesk] year shard close error (non-fatal): {e}", file=sys.stderr)


# Final cursor_loop summary log.
def _log_cursor_loop_summary(stats: _CursorLoopStats, all_entries: list[dict], t_start: float) -> None:
    wall = int(time.monotonic() - t_start)
    new_total = sum(1 for e in all_entries if e.get("_new"))
    print(
        f"[coindesk] cursor_loop done: calls={stats.ok_calls} total={len(all_entries)} "
        f"new={new_total} oldest={stats.oldest_date} wall={wall}s "
        f"rewarms={stats.rewarm_count} fallbacks={stats.fallback_count}",
        file=sys.stderr,
    )


# Build output entry dict from raw article dict; return None if pathname or date missing
def _build_entry(a: dict) -> dict | None:
    pathname = a.get("pathname") or ""
    display_date = (a.get("displayDate") or "")[:10]
    if not pathname or len(display_date) < 10:
        return None
    url = COINDESK_BASE + pathname
    iso = f"{display_date}T00:00:00+00:00"
    return {
        "url":              url,
        "lastmod":          iso,
        "publication_date": iso,
        "title":            a.get("title") or "",
        "section":          _extract_section(pathname),
    }


# Extract first path segment as section (e.g. /markets/2024/... → markets)
def _extract_section(pathname: str) -> str:
    parts = pathname.strip("/").split("/")
    return parts[0] if parts else "unknown"


# Return True if URL is a CoinDesk live-blog: slug starts with "live-"
def _is_live_blog(url: str) -> bool:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.startswith("live-")
