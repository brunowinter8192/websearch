# INFRASTRUCTURE
import asyncio
import datetime
import sys
import time
from pathlib import Path

from p1_pipe_scraper import scrape_urls
from _pipe_scrape_eval_common import REPORTS_DIR, compute_metrics

DATA_DIR = Path(__file__).parent / "07_pipe_scrape_eval_data"

PHASE3_BATCH_SIZE = 30       # URLs per batch — matches WAF burst window from Phase 1
PHASE3_INTER_BATCH_S = 30.0  # pause between batches (conservative WAF recovery)
PHASE3_RETRY_COOLDOWN_S = 60.0  # wait before retry pass on 429 URLs


# FUNCTIONS

# WAF probe: fetch N URLs at c=1, return True if WAF is clear (no 429s). Retries up to max_attempts.
async def waf_probe_wait(
    urls: list[str],
    n: int = 3,
    max_attempts: int = 10,
    wait_s: float = 60.0,
) -> bool:
    probe = urls[:n]
    for attempt in range(1, max_attempts + 1):
        print(f"  WAF probe attempt {attempt}/{max_attempts} ({n} URLs, c=1, delay=0.5s) ...", flush=True)
        results = await scrape_urls(probe, delay_s=0.5, page_timeout_ms=15000, concurrency=1)
        for r in results:
            print(f"    {r['url'][-70:]}: {r['outcome']} status={r.get('status_code')}")
        all_ok = all(r['outcome'] in ('ok', 'empty') for r in results)
        if all_ok:
            print("  WAF CLEAR — proceeding")
            return True
        remaining = max_attempts - attempt
        if remaining > 0:
            print(f"  Ban active — waiting {wait_s:.0f}s ({remaining} attempts left) ...", flush=True)
            await asyncio.sleep(wait_s)
    print(f"  WAF still active after {max_attempts} probe attempts — aborting")
    return False


