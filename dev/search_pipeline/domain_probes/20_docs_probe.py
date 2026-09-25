#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines.google import GoogleEngine
from src.search.engines.duckduckgo import DuckDuckGoEngine
from src.search.browser import close_browser

from _docs_probe_config import ENGINE_NAMES, QUERIES, SUFFIX
from _docs_probe_report import write_report

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"

ENGINE_ORDER = list(zip(ENGINE_NAMES, [GoogleEngine, DuckDuckGoEngine]))

ENGINE_MAX = {
    "google":     100,
    "duckduckgo": 200,
}

BROWSER_SLEEP_S = 1.0


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    engines = _compute_engines()

    all_runs: dict[str, list[dict]] = {}
    run_stats = _compute_run_stats()

    await _run_docs_queries(engines, run_stats, all_runs)


# FUNCTIONS

def _compute_engines():
    engines = [(name, cls()) for name, cls in ENGINE_ORDER]
    return engines


def _compute_run_stats():
    run_stats: dict[str, dict] = {name: {"total": 0, "errors": 0} for name, _ in ENGINE_ORDER}
    return run_stats


async def _run_docs_queries(engines, run_stats, all_runs):
    try:
        for qi, base_query in enumerate(QUERIES, 1):
            query = base_query + SUFFIX
            print(f"\n=== Q{qi}/{len(QUERIES)}: {query!r} ===", file=sys.stderr)
            run_results: list[dict] = []

            for i, (eng_name, engine) in enumerate(engines):
                max_r = ENGINE_MAX[eng_name]
                print(f"  {eng_name} ...", file=sys.stderr, end="", flush=True)

                t0 = time.monotonic()
                try:
                    results = await engine.search(query, "en", max_r)
                    ms = round((time.monotonic() - t0) * 1000)
                    print(f" {len(results)} ({ms}ms)", file=sys.stderr)
                    run_stats[eng_name]["total"] += len(results)
                    for r in results:
                        run_results.append({
                            "engine":   eng_name,
                            "position": r.position,
                            "url":      r.url,
                        })
                except Exception as e:
                    ms = round((time.monotonic() - t0) * 1000)
                    print(f" ERROR {e} ({ms}ms)", file=sys.stderr)
                    run_stats[eng_name]["errors"] += 1

                if i < len(engines) - 1:
                    await asyncio.sleep(BROWSER_SLEEP_S)

            all_runs[base_query] = run_results
    finally:
        report_path = write_report(all_runs, run_stats, REPORT_DIR)
        print(f"\nReport: {report_path}", file=sys.stderr)
        try:
            await close_browser()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(run_probe())
