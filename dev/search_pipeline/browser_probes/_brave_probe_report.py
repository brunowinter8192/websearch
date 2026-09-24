# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path


# FUNCTIONS

# Write markdown data report and return path
def write_report(records: list[dict], report_dir: Path, latency_gate_s: float) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"brave_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= latency_gate_s * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)

    verdict = (
        "CANDIDATE — real results, no PoW, all queries <= 5s"
        if pow_count == 0 and under_gate == len(records) and ok_count == len(records)
        else "DROP — " + (
            f"PoW/CAPTCHA triggered on {pow_count}/{len(records)} queries" if pow_count > 0
            else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
        )
    )

    lines = _render_title_verdict(ts, verdict)
    lines += _render_headline(records, ok_count, error_count, pow_count, under_gate, lo, med, hi, latency_gate_s)
    lines += _render_stack()
    lines += _render_table(records, latency_gate_s)
    lines += _render_samples(records)
    lines += _render_non_ok(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_title_verdict(ts: str, verdict: str) -> list[str]:
    return [
        f"# Brave Search Go/No-Go Probe — {ts}",
        "",
        "Dev-only probe: real result rows + no PoW/CAPTCHA + per-query wall latency <= 5s, "
        "run one query at a time (no gather-special-casing) via the pydoll stealth stack "
        "(src/search/browser.py shape, self-contained here).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]


def _render_headline(records: list[dict], ok_count: int, error_count: int, pow_count: int, under_gate: int, lo: int, med: int, hi: int, latency_gate_s: float) -> list[str]:
    return [
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **PoW/CAPTCHA triggered:** {pow_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {latency_gate_s}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        "",
    ]


def _render_stack() -> list[str]:
    return [
        "## Stack + Selectors",
        "",
        "- Stack used for this run: pydoll stealth stack (`src/search/browser.py` fingerprint "
        "patches — disable-blink-features=AutomationControlled, real Chrome UA, webrtc-leak-protection), "
        "headless, per-query fresh tab via new_tab()/kill_tab().",
        "- Also tried (see module docstring): Patchright with a real Chrome binary (`channel=\"chrome\"`, "
        "headless) — triggered a slider CAPTCHA (title `Captcha - Brave Search`, `Schieberegler ziehen` / "
        "link to `/help/pow-captcha`) on the very first query. The SAME real-Chrome binary succeeded "
        "headed (no CAPTCHA) — headless-ness itself, not the Chromium-vs-real-Chrome binary identity, "
        "is what triggers Brave's PoW for the Patchright stack. Headed is not viable in production "
        "(server pipeline, no display), so that angle is closed.",
        "- Search URL: `https://search.brave.com/search?q=<q>` (spaces as `+`), plain GET, no consent/cookie step observed.",
        "- Result container: `div[data-type=\"web\"]`. Title: `.search-snippet-title` inside the result anchor. "
        "URL: `a[href^=\"http\"]` (direct destination, no redirect wrapper). Snippet: `.snippet-content .content` "
        "(falls back to `.generic-snippet .content`).",
        "- Block/CAPTCHA detection: `document.title` containing 'captcha', or body text containing "
        "'schieberegler ziehen'/'drag the slider'/'proof of work', or presence of `a[href*=\"pow-captcha\"]`.",
        "",
    ]


def _render_table(records: list[dict], latency_gate_s: float) -> list[str]:
    lines = [
        "## Per-Query Results",
        "",
        "| # | Query | Axis | Status | Count | PoW | Elapsed ms | <= 5s? |",
        "|---|-------|------|--------|-------|-----|------------|--------|",
    ]
    for i, r in enumerate(records, 1):
        query = r["query"][:45].replace("|", "\\|")
        gate = "yes" if r["elapsed_ms"] <= latency_gate_s * 1000 else "NO"
        lines.append(
            f"| {i} | {query} | {r['axis']} | {r['status']} | {r['count']} | "
            f"{r['pow_triggered']} | {r['elapsed_ms']} | {gate} |"
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
