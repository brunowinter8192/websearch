# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path


# FUNCTIONS

# Write markdown data report and return path
def write_report(records: list[dict], report_dir: Path, latency_gate_s: float) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"yandex_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    blocked_count = sum(1 for r in records if r["status"] == "BLOCKED")
    empty_count = sum(1 for r in records if r["status"] == "EMPTY")
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= latency_gate_s * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)
    clean_run = _longest_clean_run(records)

    verdict = (
        "DROP — blocked from the very first query, zero usable results at any point"
        if ok_count == 0
        else f"CANDIDATE — {ok_count}/{len(records)} usable hits (longest clean run {clean_run}); "
             f"{'no block observed' if blocked_count == 0 else f'{blocked_count} blocked after clean hits — graceful-empty territory, like Brave'}"
    )

    lines = _render_title_verdict(ts, verdict)
    lines += _render_quality(records)
    lines += _render_headline(records, ok_count, blocked_count, empty_count, error_count, under_gate, lo, med, hi, clean_run, latency_gate_s)
    lines += _render_findings()
    lines += _render_table(records, latency_gate_s)
    lines += _render_samples(records)
    lines += _render_non_ok(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_title_verdict(ts: str, verdict: str) -> list[str]:
    return [
        f"# Yandex Scrapeability Probe — {ts}",
        "",
        "Go/no-go data probe (dev-only) for yandex.com — one of the few remaining INDEPENDENT web "
        "indexes (own crawler, not a Google/Bing frontend). Relaxed decision criterion: DROP only "
        "if there is truly no way through from query 1; a handful of clean hits before any "
        "eventual block is a CANDIDATE (real usage is low-volume, like Brave's).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]


def _render_quality(records: list[dict]) -> list[str]:
    return [
        "## Quality Axis (separate from access)",
        "",
        _quality_note(records),
        "",
    ]


def _render_headline(records: list[dict], ok_count: int, blocked_count: int, empty_count: int, error_count: int, under_gate: int, lo: int, med: int, hi: int, clean_run: int, latency_gate_s: float) -> list[str]:
    return [
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **BLOCKED (explicit CAPTCHA/marker):** {blocked_count}",
        f"- **EMPTY (no results, no marker):** {empty_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {latency_gate_s}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        f"- **Longest consecutive clean (OK) run:** {clean_run}",
        "",
    ]


def _render_findings() -> list[str]:
    return [
        "## URL / Selector Findings",
        "",
        "- Search URL: `https://yandex.com/search/?text=<q>` (international domain, NOT yandex.ru; "
        "spaces as `+`). Yandex auto-appends `&lr=<region_id>` (region param, IP-geolocation-based) "
        "on redirect — no consent step, no block.",
        "- Old selector `li.serp-item` is STILL the live result container shape.",
        "- Title + href: `a.OrganicTitle-Link` inside each `li.serp-item` — href is the DIRECT "
        "destination URL, no tracking-redirect wrapper (unlike Bing's `ck/a`).",
        "- Snippet: `.OrganicText .OrganicTextContentSpan` (falls back to `.OrganicText`).",
        "- Block detection: title/body scan for EN + RU CAPTCHA/bot-check phrasing, plus a URL-path "
        "check for `showcaptcha`/`checkcaptcha`/`/captcha` substrings.",
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


# Longest run of consecutive OK (non-block, non-error) queries in original run order
def _longest_clean_run(records: list[dict]) -> int:
    best = cur = 0
    for r in records:
        if r["status"] == "OK":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


# Build an honest quality-axis note from the German-query subset of the run
def _quality_note(records: list[dict]) -> str:
    de_records = [r for r in records if r["axis"].endswith("-de") and r["status"] == "OK"]
    if not de_records:
        return "No successful German-axis queries to assess relevance from this run."
    domains = []
    for r in de_records:
        for s in r["samples"][:3]:
            domains.append(s["url"])
    return (
        f"{len(de_records)} German-axis queries returned usable results. See the sample titles/urls "
        "below per query for a direct relevance read — the honest call belongs in the completion "
        "report after eyeballing them, not asserted generically here."
    )
