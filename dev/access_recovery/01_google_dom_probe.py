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
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.commands import TargetCommands
from pydoll.commands.network_commands import NetworkCommands
from pydoll.protocol.network.types import CookieSameSite

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"
HTML_DIR = SCRIPT_DIR / "html"
QUERIES_PATH = SCRIPT_DIR / "queries.json"

SESSION_DIR = str(Path.home() / ".access_recovery" / "google-dom-probe-session")

SEARCH_URL = "https://www.google.com/search?q={}&hl={}&num={}"
CONSENT_DOMAIN = "consent.google.com"
CAPTCHA_PATH = "/sorry/"
MAX_WAIT_CYCLES = 3
WAIT_INTERVAL = 0.2
SOCS_NAME = "SOCS"
SOCS_VALUE = "CAISHAgCEhJnd3NfMjAyNjA0MDctMCAgIBgEIAEaBgiA_fC8Bg"
SOCS_DOMAIN = ".google.com"

# Production's own google rate limiter (src/search/engines/google.py:
# _limiters["google"] = RateLimiter(max_requests=4, window_seconds=60)) allows one request roughly
# every 15s in steady state. Pacing this probe's own navigations at the same interval means the
# probe's OWN traffic pattern cannot itself induce a rate-limit/anti-bot event that production's
# real pacing would not also risk — reusing an already-calibrated number instead of inventing one.
NAV_DELAY_S = 15.0

NUM_VARIANTS = [100, 10]

_JS_WAIT = "return document.querySelectorAll('div.MjjYud').length"

_JS_PARSE = """
var _cs = document.querySelectorAll('div.MjjYud');
var _out = [];
for (var _i = 0; _i < _cs.length; _i++) {
    var _c = _cs[_i];
    var _a = null;
    var _title = '';
    var _h3 = _c.querySelector('h3');
    var _lc = _c.querySelector('.LC20lb');
    if (_h3) {
        _title = _h3.textContent.trim();
        _a = _h3.closest('a[href^="http"]') || _h3.parentElement.querySelector('a[href^="http"]');
    }
    if (!_a && _lc) {
        if (!_title) { _title = _lc.textContent.trim(); }
        _a = _lc.closest('a[href^="http"]') || _lc.parentElement.querySelector('a[href^="http"]');
    }
    if (!_a) { _a = _c.querySelector('a[href^="http"]'); }
    if (!_title && _a) { _title = _a.textContent.trim(); }
    if (!_a || !_title) continue;
    var _snip = _c.querySelector('.wHYlTd') || _c.querySelector('.VwiC3b') || _c.querySelector('[data-sncf]') || _c.querySelector('.lEBKkf');
    _out.push({url: _a.href, title: _title, snippet: _snip ? _snip.textContent.trim() : ''});
}
return JSON.stringify(_out);
"""

_JS_CONSENT = """
var btn = document.querySelector('button[jsname="b3VHJd"]') ||
           document.querySelector('.lssxud') ||
           document.querySelector('form[action*="consent"] button[type="submit"]') ||
           document.querySelector('button[aria-label*="Accept"]');
if (btn) { btn.click(); return true; }
return false;
"""

_JS_INLINE_CONSENT_CHECK = (
    "var body = document.body ? document.body.innerText : ''; "
    "return body.indexOf('Before you continue') !== -1 || body.indexOf('cookies and data') !== -1;"
)

