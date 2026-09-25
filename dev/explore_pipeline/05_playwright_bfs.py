# INFRASTRUCTURE
import argparse
import asyncio
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

SEED_URL = "https://docs.github.com/de/rest"
DEFAULT_INCLUDE_PATTERN = "/de/rest/"
DEFAULT_MAX_PAGES = 400
DEFAULT_MAX_DEPTH = 10
DEFAULT_DELAY_S = 3.0
DEFAULT_PAGE_TIMEOUT_MS = 15000
DEFAULT_CONCURRENCY = 1

AGENT_TASKS_URL = "https://docs.github.com/de/rest/agent-tasks/agent-tasks"
GOLD_DEFAULT = Path(__file__).parent / "goldstandard" / "docs_github_rest.txt"
OUTPUT_DIR = Path(__file__).parent / "md"
MISSING_SAMPLE = 20


# ORCHESTRATOR

async def playwright_bfs_workflow(seed: str, gold_path: Path, include_pattern: str,
                                   max_pages: int, max_depth: int, delay_s: float,
                                   page_timeout_ms: int, concurrency: int, stealth: bool):
    gold = load_gold(gold_path)
    print(f"Gold standard: {len(gold)} URLs from {gold_path.name}")
    print(f"Seed: {seed}  |  Pattern: {include_pattern}  |  Max pages: {max_pages}")
    print(f"Config: wait=domcontentloaded, delay={delay_s}s, timeout={page_timeout_ms}ms, "
          f"concurrency={concurrency}, stealth={stealth}")

    browser_cfg, run_cfg, crawler_strategy = make_configs(delay_s, page_timeout_ms, stealth)

    t0 = time.time()
    found_urls, bfs_stats = await bfs_crawl(
        seed, include_pattern, max_pages, max_depth, concurrency,
        browser_cfg, run_cfg, crawler_strategy,
    )
    elapsed = time.time() - t0

    recall = compute_recall(found_urls, gold)
    report = format_report(seed, gold, recall, bfs_stats, elapsed, concurrency, stealth,
                           delay_s, page_timeout_ms)
    out_path = save_report(report)
    print(f"\n{report}")
    print(f"\nReport saved: {out_path}")


# FUNCTIONS

def load_gold(path: Path) -> frozenset:
    with open(path, encoding="utf-8") as f:
        return frozenset(normalize_url(ln.strip()) for ln in f if ln.strip())


def make_configs(delay_s: float, page_timeout_ms: int, stealth: bool) -> tuple:
    if stealth:
        browser_cfg = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
        crawler_strategy = AsyncPlaywrightCrawlerStrategy(
            browser_config=browser_cfg,
            browser_adapter=UndetectedAdapter(),
        )
    else:
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        crawler_strategy = None
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=delay_s,
        page_timeout=page_timeout_ms,
        verbose=False,
    )
    return browser_cfg, run_cfg, crawler_strategy


async def bfs_crawl(seed: str, include_pattern: str, max_pages: int, max_depth: int,
                    concurrency: int, browser_cfg: BrowserConfig, run_cfg: CrawlerRunConfig,
                    crawler_strategy) -> tuple[list[str], dict]:
    seed_norm = normalize_url(seed)
    seed_netloc = urlparse(seed_norm).netloc

    frontier: deque = deque()
    visited: set[str] = {seed_norm}
    found: list[str] = []
    page_latencies: list[int] = []
    failed: list[tuple[str, str]] = []
    four_two_nine_count = 0
    consecutive_batches_429 = 0
    stop_reason: str | None = None

    frontier.append((seed_norm, 0))

    kw: dict = {"config": browser_cfg}
    if crawler_strategy:
        kw["crawler_strategy"] = crawler_strategy

    async with AsyncWebCrawler(**kw) as crawler:
        while frontier and len(found) < max_pages and stop_reason is None:
            batch = _build_batch(frontier, concurrency, max_depth)
            if not batch:
                continue

            results = await _fetch_batch(crawler, batch, run_cfg)

            four_two_nine_count, consecutive_batches_429, stop_reason = await _handle_429_batch(
                batch, results, four_two_nine_count, consecutive_batches_429,
            )

            _process_batch_results(
                batch, results, found, page_latencies, failed, visited, frontier,
                max_depth, seed_netloc, include_pattern,
            )

    stats = _build_bfs_stats(page_latencies, four_two_nine_count, stop_reason, failed)
    return found, stats


def compute_recall(found_urls: list[str], gold: frozenset) -> dict:
    found_set = set(found_urls)
    matched = found_set & gold
    missing = gold - found_set
    noise = found_set - gold
    recall_pct = len(matched) / len(gold) * 100 if gold else 0.0
    return {
        "found": len(found_set),
        "matched": len(matched),
        "missing": len(missing),
        "noise": len(noise),
        "recall_pct": recall_pct,
        "missing_sample": sorted(missing)[:MISSING_SAMPLE],
        "found_set": found_set,
    }


