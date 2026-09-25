# INFRASTRUCTURE
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from _branch_probe_canary import _canary_stats
from _branch_probe_instrument import _acq_events


# FUNCTIONS

def _write_report(
    records: list[dict],
    cascade_ok: bool,
    zero_n: int,
    report_dir: Path,
    backoff_immune: frozenset[str],
) -> Path:
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"branch_probe_{ts_str}.md"
    verdict = _overall_verdict(records)
    cstats = _canary_stats(records)
    empty_n = sum(1 for r in records if r["category"] == "empty")

    lines = _report_header(ts_str, verdict, cascade_ok, zero_n, records, empty_n)
    lines += _report_per_query_summary(records)
    lines += _report_central_discriminator(records, backoff_immune)
    lines += _report_pre_query_state(records, backoff_immune)
    lines += _report_branch_fire_aggregate(records, cstats)
    lines += _report_canary_detail(cstats)
    lines += _report_verdict_key()
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _overall_verdict(records: list[dict]) -> str:
    zc = [r["disc"] for r in records if r["category"] == "zero_cascade"]
    if not zc:
        return "no_cascade"
    counts: dict[str, int] = defaultdict(int)
    for d in zc:
        key = "mixed" if (d.startswith("mixed") or d.startswith("partial")) else d
        counts[key] += 1
    return max(counts, key=lambda k: counts[k])


def _report_header(
    ts_str: str,
    verdict: str,
    cascade_ok: bool,
    zero_n: int,
    records: list[dict],
    empty_n: int,
) -> list[str]:
    return [
        f"# Branch Probe Report — {ts_str}",
        "",
        f"**Overall verdict:** {verdict}  ",
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
        "| # | Query | cat | disc | total_ms |",
        "|---|-------|-----|------|----------|",
    ]
    for r in records:
        q = r["query"][:38].replace("|", "\\|")
        lines.append(f"| {r['qi']} | {q} | {r['category']} | {r['disc']} | {r['total_ms']} |")
    return lines


def _report_central_discriminator(records: list[dict], backoff_immune: frozenset[str]) -> list[str]:
    zc_records = [r for r in records if r["category"] == "zero_cascade"]
    lines = [
        "",
        "## Central Discriminator — Zero-Cascade Queries",
        "",
        "pre_br = backoff_remaining_s at query entry; pre_tok = len(tokens) in window;",
        "ba = backoff_sleep_attempt fired; tc = tokencap_sleep_attempt fired;",
        "wait = planned asyncio.sleep duration (before wait_for cancels at 5s).",
        "*(I) = backoff-immune engine (no .backoff() call in engine source)*",
        "",
    ]
    if not zc_records:
        lines.append("*No zero_cascade queries in this run.*")
    else:
        lines += [
            "| q# | engine | I | pre_br_s | pre_tok | ba | wait_ba_s | tc | wait_tc_s | exit | dur_ms |",
            "|----|--------|---|----------|---------|----|-----------|----|-----------|------|--------|",
        ]
        for r in zc_records:
            for eng in sorted(r["eng_detail"]):
                d = r["eng_detail"][eng]
                if d["status"] != "RATE_SKIP":
                    continue
                imm = "I" if eng in backoff_immune else ""
                ba = "Y" if d["backoff_attempt"] else "N"
                tc = "Y" if d["tokencap_attempt"] else "N"
                bw = f"{d['backoff_wait_s']:.1f}" if d["backoff_wait_s"] is not None else "—"
                tw = f"{d['tokencap_wait_s']:.1f}" if d["tokencap_wait_s"] is not None else "—"
                lines.append(
                    f"| {r['qi']} | {eng} | {imm} "
                    f"| {d['pre_backoff_remaining_s']} | {d['pre_len_tokens']} "
                    f"| {ba} | {bw} | {tc} | {tw} "
                    f"| {d['exit_class']} | {d['dur_ms'] or '—'} |"
                )
    return lines


def _report_pre_query_state(records: list[dict], backoff_immune: frozenset[str]) -> list[str]:
    first_zc = next((r for r in records if r["category"] == "zero_cascade"), None)
    lines = ["", "## Pre-Query State — First Zero-Cascade Query", ""]
    if first_zc:
        lines.append(f"Query #{first_zc['qi']}: `{first_zc['query']}`")
        lines += [
            "",
            "| engine | I | backoff_remaining_s | len_tokens | max_requests | predicted_branch |",
            "|--------|---|--------------------:|----------:|:-------------|:-----------------|",
        ]
        for eng, s in sorted(first_zc["snap"]["engines"].items()):
            imm = "I" if eng in backoff_immune else ""
            if s["backoff_remaining_s"] > 0:
                pred = "backoff(!IMMUNE)" if eng in backoff_immune else "backoff"
            elif s["len_tokens"] >= s["max_requests"]:
                pred = "tokencap"
            else:
                pred = "neither(?)"
            lines.append(
                f"| {eng} | {imm} | {s['backoff_remaining_s']} | {s['len_tokens']} "
                f"| {s['max_requests']} | {pred} |"
            )
    else:
        lines.append("*No zero_cascade queries — snapshot N/A.*")
    return lines


def _report_branch_fire_aggregate(records: list[dict], cstats: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Branch-Fire Aggregate by Category",
        "",
        "Averages = engines-per-query that fired each branch, over all queries in category.",
        "",
        "| category | n_q | avg_backoff_eng | avg_tokencap_eng | avg_neither_eng | canary_p99_ms |",
        "|----------|-----|----------------:|-----------------:|----------------:|---------------|",
    ]
    for cat in ("normal", "empty", "zero_cascade"):
        cat_rec = [r for r in records if r["category"] == cat]
        if not cat_rec:
            lines.append(f"| {cat} | 0 | — | — | — | — |")
            continue
        ba_avgs, tc_avgs, ni_avgs = [], [], []
        for r in cat_rec:
            rs = [d for d in r["eng_detail"].values() if d["status"] == "RATE_SKIP"]
            n = len(rs) or 1
            ba_avgs.append(sum(1 for d in rs if d["backoff_attempt"]) / n)
            tc_avgs.append(sum(1 for d in rs if d["tokencap_attempt"]) / n)
            ni_avgs.append(
                sum(1 for d in rs if not d["backoff_attempt"] and not d["tokencap_attempt"]) / n
            )
        mn = statistics.mean
        cs = cstats[cat]
        lines.append(
            f"| {cat} | {len(cat_rec)} | {round(mn(ba_avgs), 2)} "
            f"| {round(mn(tc_avgs), 2)} | {round(mn(ni_avgs), 2)} | {cs['p99']} |"
        )
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


def _report_verdict_key() -> list[str]:
    return [
        "",
        "## Verdict Key",
        "",
        "| Label | Meaning |",
        "|-------|---------|",
        "| tokencap | All RATE_SKIP engines fired tokencap branch (len(tokens) >= max_requests) |",
        "| backoff | All RATE_SKIP engines fired backoff branch (now < _backoff_until) |",
        "| mixed(ba=X tc=Y) | Both branches fired across engines within a single query |",
        "| neither | RATE_SKIP engines: CancelledError but no sleep branch reached |",
        "| ok | No RATE_SKIP engines |",
        "",
    ]
