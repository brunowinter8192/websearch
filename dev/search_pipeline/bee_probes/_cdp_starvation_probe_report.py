# INFRASTRUCTURE
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _cdp_starvation_probe_instrument import _cdp_ts, _slow_cb_events, SLOW_CB_THRESHOLD_S
from _cdp_starvation_probe_canary import (
    _canary_samples, PROBE_START, COLD_START_SKIP_S, _sample_category, _compute_stats,
)


# FUNCTIONS

def _derive_verdict(stats: dict) -> str:
    s_cap = stats["empty"]
    s_zc = stats["zero_cascade"]
    s_norm = stats["normal"]
    norm_p99 = max(s_norm["p99"], 1.0)

    starvation = (
        (s_cap["n"] > 0 and s_cap["p99"] > 200 and s_cap["p99"] > norm_p99 * 3) or
        (s_zc["n"] > 0 and s_zc["p99"] > 200 and s_zc["p99"] > norm_p99 * 3)
    )
    partial = (
        (s_cap["n"] > 0 and s_cap["p99"] > 50 and s_cap["p99"] > norm_p99 * 1.5) or
        (s_zc["n"] > 0 and s_zc["p99"] > 50 and s_zc["p99"] > norm_p99 * 1.5)
    )

    if starvation:
        return "CONFIRMED"
    if partial:
        return "PARTIALLY_CONFIRMED"
    if s_cap["n"] == 0 and s_zc["n"] == 0:
        return "INCONCLUSIVE"
    return "REFUTED"


def _write_report(records: list[dict], report_dir: Path) -> Path:
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"cdp_probe_{ts_str}.md"
    stats = _compute_stats(records)
    verdict = _derive_verdict(stats)
    run_dur_s = (records[-1]["t_end"] - PROBE_START) if records else 0.0

    lines: list[str] = []
    lines += _r_header(records, ts_str, run_dur_s, verdict)
    lines += _r_query_table(records)
    lines += _r_latency_stats(stats)
    lines += _r_timeseries(records)
    lines += _r_cdp_table(records)
    lines += _r_slow_callbacks()
    lines += _r_verdict_section(stats, verdict)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _r_header(records: list[dict], ts_str: str, run_dur_s: float, verdict: str) -> list[str]:
    empty_n = sum(1 for r in records if r["category"] == "empty")
    zero_n = sum(1 for r in records if r["category"] == "zero_cascade")
    return [
        f"# CDP Starvation Probe Report — {ts_str}",
        "",
        f"**Verdict:** {verdict}  ",
        f"**Queries:** {len(records)}  ",
        f"**Empty queries:** {empty_n}  ",
        f"**Zero-cascade queries:** {zero_n}  ",
        f"**Total CDP messages:** {len(_cdp_ts)}  ",
        f"**Total canary samples:** {len(_canary_samples)}  ",
        f"**Slow-callback events:** {len(_slow_cb_events)}  ",
        f"**Run duration:** {run_dur_s:.0f}s  ",
        "",
        "---",
        "",
    ]


def _r_query_table(records: list[dict]) -> list[str]:
    lines = [
        "## Per-Query Summary",
        "",
        "| # | Query | total_ms | google | category | cdp_events | cdp_rate/s |",
        "|---|-------|----------|--------|----------|------------|------------|",
    ]
    for r in records:
        q = r["query"][:42].replace("|", "\\|")
        lines.append(
            f"| {r['qi']} | {q} | {r['total_ms']} "
            f"| {r['google_status']} | {r['category']} "
            f"| {r['cdp_events']} | {r['cdp_rate']:.1f} |"
        )
    return lines + [""]


