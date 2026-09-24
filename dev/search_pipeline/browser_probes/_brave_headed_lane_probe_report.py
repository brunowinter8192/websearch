# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path


# FUNCTIONS

# Write markdown data report and return path
def write_report(records: list[dict], report_dir: Path, latency_gate_s: float) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"brave_headed_lane_probe_{ts}.md"

    ok_count = sum(1 for r in records if r["status"] == "OK")
    pow_count = sum(1 for r in records if r["pow_triggered"])
    error_count = sum(1 for r in records if r["status"] == "ERROR")
    under_gate = sum(1 for r in records if r["elapsed_ms"] <= latency_gate_s * 1000)
    lo, med, hi = _latency_stats(records) if records else (0, 0, 0)
    clean_run = _longest_clean_run(records)

    verdict = (
        "CANDIDATE — real results, <=5s, usable run of consecutive clean queries"
        if clean_run >= 3 and under_gate == len(records) and pow_count < len(records)
        else "DROP — " + (
            f"PoW/CAPTCHA triggered on {pow_count}/{len(records)} queries, longest clean run only {clean_run}"
            if pow_count > 0 else f"latency gate failed on {len(records) - under_gate}/{len(records)} queries"
        )
    )

    lines = _render_title_verdict(ts, verdict)
    lines += _render_mechanism()
    lines += _render_headline(records, ok_count, error_count, pow_count, under_gate, lo, med, hi, clean_run, latency_gate_s)
    lines += _render_table(records, latency_gate_s)
    lines += _render_samples(records)
    lines += _render_non_ok(records)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_title_verdict(ts: str, verdict: str) -> list[str]:
    return [
        f"# Brave Headed-Background Lane Probe — {ts}",
        "",
        "Dev-only probe: headed-but-backgrounded Chrome (macOS `open -g`, isolated profile) against "
        "Brave Search, one query at a time. Gate: real results, <=5s per query, and a usable run of "
        "3-4+ consecutive clean (no-PoW) queries (relaxed bar — does not need to be block-free forever).",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
    ]


def _render_mechanism() -> list[str]:
    return [
        "## Launch Mechanism",
        "",
        "- `Chrome(options)` constructed normally, then `browser._browser_process_manager` is "
        "swapped for `BrowserProcessManager(process_creator=_open_process_creator)` BEFORE "
        "`await browser.start()` (`Chrome.__init__` does not expose `process_creator`).",
        "- `_open_process_creator(command)` drops `command[0]` (resolved binary_location, unused) "
        "and runs `open -g -n -a \"Google Chrome\" --args --remote-debugging-port=<port> "
        "--user-data-dir=<isolated dir> ...` — `-g` = no focus steal, `-n` = force new instance.",
        "- Isolated profile: `~/.searxng-mcp/brave-headed-probe-session` (NOT the shared engine "
        "session dir) — block-isolation + forces a genuinely fresh Chrome process.",
        "- Teardown: CDP `browser.stop()` (works — it's a real `Browser.close` CDP command against "
        "the real Chrome instance) PLUS an unconditional `pkill -f user-data-dir=<isolated dir>` "
        "safety net, because `open -g` returns immediately so pydoll's own `stop_process()` only "
        "ever had the short-lived `open` wrapper process to reap, not Chrome itself.",
        "",
    ]


def _render_headline(records: list[dict], ok_count: int, error_count: int, pow_count: int, under_gate: int, lo: int, med: int, hi: int, clean_run: int, latency_gate_s: float) -> list[str]:
    return [
        "## Headline",
        "",
        f"- **Queries:** {len(records)}",
        f"- **OK (results returned):** {ok_count}",
        f"- **PoW/CAPTCHA triggered:** {pow_count}",
        f"- **ERROR:** {error_count}",
        f"- **Latency <= {latency_gate_s}s:** {under_gate}/{len(records)}",
        f"- **Latency distribution (ms):** min={lo}, median={med}, max={hi}",
        f"- **Longest consecutive clean (no-PoW) run:** {clean_run}",
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


# Longest run of consecutive OK (non-PoW, non-error) queries in original run order
def _longest_clean_run(records: list[dict]) -> int:
    best = cur = 0
    for r in records:
        if r["status"] == "OK":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best
