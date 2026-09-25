#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.search.browser import close_browser
from src.search.cache import cache_key, cache_read
from src.search.search_web import search_web_workflow

SCRIPT_DIR   = Path(__file__).parent
QUERIES_FILE = SCRIPT_DIR / "queries.txt"
REPORT_DIR   = SCRIPT_DIR / "md"

_STATUS_HINTS: dict[str, str] = {
    "TIMEOUT_WATCHDOG":      "watchdog timeout",
    "TIMEOUT_NONCOOP":       "non-cooperative",
    "TIMEOUT_HTTPX":         "httpx timeout",
    "ERROR_BROWSER":         "Chrome error",
    "ERROR_HTTP":            "HTTP error",
    "ERROR_PARSE":           "parse error",
    "ERROR_OTHER":           "unexpected error",
    "RATE_SKIP":             "rate skip",
    "EMPTY":                 "empty",
    "ERROR":                 "error",
}


# ORCHESTRATOR

async def run_pipeline_smoke(max_queries: int | None, language: str, engine_timeout: float | None = None, report_prefix: str = "pipeline_smoke") -> None:
    queries = _load_queries(QUERIES_FILE, max_queries)
    print(f"Pipeline smoke | Queries: {len(queries)} | Language: {language}", file=sys.stderr)
    records = []
    checkpoints: list[dict] = []
    t_run_start = time.perf_counter()
    prev_qi = 0
    prev_elapsed = 0.0
    try:
        for qi, query in enumerate(queries, 1):
            _, timings = await search_web_workflow(query, language, None, None, _with_timings=True, engine_timeout=engine_timeout)
            key  = cache_key(query, language, None, None)
            hit  = cache_read(key)
            pools = hit.get("pools", {}) if hit else {}
            record = _build_record(query, pools, timings)
            records.append(record)
            print(
                f"[{qi}/{len(queries)}] {query!r} -> urls={record['total_urls']} "
                f"total_ms={timings['total_ms']}",
                file=sys.stderr,
            )
            if qi in {4, 8, 12, 16, 20}:
                elapsed = round(time.perf_counter() - t_run_start, 1)
                cp = _build_checkpoint(records, prev_qi, qi, elapsed, prev_elapsed)
                checkpoints.append(cp)
                print(
                    f"[CHECKPOINT Q{qi}] cumulative={cp['cumulative_s']}s avg/q={cp['avg_per_q_s']}s "
                    f"ok={cp['engines_ok']} rate_skip={cp['engines_rate_skip']}",
                    file=sys.stderr,
                )
                prev_qi = qi
                prev_elapsed = elapsed
    finally:
        await close_browser()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = _write_report(records, language, checkpoints, report_prefix)
    ok = sum(1 for r in records if r["total_urls"] > 0)
    print(f"\nReport: {path}", file=sys.stderr)
    print(f"Done: {ok}/{len(records)} queries with results", file=sys.stderr)


# FUNCTIONS

def _load_queries(path: Path, max_queries: int | None) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    qs = [ln.strip() for ln in lines if ln.strip()]
    return qs[:max_queries] if max_queries else qs


def _build_record(query: str, pools: dict, timings: dict) -> dict:
    engine_url_counts = {eng: len(pool) for eng, pool in pools.items()}
    return {
        "query":             query,
        "total_urls":        sum(engine_url_counts.values()),
        "engine_url_counts": engine_url_counts,
        "timings":           timings,
    }


def _build_checkpoint(records: list[dict], prev_qi: int, qi: int, elapsed: float, prev_elapsed: float) -> dict:
    seg_records = records[prev_qi:qi]
    seg_s = elapsed - prev_elapsed
    avg_per_q = round(seg_s / len(seg_records), 1)
    ok_count = 0
    rs_count = 0
    for rec in seg_records:
        for info in (rec["timings"] or {}).get("engine_details", {}).values():
            st = info.get("status", "")
            if st == "OK":
                ok_count += 1
            elif st == "RATE_SKIP":
                rs_count += 1
    return {
        "milestone": f"Q{qi}",
        "cumulative_s": elapsed,
        "avg_per_q_s": avg_per_q,
        "engines_ok": ok_count,
        "engines_rate_skip": rs_count,
    }