# Diagnostic pass — NOT part of google.py today. Runs whenever div.MjjYud containers are found,
# regardless of whether the current parse succeeds, and reports the structural evidence this
# milestone needs: does h3/.LC20lb still exist inside a container, how many http anchors sit
# inside it, what are its own immediate child tags, and a truncated outerHTML sample — enough for
# a later agent to read the saved raw HTML and pinpoint the replacement selector without
# re-running a browser.
_JS_DIAGNOSTIC = """
var _cs = document.querySelectorAll('div.MjjYud');
var _samples = [];
var _n = Math.min(_cs.length, 5);
for (var _i = 0; _i < _n; _i++) {
    var _c = _cs[_i];
    var _h3 = _c.querySelector('h3');
    var _lc = _c.querySelector('.LC20lb');
    var _httpAnchors = _c.querySelectorAll('a[href^="http"]');
    var _allAnchors = _c.querySelectorAll('a');
    var _childTags = [];
    for (var _j = 0; _j < _c.children.length; _j++) {
        var _el = _c.children[_j];
        var _cls = _el.className && typeof _el.className === 'string' ? '.' + _el.className.trim().split(/\\s+/).join('.') : '';
        _childTags.push(_el.tagName + _cls);
    }
    _samples.push({
        index: _i,
        has_h3: !!_h3,
        has_lc20lb: !!_lc,
        http_anchor_count: _httpAnchors.length,
        total_anchor_count: _allAnchors.length,
        child_tags: _childTags.join(' | '),
        outer_html_sample: _c.outerHTML.slice(0, 800)
    });
}
return JSON.stringify({
    container_count: _cs.length,
    page_wide_h3_count: document.querySelectorAll('h3').length,
    page_wide_http_anchor_count: document.querySelectorAll('a[href^="http"]').length,
    samples: _samples
});
"""

_JS_DIAGNOSE = """
return JSON.stringify({
    title: document.title,
    url: window.location.href,
    ready_state: document.readyState
});
"""

_browser = None


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

    report_path = write_report(records, run_ts, html_run_dir)
    outcome_counts = _count_outcomes(records)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Outcomes: {outcome_counts}", file=sys.stderr)


# FUNCTIONS

def _load_queries() -> list[dict]:
    with open(QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _kill_stale_chrome() -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True)


def _build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.block_popups = True
    options.block_notifications = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    return options


def _open_background_process_creator(command: list[str]):
    import subprocess as _sp
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", "Google Chrome", "--args", *args]
    return _sp.Popen(open_cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)


async def _new_tab():
    global _browser
    if _browser is None:
        _kill_stale_chrome()
        from pydoll.browser.managers import BrowserProcessManager
        _browser = Chrome(_build_options())
        _browser._browser_process_manager = BrowserProcessManager(
            process_creator=_open_background_process_creator
        )
        await _browser.start()
    return await _browser.new_tab()


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


async def close_browser() -> None:
    global _browser
    if _browser is not None:
        await _browser.stop()
        _browser = None


def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def _inject_socs_cookie(tab) -> None:
    await tab._execute_command(NetworkCommands.set_cookie(
        name=SOCS_NAME, value=SOCS_VALUE, domain=SOCS_DOMAIN, path="/",
        secure=True, same_site=CookieSameSite.LAX,
    ))


async def _has_inline_consent(tab) -> bool:
    raw = await tab.execute_script(_JS_INLINE_CONSENT_CHECK)
    return bool(_extract_value(raw))


async def _handle_consent(tab) -> None:
    await tab.execute_script(_JS_CONSENT)


async def _wait_for_results(tab) -> tuple[bool, int]:
    count = 0
    for _ in range(MAX_WAIT_CYCLES):
        raw = await tab.execute_script(_JS_WAIT)
        val = _extract_value(raw)
        count = int(val) if val else 0
        if count > 0:
            return True, count
        await asyncio.sleep(WAIT_INTERVAL)
    return False, count


def _clean_url(href: str) -> str:
    if not href:
        return ""
    if "/url?" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        return qs.get("q", [href])[0]
    return href


async def _parse_results(tab) -> list[dict]:
    raw = await tab.execute_script(_JS_PARSE)
    value = _extract_value(raw)
    if not value:
        return []
    items = json.loads(value)
    out = []
    for item in items:
        url = _clean_url(item.get("url", ""))
        if not url:
            continue
        out.append({"url": url, "title": item.get("title", ""), "snippet": item.get("snippet", "")})
    return out


async def _diagnostic_scan(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSTIC)
    val = _extract_value(raw)
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return {}


async def _diagnose(tab) -> dict:
    raw = await tab.execute_script(_JS_DIAGNOSE)
    val = _extract_value(raw)
    diag = {"title": "", "url": "", "ready_state": ""}
    if val:
        try:
            diag.update(json.loads(val))
        except (json.JSONDecodeError, TypeError):
            pass
    return diag