def _r_latency_stats(stats: dict) -> list[str]:
    lines = [
        "",
        "## Scheduling Latency by Query Category (Pattern B)",
        "",
        f"> Cold-start first {COLD_START_SKIP_S:.0f}s excluded from per-category stats.",
        "",
        "| Category | n | p50 ms | p95 ms | p99 ms | max ms | mean ms |",
        "|----------|---|--------|--------|--------|--------|---------|",
    ]
    for label, key in [
        ("Normal queries", "normal"),
        ("Empty queries (google=EMPTY, was EMPTY_BLOCK)", "empty"),
        ("Zero-cascade (all RATE_SKIP)", "zero_cascade"),
        ("Overall (non-cold-start)", "overall"),
        ("Cold-start (first 5s)", "cold_start"),
    ]:
        s = stats[key]
        lines.append(
            f"| {label} | {s['n']} | {s['p50']} | {s['p95']} | {s['p99']} | {s['max']} | {s['mean']} |"
        )
    return lines + [""]


def _r_timeseries(records: list[dict]) -> list[str]:
    if not _canary_samples:
        return []
    buckets: dict[int, list] = defaultdict(list)
    for ts, lat, ntasks in _canary_samples:
        offset_s = int((ts - PROBE_START) // 2) * 2
        buckets[offset_s].append((ts, lat, ntasks))

    lines = [
        "",
        "## Scheduling Latency Time-Series (2s buckets)",
        "",
        "| offset_s | lat_mean ms | lat_max ms | tasks_mean | cdp/s | category |",
        "|----------|-------------|------------|------------|-------|----------|",
    ]
    for offset_s in sorted(buckets):
        bucket = buckets[offset_s]
        ts_mid = PROBE_START + offset_s + 1.0
        lats = [x[1] for x in bucket]
        tasks_vals = [x[2] for x in bucket]
        t_s = PROBE_START + offset_s
        t_e = t_s + 2.0
        cdp_rate = sum(1 for ct in _cdp_ts if t_s <= ct < t_e) / 2.0
        cat = _sample_category(ts_mid, records)
        lines.append(
            f"| {offset_s} | {statistics.mean(lats):.1f} | {max(lats):.1f} "
            f"| {statistics.mean(tasks_vals):.1f} | {cdp_rate:.1f} | {cat} |"
        )
    return lines + [""]


def _r_cdp_table(records: list[dict]) -> list[str]:
    lines = [
        "",
        "## CDP Event Counts Per Query",
        "",
        f"Total CDP messages across entire run: {len(_cdp_ts)}",
        "",
        "| # | Query | dur_s | cdp_events | cdp_rate/s | category |",
        "|---|-------|-------|------------|------------|----------|",
    ]
    for r in records:
        q = r["query"][:40].replace("|", "\\|")
        lines.append(
            f"| {r['qi']} | {q} | {r['duration_s']:.1f} "
            f"| {r['cdp_events']} | {r['cdp_rate']:.1f} | {r['category']} |"
        )
    return lines + [""]


def _r_slow_callbacks() -> list[str]:
    lines = [
        "",
        f"## Pattern A: Slow Callback Events (threshold={SLOW_CB_THRESHOLD_S*1000:.0f}ms)",
        "",
        f"Total: {len(_slow_cb_events)} events",
        "",
    ]
    if not _slow_cb_events:
        lines.append("*None captured.*")
        lines.append("")
        return lines
    for evt in _slow_cb_events[:60]:
        lines.append(f"    {evt}")
    if len(_slow_cb_events) > 60:
        lines.append(f"    ... {len(_slow_cb_events) - 60} more")
    lines.append("")
    return lines


def _r_verdict_section(stats: dict, verdict: str) -> list[str]:
    s_cap = stats["empty"]
    s_zc = stats["zero_cascade"]
    s_norm = stats["normal"]
    return [
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        "| Metric | normal | empty | zero_cascade |",
        "|--------|--------|---------|--------------|",
        f"| p99 ms | {s_norm['p99']} | {s_cap['p99']} | {s_zc['p99']} |",
        f"| max ms | {s_norm['max']} | {s_cap['max']} | {s_zc['max']} |",
        f"| n samples | {s_norm['n']} | {s_cap['n']} | {s_zc['n']} |",
        "",
    ]