def format_report(seed: str, gold: frozenset, recall: dict, bfs_stats: dict,
                  elapsed: float, concurrency: int, stealth: bool,
                  delay_s: float, page_timeout_ms: int) -> str:
    lines = _format_header_and_recall_table(
        seed, gold, recall, bfs_stats, elapsed, concurrency, stealth, delay_s, page_timeout_ms)
    lines += _format_key_url_and_baseline(recall, concurrency, delay_s)
    lines += _format_missing_sample(recall)
    lines += _format_fetch_failures(bfs_stats)
    lines += _format_early_stop(bfs_stats)
    return "\n".join(lines)


def save_report(report: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"05_docs_github_rest_{datetime.now().strftime('%Y%m%d')}.md"
    path.write_text(report, encoding="utf-8")
    return path


def _build_batch(frontier: deque, concurrency: int, max_depth: int) -> list[tuple[str, int]]:
    batch: list[tuple[str, int]] = []
    while frontier and len(batch) < concurrency:
        url, depth = frontier.popleft()
        if depth <= max_depth:
            batch.append((url, depth))
    return batch


async def _fetch_batch(crawler: AsyncWebCrawler, batch: list[tuple[str, int]],
                       run_cfg: CrawlerRunConfig) -> list:
    tasks = [fetch_page(crawler, url, run_cfg) for url, _ in batch]
    return await asyncio.gather(*tasks)


async def _handle_429_batch(batch: list[tuple[str, int]], results: list,
                            four_two_nine_count: int, consecutive_batches_429: int) -> tuple:
    stop_reason: str | None = None
    batch_429 = sum(1 for status, _, _, _ in results if status == 429)
    if batch_429 > 0:
        four_two_nine_count += batch_429
        consecutive_batches_429 += 1
        urls_429 = [url for (url, _), (s, _, _, _) in zip(batch, results) if s == 429]
        print(f"  429 on: {urls_429}")
        if consecutive_batches_429 == 1:
            print("  Backing off 5s (first 429 batch)...")
            await asyncio.sleep(5)
        else:
            print("  429 persists — stopping BFS.")
            stop_reason = "429_persistent"
    else:
        consecutive_batches_429 = 0
    return four_two_nine_count, consecutive_batches_429, stop_reason


def _process_batch_results(batch: list[tuple[str, int]], results: list, found: list[str],
                           page_latencies: list[int], failed: list[tuple[str, str]],
                           visited: set[str], frontier: deque,
                           max_depth: int, seed_netloc: str, include_pattern: str) -> None:
    for (url, depth), (status, links, latency_ms, error) in zip(batch, results):
        page_latencies.append(latency_ms)
        if error is not None:
            failed.append((url, error))
            print(f"  WARN: fetch failed for {url}: {error}")
            continue
        if status == 429:
            continue
        if status is not None and status >= 400:
            print(f"  WARN: HTTP {status} on {url}")
            continue
        found.append(url)
        print(f"  [{len(found):3d}] {url}  ({latency_ms}ms)")
        if depth >= max_depth:
            continue
        for lk in links:
            href = lk.get("href", "") if isinstance(lk, dict) else str(lk)
            if not href.startswith("http"):
                continue
            norm = normalize_url(href)
            if urlparse(norm).netloc != seed_netloc:
                continue
            if include_pattern and include_pattern not in norm:
                continue
            if norm not in visited:
                visited.add(norm)
                frontier.append((norm, depth + 1))


def _build_bfs_stats(page_latencies: list[int], four_two_nine_count: int, stop_reason: str | None,
                     failed: list[tuple[str, str]]) -> dict:
    return {
        "pages_fetched": len(page_latencies),
        "four_two_nine_count": four_two_nine_count,
        "stop_reason": stop_reason,
        "fetch_failures": len(failed),
        "failed_fetches": failed,
        "avg_latency_ms": int(sum(page_latencies) / len(page_latencies)) if page_latencies else 0,
        "min_latency_ms": min(page_latencies) if page_latencies else 0,
        "max_latency_ms": max(page_latencies) if page_latencies else 0,
    }


def _format_header_and_recall_table(seed: str, gold: frozenset, recall: dict, bfs_stats: dict,
                                    elapsed: float, concurrency: int, stealth: bool,
                                    delay_s: float, page_timeout_ms: int) -> list:
    return [
        "# Playwright-per-page BFS — docs.github.com/de/rest",
        "",
        f"Seed: {seed}  |  Gold: {len(gold)} URLs",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Config: wait=domcontentloaded, delay={delay_s}s, timeout={page_timeout_ms}ms, "
        f"concurrency={concurrency}, stealth={stealth}",
        "",
        "## Recall Results",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Found (unique) | {recall['found']} |",
        f"| Matched gold | {recall['matched']} / {len(gold)} |",
        f"| Recall % | {recall['recall_pct']:.1f}% |",
        f"| Missing | {recall['missing']} |",
        f"| Noise (extra) | {recall['noise']} |",
        f"| Total time | {elapsed:.1f}s |",
        f"| Pages fetched | {bfs_stats['pages_fetched']} |",
        f"| Avg latency | {bfs_stats['avg_latency_ms']}ms |",
        f"| Min / Max latency | {bfs_stats['min_latency_ms']}ms / {bfs_stats['max_latency_ms']}ms |",
        f"| 429 incidents | {bfs_stats['four_two_nine_count']} |",
        f"| Fetch failures | {bfs_stats['fetch_failures']} |",
        f"| Stop reason | {bfs_stats['stop_reason'] or 'completed'} |",
    ]


def _format_key_url_and_baseline(recall: dict, concurrency: int, delay_s: float) -> list:
    agent_hit = AGENT_TASKS_URL in recall["found_set"]
    return [
        "",
        "## Key URL Check",
        "",
        f"- `agent-tasks/agent-tasks`: **{'FOUND ✓' if agent_hit else 'MISSING ✗'}**",
        "",
        "## Baseline Comparison",
        "",
        "| Strategy | Recall % | Notes |",
        "|----------|----------|-------|",
        "| HTTP BFS — Strategy C (Phase A) | 67.2% | crawl4ai BFSDeepCrawlStrategy, HTTP-based |",
        f"| Playwright-per-page BFS (this run) | {recall['recall_pct']:.1f}% | "
        f"domcontentloaded + {delay_s}s delay, concurrency={concurrency} |",
    ]


def _format_missing_sample(recall: dict) -> list:
    lines = []
    if recall["missing_sample"]:
        lines += [
            "",
            f"## Still Missing (sample of {recall['missing']} total)",
            "",
        ]
        for u in recall["missing_sample"]:
            lines.append(f"- {u}")
    return lines


def _format_fetch_failures(bfs_stats: dict) -> list:
    lines = []
    if bfs_stats["failed_fetches"]:
        lines += [
            "",
            f"## Failed Fetches ({bfs_stats['fetch_failures']} total, not counted as found)",
            "",
        ]
        for url, error in bfs_stats["failed_fetches"]:
            lines.append(f"- {url}: {error}")
    return lines


def _format_early_stop(bfs_stats: dict) -> list:
    lines = []
    if bfs_stats["stop_reason"]:
        lines += [
            "",
            f"## Early Stop: {bfs_stats['stop_reason']}",
            "",
            f"BFS halted: {bfs_stats['four_two_nine_count']} 429 incidents total.",
        ]
    return lines


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r'/[^/]*@[^/]+', '', parsed.path)
    path = path.rstrip('/')
    return f"{parsed.scheme}://{parsed.netloc}{path}"


