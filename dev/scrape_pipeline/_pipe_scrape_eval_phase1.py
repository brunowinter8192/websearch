# INFRASTRUCTURE
import datetime
import time
from pathlib import Path

from p1_pipe_scraper import scrape_urls
from _pipe_scrape_eval_common import DISCOVERED_URLS, REPORTS_DIR, compute_metrics, stratify


# FUNCTIONS

async def phase1_concurrency_sweep(urls: list[str], sample_n: int = 30) -> int:
    sample = stratify(urls, sample_n)
    print(f"Phase 1: concurrency sweep — {len(sample)} stratified URLs, delay=1.0s, timeout=15000ms")
    print(f"Sample (first 3): {sample[:3]}")

    sweep_rows = []
    for concurrency in [1, 3, 5, 10]:
        print(f"\n  concurrency={concurrency} ...", flush=True)
        t0 = time.time()
        results = await scrape_urls(
            sample, delay_s=1.0, page_timeout_ms=15000, concurrency=concurrency
        )
        wall_s = time.time() - t0
        m = compute_metrics(results)
        sweep_rows.append((concurrency, m, wall_s))
        print(f"  ok={m['ok']}/{m['total']} empty={m['empty']} 429s={m['waf_429']} "
              f"p50={m['lat_p50']}ms p95={m['lat_p95']}ms wall={wall_s:.0f}s")

        if m['waf_429'] > 0:
            print(f"  ✗ WAF triggered at concurrency={concurrency} — stopping sweep early")
            break

    report_path, best = write_phase1_report(sweep_rows, len(sample))
    print(f"\nPhase 1 report: {report_path}")
    print(f"Recommended concurrency: {best}")
    return best


def write_phase1_report(sweep_rows: list[tuple], sample_n: int) -> tuple[Path, int]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    path = REPORTS_DIR / f"07_concurrency_sweep_{ts}.md"

    best = 1
    for concurrency, m, _ in sweep_rows:
        if m['waf_429'] == 0:
            best = concurrency

    lines = [
        "# Phase 1 — Concurrency Sweep (WAF Detection)",
        "",
        f"Input: {DISCOVERED_URLS.name} ({sample_n} stratified URLs)  ",
        "Fixed: `delay=1.0s`, `page_timeout=15000ms`, `wait_until=domcontentloaded`",
        "",
        "| Concurrency | Success | Empty | HTTPErr | 429s | p50_ms | p95_ms | max_ms | Wall_s | WAF-Safe |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for concurrency, m, wall_s in sweep_rows:
        lines.append(fmt_sweep_row(concurrency, m, wall_s))

    lines += [
        "",
        "## Conclusion",
        "",
        f"**WAF-safe concurrency: {best}** — highest level with 0×429",
        "",
        f"→ Use `concurrency={best}` for Phase 2 (delay sweep) and Phase 3 (full run).",
        "",
        "## Phase 2 + 3 Plan (Successor)",
        "",
        "Phase 2 — Delay sweep on 30 stratified URLs at `concurrency=" + str(best) + "`:  ",
        "  Sweep `delay_s` ∈ {0.5, 1.0, 2.0, 3.0}. Metric: bytes_p50 as completeness proxy.",
        "",
        "Phase 3 — Full run on all URLs at best (concurrency, delay):  ",
        "  Save raw markdown to `07_pipe_scrape_eval_data/full_run_<ts>/`.  ",
        "  Report: p50/p95/max latency, success/empty/timeout rates, total wallclock.",
        "",
        "Then record the config decision in process history.",
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path, best


def fmt_sweep_row(concurrency: int, m: dict, wall_s: float) -> str:
    waf_safe = "✓" if m['waf_429'] == 0 else "✗"
    return (
        f"| {concurrency} | {m['ok']}/{m['total']} | {m['empty']} | "
        f"{m['http_error']} | {m['waf_429']} | "
        f"{m['lat_p50']} | {m['lat_p95']} | {m['lat_max']} | "
        f"{wall_s:.0f}s | {waf_safe} |"
    )
