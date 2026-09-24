#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

import src.search.engines.scholar as scholar_mod
import src.search.engines.google as google_mod

from src.search.engines.google import GoogleEngine
from src.search.engines.scholar import ScholarEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.engines.openalex import OpenAlexEngine
from src.search.browser import close_browser
from src.search.rate_limiter import _limiters, get_limiter

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR  = SCRIPT_DIR / "md"
MAX_RESULTS = 10
PAUSE_S     = 120

QUERIES = [
    "python asyncio",
    "tolkien hobbit",
    "sparse retrieval models",
]

ENGINES = [
    ("google",         GoogleEngine()),
    ("google_scholar", ScholarEngine()),
    ("duckduckgo",     DuckDuckGoEngine()),
    ("openalex",       OpenAlexEngine()),
]

HTTP_ENGINES = ("openalex",)

_ORIG = {
    "scholar_MAX_WAIT_CYCLES": scholar_mod.MAX_WAIT_CYCLES,
    "scholar_WAIT_INTERVAL":   scholar_mod.WAIT_INTERVAL,
    "scholar_handle_consent":  scholar_mod._handle_consent,
    "google_handle_consent":   google_mod._handle_consent,
    **{f"{n}_max_requests": _limiters[n]._max_requests for n in HTTP_ENGINES},
}


async def _scholar_consent_noop(tab) -> None:
    await tab.execute_script(scholar_mod._JS_CONSENT)


async def _google_consent_noop(tab) -> None:
    await tab.execute_script(google_mod._JS_CONSENT)


def apply_config_b() -> None:
    scholar_mod.MAX_WAIT_CYCLES = 3
    scholar_mod.WAIT_INTERVAL   = 0.2
    scholar_mod._handle_consent = _scholar_consent_noop
    google_mod._handle_consent  = _google_consent_noop
    for name in HTTP_ENGINES:
        _limiters[name]._max_requests = 30
        _limiters[name]._tokens.clear()


def restore_config_a() -> None:
    scholar_mod.MAX_WAIT_CYCLES = _ORIG["scholar_MAX_WAIT_CYCLES"]
    scholar_mod.WAIT_INTERVAL   = _ORIG["scholar_WAIT_INTERVAL"]
    scholar_mod._handle_consent = _ORIG["scholar_handle_consent"]
    google_mod._handle_consent  = _ORIG["google_handle_consent"]
    for name in HTTP_ENGINES:
        _limiters[name]._max_requests = _ORIG[f"{name}_max_requests"]
        _limiters[name]._tokens.clear()


# ORCHESTRATOR

async def run_ablation() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== CONFIG A (status quo) ===", file=sys.stderr)
    records_a = await run_config("A")
    await close_browser()

    print(f"\nPausing {PAUSE_S}s for rate-limiter buckets to drain…", file=sys.stderr)
    await asyncio.sleep(PAUSE_S)
    print("Pause done.", file=sys.stderr)

    print("\n=== CONFIG B (aggressive) ===", file=sys.stderr)
    apply_config_b()
    try:
        records_b = await run_config("B")
    finally:
        restore_config_a()
        await close_browser()

    report_path = write_report(records_a, records_b)
    print(f"\nReport: {report_path}", file=sys.stderr)


async def run_config(label: str) -> list[dict]:
    all_records = []
    for qi, query in enumerate(QUERIES):
        print(f"  [{qi+1}/{len(QUERIES)}] {query!r}", file=sys.stderr, end="", flush=True)
        t0    = time.monotonic()
        tasks = [engine_timed(name, eng, query) for name, eng in ENGINES]
        batch = await asyncio.gather(*tasks)
        wall_ms = round((time.monotonic() - t0) * 1000)
        print(f" → wall {wall_ms}ms", file=sys.stderr)
        for r in batch:
            r["config"]  = label
            r["wall_ms"] = wall_ms
            status_sym = "✓" if r["status"] == "OK" else "✗"
            print(
                f"    {status_sym} {r['engine']:16} {r['latency_ms']:5}ms  "
                f"{r['returned']:3} results",
                file=sys.stderr,
            )
        all_records.extend(batch)
    return all_records


# FUNCTIONS

async def engine_timed(name: str, engine, query: str) -> dict:
    await get_limiter(engine.name).acquire()
    t0 = time.monotonic()
    try:
        results = await engine.search(query, "en", MAX_RESULTS)
        latency = round((time.monotonic() - t0) * 1000)
        return {
            "engine":     name,
            "query":      query,
            "latency_ms": latency,
            "returned":   len(results),
            "status":     "OK" if results else "EMPTY",
            "urls":       {r.url for r in results},
        }
    except Exception as e:
        return {
            "engine":     name,
            "query":      query,
            "latency_ms": round((time.monotonic() - t0) * 1000),
            "returned":   0,
            "status":     "ERROR",
            "urls":       set(),
            "error":      f"{type(e).__name__}: {str(e)[:80]}",
        }


