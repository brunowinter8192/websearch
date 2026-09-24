#!/usr/bin/env python3
# INFRASTRUCTURE
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus

from curl_cffi import requests
from lxml import html as lhtml

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"
WML_DIR = SCRIPT_DIR / "wml"
QUERIES_PATH = SCRIPT_DIR / "queries.json"

WML_URL = "https://www.google.com/wml/search?q={}&hl=en"
NOKIA_UA = "Nokia7610/2.0 (5.0509.0) SymbianOS/7.0s Series60/2.1 Profile/MIDP-2.0 Configuration/CLDC-1.0"
IMPERSONATE = "chrome99_android"
TIMEOUT_S = 15.0

NAV_DELAY_S = 5.0

_BLOCK_MARKERS = (
    "detected unusual traffic",
    "unusual traffic from your computer",
    "/sorry/",
    "our systems have detected unusual traffic",
    "captcha",
)

_CONTAINER_XPATH = '//div[contains(@class, "zMzFAb")]'
_TITLE_XPATH = './/a[contains(@class, "fuLhoc")]//span[contains(@class, "CVA68e")]'
_URL_XPATH = './/a[contains(@class, "fuLhoc")]/@href'
_SNIPPET_XPATH = './/div[contains(@class, "taTFJ")]//span[contains(@class, "FrIlee")]'


# ORCHESTRATOR

def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    queries = _load_queries()
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    wml_run_dir = WML_DIR / f"google_wml_probe_{run_ts}"
    wml_run_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for qi, q in enumerate(queries):
        print(f"[{qi + 1}/{len(queries)}] ({q['axis']}) {q['query']}", file=sys.stderr)
        record = run_query(q["query"], q["axis"], wml_run_dir)
        records.append(record)
        print(
            f"  -> {record['outcome']} | status={record['status_code']} | "
            f"{record['count']} results | {record['elapsed_ms']}ms",
            file=sys.stderr,
        )
        if qi < len(queries) - 1:
            print(f"  (pacing {NAV_DELAY_S}s before next request)", file=sys.stderr)
            time.sleep(NAV_DELAY_S)

    report_path = write_report(records, run_ts)
    counts = _count_outcomes(records)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Outcomes: {counts}", file=sys.stderr)


# FUNCTIONS

def _load_queries() -> list[dict]:
    with open(QUERIES_PATH, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _clean_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("/url?"):
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        return qs.get("q", [href])[0]
    return href


def _parse_results(body: str) -> tuple[int, list, list]:
    doc = lhtml.fromstring(body)
    containers = doc.xpath(_CONTAINER_XPATH)
    results = []
    for c in containers:
        title_els = c.xpath(_TITLE_XPATH)
        url_els = c.xpath(_URL_XPATH)
        snip_els = c.xpath(_SNIPPET_XPATH)
        if not title_els or not url_els:
            continue
        url = _clean_url(url_els[0])
        if not url:
            continue
        title = title_els[0].text_content().strip()
        snippet = snip_els[0].text_content().strip() if snip_els else ""
        results.append({"url": url, "title": title, "snippet": snippet})
    return len(containers), results, containers


def _detect_block(status_code: int, body: str) -> bool:
    if status_code != 200:
        return True
    lower = body.lower()
    return any(marker in lower for marker in _BLOCK_MARKERS)


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60]