async def run_navigation(query: str, axis: str, num: int, html_run_dir: Path) -> dict:
    record: dict = {
        "query": query, "axis": axis, "num": num, "outcome": "ERROR",
        "count": 0, "samples": [], "containers_count": None, "diagnostic": None,
        "landed_url": None, "error": None,
    }
    t0 = time.monotonic()
    tab = await _new_tab()
    try:
        await _inject_socs_cookie(tab)
        search_url = SEARCH_URL.format(quote_plus(query), "en", num)
        await tab.go_to(search_url, timeout=10.0)
        current = await tab.current_url
        if CONSENT_DOMAIN in current or await _has_inline_consent(tab):
            await _handle_consent(tab)
            await tab.go_to(search_url, timeout=10.0)
            current = await tab.current_url
        record["landed_url"] = current

        if CAPTCHA_PATH in current:
            record["outcome"] = "BLOCKED"
            diag = await _diagnose(tab)
            record["diagnose"] = diag
        else:
            found, containers_count = await _wait_for_results(tab)
            record["containers_count"] = containers_count
            if not found:
                record["outcome"] = "NO_CONTAINERS"
                record["diagnose"] = await _diagnose(tab)
            else:
                record["diagnostic"] = await _diagnostic_scan(tab)
                results = await _parse_results(tab)
                record["count"] = len(results)
                record["samples"] = results[:5]
                record["outcome"] = "OK" if results else "EMPTY_PARSED"

        html = await tab.execute_script("return document.documentElement.outerHTML")
        html_val = _extract_value(html)
        if html_val:
            slug = _slugify(query)
            (html_run_dir / f"{slug}_num{num}.html").write_text(html_val, encoding="utf-8")
        if record.get("diagnostic"):
            slug = _slugify(query)
            (html_run_dir / f"{slug}_num{num}_diagnostic.json").write_text(
                json.dumps(record["diagnostic"], indent=2), encoding="utf-8"
            )
    except Exception as e:
        record["outcome"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        await _kill_tab(tab)
    record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    return record


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60]


def _count_outcomes(records: list[dict]) -> dict:
    counts = {"OK": 0, "EMPTY_PARSED": 0, "NO_CONTAINERS": 0, "BLOCKED": 0, "ERROR": 0}
    for r in records:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return counts


