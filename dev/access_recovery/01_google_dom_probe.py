#!/usr/bin/env python3
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

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"
HTML_DIR = SCRIPT_DIR / "html"
QUERIES_PATH = SCRIPT_DIR / "queries.json"

SEARCH_URL = "https://www.google.com/search?q={}&hl={}&num={}"

NAV_DELAY_S = 15.0

NUM_VARIANTS = [100, 10]


# ORCHESTRATOR

async def run_probe() -> None:
    _configure_logging()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    queries = _load_queries()
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_run_dir = _compute_html_run_dir(run_ts)
    html_run_dir.mkdir(parents=True, exist_ok=True)

    total_navs = _compute_total_navs(queries)
    records = await _run_navigations(queries, total_navs, html_run_dir)

    report_path = write_report(records, run_ts, REPORT_DIR, NUM_VARIANTS, NAV_DELAY_S)
    outcome_counts = count_outcomes(records)
    _print_report(report_path, outcome_counts)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _load_queries() -> list[dict]:
    with open(QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _compute_html_run_dir(run_ts):
    html_run_dir = HTML_DIR / f"google_dom_probe_{run_ts}"
    return html_run_dir


def _compute_total_navs(queries):
    total_navs = len(queries) * len(NUM_VARIANTS)
    return total_navs


async def _run_navigations(queries, total_navs, html_run_dir):
    nav_index = 0
    records = []
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
    return records


def _print_report(report_path, outcome_counts):
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Outcomes: {outcome_counts}", file=sys.stderr)


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


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60]


if __name__ == "__main__":
    asyncio.run(run_probe())