def run_query(query: str, axis: str, wml_run_dir: Path) -> dict:
    record: dict = {
        "query": query, "axis": axis, "outcome": "ERROR", "status_code": None,
        "count": 0, "samples": [], "container_count": None, "error": None,
    }
    t0 = time.monotonic()
    try:
        resp = requests.get(
            WML_URL.format(quote_plus(query)),
            headers={"User-Agent": NOKIA_UA},
            impersonate=IMPERSONATE,
            timeout=TIMEOUT_S,
        )
        record["status_code"] = resp.status_code
        body = resp.text or ""

        slug = _slugify(query)
        (wml_run_dir / f"{slug}.html").write_text(body, encoding="utf-8")

        if _detect_block(resp.status_code, body):
            record["outcome"] = "BLOCKED"
        else:
            container_count, results, _ = _parse_results(body)
            record["container_count"] = container_count
            if container_count == 0:
                record["outcome"] = "NO_CONTAINERS"
            else:
                record["count"] = len(results)
                record["samples"] = results[:5]
                record["outcome"] = "OK" if results else "EMPTY_PARSED"
    except Exception as e:
        record["outcome"] = "ERROR"
        record["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    record["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    return record


def _count_outcomes(records: list[dict]) -> dict:
    counts = {"OK": 0, "EMPTY_PARSED": 0, "NO_CONTAINERS": 0, "BLOCKED": 0, "ERROR": 0}
    for r in records:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return counts


def _compute_verdict(records: list[dict], counts: dict) -> str:
    return (
        "CANDIDATE — real results parsed via SearXNG's own selectors, from this machine's IP, "
        "this run"
        if counts["OK"] == len(records)
        else "NOT A CANDIDATE as measured — see per-query outcomes below"
    )


def _build_header(run_ts: str, records: list[dict], verdict: str) -> list[str]:
    return [
        f"# Google WML Route Probe (Path B) — {run_ts}",
        "",
        "Replicates SearXNG's current Google engine (endpoint, Nokia UA, "
        "impersonate=\"chrome99_android\", plain HTTP via curl_cffi, lxml parse) against a live "
        "Google response, from this machine's IP, on this day.",
        "",
        "**Interpretation note:** whatever this run shows is a finding about THIS machine's IP on "
        "THIS day, not a general claim about the method — same caveat already on record for the "
        "2026-07-21 Startpage probe "
        "(`process-docs/engine_expansion/startpage_reeval_2026-07-21.md`).",
        "",
        f"## Verdict (this run)",
        "",
        f"**{verdict}**",
        "",
        f"**Queries:** {len(records)} (see `dev/access_recovery/queries.json`, shared with the "
        "Path A probe — the same 10-query, axis-tagged set "
        "`dev/search_pipeline/26_brave_probe.py` uses).",
        f"**Pacing:** {NAV_DELAY_S}s between every request (lighter than Path A's browser pacing, "
        "still deliberately non-zero — see this script's own module docstring for why).",
        "",
    ]


def _build_outcome_counts_section(counts: dict) -> list[str]:
    return [
        "## Outcome counts",
        "",
        f"- **OK**: {counts['OK']}",
        f"- **EMPTY_PARSED** (container matched, title/url extraction found zero): "
        f"{counts['EMPTY_PARSED']}",
        f"- **NO_CONTAINERS** (zMzFAb selector matched nothing): {counts['NO_CONTAINERS']}",
        f"- **BLOCKED** (non-200 or a block-indicator string in the body): {counts['BLOCKED']}",
        f"- **ERROR**: {counts['ERROR']}",
        "",
    ]


def _build_per_query_table(records: list[dict]) -> list[str]:
    lines = [
        "## Per-query results",
        "",
        "| # | Axis | Query | Status | Outcome | Containers | Count | Elapsed ms |",
        "|---|------|-------|--------|---------|------------|-------|------------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:40].replace("|", "\\|")
        lines.append(
            f"| {i} | {r['axis']} | {q} | {r['status_code']} | {r['outcome']} | "
            f"{r.get('container_count')} | {r['count']} | {r['elapsed_ms']} |"
        )
    lines.append("")
    return lines


def _build_ok_samples_section(records: list[dict]) -> list[str]:
    ok_recs = [r for r in records if r["outcome"] == "OK"]
    if not ok_recs:
        return []
    lines = ["## OK samples (quality eyeball)", ""]
    for r in ok_recs:
        lines.append(f"### {r['query']} ({r['axis']}) — {r['count']} results")
        lines.append("")
        for s in r["samples"]:
            lines.append(f"- **{s['title']}** — {s['url']}")
        lines.append("")
    return lines


def _build_non_ok_section(records: list[dict]) -> list[str]:
    non_ok = [r for r in records if r["outcome"] != "OK"]
    if not non_ok:
        return []
    lines = ["## Non-OK details", ""]
    for r in non_ok:
        lines.append(f"### [{r['outcome']}] {r['query']} ({r['axis']})")
        lines.append("")
        lines.append(f"- status_code: {r['status_code']}")
        if r.get("container_count") is not None:
            lines.append(f"- container_count: {r['container_count']}")
        if r.get("error"):
            lines.append(f"- error: {r['error']}")
        lines.append("")
    return lines


def _build_raw_bodies_section(run_ts: str) -> list[str]:
    return [
        "## Raw response bodies",
        "",
        f"Saved under `dev/access_recovery/wml/google_wml_probe_{run_ts}/` "
        "(gitignored — local evidence, not carried in the repo).",
        "",
    ]


def write_report(records: list[dict], run_ts: str) -> Path:
    path = REPORT_DIR / f"google_wml_probe_{run_ts}.md"
    counts = _count_outcomes(records)
    verdict = _compute_verdict(records, counts)

    lines = []
    lines += _build_header(run_ts, records, verdict)
    lines += _build_outcome_counts_section(counts)
    lines += _build_per_query_table(records)
    lines += _build_ok_samples_section(records)
    lines += _build_non_ok_section(records)
    lines += _build_raw_bodies_section(run_ts)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    run_probe()
