#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.browser import new_tab, close_browser
from src.cdp_value import extract_value
from src.search.engines.google import (
    _inject_socs_cookie, _build_url, _wait_for_results,
)

REPORT_DIR = SCRIPT_DIR / "md"
QUERY = "python asyncio"
NUM = 100

_JS_COUNTS = """
var c = {};

// Current production selector
c.rso_h3 = document.querySelectorAll('#rso h3').length;

// Classic / modern organic result containers
c.div_g            = document.querySelectorAll('div.g').length;
c.div_MjjYud       = document.querySelectorAll('div.MjjYud').length;
c.div_hveid        = document.querySelectorAll('div[data-hveid]').length;
c.rso_direct_div   = document.querySelectorAll('#rso > div').length;

// #rso > div that contain at least one h3
var _rsoD = document.querySelectorAll('#rso > div');
var _rsoH3 = 0;
for (var _i = 0; _i < _rsoD.length; _i++) {
    if (_rsoD[_i].querySelector('h3')) _rsoH3++;
}
c.rso_div_with_h3 = _rsoH3;

// All h3 on the full page
c.page_h3_total = document.querySelectorAll('h3').length;

// h3 anywhere that has a reachable external ancestor/descendant link
var _allH3 = document.querySelectorAll('h3');
var _linked = 0;
for (var _j = 0; _j < _allH3.length; _j++) {
    var _h = _allH3[_j];
    var _blk = _h.closest('.MjjYud') || _h.closest('#rso > div') || _h.parentElement;
    var _a   = _h.closest('a[href^="http"]') || (_blk ? _blk.querySelector('a[href^="http"]') : null);
    if (_a && _a.href.indexOf('google.com') === -1) _linked++;
}
c.h3_with_external_link = _linked;

// div.g that contain an external link
var _dg = document.querySelectorAll('div.g');
var _dgExt = 0;
for (var _k = 0; _k < _dg.length; _k++) {
    var _a2 = _dg[_k].querySelector('a[href^="http"]');
    if (_a2 && _a2.href.indexOf('google.com') === -1) _dgExt++;
}
c.div_g_with_external_link = _dgExt;

// Total external links anywhere on page (non-google.com / non-gstatic)
var _allA = document.querySelectorAll('a[href^="http"]');
var _extA = 0;
for (var _l = 0; _l < _allA.length; _l++) {
    var _hr = _allA[_l].href;
    if (_hr.indexOf('google.com') === -1 && _hr.indexOf('gstatic.com') === -1) _extA++;
}
c.external_links_total = _extA;

// Special SERP feature containers
c.featured_snippet  = document.querySelectorAll('.g-blk, .xpdopen, .ULSxyf, .IVvPP, .ifM9O').length;
c.knowledge_panel   = document.querySelectorAll('.kp-wholepage, #rhs .kp-blk, .osrp-blk').length;
c.people_also_ask   = document.querySelectorAll('.related-question-pair, [jsname="Cpkphb"], .g4LTO, .HwtpBd').length;

return JSON.stringify(c);
"""

_JS_STRUCTURE = """
var _h3s = document.querySelectorAll('#rso h3');
var _out = [];
for (var _i = 0; _i < Math.min(_h3s.length, 6); _i++) {
    var _h = _h3s[_i];
    var _blk = _h.closest('.MjjYud') || _h.closest('#rso > div') || _h.parentElement;
    var _a   = _h.closest('a[href^="http"]') || (_blk ? _blk.querySelector('a[href^="http"]') : null);
    _out.push({
        title:       _h.textContent.trim().slice(0, 60),
        has_MjjYud:  !!_h.closest('.MjjYud'),
        has_rso_div: !!_h.closest('#rso > div'),
        parent_tag:  _h.parentElement ? _h.parentElement.tagName : null,
        link:        _a ? _a.href.slice(0, 80) : null,
    });
}
return JSON.stringify(_out);
"""


# ORCHESTRATOR

async def run_probe() -> None:
    _configure_logging()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    url = _build_url(QUERY, "en", NUM)
    _print_url(url)
    probed = await _probe_page(url)
    if probed is None:
        return
    counts, structure = probed

    report_path = write_report(counts, structure, url)
    _print_report(report_path)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _print_url(url):
    print(f"URL: {url}", file=sys.stderr)


async def _probe_page(url):
    tab = await new_tab()
    try:
        await _inject_socs_cookie(tab)
        await tab.go_to(url, timeout=20)
        if not await _wait_for_results(tab):
            print("ERROR: no results loaded", file=sys.stderr)
            return None
        counts = await read_counts(tab)
        structure = await read_structure(tab)
    finally:
        await tab.close()
        await close_browser()
    return counts, structure


