# INFRASTRUCTURE
import json
from datetime import datetime
from pathlib import Path

# Flagged from an EARLIER live run this session (search_web across all 14 engines) — these three
# returned 0 results THEN, unrelated to this probe. A repeat non-OK here is annotated, not fresh.
PRE_FLAGGED_EMPTY_EARLIER = {"google", "duckduckgo", "brave"}


# FUNCTIONS

# --- Report ---

def write_report(records: list[dict], report_dir: Path, queries: list, retry_cooldown_s: float) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"date_availability_probe_{ts}.md"

    lines = _render_header(ts, queries, retry_cooldown_s)

    by_engine: dict[str, list[dict]] = {}
    for r in records:
        by_engine.setdefault(r["engine"], []).append(r)

    for engine, recs in by_engine.items():
        lines += _render_engine_section(engine, recs)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_header(ts: str, queries: list, retry_cooldown_s: float) -> list[str]:
    return [
        f"# Date-Availability Probe (Milestone 2) — {ts}",
        "",
        "Raw evidence dump for the 8 DOM-scraped web engines. Measurement only — no src/ touched, "
        "no wiring. Queries: " + ", ".join(f"`{q}` ({a})" for q, a in queries) + ". "
        "One retry (query 1, after a "
        f"{retry_cooldown_s:.0f}s cooldown) only for engines non-OK on all 3 primary queries.",
        "",
        "## Classification",
        "",
        "*(filled in by hand after reading the raw evidence below — see chat report)*",
        "",
        "## Raw Evidence",
        "",
    ]


def _render_engine_section(engine: str, recs: list[dict]) -> list[str]:
    lines = []
    lines.append(f"### {engine}")
    lines.append("")
    pre_flag = " — **pre-flagged: returned 0 results in an earlier live run this session, unrelated to this probe**" if engine in PRE_FLAGGED_EMPTY_EARLIER else ""
    lines.append(f"Pre-flag: {'yes' + pre_flag if engine in PRE_FLAGGED_EMPTY_EARLIER else 'no'}")
    lines.append("")
    for r in recs:
        lines += _render_record(r)
    lines.append("---")
    lines.append("")
    return lines


def _render_record(r: dict) -> list[str]:
    lines = []
    tag = " (RETRY)" if r["retry"] else ""
    lines.append(f"#### [{r['axis']}]{tag} `{r['query']}` — status={r['status']} containers={r['container_count']} elapsed={r['elapsed_ms']}ms")
    lines.append("")
    if r.get("error"):
        lines.append(f"- **Error:** {r['error']}")
        lines.append("")
    if r.get("diag"):
        lines.append(f"- **Diagnosis:** `{json.dumps(r['diag'], ensure_ascii=False)}`")
        lines.append("")
    for si, s in enumerate(r["samples"], 1):
        lines += _render_container(si, s)
    return lines


def _render_container(si: int, s: dict) -> list[str]:
    lines = []
    lines.append(f"**Container {si}**")
    lines.append("")
    lines.append(f"- time elements: `{json.dumps(s['time_els'], ensure_ascii=False)}`")
    lines.append(f"- date-like class/id elements: `{json.dumps(s['date_like_els'], ensure_ascii=False)}`")
    lines.append(f"- container text (600c): `{s['text']}`")
    lines.append("- html head:")
    lines.append("```html")
    lines.append(s["html_head"])
    lines.append("```")
    lines.append("")
    return lines