def _write_report(records: list[dict], language: str, checkpoints: list[dict], prefix: str = "pipeline_smoke") -> Path:
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{prefix}_{ts}.md"
    lines = (
        _render_header(records, language, ts)
        + _render_summary(records)
        + _render_timing_checkpoints(checkpoints)
        + ["", "---", ""]
        + _render_per_query_engine_breakdown(records)
        + _render_timing_section(records)
        + _render_engine_reliability(records)
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_header(records: list[dict], language: str, ts: str) -> list[str]:
    return [
        f"# Pipeline Smoke Report -- {ts}",
        "",
        f"**Language:** {language}  ",
        f"**Queries:** {len(records)}  ",
        f"**Queries with results:** {sum(1 for r in records if r['total_urls'] > 0)}",
        "",
    ]


def _render_summary(records: list[dict]) -> list[str]:
    L: list[str] = [
        "## Summary",
        "",
        "| # | Query | URLs returned |",
        "|---|-------|--------------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:65].replace("|", "\\|")
        L.append(f"| {i} | {q} | {r['total_urls']} |")
    return L


def _render_timing_checkpoints(checkpoints: list[dict]) -> list[str]:
    if not checkpoints:
        return []
    L: list[str] = [
        "",
        "## Timing Checkpoints",
        "",
        "| Milestone | Cumulative wall (s) | Avg/query in segment (s) | Engines OK | Engines RATE_SKIP |",
        "|-----------|--------------------:|-------------------------:|-----------:|------------------:|",
    ]
    for cp in checkpoints:
        L.append(
            f"| {cp['milestone']} | {cp['cumulative_s']} | {cp['avg_per_q_s']} "
            f"| {cp['engines_ok']} | {cp['engines_rate_skip']} |"
        )
    return L


def _render_per_query_engine_breakdown(records: list[dict]) -> list[str]:
    L: list[str] = ["## Per-Query Engine Breakdown", ""]
    for qi, r in enumerate(records, 1):
        L.append(f"### Q{qi}: {r['query']}")
        L.append("")
        det = (r["timings"] or {}).get("engine_details", {})
        if not det:
            L += ["*No engine data.*", ""]
            continue
        eu = r["engine_url_counts"]
        rows: list[tuple] = []
        for eng, info in det.items():
            status = info.get("status", "")
            ms     = info.get("ms", 0)
            n      = eu.get(eng, 0)
            reason = _STATUS_HINTS.get(status, "") if status != "OK" else ""
            rows.append((n, eng, status, reason, ms))
        rows.sort(key=lambda x: (-x[0], x[1]))
        L.append("| Engine | URLs | Status | Reason | ms |")
        L.append("|--------|-----:|--------|--------|----|")
        for n, eng, status, reason, ms in rows:
            L.append(f"| {eng} | {n} | {status} | {reason} | {ms} |")
        L.append("")
    return L


def _render_timing_section(records: list[dict]) -> list[str]:
    all_total_ms = [r["timings"]["total_ms"] for r in records if r["timings"]]
    L: list[str] = [
        "## Timing",
        "",
        "### Per-Query",
        "",
        "| # | Query | total_ms | fanout_ms | pool_ms | cache_ms |",
        "|---|-------|----------|---------|---------|---------|",
    ]
    for i, r in enumerate(records, 1):
        t = r["timings"]
        q = r["query"][:40].replace("|", "\\|")
        L.append(
            f"| {i} | {q} | {t.get('total_ms', '—')} | {t.get('engine_fanout_ms', '—')} "
            f"| {t.get('pool_build_ms', '—')} | {t.get('cache_write_ms', '—')} |"
        )
    if all_total_ms:
        srt = sorted(all_total_ms)
        p90 = srt[int(len(srt) * 0.9)]
        L += [
            "",
            "### Aggregate (total_ms across all queries)",
            "",
            "| min | median | p90 | mean | max |",
            "|-----|--------|-----|------|-----|",
            f"| {min(all_total_ms)} | {round(statistics.median(all_total_ms))} | {p90} "
            f"| {round(statistics.mean(all_total_ms))} | {max(all_total_ms)} |",
        ]
    return L


def _render_engine_reliability(records: list[dict]) -> list[str]:
    engine_data = _collect_engine_data(records)
    if not engine_data:
        return []

    L = _reliability_header()

    for eng in sorted(engine_data):
        d = engine_data[eng]
        c = d["counts"]
        n = sum(c.values())
        if n == 0:
            continue
        L.append(_render_engine_row(eng, c, n, d["ok_ms"]))

    top3_str = _top3_bottleneck(records)

    L += [
        "",
        f"**Top-3 bottleneck engines** (most queries where this engine had highest search_ms): {top3_str}",
        "",
    ]
    return L


def _collect_engine_data(records: list[dict]) -> dict[str, dict[str, Any]]:
    STATUS_KEYS = [
        "OK", "EMPTY",
        "TIMEOUT_WATCHDOG", "TIMEOUT_NONCOOP", "TIMEOUT_HTTPX",
        "ERROR_BROWSER", "ERROR_HTTP", "ERROR_PARSE", "ERROR_OTHER",
        "RATE_SKIP",
    ]
    engine_data: dict[str, dict[str, Any]] = {}
    for r in records:
        det = (r["timings"] or {}).get("engine_details", {})
        for eng, info in det.items():
            if eng not in engine_data:
                engine_data[eng] = {"counts": {k: 0 for k in STATUS_KEYS}, "ok_ms": []}
            st = info.get("status", "ERROR_OTHER")
            key = st if st in engine_data[eng]["counts"] else "ERROR_OTHER"
            engine_data[eng]["counts"][key] += 1
            if st == "OK":
                engine_data[eng]["ok_ms"].append(info.get("ms", 0))
    return engine_data


def _reliability_header() -> list[str]:
    cols = [
        "Engine", "n",
        "OK%", "EMPTY%",
        "T_WD%", "T_NC%", "T_HX%",
        "E_BR%", "E_HT%", "E_PA%", "E_OT%",
        "RS%", "mean_ms(OK)", "p95_ms",
    ]
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    header = "|" + "|".join(cols) + "|"
    return [
        "",
        "## Per-Engine Reliability Baseline",
        "",
        "> Source: `records[i]['timings']['engine_details']` (in-memory, identical to query_log.jsonl).",
        "> Percentages = count / n_queries × 100. mean_ms and p95_ms computed on OK entries only.",
        "",
        header,
        sep,
    ]


def _render_engine_row(eng: str, c: dict, n: int, ok_ms: list) -> str:
    def pct(k: str) -> str:
        v = c.get(k, 0)
        return f"{round(v / n * 100)}" if v else "0"

    if ok_ms:
        mean_ms = round(statistics.mean(ok_ms))
        p95_ms = round(statistics.quantiles(ok_ms, n=20)[18]) if len(ok_ms) >= 2 else ok_ms[0]
    else:
        mean_ms = "—"
        p95_ms = "—"

    return (
        f"| {eng} | {n} "
        f"| {pct('OK')} | {pct('EMPTY')} "
        f"| {pct('TIMEOUT_WATCHDOG')} | {pct('TIMEOUT_NONCOOP')} | {pct('TIMEOUT_HTTPX')} "
        f"| {pct('ERROR_BROWSER')} | {pct('ERROR_HTTP')} | {pct('ERROR_PARSE')} | {pct('ERROR_OTHER')} "
        f"| {pct('RATE_SKIP')} | {mean_ms} | {p95_ms} |"
    )


def _top3_bottleneck(records: list[dict]) -> str:
    bottleneck_counts: dict[str, int] = {}
    for r in records:
        det = (r["timings"] or {}).get("engine_details", {})
        if not det:
            continue
        slowest = max(det, key=lambda e: det[e].get("ms", 0))
        bottleneck_counts[slowest] = bottleneck_counts.get(slowest, 0) + 1
    top3 = sorted(bottleneck_counts, key=lambda e: bottleneck_counts[e], reverse=True)[:3]
    return ", ".join(f"{e} ({bottleneck_counts[e]}×)" for e in top3) if top3 else "—"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full pipeline smoke: search_web_workflow per query, engine-reliability focus."
    )
    parser.add_argument(
        "--max-queries",
        dest="max_queries",
        type=int,
        default=None,
        help="Limit to first N queries from queries.txt (default: all)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="ISO language code (default: en)",
    )
    parser.add_argument(
        "--engine-timeout",
        dest="engine_timeout",
        type=float,
        default=None,
        help="Hard timeout per engine call in seconds, e.g. 8.0 (default: None = no timeout)",
    )
    parser.add_argument(
        "--report-prefix",
        dest="report_prefix",
        default="pipeline_smoke",
        help="Report filename prefix (default: pipeline_smoke → pipeline_smoke_<ts>.md)",
    )
    args = parser.parse_args()
    asyncio.run(run_pipeline_smoke(args.max_queries, args.language, args.engine_timeout, args.report_prefix))
