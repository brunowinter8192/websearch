#!/usr/bin/env python3
"""Startpage go/no-go probe — empirically checks scrapeability of startpage.com from this IP.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Historical note: Startpage was dropped previously at "0/30 results, root cause unclear".
Empirical finding here: a direct GET to /sp/search?query=... (no prior homepage visit) returns
a degraded empty shell with zero organic results and NO captcha/block marker — the request is
missing the per-session `sc` token embedded in the homepage's search form. That silent-empty
behavior is the most likely explanation for the historical 0/30. This probe instead drives the
real homepage search form (load homepage -> set #q -> click .search-btn) to get a valid session
token, then measures actual result count/quality/block behavior per query.
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

from _startpage_probe_report import write_report

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent.parent
REPORT_DIR = SCRIPT_DIR / "md"

SESSION_DIR = str(Path.home() / ".searxng-mcp" / "browser-session")
REAL_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.7680.154 Safari/537.36"
)

HOME_URL = "https://www.startpage.com/"
EXPECTED_RESULT_PATH = "/sp/search"
MAX_WAIT_CYCLES = 25
WAIT_INTERVAL = 0.3
INTER_QUERY_DELAY_S = 2.0

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

_JS_WAIT = "return document.querySelectorAll('div.result').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div.result');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = _c.querySelector('a.result-title');
    var _h2 = _c.querySelector('h2.wgl-title');
    var _desc = _c.querySelector('p.description');
    if (!_a || !_a.href) continue;
    _out.push({
        url: _a.href,
        title: _h2 ? _h2.textContent.trim() : (_a.textContent || '').trim(),
        snippet: _desc ? _desc.textContent.trim() : ''
    });
}
return JSON.stringify(_out);
"""

_JS_DIAGNOSE = """
var body = document.body ? document.body.innerText.toLowerCase() : '';
var title = document.title.toLowerCase();
var markers = ['captcha', 'unusual traffic', 'verify you are human', 'are you a robot',
               'access denied', 'checking your browser', 'temporarily blocked',
               'too many requests', 'rate limit exceeded', 'automated queries'];
var hit = null;
for (var _i = 0; _i < markers.length; _i++) {
    if (body.indexOf(markers[_i]) !== -1 || title.indexOf(markers[_i]) !== -1) { hit = markers[_i]; break; }
}
var iframeChallenge = document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="challenge"]');
return JSON.stringify({
    marker: hit,
    iframe_challenge: !!iframeChallenge,
    title: document.title,
    url: window.location.href,
    body_len: body.length
});
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
            if qi < len(QUERIES) - 1:
                await asyncio.sleep(INTER_QUERY_DELAY_S)
    finally:
        await close_browser()

    report_path = write_report(records, REPORT_DIR)
    ok_count = sum(1 for r in records if r["status"] == "OK")
    block_count = sum(1 for r in records if r["status"] == "BLOCKED")
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(
        f"Result: {ok_count}/{len(records)} OK, {block_count}/{len(records)} BLOCKED, "
        f"{len(records) - ok_count - block_count}/{len(records)} other",
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


# Drive the real homepage search form (native-setter input + real button click) to obtain
# a valid per-session `sc` token; a direct GET to /sp/search?query=... skips this token and
# silently returns zero results (empirically verified — see module docstring).
async def _submit_search(tab, query: str) -> None:
    await tab.go_to(HOME_URL, timeout=10.0)
    await asyncio.sleep(1.5)
    js_set_query = f"""
    var inp = document.querySelector('#q');
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(inp, {json.dumps(query)});
    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
    """
    await tab.execute_script(js_set_query)
    await asyncio.sleep(0.3)
    await tab.execute_script("document.querySelector('button.search-btn').click();")


# Poll for result containers up to MAX_WAIT_CYCLES x WAIT_INTERVAL seconds, return True when found
async def _wait_for_results(tab) -> bool:
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        count = _extract_value(raw)
        if count and int(count) > 0:
            return True
        await asyncio.sleep(WAIT_INTERVAL)
    return False


# Query DOM for div.result containers and return result dicts
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


# Diagnose why Startpage returned zero div.result — distinguishes explicit block/captcha
# markers from a bare degraded-shell page (loaded, no marker, no results, wrong URL path)
async def _diagnose_empty(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"marker": None, "iframe_challenge": False, "title": "", "url": "", "body_len": 0}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    if diag["marker"] or diag["iframe_challenge"]:
        diag["reason"] = "BLOCK_MARKER"
    elif EXPECTED_RESULT_PATH not in diag.get("url", ""):
        diag["reason"] = "WRONG_PATH_SHELL"
    else:
        diag["reason"] = "NO_CONTAINER"
    return diag


# Run one query end-to-end, return a data record for the report
async def run_query(query: str, axis: str) -> dict:
    record: dict = {
        "query": query, "axis": axis, "count": 0, "status": "EMPTY",
        "samples": [], "diag": None,
    }
    tab = await _new_tab()
    try:
        await _submit_search(tab, query)
        if await _wait_for_results(tab):
            results = await _parse_results(tab, max_results=10)
            record["count"] = len(results)
            record["status"] = "OK" if results else "EMPTY"
            record["samples"] = [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")[:160]}
                for r in results[:5]
            ]
        else:
            diag = await _diagnose_empty(tab)
            record["diag"] = diag
            record["status"] = "BLOCKED" if diag["reason"] == "BLOCK_MARKER" else "EMPTY"
    except Exception as e:
        record["status"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        await _kill_tab(tab)
    return record


if __name__ == "__main__":
    asyncio.run(run_probe())
