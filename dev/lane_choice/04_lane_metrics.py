#!/usr/bin/env python3
# INFRASTRUCTURE
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lane_metrics_aggregate import compute_aggregate
from _lane_metrics_pairing import collect_pairs_from_scrape_log
from _lane_metrics_prose import (
    PROSE_PERCENTILE, compute_file_metrics, compute_metrics_from_blocks, compute_prose_cap,
)
from _lane_metrics_blocks import read_blocks
from _lane_metrics_report import write_report


# ORCHESTRATOR

def main():
    lane_metrics_workflow()


# FUNCTIONS

def lane_metrics_workflow() -> None:
    t_start = time.perf_counter()

    pairs = collect_pairs_from_scrape_log()
    chromium_blocks_by_url = {pair["url"]: read_blocks(pair["chromium_path"]) for pair in pairs}
    cap, distribution = compute_prose_cap(list(chromium_blocks_by_url.values()))

    results = []
    for pair in pairs:
        url = pair["url"]
        lane_metrics = {
            "chromium": compute_metrics_from_blocks(chromium_blocks_by_url[url], cap),
            "camoufox": compute_file_metrics(pair["camoufox_path"], cap),
        }
        results.append({"url": url, "lanes": lane_metrics})

    aggregate = compute_aggregate(results)
    report_path = write_report(results, aggregate, cap, distribution)

    wall_s = time.perf_counter() - t_start
    print(f"Pairs: {len(pairs)}", file=sys.stderr)
    print(f"PROSE cap: {cap} words (p{PROSE_PERCENTILE} of {distribution['n']} chromium blocks)", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(f"Wall time: {wall_s:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
