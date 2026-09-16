# INFRASTRUCTURE
import argparse
import asyncio
import sys
from pathlib import Path

# Local import — run from project root: ./venv/bin/python dev/scrape_pipeline/07_pipe_scrape_eval.py
sys.path.insert(0, str(Path(__file__).parent))
# From p1_pipe_scraper.py: raw URL scraper (domcontentloaded, no filter, configurable knobs)
from p1_pipe_scraper import scrape_urls  # noqa: E402
from _pipe_scrape_eval_common import DISCOVERED_URLS, load_urls  # noqa: E402
from _pipe_scrape_eval_phase1 import phase1_concurrency_sweep  # noqa: E402
from _pipe_scrape_eval_phase2 import phase2_delay_sweep  # noqa: E402
from _pipe_scrape_eval_phase3 import phase3_full_run  # noqa: E402


# ORCHESTRATOR
async def main(phase: str, delay: float) -> None:
    urls = load_urls()
    print(f"Loaded {len(urls)} URLs from {DISCOVERED_URLS}")

    if phase == 'smoke':
        await smoke_test(urls)
    elif phase == 'phase1':
        await phase1_concurrency_sweep(urls)
    elif phase == 'phase2':
        await phase2_delay_sweep(urls)
    elif phase == 'phase3':
        await phase3_full_run(urls, delay_s=delay)
    else:
        raise ValueError(f"Unknown phase: {phase!r}")


# FUNCTIONS

# Smoke test: 1 URL, verify module runs end-to-end
async def smoke_test(urls: list[str]) -> None:
    print(f"Smoke test: 1 URL — delay=1.0s, timeout=15000ms, concurrency=1")
    sample = [urls[0]]
    results = await scrape_urls(sample, delay_s=1.0, page_timeout_ms=15000, concurrency=1)
    r = results[0]
    print(f"  url:     {r['url']}")
    print(f"  outcome: {r['outcome']}")
    print(f"  bytes:   {r['bytes']}")
    print(f"  wall_ms: {r['wall_ms']}")
    print(f"  status:  {r['status_code']}")
    valid = r['outcome'] in ('ok', 'empty', 'http_error', 'waf_429', 'error')
    assert valid, f"unexpected outcome: {r['outcome']}"
    print("Smoke OK")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipe-scraper eval harness')
    parser.add_argument(
        'phase',
        choices=['smoke', 'phase1', 'phase2', 'phase3'],
        help='smoke | phase1: WAF/concurrency sweep | phase2: delay sweep | phase3: full run',
    )
    parser.add_argument(
        '--delay', type=float, default=0.5,
        help='delay_s for phase3 (Phase 2 result: 0.5s; default=0.5)',
    )
    args = parser.parse_args()
    asyncio.run(main(args.phase, args.delay))
