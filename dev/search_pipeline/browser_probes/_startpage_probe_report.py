# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path


# FUNCTIONS

def write_report(records: list[dict], report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"startpage_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    blocked_count = sum(1 for r in records if r["status"] == "BLOCKED")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    error_count = sum(1 for r in records if r["status"] == "ERROR")

    lines = _render_title(ts)
    lines += _render_headline(records, ok_count, blocked_count, empty_count, error_count)
    lines += _render_findings()
    lines += _render_table(records)
    lines += _render_samples(records)
    lines += _render_non_ok(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_title(ts: str) -> list[str]:
    return [
        f"# Startpage Scrapeability Probe — {ts}",
        "",
        "Go/no-go data probe (dev-only) for startpage.com as a Google-index frontend, "
        "run from this machine's current IP.",
        "",
    ]


def _render_headline(records: list[dict], ok_count: int, blocked_count: int, empty_count: int, error_count: int) -> list[str]:
    return [
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **BLOCKED (explicit captcha/block marker):** {blocked_count}",
        f"- **EMPTY (no results, no block marker):** {empty_count}",
        f"- **ERROR:** {error_count}",
        f"- **Rate-limit behavior:** {_rate_limit_summary(records)}",
        "",
    ]


def _render_findings() -> list[str]:
    return [
        "## URL / Selector Findings",
        "",
        "- Direct GET to `https://www.startpage.com/sp/search?query=<q>` (no prior homepage "
        "visit) returns a degraded shell: header/nav + privacy-guarantee dropdown only, "
        "**zero** `div.result` nodes, **zero** external links, and **no** captcha/block "
        "marker in body text or title. It redirects internally to `/do/search?...&sc=...` "
        "with a `sc` token that does not match a valid session.",
        "- Working path: load `https://www.startpage.com/` -> set `#q` value via the native "
        "`HTMLInputElement.value` setter + `input` event (React controlled component) -> "
        "click `button.search-btn` (real click, not `form.submit()` which bypasses the React "
        "submit handler and just reloads the homepage). This POSTs to `/sp/search` carrying "
        "the session's `sc`/`search_sc` tokens and returns full rendered results.",
        "- Result row selector: `div.result` (10 per page). Title: `a.result-title h2.wgl-title` "
        "(href on `a.result-title`). Snippet: `p.description`.",
        "",
    ]


def _render_table(records: list[dict]) -> list[str]:
    lines = [
        "## Per-Query Results",
        "",
        "| # | Query | Axis | Status | Count | Elapsed ms |",
        "|---|-------|------|--------|-------|------------|",
    ]
    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        lines.append(
            f"| {i} | {query} | {r['axis']} | {r['status']} | {r['count']} | {r['elapsed_ms']} |"
        )
    return lines


def _render_samples(records: list[dict]) -> list[str]:
    lines = ["", "## Sample Results (quality eyeball)", ""]
    for i, r in enumerate(records, 1):
        if not r["samples"]:
            continue
        lines.append(f"### [{i}] {r['query']} ({r['axis']}) — {r['count']} results")
        lines.append("")
        for s in r["samples"]:
            lines.append(f"- **{s['title']}** — {s['url']}")
            lines.append(f"  - {s['snippet']}")
        lines.append("")
    return lines


def _render_non_ok(records: list[dict]) -> list[str]:
    lines = []
    non_ok = [r for r in records if r["status"] != "OK"]
    if non_ok:
        lines += ["## Non-OK Details", ""]
        for r in non_ok:
            lines.append(f"### [{r['status']}] {r['query']} ({r['axis']})")
            lines.append("")
            if r.get("error"):
                lines.append(f"- **Error:** {r['error']}")
            if r.get("diag"):
                lines.append(f"- **Diagnosis:** `{json.dumps(r['diag'])}`")
            lines.append("")
    return lines


def _rate_limit_summary(records: list[dict]) -> str:
    n = len(records)
    if n < 4:
        return "Too few queries to assess a within-run trend."
    mid = n // 2
    first, second = records[:mid], records[mid:]
    avg = lambda rs: sum(r["elapsed_ms"] for r in rs) / len(rs)
    blocked = lambda rs: sum(1 for r in rs if r["status"] == "BLOCKED")
    return (
        f"First half ({len(first)} queries): avg {avg(first):.0f}ms, {blocked(first)} blocked. "
        f"Second half ({len(second)} queries): avg {avg(second):.0f}ms, {blocked(second)} blocked."
    )
