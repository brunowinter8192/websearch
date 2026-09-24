#!/usr/bin/env python3
"""Download-classify probe — sniff-classifies academic URLs from the search pool without saving any content."""

# INFRASTRUCTURE
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

from _download_classify_probe_pool import (
    _latest_report, _extract_pool, _filter_and_tier, _apply_doi_sampling, _write_pool_files,
)
from _download_classify_probe_classify import _classify_all
from _download_classify_probe_report import _write_report

SCRIPT_DIR = Path(__file__).parent.parent
REPORT_DIR = SCRIPT_DIR / "md"
DATA_DIR = SCRIPT_DIR / "txt"

SMOKE_REPORTS_GLOB = "pipeline_smoke_*.md"
FREE_WORD_REPORTS_GLOB = "free_word_injection_probe_*.md"


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Pool extraction
    smoke_path = _latest_report(SMOKE_REPORTS_GLOB, REPORT_DIR)
    free_path = _latest_report(FREE_WORD_REPORTS_GLOB, REPORT_DIR)
    print(f"[pool] smoke={smoke_path.name}", file=sys.stderr)
    print(f"[pool] free_word={free_path.name}", file=sys.stderr)

    all_urls = _extract_pool(smoke_path, free_path)
    tier_pool = _filter_and_tier(all_urls)
    sampled_pool, doi_sample = _apply_doi_sampling(tier_pool)
    _write_pool_files(sampled_pool, doi_sample, ts, DATA_DIR)

    total = len(sampled_pool)
    print(f"[pool] {total} URLs to classify (doi sample={len(doi_sample)}/all={sum(1 for u,t in tier_pool if t=='T3')})", file=sys.stderr)

    # Classification
    t_wall_start = time.monotonic()
    results = await _classify_all(sampled_pool)
    wall_secs = time.monotonic() - t_wall_start

    report_path = _write_report(results, sampled_pool, doi_sample, wall_secs, smoke_path, free_path, ts, REPORT_DIR)
    print(f"\nReport: {report_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run_probe())