async def fetch_page(crawler: AsyncWebCrawler, url: str,
                     run_cfg: CrawlerRunConfig) -> tuple:
    t0 = time.time()
    try:
        result = await crawler.arun(url=url, config=run_cfg)
        latency_ms = int((time.time() - t0) * 1000)
        status = result.status_code if hasattr(result, "status_code") else 200
        links = result.links.get("internal", []) if isinstance(result.links, dict) else []
        return status, links, latency_ms, None
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        return None, [], latency_ms, f"{type(exc).__name__}: {exc}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Playwright-per-page BFS — measures URL discovery recall vs gold standard"
    )
    parser.add_argument("--gold", type=Path, default=GOLD_DEFAULT,
                        help="Gold standard file (default: goldstandard/docs_github_rest.txt)")
    parser.add_argument("--seed", type=str, default=SEED_URL,
                        help=f"Seed URL (default: {SEED_URL})")
    parser.add_argument("--include-pattern", type=str, default=DEFAULT_INCLUDE_PATTERN,
                        help=f"URL substring filter (default: {DEFAULT_INCLUDE_PATTERN})")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help=f"Max pages to fetch (default: {DEFAULT_MAX_PAGES})")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                        help=f"Max BFS depth (default: {DEFAULT_MAX_DEPTH})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S,
                        help=f"delay_before_return_html in seconds (default: {DEFAULT_DELAY_S})")
    parser.add_argument("--page-timeout", type=int, default=DEFAULT_PAGE_TIMEOUT_MS,
                        help=f"page_timeout in ms (default: {DEFAULT_PAGE_TIMEOUT_MS})")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        choices=[1, 2, 3],
                        help=f"Concurrent arun() calls (default: {DEFAULT_CONCURRENCY}, max: 3)")
    parser.add_argument("--stealth", action="store_true",
                        help="Enable stealth mode (BrowserConfig enable_stealth + UndetectedAdapter)")
    args = parser.parse_args()

    asyncio.run(playwright_bfs_workflow(
        args.seed, args.gold, args.include_pattern, args.max_pages, args.max_depth,
        args.delay, args.page_timeout, args.concurrency, args.stealth,
    ))
