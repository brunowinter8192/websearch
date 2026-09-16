#!/usr/bin/env python3
"""Boilerplate/content block classifier over EVERY paired chromium/camoufox scrape in the
production log — a faithful, mechanical implementation of Kohlschuetter/Fankhauser/Nejdl (WSDM
2010, Algorithm 2), adapted to markdown, plus the jusText-style short-heading rescue rule, plus a
block-level PROSE test on top of CONTENT: CONTENT, at or under a corpus-derived length cap, and
containing a sentence-ending mark — added because a single very long markdown line (embedded JSON/
CSS/markup) can pass the CONTENT tree with a huge word count that no real prose block has. Builds
its own pair list from the production `scrape_log.jsonl` (every URL where both lanes have a
freshest record with no `acquisition_error` and real `bytes_returned`, plus a `content_path` —
the log no longer computes an "ok" verdict itself, see src/scraper/DOCS.md's Gotchas), no external
file dependency. Reports numbers only — no verdict on which lane is "better".
"""
# INFRASTRUCTURE
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lane_metrics_aggregate import compute_aggregate  # noqa: E402
from _lane_metrics_pairing import collect_pairs_from_scrape_log  # noqa: E402
from _lane_metrics_prose import (  # noqa: E402
    PROSE_PERCENTILE, compute_file_metrics, compute_metrics_from_blocks, compute_prose_cap,
)
from _lane_metrics_blocks import read_blocks  # noqa: E402
from _lane_metrics_report import write_report  # noqa: E402


# ORCHESTRATOR

# Build the pair list from the production log, derive the PROSE cap, classify both lanes per URL, report
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


def main():
    lane_metrics_workflow()


if __name__ == "__main__":
    main()
