#!/usr/bin/env python3
"""Yandex Search go/no-go probe — empirically checks scrapeability of yandex.com, one of the few
remaining INDEPENDENT web indexes (own crawler, distinct from Google/Bing) — a genuine new-coverage
candidate for the general axis, and a hard anti-bot target (Yandex SmartCaptcha), in the Brave league.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Decision criterion (relaxed, per task): DROP only if there is truly no way through — blocked from
the very first query, never a single usable result. A handful of clean hits before any eventual
block is a CANDIDATE (real usage is 3-4 queries every few days — comfortably inside any clean
window observed), same reasoning that landed Brave as a production candidate. Quality (relevance
of results, especially for German/Western queries against a Russia-based index) is tracked as a
SEPARATE axis from access/blocking.

Empirical finding: `https://yandex.com/search/?text=<q>` (yandex.com, NOT yandex.ru) redirects to
`&lr=<region_id>` (a region parameter, auto-detected from IP geolocation — no block, no consent
step) and renders full results immediately. The old `li.serp-item` container selector is STILL the
live shape (confirmed via direct DOM inspection) — title is `a.OrganicTitle-Link` (direct href, NO
URL-wrapping/redirect unlike Bing's ck/a), snippet is `.OrganicText .OrganicTextContentSpan`.
"""

# INFRASTRUCTURE
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import TargetCommands

from _yandex_probe_report import write_report

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent.parent
REPORT_DIR = SCRIPT_DIR / "md"

SESSION_DIR = str(Path.home() / ".searxng-mcp" / "browser-session")
REAL_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

SEARCH_URL = "https://yandex.com/search/?text={}"
LATENCY_GATE_S = 5.0
MAX_WAIT_CYCLES = 20
WAIT_INTERVAL = 0.3

# Same query set as 26_brave_probe.py / 28_bing_probe.py (mixed axes, DE+EN)
QUERIES = [
    ("beste kaffeemaschine test", "mainstream-de"),
    ("python asyncio tutorial", "docs-en"),
    ("gebrauchte waschmaschine frankfurt", "local-biz-de"),
    ("hausgeräte händler frankfurt", "local-biz-de"),
    ("gebrauchtwagen ankauf frankfurt", "local-biz-de"),
    ("best noise cancelling headphones 2025", "mainstream-en"),
    ("how does DNS work", "docs-en"),
    ("fastapi websocket reconnect handler", "docs-en"),
    ("climate change carbon capture technology 2025", "mainstream-en"),
    ("Mietvertrag Kündigungsfrist gesetzliche Regelung", "docs-de"),
]

_JS_WAIT = "return document.querySelectorAll('li.serp-item').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('li.serp-item');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a.OrganicTitle-Link');
    var _snip = _c.querySelector('.OrganicText .OrganicTextContentSpan') || _c.querySelector('.OrganicText');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _a.textContent.trim(),
        snippet: _snip ? _snip.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var url = window.location.href.toLowerCase();
var markers = ['captcha', 'confirm you are not a robot', 'unusual activity',
               'smartcaptcha', 'подтвердите, что запросы', 'подозрительн', 'ты робот'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
var urlBlock = url.indexOf('showcaptcha') !== -1 || url.indexOf('checkcaptcha') !== -1 || url.indexOf('/captcha') !== -1;
return JSON.stringify({marker: hit, url_block: urlBlock, url: window.location.href, ready_state: document.readyState});
"""

_browser = None


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        for qi, (query, axis) in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] ({axis}) {query}", file=sys.stderr)
            t0 = time.monotonic()
            record = await run_query(query, axis)
            record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
            records.append(record)
            print(
                f"  -> {record['status']} | {record['count']} results | {record['elapsed_ms']}ms",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    report_path = write_report(records, REPORT_DIR, LATENCY_GATE_S)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    block_count = sum(1 for r in records if r["status"] == "BLOCKED")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= LATENCY_GATE_S * 1000)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {block_count}/{len(records)} BLOCKED, "
        f"{under_gate}/{len(records)} <= {LATENCY_GATE_S}s, longest clean run = {_longest_clean_run(records)}",
        file=sys.stderr,
    )


# FUNCTIONS

# Kill stale Chrome processes using our session dir
def _kill_stale_chrome() -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True)


# Build Chrome options matching the production stealth-browser shape
def _build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.headless = not os.environ.get("SEARXNG_HEADED")
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.block_popups = True
    options.block_notifications = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True
    options.add_argument(f"--user-agent={REAL_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    return options


# Get or create the shared browser + a fresh tab per query
async def _new_tab():
    global _browser
    if _browser is None:
        _kill_stale_chrome()
        _browser = Chrome(_build_options())
        await _browser.start()
    return await _browser.new_tab()


# Close a tab via browser-level Target.closeTarget
async def _kill_tab(tab) -> None:
    global _browser
    target_id = getattr(tab, "_target_id", None)
    if _browser is None or target_id is None:
        return
    try:
        await asyncio.wait_for(
            _browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0
        )
    except Exception as e:
        logging.warning("kill_tab failed (target_id=%s): %s", target_id, e)
    finally:
        _browser._tabs_opened.pop(target_id, None)


# Cleanup browser on shutdown
async def close_browser() -> None:
    global _browser
    if _browser is not None:
        await _browser.stop()
        _browser = None


# Extract primitive value from CDP execute_script result dict
def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


# Poll for result containers up to MAX_WAIT_CYCLES x WAIT_INTERVAL seconds, return True when found
async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


# Query DOM for li.serp-item containers and return result dicts (direct hrefs, no unwrap needed)
async def _parse_results(tab, max_results: int = 10) -> list[dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    try:
        items = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return [item for item in items[:max_results] if item.get("url")]


# Diagnose CAPTCHA/block trigger via title/body marker scan (EN + RU phrasing) + URL path check
async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "url_block": False, "url": "", "ready_state": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag


# Run one query end-to-end (new tab -> go_to -> wait/diagnose -> kill tab), return a data record
async def run_query(query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "samples": [], "diag": None,
    }
    tab = await _new_tab()
    try:
        await tab.go_to(SEARCH_URL.format(query.replace(" ", "+")), timeout=10.0)
        if await _wait_for_results(tab):
            results = await _parse_results(tab, max_results=10)
            record["count"] = len(results)
            record["status"] = "OK" if results else "EMPTY"
            record["samples"] = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")[:160]}
                for r in results[:5]
            ]
        else:
            diag = await _diagnose(tab)
            record["diag"] = diag
            record["status"] = "BLOCKED" if (diag["marker"] or diag["url_block"]) else "EMPTY"
    except Exception as e:
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        await _kill_tab(tab)
    return record


if __name__ == "__main__":
    asyncio.run(run_probe())