def make_index(records: list[dict]) -> dict:
    return {(r["engine"], r["query"]): r for r in records}


def jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def write_report(records_a: list[dict], records_b: list[dict]) -> Path:
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    path  = REPORT_DIR / f"timing_ablation_{ts}.md"
    idx_a = make_index(records_a)
    idx_b = make_index(records_b)
    eng_names = [n for n, _ in ENGINES]

    lines = _render_config_overview(ts)
    lines += _render_wall_clock(records_a, records_b)
    lines += _render_per_call_detail(eng_names, idx_a, idx_b)
    lines += _render_mean_latency(eng_names, records_a, records_b)
    jaccard_rows, jaccard_by_engine = _render_jaccard_pairs(eng_names, idx_a, idx_b)
    lines += jaccard_rows
    lines += _render_jaccard_summary(eng_names, jaccard_by_engine)
    lines += _render_bottom_line(records_a, records_b, jaccard_by_engine)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_config_overview(ts: str) -> list[str]:
    return [
        f"# Timing Ablation A vs B — {ts}",
        "",
        "## Config Overview",
        "",
        "| Parameter | CONFIG A (status quo) | CONFIG B (aggressive) |",
        "|-----------|----------------------|----------------------|",
        "| Scholar MAX_WAIT_CYCLES | 15 | 3 |",
        "| Scholar WAIT_INTERVAL | 1.0s | 0.2s |",
        "| Scholar max polling budget | 15.0s | 0.6s |",
        "| Google/Scholar consent sleep | 2.0s | 0s — SOCS cookie prevents redirect; Δ expected 0 |",
        "| OpenAlex / CrossRef / SE rate limit | 4 req/min | 30 req/min |",
        "| Browser engine rate limits | 4 req/min | 4 req/min (unchanged) |",
        "| Execution mode | asyncio.gather × 8 engines per query | same |",
        f"| max_results | {MAX_RESULTS} | {MAX_RESULTS} |",
        "",
        "---",
        "",
        "## Per-Query Wall-Clock",
        "",
        "| Query | A (ms) | B (ms) | Δ ms | Δ% |",
        "|-------|--------|--------|------|-----|",
    ]


def _render_wall_clock(records_a: list[dict], records_b: list[dict]) -> list[str]:
    lines = []
    for q in QUERIES:
        wa = next((r["wall_ms"] for r in records_a if r["query"] == q), None)
        wb = next((r["wall_ms"] for r in records_b if r["query"] == q), None)
        if wa is not None and wb is not None:
            d   = wb - wa
            pct = f"{d / wa * 100:+.1f}%" if wa else "n/a"
            lines.append(f"| {q} | {wa} | {wb} | {d:+d} | {pct} |")
    return lines


def _render_per_call_detail(eng_names: list[str], idx_a: dict, idx_b: dict) -> list[str]:
    lines = [
        "",
        "---",
        "",
        "## Per-Engine Latency",
        "",
        "### Per-Call Detail",
        "",
        "| Engine | Query | A (ms) | B (ms) | Δ ms | A status | B status |",
        "|--------|-------|--------|--------|------|----------|----------|",
    ]
    for eng in eng_names:
        for q in QUERIES:
            ra = idx_a.get((eng, q))
            rb = idx_b.get((eng, q))
            a_ms   = ra["latency_ms"] if ra else "—"
            b_ms   = rb["latency_ms"] if rb else "—"
            d_str  = f"{rb['latency_ms'] - ra['latency_ms']:+d}" if (ra and rb) else "—"
            a_stat = ra["status"] if ra else "—"
            b_stat = rb["status"] if rb else "—"
            lines.append(f"| {eng} | {q} | {a_ms} | {b_ms} | {d_str} | {a_stat} | {b_stat} |")
    return lines


def _render_mean_latency(eng_names: list[str], records_a: list[dict], records_b: list[dict]) -> list[str]:
    lines = [
        "",
        "### Mean Latency Per Engine (across 3 queries)",
        "",
        "| Engine | A mean (ms) | B mean (ms) | Δ ms | Δ% |",
        "|--------|-------------|-------------|------|-----|",
    ]
    for eng in eng_names:
        a_vals = [r["latency_ms"] for r in records_a if r["engine"] == eng]
        b_vals = [r["latency_ms"] for r in records_b if r["engine"] == eng]
        if a_vals and b_vals:
            am = round(mean(a_vals))
            bm = round(mean(b_vals))
            d  = bm - am
            pct = f"{d / am * 100:+.1f}%" if am else "n/a"
            lines.append(f"| {eng} | {am} | {bm} | {d:+d} | {pct} |")
    return lines


