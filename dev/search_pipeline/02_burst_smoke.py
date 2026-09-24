#!/usr/bin/env python3
"""Burst smoke test — N queries per burst via searxng-cli search_batch, one Chrome boot per burst."""

# INFRASTRUCTURE
import argparse
import asyncio
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yml"
CLI_PY = PROJECT_ROOT / "cli.py"
QUERY_TIMEOUT_S = 120
SNIPPET_PREVIEW = 200


# ORCHESTRATOR

async def run_burst_smoke(queries_per_burst: int, cooldown: float, max_queries: int | None) -> None:
    cfg = load_config(CONFIG_PATH)
    all_queries = load_queries(SCRIPT_DIR / cfg["run"]["queries_file"])
    if max_queries is not None:
        all_queries = all_queries[:max_queries]
    report_dir = (SCRIPT_DIR / cfg["report"]["output_dir"]).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    batches = [all_queries[i:i + queries_per_burst] for i in range(0, len(all_queries), queries_per_burst)]
    records: list[dict] = []
    batch_times: list[float] = []

    t_total = time.monotonic()
    for bi, batch in enumerate(batches, 1):
        t_batch = time.monotonic()
        batch_records = await run_batch(batch, bi)
        batch_elapsed = time.monotonic() - t_batch
        batch_times.append(batch_elapsed)
        records.extend(batch_records)
        statuses = " ".join(r["status"] for r in batch_records)
        start_idx = sum(len(batches[j]) for j in range(bi - 1)) + 1
        end_idx = start_idx + len(batch) - 1
        print(f"[Batch {bi}/{len(batches)}] queries {start_idx}-{end_idx}, "
              f"wall={batch_elapsed:.1f}s, status: {statuses}", file=sys.stderr)
        if bi < len(batches) and cooldown > 0:
            await asyncio.sleep(cooldown)
    total_elapsed = time.monotonic() - t_total

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = write_report(records, batch_times, total_elapsed, report_dir, ts, len(batches),
                                queries_per_burst, cooldown)
    counts = Counter(r["status"] for r in records)
    dist = " / ".join(f"{v} {k}" for k, v in counts.most_common())
    times = [r["search_ms"] for r in records]
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Result: {dist} (out of {len(records)})", file=sys.stderr)
    print(f"Timing: mean {int(statistics.mean(times))}ms / max {max(times)}ms", file=sys.stderr)


# FUNCTIONS