def write_report(counts: dict, structure: list, url: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"google_selector_probe_{ts}.md"
    hypothesis, detail = diagnose(counts)

    lines = _render_dom_counts(counts, ts, url)
    lines += _render_structure(structure)
    lines += _render_hypothesis(hypothesis, detail)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _print_report(report_path):
    print(f"Report: {report_path}", file=sys.stderr)


async def read_counts(tab) -> dict:
    raw = await tab.execute_script(_JS_COUNTS)
    val = extract_value(raw)
    if not val:
        return {}
    return json.loads(val)


async def read_structure(tab) -> list:
    raw = await tab.execute_script(_JS_STRUCTURE)
    val = extract_value(raw)
    if not val:
        return []
    return json.loads(val)


def diagnose(counts: dict) -> tuple[str, str]:
    rso_h3   = counts.get("rso_h3", 0)
    div_g    = counts.get("div_g", 0)
    div_mjj  = counts.get("div_MjjYud", 0)
    ext_tot  = counts.get("external_links_total", 0)
    div_g_ext = counts.get("div_g_with_external_link", 0)
    h3_linked = counts.get("h3_with_external_link", 0)

    if div_g_ext > rso_h3 + 3 or div_mjj > rso_h3 + 3:
        label = "A — selector `#rso h3` captures only a subset; more organic results exist in DOM"
        detail = (
            f"`div.g` contains {div_g_ext} organic results vs `#rso h3` finding {rso_h3}. "
            f"`div.MjjYud` = {div_mjj}. "
            f"Switching the parse walk to `div.MjjYud` or `div.g` as the result-block root "
            f"would yield ~{max(div_g_ext, div_mjj)} results per call."
        )
    elif ext_tot < 15:
        label = "B — Google caps organics server-side at ~10-11 regardless of num= value"
        detail = (
            f"External link total = {ext_tot} — too low to hide hidden results. "
            "Google is simply not rendering more organic entries for this query at this fingerprint level."
        )
    else:
        label = "C — JS scope issue: h3 elements exist but are outside `#rso`"
        detail = (
            f"Page has {counts.get('page_h3_total', 0)} h3 total; {h3_linked} h3 with external links; "
            f"but `#rso h3` only sees {rso_h3}. Results live in a different DOM branch."
        )
    return label, detail


def _render_dom_counts(counts: dict, ts: str, url: str) -> list[str]:
    LABELS = [
        ("rso_h3",                   "`#rso h3` — current parse selector"),
        ("div_g",                    "`div.g` — classic organic container"),
        ("div_MjjYud",               "`div.MjjYud` — modern result wrapper"),
        ("div_hveid",                "`div[data-hveid]` — result attribute"),
        ("rso_direct_div",           "`#rso > div` — direct RSO children"),
        ("rso_div_with_h3",          "`#rso > div` containing an h3"),
        ("page_h3_total",            "All `h3` on page"),
        ("h3_with_external_link",    "`h3` with a reachable external link"),
        ("div_g_with_external_link", "`div.g` with external link child"),
        ("external_links_total",     "External `<a>` total (non-google.com)"),
        ("featured_snippet",         "Featured snippet containers"),
        ("knowledge_panel",          "Knowledge Panel containers"),
        ("people_also_ask",          "People Also Ask containers"),
    ]

    lines = [
        f"# Google DOM Selector Probe — {ts}",
        "",
        f"**Query:** `{QUERY}`  **num=:** `{NUM}`",
        f"**URL:** `{url}`",
        "",
        "## DOM Counts",
        "",
        "| Selector / Metric | Count |",
        "|-------------------|-------|",
    ]
    for key, label in LABELS:
        lines.append(f"| {label} | {counts.get(key, 'N/A')} |")
    return lines


def _render_structure(structure: list) -> list[str]:
    lines = [
        "",
        "## First-6 `#rso h3` Structure",
        "",
        "| # | Title | has MjjYud | has #rso>div | parent tag | link (80ch) |",
        "|---|-------|------------|--------------|------------|-------------|",
    ]
    for i, s in enumerate(structure, 1):
        link = (s.get("link") or "")[:80]
        lines.append(
            f"| {i} | {s.get('title','')} | {s.get('has_MjjYud')} | "
            f"{s.get('has_rso_div')} | {s.get('parent_tag')} | {link} |"
        )
    return lines


def _render_hypothesis(hypothesis: str, detail: str) -> list[str]:
    return [
        "",
        "## Hypothesis",
        "",
        f"**Dominant cause:** {hypothesis}",
        "",
        detail,
    ]


if __name__ == "__main__":
    asyncio.run(run_probe())