def _render_jaccard_pairs(eng_names: list[str], idx_a: dict, idx_b: dict) -> tuple[list[str], dict]:
    lines = [
        "",
        "---",
        "",
        "## URL Set Comparison — Jaccard Index",
        "",
        "### Per (Engine, Query)",
        "",
        "| Engine | Query | \\|A\\| | \\|B\\| | \\|A∩B\\| | \\|A∪B\\| | Jaccard |",
        "|--------|-------|------|------|--------|--------|---------|",
    ]
    jaccard_by_engine: dict[str, list[float]] = {n: [] for n in eng_names}
    for eng in eng_names:
        for q in QUERIES:
            ra = idx_a.get((eng, q))
            rb = idx_b.get((eng, q))
            ua = ra["urls"] if ra else set()
            ub = rb["urls"] if rb else set()
            j  = jaccard(ua, ub)
            jaccard_by_engine[eng].append(j)
            lines.append(
                f"| {eng} | {q} | {len(ua)} | {len(ub)} | "
                f"{len(ua & ub)} | {len(ua | ub)} | {j:.3f} |"
            )
    return lines, jaccard_by_engine


def _render_jaccard_summary(eng_names: list[str], jaccard_by_engine: dict) -> list[str]:
    lines = [
        "",
        "### Per-Engine Jaccard Summary",
        "",
        "| Engine | Mean Jaccard | Min Jaccard |",
        "|--------|-------------|-------------|",
    ]
    for eng in eng_names:
        jv = jaccard_by_engine[eng]
        if jv:
            lines.append(f"| {eng} | {mean(jv):.3f} | {min(jv):.3f} |")
    return lines


def _render_bottom_line(records_a: list[dict], records_b: list[dict], jaccard_by_engine: dict) -> list[str]:
    all_j  = [j for vals in jaccard_by_engine.values() for j in vals]
    mean_j = mean(all_j) if all_j else 0.0
    min_j  = min(all_j)  if all_j else 0.0

    scholar_note = _scholar_note(records_a, records_b)
    wall_note = _wall_note(records_a, records_b)
    verdict = _verdict(min_j)

    return [
        "",
        "---",
        "",
        "## Bottom Line",
        "",
        f"Overall Jaccard: mean {mean_j:.3f}, min {min_j:.3f}.  ",
        f"{scholar_note}  ",
        f"{wall_note}",
        "",
        f"**Verdict:** {verdict}",
    ]


def _scholar_note(records_a: list[dict], records_b: list[dict]) -> str:
    scholar_a = [r["latency_ms"] for r in records_a if r["engine"] == "google_scholar"]
    scholar_b = [r["latency_ms"] for r in records_b if r["engine"] == "google_scholar"]
    scholar_note = ""
    if scholar_a and scholar_b:
        sa = round(mean(scholar_a))
        sb = round(mean(scholar_b))
        scholar_note = f"Scholar mean latency: {sa}ms (A) → {sb}ms (B), Δ {sb-sa:+d}ms."
    return scholar_note


def _wall_note(records_a: list[dict], records_b: list[dict]) -> str:
    wall_a_vals = list(dict.fromkeys(r["wall_ms"] for r in records_a))
    wall_b_vals = list(dict.fromkeys(r["wall_ms"] for r in records_b))
    wall_note = ""
    if wall_a_vals and wall_b_vals:
        wa = round(mean(wall_a_vals))
        wb = round(mean(wall_b_vals))
        wall_note = f"Mean per-query wall-clock: {wa}ms (A) → {wb}ms (B), Δ {wb-wa:+d}ms."
    return wall_note


def _verdict(min_j: float) -> str:
    if min_j >= 0.95:
        return (
            "**EQUIVALENT** — URL sets stable across all engines (min Jaccard ≥ 0.95). "
            "CONFIG B is safe to adopt. Scholar polling reduction carries no result loss."
        )
    elif min_j >= 0.80:
        return (
            "**MOSTLY EQUIVALENT** — Minor divergence in at least one engine (min Jaccard < 0.95). "
            "Investigate the engine(s) with lowest Jaccard before adopting B wholesale."
        )
    else:
        return (
            "**NOT EQUIVALENT** — Significant URL divergence (min Jaccard < 0.80). "
            "CONFIG B causes result loss. Do not adopt; investigate per-engine failure."
        )


if __name__ == "__main__":
    asyncio.run(run_ablation())