# Load and return parsed config.yml
def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# Load queries from file, one per line, skip blank lines
def load_queries(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


# Run one batch of queries via search_batch subprocess, return per-query result records
async def run_batch(batch_queries: list[str], batch_idx: int) -> list[dict]:
    t0 = time.monotonic()
    batch_timeout = len(batch_queries) * QUERY_TIMEOUT_S
    try:
        args = [sys.executable, str(CLI_PY), "search_batch"] + batch_queries + ["--engines", "google", "--pages", "1"]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=batch_timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            per_ms = int(batch_timeout * 1000 // len(batch_queries))
            return [_record(q, batch_idx, "ERROR", 0, 0, per_ms, [], "timeout")
                    for q in batch_queries]
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        per_query_ms = elapsed_ms // max(len(batch_queries), 1)
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        blocks = stdout.split("\n---\n")
        while len(blocks) < len(batch_queries):
            blocks.append("")
        records = []
        for q, block in zip(batch_queries, blocks):
            count, results = parse_stdout(block)
            domains = {_domain(r["url"]) for r in results if r["url"]}
            sample = [{"url": r["url"], "snippet": r["snippet"][:SNIPPET_PREVIEW] if r["snippet"] else None}
                      for r in results[:3]]
            records.append(_record(q, batch_idx,
                                   derive_status(count, len(domains), stderr, proc.returncode),
                                   count, len(domains), per_query_ms, sample))
        return records
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return [_record(q, batch_idx, "ERROR", 0, 0, elapsed_ms, [], str(e)[:80])
                for q in batch_queries]


# Build per-query record dict
def _record(query, batch_idx, status, count, domains, search_ms, sample_results, note=""):
    return {"query": query, "batch": batch_idx, "status": status,
            "count": count, "domains": domains, "search_ms": search_ms,
            "sample_results": sample_results, "note": note}


# Parse one result block from search_batch stdout: return (result_count, list of {url, snippet})
def parse_stdout(block: str) -> tuple[int, list[dict]]:
    if "No results found for" in block:
        return 0, []
    m = re.search(r'Found (\d+) results for', block)
    if not m:
        return 0, []
    count = int(m.group(1))
    results = []
    lines = block.splitlines()
    for i, line in enumerate(lines):
        um = re.match(r'^\s+URL: (.+)$', line)
        if um:
            url = um.group(1).strip()
            snippet = None
            if i + 1 < len(lines):
                sm = re.match(r'^\s+Snippet: (.+)$', lines[i + 1])
                if sm:
                    snippet = sm.group(1).strip()
            results.append({"url": url, "snippet": snippet})
    return count, results


# Derive status from count, domains, stderr content and exit code
def derive_status(count: int, domains: int, stderr: str, returncode: int) -> str:
    if returncode != 0:
        return "ERROR"
    # Positive results: trust the count, ignore batch-shared stderr noise
    if count > 0:
        if count >= 8 and domains >= 5:
            return "OK"
        return "SUSPECT"
    # No results: check stderr for the actual reason
    if "CAPTCHA detected" in stderr:
        return "CAPTCHA"
    if "Rate limited" in stderr:
        return "RATE_LIMIT"
    if "Google search failed" in stderr:
        return "ERROR"
    return "EMPTY"


# Extract domain from URL string
def _domain(url: str) -> str:
    try:
        return urlparse(url.strip()).netloc
    except Exception:
        return ""


# Write markdown report and return path
def write_report(records, batch_times, total_s, report_dir, ts, n_batches,
                 queries_per_burst, cooldown) -> Path:
    path = report_dir / f"burst_{ts}.md"
    counts = Counter(r["status"] for r in records)
    lines = _render_config_overview(records, ts, n_batches, queries_per_burst, cooldown, total_s, counts)
    lines += _render_status_distribution(counts)
    lines += _render_per_query_results(records)
    lines += _render_timing_summary(records, batch_times)
    lines += _render_sample_results(records)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_config_overview(records, ts, n_batches, queries_per_burst, cooldown, total_s, counts) -> list[str]:
    dist = " / ".join(f"{v} {k}" for k, v in counts.most_common())
    total_min, total_sec = divmod(int(total_s), 60)
    return [
        f"# Burst Smoke Report — burst_{ts}",
        "",
        "## Configuration",
        f"- Queries file: dev/search_pipeline/queries.txt ({len(records)} queries)",
        "- Engine: google (--engines google)",
        "- Pages: 1",
        f"- Queries per burst: {queries_per_burst} (sequential, shared Chrome)",
        f"- Cooldown between batches: {cooldown}s",
        f"- Total batches: {n_batches}",
        "",
        "## Overview",
        f"- Total wall time: {total_min} min {total_sec} s",
        f"- Status distribution: {dist}",
        "",
    ]


def _render_status_distribution(counts) -> list[str]:
    lines = [
        "## Status Distribution",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for status, cnt in counts.most_common():
        lines.append(f"| {status} | {cnt} |")
    return lines


def _render_per_query_results(records) -> list[str]:
    lines = [
        "",
        "## Per-Query Results",
        "| Idx | Query | Status | Results | Domains | ~ms/query | Batch |",
        "|-----|-------|--------|---------|---------|-----------|-------|",
    ]
    for i, r in enumerate(records, 1):
        q = r["query"][:50].replace("|", "\\|")
        lines.append(f"| {i} | {q} | {r['status']} | {r['count']} "
                     f"| {r['domains']} | {r['search_ms']} | {r['batch']} |")
    return lines


def _render_timing_summary(records, batch_times) -> list[str]:
    times = [r["search_ms"] for r in records]
    st = sorted(times)
    n = len(st)
    lines = [
        "",
        "## Timing Summary",
        "",
        "### Per-Query Estimated Time (ms, batch total ÷ N)",
        f"- Mean: {int(statistics.mean(times))}",
        f"- Median: {int(statistics.median(times))}",
        f"- Max: {max(times)}",
        f"- p95: {st[min(int(n * 0.95), n - 1)]}",
        "",
        "### Per-Batch Wall Time (s)",
    ]
    for bi, bt in enumerate(batch_times, 1):
        lines.append(f"- Batch {bi}: {bt:.1f}s")
    return lines


def _render_sample_results(records) -> list[str]:
    lines = ["", "## Sample Results (first 3 per query)", ""]
    for i, r in enumerate(records, 1):
        lines.append(f"### Q{i}: {r['query']}")
        if not r["sample_results"]:
            lines.append("- (no results)")
        else:
            for res in r["sample_results"]:
                lines.append(f"- {res['url']}")
                if res["snippet"]:
                    lines.append(f"  Snippet: {res['snippet']}")
        lines.append("")
    return lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Burst smoke test for searxng-cli search_batch.")
    parser.add_argument("--queries-per-burst", type=int, default=4,
                        help="Number of queries per search_batch call (default: 4)")
    parser.add_argument("--cooldown", type=float, default=60.0,
                        help="Seconds to wait between batches (default: 60)")
    parser.add_argument("--max-queries", type=int, default=None,
                        help="Cap total queries processed (default: all)")
    args = parser.parse_args()
    asyncio.run(run_burst_smoke(args.queries_per_burst, args.cooldown, args.max_queries))
