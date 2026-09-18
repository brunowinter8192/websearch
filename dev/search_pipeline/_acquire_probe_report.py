# INFRASTRUCTURE
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _acquire_probe_instrument import _acq_events
from _acquire_probe_canary import _canary_stats
from _acquire_probe_analysis import _agg_ratios


# FUNCTIONS

def _overall_disc(records: list[dict]) -> str:
    zc = [r["disc"] for r in records if r["category"] == "zero_cascade"]
    if not zc:
        return "no_cascade"
    counts: dict[str, int] = defaultdict(int)
    for d in zc:
        counts[d] += 1
    return max(counts, key=lambda k: counts[k])


def _write_report(records: list[dict], cascade_ok: bool, zero_n: int, report_dir: Path) -> Path:
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"acquire_probe_{ts_str}.md"
    od = _overall_disc(records)
    cstats = _canary_stats(records)
    empty_n = sum(1 for r in records if r["category"] == "empty")

    lines = _report_header(ts_str, od, cascade_ok, zero_n, records, empty_n)
    lines += _report_per_query_summary(records)
    lines += _report_zero_cascade_detail(records)
    lines += _report_aggregate_by_category(records)
    lines += _report_canary_detail(cstats)
    lines += _report_verdict(od)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _report_header(
    ts_str: str,
    od: str,
    cascade_ok: bool,
    zero_n: int,
    records: list[dict],
    empty_n: int,
) -> list[str]:
    return [
        f"# Acquire Probe Report — {ts_str}",
        "",
        f"**Overall discriminator:** {od}  ",
        f"**Cascade reproduced:** {cascade_ok} ({zero_n}/{len(records)} zero_cascade)  ",
        f"**Empty queries:** {empty_n}  ",
        f"**Total acquire events:** {len(_acq_events)}  ",
        "",
        "---",
        "",
    ]


def _report_per_query_summary(records: list[dict]) -> list[str]:
    lines = [
        "## Per-Query Summary",
        "",
        "| # | Query | cat | disc | total_ms | ent/rs | lg/rs | ok/rs | err/rs |",
        "|---|-------|-----|------|----------|--------|-------|-------|--------|",
    ]
    for r in records:
        rs = [d for d in r["eng_summary"].values() if d["status"] == "RATE_SKIP"]
        n_rs = len(rs)
        n_ent = sum(1 for d in rs if d["entered"])
        n_lg = sum(1 for d in rs if d["lock_granted"])
        n_ok = sum(1 for d in rs if d["exit_class"] == "ok")
        n_err = sum(1 for d in rs if d["exit_class"].startswith("err:"))
        q = r["query"][:38].replace("|", "\\|")
        lines.append(
            f"| {r['qi']} | {q} | {r['category']} | {r['disc']} "
            f"| {r['total_ms']} | {n_ent}/{n_rs} | {n_lg}/{n_rs} | {n_ok}/{n_rs} | {n_err}/{n_rs} |"
        )
    return lines


def _report_zero_cascade_detail(records: list[dict]) -> list[str]:
    zc_records = [r for r in records if r["category"] == "zero_cascade"]
    lines = ["", "## Zero-Cascade Per-Engine Detail", ""]
    if not zc_records:
        lines.append("*No zero_cascade queries in this run.*")
    else:
        lines += [
            "| query | engine | status | entered | lock_granted | lock_released | lock_stuck | exit_class | dur_ms |",
            "|-------|--------|--------|---------|--------------|---------------|------------|------------|--------|",
        ]
        for r in zc_records:
            q = r["query"][:28].replace("|", "\\|")
            for eng in sorted(r["eng_summary"]):
                d = r["eng_summary"][eng]
                yn = lambda b: "Y" if b else "N"  # noqa: E731
                lines.append(
                    f"| {q} | {eng} | {d['status']} "
                    f"| {yn(d['entered'])} | {yn(d['lock_granted'])} "
                    f"| {yn(d['lock_released'])} | {yn(d['lock_stuck'])} "
                    f"| {d['exit_class']} | {d['dur_ms'] or '—'} |"
                )
    return lines


def _report_aggregate_by_category(records: list[dict]) -> list[str]:
    lines = [
        "",
        "## Aggregate by Category",
        "",
        "Ratios = fraction of RATE_SKIP engines per query, averaged over queries in category.",
        "",
        "| Category | n_q | avg_ent | avg_lg | avg_ok | avg_err | p99_dur_ms |",
        "|----------|-----|---------|--------|--------|---------|------------|",
    ]
    for cat in ("normal", "empty", "zero_cascade"):
        cat_rec = [r for r in records if r["category"] == cat]
        if not cat_rec:
            lines.append(f"| {cat} | 0 | — | — | — | — | — |")
            continue
        ent, lg, ok, err, dp99 = _agg_ratios(cat_rec)
        lines.append(f"| {cat} | {len(cat_rec)} | {ent} | {lg} | {ok} | {err} | {dp99} |")
    return lines


def _report_canary_detail(cstats: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Pattern B Canary — Scheduling Latency",
        "",
        "| Category | n | p50 ms | p99 ms | max ms |",
        "|----------|---|--------|--------|--------|",
    ]
    for cat in ("normal", "empty", "zero_cascade"):
        s = cstats[cat]
        lines.append(f"| {cat} | {s['n']} | {s['p50']} | {s['p99']} | {s['max']} |")
    return lines


def _report_verdict(od: str) -> list[str]:
    return [
        "",
        "## Verdict",
        "",
        f"**{od}**",
        "",
        "| Label | Meaning |",
        "|-------|---------|",
        "| B | acquire() Task never scheduled — asyncio scheduling gap |",
        "| A-lock | Task entered, blocked on lock — Python 3.14 Lock non-release under CancelledError |",
        "| A-sleep | Task got lock, blocked on asyncio.sleep(backoff_s) — expected only for Google |",
        "| C | acquire() returned ok — bug lies downstream |",
        "",
    ]
