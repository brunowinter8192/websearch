# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path


# FUNCTIONS

# Write markdown data report and return path
def write_report(records: list[dict], report_dir: Path, latency_gate_s: float) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"bing_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    blocked_count = sum(1 for r in records if r["status"] == "BLOCKED")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= latency_gate_s * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)

    verdict = (
        "CANDIDATE — real results, no persistent block, usable latency"
        if ok_count == len(records) and under_gate == len(records)
        else "DROP — " + (
            f"blocked on {blocked_count}/{len(records)} queries" if blocked_count > 0
            else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
            if under_gate < len(records)
            else f"only {ok_count}/{len(records)} returned results"
        )
    )

    lines = _render_title_verdict(ts, verdict)
    lines += _render_headline(records, ok_count, blocked_count, empty_count, error_count, under_gate, lo, med, hi, latency_gate_s)
    lines += _render_findings()
    lines += _render_table(records, latency_gate_s)
    lines += _render_samples(records)
    lines += _render_non_ok(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_title_verdict(ts: str, verdict: str) -> list[str]:
    return [
        f"# Bing Scrapeability Probe — {ts}",
        "",
        "Go/no-go data probe (dev-only) for bing.com as a second, independent access path to the "
        "Bing web index (redundant to DuckDuckGo) — question is SCRAPEABILITY + LATENCY, not "
        "coverage (overlap with DDG is expected and fine by design).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]


def _render_headline(records: list[dict], ok_count: int, blocked_count: int, empty_count: int, error_count: int, under_gate: int, lo: int, med: int, hi: int, latency_gate_s: float) -> list[str]:
    return [
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **BLOCKED (explicit marker):** {blocked_count}",
        f"- **EMPTY (no results, no marker):** {empty_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {latency_gate_s}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        "",
    ]


def _render_findings() -> list[str]:
    return [
        "## URL / Selector Findings",
        "",
        "- Search URL: `https://www.bing.com/search?q=<q>` (spaces as `+`), plain GET, no consent/form step required.",
        "- Old selector `#b_results .b_algo` had NOT actually drifted structurally — "
        "`li.b_algo` inside `#b_results` is still the live result container (10/page).",
        "- Title + href: `h2 a` inside each `li.b_algo`. Snippet: `.b_caption p` (falls back to `.b_caption`).",
        "- **New since the old evaluation:** every organic href is wrapped in a "
        "`bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect — unwrapped by parsing the "
        "`u` query param, stripping its 2-char prefix (observed: `a1`), then base64url-decoding "
        "(with padding) to recover the real destination URL.",
        "- A Microsoft cookie/consent banner is present in the DOM (`Microsoft und unsere "
        "Drittanbieter verwenden Cookies...`) but does NOT gate result rendering — `li.b_algo` "
        "content is fully present in the DOM alongside it; no click/accept step needed for scraping.",
        "- Block detection: title/body scan for EN + DE bot-check phrasing "
        "(`captcha`, `unusual traffic`, `verify you are human`, `ungewöhnlichen datenverkehr`, etc.).",
        "",
    ]


def _render_table(records: list[dict], latency_gate_s: float) -> list[str]:
    lines = [
        "## Per-Query Results",
        "",
        "| # | Query | Axis | Status | Count | Elapsed ms | <= 5s? |",
        "|---|-------|------|--------|-------|------------|--------|",
    ]
    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        gate = "yes" if r["elapsed_ms"] <= latency_gate_s * 1000 else "NO"
        lines.append(
            f"| {i} | {query} | {r['axis']} | {r['status']} | {r['count']} | {r['elapsed_ms']} | {gate} |"
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


# Compute latency distribution (min/median/max) across all queries
def _latency_stats(records: list[dict]) -> tuple[int, int, int]:
    ms = sorted(r["elapsed_ms"] for r in records)
    n = len(ms)
    median = ms[n // 2] if n % 2 else (ms[n // 2 - 1] + ms[n // 2]) // 2
    return ms[0], median, ms[-1]
