#!/usr/bin/env python3
"""Path A probe — does Google's own results page still work through OUR browser's DOM path?

Reproduces src/search/engines/google.py's exact current selectors (div.MjjYud containers, h3/
.LC20lb title, closest a[href^="http"]) against real live Google navigations, run through a
self-contained pydoll stealth browser matching src/search/browser.py's own shape (--disable-
blink-features=AutomationControlled, webrtc_leak_protection, the three BACKGROUNDING_FLAGS,
open -g -n headed-backgrounded launch — no extra stealth beyond what production actually has, on
purpose: this probe measures why PRODUCTION fails, not whether a more-stealthed setup would
succeed). SOCS consent cookie + inline-consent click-through are also copied verbatim, so a
probe-only consent wall cannot masquerade as a DOM break or a block.

Launch/watchdog/teardown go through dev/_lib/browser_launch.py (dev-wide shared helper, see its own
DOCS.md) — `open -g` alone only suppresses activation at the launch moment, so the helper also runs
a PID-keyed focus-steal reclaim watchdog for this probe's whole run.

Self-contained: does NOT import src/ (dev-script isolation, matching dev/search_pipeline/
26_brave_probe.py's own convention) — the selectors, cookie injection, and consent handling below
are a COPY of google.py's shape as it stood 2026-09-15, not a shared import; this probe keeps
measuring even after src/ changes.

Every query runs TWO navigations, in fresh tabs: num=100 (today's production URL) and num=10 (the
num=100-deprecation hypothesis from external SEO-industry reporting, handed to this milestone as
fact, not verified in code here — this probe is what verifies it against a live page).

Outcomes are classified into FOUR states per navigation, not collapsed into "empty":
  BLOCKED       - landed on the /sorry/ CAPTCHA path. A rate-limit/anti-bot event, not a DOM break.
  NO_CONTAINERS - div.MjjYud never appeared within the wait budget.
  EMPTY_PARSED  - div.MjjYud appeared (containers_found=true) but title/url extraction found zero
                  results — the exact production failure shape this milestone exists to explain.
  OK            - real results extracted.
Collapsing BLOCKED into EMPTY_PARSED would make a rate-limited run look like a DOM break and draw
the wrong conclusion from this probe — see process-docs/engine_expansion/brave_reeval_2026-07-21.md
for a real prior case of exactly that measurement failure mode (10 back-to-back queries, no delay,
4 clean then 6 read as failures that were actually a PoW gate).

Pacing: NAV_DELAY_S seconds between every individual navigation (not just every query) — see the
constant below for the exact value and why.
"""

# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from _browser import new_tab, kill_tab, close_browser
from _dom import (
    CONSENT_DOMAIN, CAPTCHA_PATH, extract_value, inject_socs_cookie, has_inline_consent,
    accept_consent, wait_for_results, parse_results, diagnostic_scan, diagnose,
)
from _report import write_report, count_outcomes

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"
HTML_DIR = SCRIPT_DIR / "html"
QUERIES_PATH = SCRIPT_DIR / "queries.json"

SEARCH_URL = "https://www.google.com/search?q={}&hl={}&num={}"

# Production's own google rate limiter (src/search/engines/google.py:
# _limiters["google"] = RateLimiter(max_requests=4, window_seconds=60)) allows one request roughly
# every 15s in steady state. Pacing this probe's own navigations at the same interval means the
# probe's OWN traffic pattern cannot itself induce a rate-limit/anti-bot event that production's
# real pacing would not also risk — reusing an already-calibrated number instead of inventing one.
NAV_DELAY_S = 15.0

NUM_VARIANTS = [100, 10]


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    queries = _load_queries()
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_run_dir = HTML_DIR / f"google_dom_probe_{run_ts}"
    html_run_dir.mkdir(parents=True, exist_ok=True)

    records = []
    nav_index = 0
    total_navs = len(queries) * len(NUM_VARIANTS)
    try:
        for qi, q in enumerate(queries):
            for num in NUM_VARIANTS:
                nav_index += 1
                print(f"[{nav_index}/{total_navs}] num={num} ({q['axis']}) {q['query']}", file=sys.stderr)
                record = await run_navigation(q["query"], q["axis"], num, html_run_dir)
                records.append(record)
                print(
                    f"  -> {record['outcome']} | {record['count']} results | "
                    f"containers={record.get('containers_count')} | {record['elapsed_ms']}ms",
                    file=sys.stderr,
                )
                if nav_index < total_navs:
                    print(f"  (pacing {NAV_DELAY_S}s before next navigation)", file=sys.stderr)
                    await asyncio.sleep(NAV_DELAY_S)
    finally:
        await close_browser()

    report_path = write_report(records, run_ts, html_run_dir, REPORT_DIR, NUM_VARIANTS, NAV_DELAY_S)
    outcome_counts = count_outcomes(records)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Outcomes: {outcome_counts}", file=sys.stderr)


# FUNCTIONS

def _load_queries() -> list[dict]:
    with open(QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60]


async def _navigate_with_consent(tab, search_url: str) -> str:
    await tab.go_to(search_url, timeout=10.0)
    current = await tab.current_url
    if CONSENT_DOMAIN in current or await has_inline_consent(tab):
        await accept_consent(tab)
        await tab.go_to(search_url, timeout=10.0)
        current = await tab.current_url
    return current


async def _classify_navigation(tab, record: dict, current: str) -> None:
    if CAPTCHA_PATH in current:
        record["outcome"] = "BLOCKED"
        record["diagnose"] = await diagnose(tab)
    else:
        found, containers_count = await wait_for_results(tab)
        record["containers_count"] = containers_count
        if not found:
            record["outcome"] = "NO_CONTAINERS"
            record["diagnose"] = await diagnose(tab)
        else:
            record["diagnostic"] = await diagnostic_scan(tab)
            results = await parse_results(tab)
            record["count"] = len(results)
            record["samples"] = results[:5]
            record["outcome"] = "OK" if results else "EMPTY_PARSED"


async def _save_navigation_artifacts(tab, record: dict, query: str, num: int, html_run_dir: Path) -> None:
    html = await tab.execute_script("return document.documentElement.outerHTML")
    html_val = extract_value(html)
    if html_val:
        slug = _slugify(query)
        (html_run_dir / f"{slug}_num{num}.html").write_text(html_val, encoding="utf-8")
    if record.get("diagnostic"):
        slug = _slugify(query)
        (html_run_dir / f"{slug}_num{num}_diagnostic.json").write_text(
            json.dumps(record["diagnostic"], indent=2), encoding="utf-8"
        )


async def run_navigation(query: str, axis: str, num: int, html_run_dir: Path) -> dict:
    record: dict = {
        "query": query, "axis": axis, "num": num, "outcome": "ERROR",
        "count": 0, "samples": [], "containers_count": None, "diagnostic": None,
        "landed_url": None, "error": None,
    }
    t0 = time.monotonic()
    tab = await new_tab()
    try:
        await inject_socs_cookie(tab)
        search_url = SEARCH_URL.format(quote_plus(query), "en", num)
        current = await _navigate_with_consent(tab, search_url)
        record["landed_url"] = current
        await _classify_navigation(tab, record, current)
        await _save_navigation_artifacts(tab, record, query, num, html_run_dir)
    except Exception as e:
        record["outcome"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        await kill_tab(tab)
    record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    return record


if __name__ == "__main__":
    asyncio.run(run_probe())