def write_report(records: list[dict], run_ts: str, html_run_dir: Path) -> Path:
    path = REPORT_DIR / f"google_dom_probe_{run_ts}.md"
    by_num = {n: [r for r in records if r["num"] == n] for n in NUM_VARIANTS}
    counts = _count_outcomes(records)

    lines = [
        f"# Google DOM Path Probe (Path A) — {run_ts}",
        "",
        "Reproduces src/search/engines/google.py's exact current selectors (div.MjjYud / h3 / "
        ".LC20lb / closest a[href^=\"http\"]) against real live Google navigations, self-contained "
        "(no src/ import), pydoll stealth stack matching src/search/browser.py's shape exactly — "
        "no extra stealth beyond what production has, so this measures production's own failure, "
        "not a more-stealthed setup's success.",
        "",
        f"**Queries:** {len(by_num[NUM_VARIANTS[0]])} (see `dev/access_recovery/queries.json`, "
        "shared with the Path B probe) — the same 10-query, axis-tagged set "
        "`dev/search_pipeline/26_brave_probe.py` uses.",
        f"**Navigations:** {len(records)} total ({len(NUM_VARIANTS)} num-variants x "
        f"{len(by_num[NUM_VARIANTS[0]])} queries).",
        f"**Pacing:** {NAV_DELAY_S}s between every individual navigation (not just every query) — "
        "matched to production's own google rate limiter "
        "(`RateLimiter(max_requests=4, window_seconds=60)` in `src/search/engines/google.py`, "
        "~15s/request in steady state), so this probe's own traffic pattern cannot induce a "
        "rate-limit event production's real pacing would not also risk. See "
        "`process-docs/engine_expansion/brave_reeval_2026-07-21.md` for why this matters — a "
        "prior probe with no inter-query delay measured a block, not the thing it was built to "
        "measure.",
        "",
        "## Outcome counts (all navigations)",
        "",
        f"- **OK** (real results extracted): {counts['OK']}",
        f"- **EMPTY_PARSED** (containers found, title/url extraction found zero — the production "
        f"failure shape this milestone exists to explain): {counts['EMPTY_PARSED']}",
        f"- **NO_CONTAINERS** (div.MjjYud never appeared): {counts['NO_CONTAINERS']}",
        f"- **BLOCKED** (landed on /sorry/): {counts['BLOCKED']}",
        f"- **ERROR**: {counts['ERROR']}",
        "",
        "## num=100 vs num=10",
        "",
    ]

    for num in NUM_VARIANTS:
        recs = by_num[num]
        c = _count_outcomes(recs)
        lines.append(f"**num={num}** ({len(recs)} navigations): OK={c['OK']}, "
                      f"EMPTY_PARSED={c['EMPTY_PARSED']}, NO_CONTAINERS={c['NO_CONTAINERS']}, "
                      f"BLOCKED={c['BLOCKED']}, ERROR={c['ERROR']}")
    lines.append("")

    lines += [
        "## Per-navigation results",
        "",
        "| # | num | Axis | Query | Outcome | Containers | Count | Elapsed ms |",
        "|---|-----|------|-------|---------|------------|-------|------------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:40].replace("|", "\\|")
        lines.append(
            f"| {i} | {r['num']} | {r['axis']} | {q} | {r['outcome']} | "
            f"{r.get('containers_count')} | {r['count']} | {r['elapsed_ms']} |"
        )
    lines.append("")

    ok_recs = [r for r in records if r["outcome"] == "OK"]
    if ok_recs:
        lines += ["## OK samples (quality eyeball)", ""]
        for r in ok_recs:
            lines.append(f"### num={r['num']} — {r['query']} ({r['axis']}) — {r['count']} results")
            lines.append("")
            for s in r["samples"]:
                lines.append(f"- **{s['title']}** — {s['url']}")
            lines.append("")

    empty_recs = [r for r in records if r["outcome"] == "EMPTY_PARSED"]
    if empty_recs:
        lines += [
            "## EMPTY_PARSED diagnostic evidence",
            "",
            "For each: container_count / page-wide h3 count / page-wide http-anchor count, then "
            "per-sampled-container has_h3 / has_lc20lb / http_anchor_count / child_tags. Full "
            f"outerHTML samples and raw page HTML saved under `dev/access_recovery/html/"
            f"google_dom_probe_{run_ts}/` (gitignored — local evidence, not carried in the repo).",
            "",
        ]
        for r in empty_recs:
            d = r.get("diagnostic") or {}
            lines.append(f"### num={r['num']} — {r['query']} ({r['axis']})")
            lines.append("")
            lines.append(
                f"- container_count={d.get('container_count')}, "
                f"page_wide_h3_count={d.get('page_wide_h3_count')}, "
                f"page_wide_http_anchor_count={d.get('page_wide_http_anchor_count')}"
            )
            for s in d.get("samples", []):
                lines.append(
                    f"- sample[{s['index']}]: has_h3={s['has_h3']}, has_lc20lb={s['has_lc20lb']}, "
                    f"http_anchor_count={s['http_anchor_count']}, "
                    f"total_anchor_count={s['total_anchor_count']}"
                )
                lines.append(f"  - child_tags: `{s['child_tags']}`")
            lines.append("")

    blocked_recs = [r for r in records if r["outcome"] == "BLOCKED"]
    if blocked_recs:
        lines += ["## BLOCKED details", ""]
        for r in blocked_recs:
            lines.append(f"- num={r['num']} — {r['query']} ({r['axis']}) — landed_url: "
                         f"`{r.get('landed_url')}`")
        lines.append("")

    error_recs = [r for r in records if r["outcome"] == "ERROR"]
    if error_recs:
        lines += ["## ERROR details", ""]
        for r in error_recs:
            lines.append(f"- num={r['num']} — {r['query']} ({r['axis']}) — `{r.get('error')}`")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    asyncio.run(run_probe())