# Write Phase 3 report — batched run with optional retry pass
def write_phase3_report(
    m_main: dict,
    m_final: dict,
    wall_s_main: float,
    wall_s_total: float,
    delay_s: float,
    concurrency: int,
    waf_urls_main: list[str],
    waf_onset: int | None,
    retry_results: list[dict],
    output_dir: Path,
    ts: str,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"07_full_run_{ts}.md"

    lines = _format_phase3_header_and_main_pass(
        m_main, m_final, wall_s_main, delay_s, concurrency, waf_onset, output_dir)
    lines += _format_phase3_retry_section(retry_results)
    lines += _format_phase3_final_results_section(m_final, wall_s_total)
    lines += _format_phase3_latency_and_size_section(m_final)
    lines += _format_phase3_waf_urls_section(waf_urls_main)

    path.write_text('\n'.join(lines), encoding='utf-8')
    return path


def _format_phase3_header_and_main_pass(
    m_main: dict, m_final: dict, wall_s_main: float, delay_s: float,
    concurrency: int, waf_onset: int | None, output_dir: Path,
) -> list:
    return [
        "# Phase 3 — Full Run",
        "",
        f"Config: `concurrency={concurrency}`, `delay_s={delay_s}`, `page_timeout=15000ms`, "
        f"`wait_until=domcontentloaded`  ",
        f"Pacing: `batch_size={PHASE3_BATCH_SIZE}`, `inter_batch_sleep={PHASE3_INTER_BATCH_S}s`  ",
        f"Dataset: all {m_final['total']} URLs from `06_discovered_urls.txt`  ",
        f"Output dir: `{output_dir.name}/`",
        "",
        "## Main Pass",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total URLs | {m_main['total']} |",
        f"| Success (ok) | {m_main['ok']} |",
        f"| Empty (<100 B) | {m_main['empty']} |",
        f"| HTTP Error | {m_main['http_error']} |",
        f"| WAF 429 | {m_main['waf_429']} |",
        f"| Error (exception) | {m_main['error']} |",
        f"| Wallclock (main pass) | {wall_s_main:.0f}s |",
        f"| 429-onset position | {waf_onset if waf_onset is not None else 'N/A (no 429s)'} |",
    ]


def _format_phase3_retry_section(retry_results: list[dict]) -> list:
    lines = []
    if retry_results:
        retry_ok = sum(1 for r in retry_results if r['outcome'] == 'ok')
        retry_429 = sum(1 for r in retry_results if r['outcome'] == 'waf_429')
        lines += [
            "",
            f"## Retry Pass ({len(retry_results)} URLs, after {PHASE3_RETRY_COOLDOWN_S:.0f}s cooldown)",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Retried | {len(retry_results)} |",
            f"| Recovered (ok) | {retry_ok} |",
            f"| Still 429 | {retry_429} |",
            f"| Other | {len(retry_results) - retry_ok - retry_429} |",
        ]
    return lines


def _format_phase3_final_results_section(m_final: dict, wall_s_total: float) -> list:
    return [
        "",
        "## Final Results (after retry merge)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total URLs | {m_final['total']} |",
        f"| Success (ok) | {m_final['ok']} |",
        f"| Empty (<100 B) | {m_final['empty']} |",
        f"| HTTP Error | {m_final['http_error']} |",
        f"| WAF 429 (residual) | {m_final['waf_429']} |",
        f"| Error (exception) | {m_final['error']} |",
        f"| Total wallclock | {wall_s_total:.0f}s |",
    ]


def _format_phase3_latency_and_size_section(m_final: dict) -> list:
    return [
        "",
        "## Latency (ok URLs, final results)",
        "",
        "| p50_ms | p95_ms | max_ms | std_ms |",
        "|---|---|---|---|",
        f"| {m_final['lat_p50']} | {m_final['lat_p95']} | {m_final['lat_max']} | {m_final['lat_std']} |",
        "",
        "## Content Size (ok URLs, final results)",
        "",
        "| bytes_p50 | bytes_p95 |",
        "|---|---|",
        f"| {m_final['bytes_p50']:,} | {m_final['bytes_p95']:,} |",
    ]


def _format_phase3_waf_urls_section(waf_urls_main: list[str]) -> list:
    if waf_urls_main:
        lines = ["", f"## WAF-429 URLs in Main Pass ({len(waf_urls_main)} total)", ""]
        for url in waf_urls_main:
            lines.append(f"- {url}")
        return lines
    return ["", "## WAF-429 URLs", "", "None — WAF-safe at full scale (c=5, batched+paced)."]


# Phase 3 — Full run: WAF probe → batched main pass → optional retry pass
async def phase3_full_run(urls: list[str], delay_s: float, concurrency: int = 5) -> None:
    print(f"Phase 3: {len(urls)} URLs | c={concurrency} | delay={delay_s}s | "
          f"batch={PHASE3_BATCH_SIZE} | inter_batch={PHASE3_INTER_BATCH_S}s")

    # WAF probe: confirm budget reset before committing to 316-URL run
    print("\nStep 1: WAF probe (up to 10min wait) ...")
    clear = await waf_probe_wait(urls, n=3, max_attempts=10, wait_s=60.0)
    if not clear:
        print("ERROR: WAF ban did not lift — aborting Phase 3")
        sys.exit(1)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    output_dir = DATA_DIR / f"full_run_{ts}"

    t0 = time.time()
    all_results, main_wall_s = await run_main_pass_step(urls, delay_s, concurrency, output_dir, t0)
    m_main = compute_metrics(all_results)
    waf_urls_main, waf_onset = summarize_main_pass(all_results, m_main, main_wall_s)

    retry_results = await run_retry_pass_step(waf_urls_main, delay_s, concurrency, output_dir)

    total_wall_s = time.time() - t0
    final_results = merge_retry_results(all_results, retry_results)
    m_final = compute_metrics(final_results)

    report_path = write_phase3_report(
        m_main=m_main, m_final=m_final,
        wall_s_main=main_wall_s, wall_s_total=total_wall_s,
        delay_s=delay_s, concurrency=concurrency,
        waf_urls_main=waf_urls_main, waf_onset=waf_onset,
        retry_results=retry_results,
        output_dir=output_dir, ts=ts,
    )
    print(f"\nPhase 3 report: {report_path}")
    print(f"Output dir:    {output_dir}")
    print(f"FINAL: ok={m_final['ok']}/{m_final['total']} 429s={m_final['waf_429']} "
          f"empty={m_final['empty']} bytes_p50={m_final['bytes_p50']:,} wall={total_wall_s:.0f}s")


# Main pass: batched with inter-batch pause
async def run_main_pass_step(
    urls: list[str], delay_s: float, concurrency: int, output_dir: Path, t0: float,
) -> tuple[list[dict], float]:
    print(f"\nStep 2: Main pass — {len(urls)} URLs in batches of {PHASE3_BATCH_SIZE} ...")
    all_results: list[dict] = []
    batches = [urls[i:i + PHASE3_BATCH_SIZE] for i in range(0, len(urls), PHASE3_BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        offset = batch_idx * PHASE3_BATCH_SIZE
        print(f"  Batch {batch_idx + 1}/{len(batches)} (URLs {offset}–{offset + len(batch) - 1}) ...",
              flush=True)
        results = await scrape_urls(
            batch, delay_s=delay_s, page_timeout_ms=15000,
            concurrency=concurrency, output_dir=output_dir,
        )
        for i, r in enumerate(results):
            r['position'] = offset + i
        all_results.extend(results)

        b_ok = sum(1 for r in results if r['outcome'] == 'ok')
        b_429 = sum(1 for r in results if r['outcome'] == 'waf_429')
        b_empty = sum(1 for r in results if r['outcome'] == 'empty')
        print(f"    ok={b_ok} empty={b_empty} 429s={b_429}")

        if batch_idx < len(batches) - 1:
            print(f"    pause {PHASE3_INTER_BATCH_S:.0f}s ...", flush=True)
            await asyncio.sleep(PHASE3_INTER_BATCH_S)

    main_wall_s = time.time() - t0
    return all_results, main_wall_s


def summarize_main_pass(all_results: list[dict], m_main: dict, main_wall_s: float) -> tuple[list[str], int | None]:
    waf_urls_main = [r['url'] for r in all_results if r['outcome'] == 'waf_429']
    waf_positions = sorted(r['position'] for r in all_results if r['outcome'] == 'waf_429')
    waf_onset = waf_positions[0] if waf_positions else None
    print(f"\n  Main pass done: ok={m_main['ok']}/{m_main['total']} 429s={m_main['waf_429']} "
          f"onset={waf_onset} wall={main_wall_s:.0f}s")
    return waf_urls_main, waf_onset


# Retry pass: one attempt for any 429s after cooldown
async def run_retry_pass_step(
    waf_urls_main: list[str], delay_s: float, concurrency: int, output_dir: Path,
) -> list[dict]:
    retry_results: list[dict] = []
    if waf_urls_main:
        print(f"\nStep 3: Retry pass — {len(waf_urls_main)} URLs after {PHASE3_RETRY_COOLDOWN_S:.0f}s cooldown ...")
        await asyncio.sleep(PHASE3_RETRY_COOLDOWN_S)
        retry_results = await scrape_urls(
            waf_urls_main, delay_s=delay_s, page_timeout_ms=15000,
            concurrency=concurrency, output_dir=output_dir,
        )
        r_ok = sum(1 for r in retry_results if r['outcome'] == 'ok')
        r_429 = sum(1 for r in retry_results if r['outcome'] == 'waf_429')
        print(f"  Retry: ok={r_ok}/{len(retry_results)} still-429={r_429}")
    else:
        print("\nStep 3: No retry needed (0 WAF 429s in main pass)")
    return retry_results


# Merge retry successes back into results
def merge_retry_results(all_results: list[dict], retry_results: list[dict]) -> list[dict]:
    final_results = list(all_results)
    if retry_results:
        retry_map = {r['url']: r for r in retry_results if r['outcome'] == 'ok'}
        for i, r in enumerate(final_results):
            if r['url'] in retry_map:
                final_results[i] = retry_map[r['url']]
    return final_results
