# INFRASTRUCTURE
import argparse
import asyncio
import logging
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig,
                      CacheMode, UndetectedAdapter)
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.async_dispatcher import SemaphoreDispatcher

from src.crawler.garbage_filter import is_garbage_content

logger = logging.getLogger(__name__)

PERMALINK_PATTERN = re.compile(r'\[¶\]\([^)]+\)')
TRAILING_SLASH = re.compile(r'/$')
DEFAULT_CONCURRENCY = 10
DEFAULT_DELAY_S = 3.0
DEFAULT_PAGE_TIMEOUT_MS = 15000
DEFAULT_DISCOVER_CONCURRENCY = 1


# ORCHESTRATOR
async def crawl_site_workflow(url: str, output_dir: str, depth: int, max_pages: int,
                              exclude_patterns: str = None, include_patterns: str = None,
                              url_file: str = None, delay_s: float = DEFAULT_DELAY_S,
                              page_timeout_ms: int = DEFAULT_PAGE_TIMEOUT_MS,
                              concurrency: int = DEFAULT_DISCOVER_CONCURRENCY,
                              stealth: bool = False):
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    if url_file:
        logger.info("Reading URLs from %s", url_file)
        urls = read_url_file(url_file)
        logger.info("Loaded %d URLs", len(urls))
    else:
        logger.info("Discovering URLs: Playwright-per-page BFS (max_pages=%d, depth=%d, concurrency=%d)",
                    max_pages, depth, concurrency)
        urls, stats = await discover_urls_playwright(
            url, include_patterns, exclude_patterns, max_pages, depth,
            delay_s, page_timeout_ms, concurrency, stealth,
        )
        logger.info("Discovery: %d URLs, stop_reason=%s, 429s=%d, avg_latency=%dms",
                    len(urls), stats["stop_reason"], stats["four_two_nine_count"],
                    stats["avg_latency_ms"])

    results = await crawl_urls(urls)
    logger.info("Crawled %d pages", len(results))
    unique = deduplicate(results)
    saved = save_markdown(unique, url, target)
    logger.info("Done: %d files saved to %s", saved, target)


# FUNCTIONS

# Strip query/fragment, @version path segments, trailing slash
def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r'/[^/]*@[^/]+', '', parsed.path)
    path = path.rstrip('/')
    return f"{parsed.scheme}://{parsed.netloc}{path}"


# Fetch one page; return (status_code | None, internal_links, latency_ms)
async def _fetch_page(crawler: AsyncWebCrawler, url: str,
                      run_cfg: CrawlerRunConfig) -> tuple:
    t0 = time.time()
    try:
        result = await crawler.arun(url=url, config=run_cfg)
        latency_ms = int((time.time() - t0) * 1000)
        status = result.status_code if hasattr(result, "status_code") else 200
        links = result.links.get("internal", []) if isinstance(result.links, dict) else []
        return status, links, latency_ms
    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        logger.warning("Fetch failed for %s: %s", url, exc)
        return None, [], latency_ms


# Build CrawlerRunConfig and AsyncWebCrawler keyword args for discovery (stealth or normal)
def _build_crawler_config(delay_s: float, page_timeout_ms: int, stealth: bool) -> tuple:
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=delay_s,
        page_timeout=page_timeout_ms,
        verbose=False,
    )
    if stealth:
        browser_cfg = BrowserConfig(headless=True, verbose=False, enable_stealth=True)
        crawler_strategy = AsyncPlaywrightCrawlerStrategy(
            browser_config=browser_cfg,
            browser_adapter=UndetectedAdapter(),
        )
    else:
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        crawler_strategy = None
    kw: dict = {"config": browser_cfg}
    if crawler_strategy:
        kw["crawler_strategy"] = crawler_strategy
    return run_cfg, kw


# Account for 429s in a batch; back off once on first, stop on second consecutive; return updated counters
async def _handle_429_batch(results: list, batch: list,
                            four_two_nine_count: int, consecutive_batches_429: int) -> tuple:
    batch_429 = sum(1 for status, _, _ in results if status == 429)
    if batch_429 > 0:
        four_two_nine_count += batch_429
        consecutive_batches_429 += 1
        urls_429 = [u for (u, _), (s, _, _) in zip(batch, results) if s == 429]
        logger.warning("429 on: %s", urls_429)
        if consecutive_batches_429 == 1:
            logger.warning("Backing off 5s (first 429 batch)...")
            await asyncio.sleep(5)
        else:
            logger.warning("429 persists — stopping BFS.")
            return four_two_nine_count, consecutive_batches_429, "429_persistent"
    else:
        consecutive_batches_429 = 0
    return four_two_nine_count, consecutive_batches_429, None


# Filter page links against domain, include/exclude patterns, and visited; return new (url, depth) pairs
def _extract_frontier_links(links: list, seed_netloc: str, include_pats: list,
                            exclude_pats: list, visited: set, depth: int) -> list:
    new_links = []
    seen_in_batch: set = set()
    for lk in links:
        href = lk.get("href", "") if isinstance(lk, dict) else str(lk)
        if not href.startswith("http"):
            continue
        norm = normalize_url(href)
        if urlparse(norm).netloc != seed_netloc:
            continue
        if include_pats and not any(p in norm for p in include_pats):
            continue
        if exclude_pats and any(p in norm for p in exclude_pats):
            continue
        if norm not in visited and norm not in seen_in_batch:
            seen_in_batch.add(norm)
            new_links.append((norm, depth + 1))
    return new_links


# Classify one batch's fetch results, collect found URLs/latencies, and expand the frontier in place
def _process_batch_results(batch: list, results: list, found: list, page_latencies: list,
                           visited: set, frontier: deque, seed_netloc: str,
                           include_pats: list, exclude_pats: list, max_depth: int) -> None:
    for (url, depth), (status, links, latency_ms) in zip(batch, results):
        page_latencies.append(latency_ms)
        if status == 429:
            continue
        if status is not None and status >= 400:
            logger.debug("HTTP %d on %s", status, url)
            continue
        found.append(url)
        logger.debug("[%3d] %s (%dms)", len(found), url, latency_ms)
        if depth >= max_depth:
            continue
        for norm, next_depth in _extract_frontier_links(
            links, seed_netloc, include_pats, exclude_pats, visited, depth
        ):
            visited.add(norm)
            frontier.append((norm, next_depth))


# Playwright-per-page BFS: render each page, extract links.internal from post-JS DOM
async def discover_urls_playwright(seed: str, include_patterns: str | None,
                                   exclude_patterns: str | None, max_pages: int,
                                   max_depth: int, delay_s: float, page_timeout_ms: int,
                                   concurrency: int, stealth: bool) -> tuple[list[str], dict]:
    seed_norm = normalize_url(seed)
    seed_netloc = urlparse(seed_norm).netloc

    include_pats = [p.strip() for p in include_patterns.split(",") if p.strip()] if include_patterns else []
    exclude_pats = [p.strip() for p in exclude_patterns.split(",") if p.strip()] if exclude_patterns else []

    frontier: deque = deque()
    visited: set[str] = {seed_norm}
    found: list[str] = []
    page_latencies: list[int] = []
    four_two_nine_count = 0
    consecutive_batches_429 = 0
    stop_reason: str | None = None

    frontier.append((seed_norm, 0))

    run_cfg, crawler_kw = _build_crawler_config(delay_s, page_timeout_ms, stealth)

    async with AsyncWebCrawler(**crawler_kw) as crawler:
        while frontier and len(found) < max_pages and stop_reason is None:
            batch = _pop_batch(frontier, concurrency, max_depth)
            if not batch:
                continue

            tasks = [_fetch_page(crawler, url, run_cfg) for url, _ in batch]
            results = await asyncio.gather(*tasks)

            four_two_nine_count, consecutive_batches_429, batch_stop = await _handle_429_batch(
                results, batch, four_two_nine_count, consecutive_batches_429
            )
            if batch_stop:
                stop_reason = batch_stop

            _process_batch_results(batch, results, found, page_latencies, visited, frontier,
                                    seed_netloc, include_pats, exclude_pats, max_depth)

    stats = _build_discovery_stats(frontier, page_latencies, four_two_nine_count, stop_reason)
    return found, stats


# Pop up to `concurrency` frontier entries within max_depth into a batch.
def _pop_batch(frontier: deque, concurrency: int, max_depth: int) -> list[tuple[str, int]]:
    batch: list[tuple[str, int]] = []
    while frontier and len(batch) < concurrency:
        url, depth = frontier.popleft()
        if depth <= max_depth:
            batch.append((url, depth))
    return batch


# Resolve stop_reason if the loop ended without one, and build the final stats dict.
def _build_discovery_stats(
    frontier: deque, page_latencies: list[int], four_two_nine_count: int, stop_reason: str | None,
) -> dict:
    if stop_reason is None:
        stop_reason = "frontier_exhausted" if not frontier else "max_pages_reached"
    return {
        "pages_fetched": len(page_latencies),
        "four_two_nine_count": four_two_nine_count,
        "stop_reason": stop_reason,
        "avg_latency_ms": int(sum(page_latencies) / len(page_latencies)) if page_latencies else 0,
    }


# Read URL list from text file (one URL per line)
def read_url_file(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# Phase 2: Parallel crawl of discovered URLs
async def crawl_urls(urls: list[str]) -> list:
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    dispatcher = SemaphoreDispatcher(max_session_permit=DEFAULT_CONCURRENCY)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls=urls, config=run_config, dispatcher=dispatcher)

    return results if isinstance(results, list) else list(results)


# Remove duplicate URLs (trailing slash normalization)
def deduplicate(results: list) -> list:
    seen = set()
    unique = []
    for r in results:
        normalized = TRAILING_SLASH.sub('', r.url) if hasattr(r, 'url') else None
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(r)
    logger.debug("Unique after dedup: %d", len(unique))
    return unique


# Save crawled pages as markdown files
def save_markdown(results: list, seed_url: str, output_dir: Path) -> int:
    saved = 0
    for r in results:
        url = TRAILING_SLASH.sub('', r.url) if hasattr(r, 'url') else None
        raw_md = r.markdown.raw_markdown if r.markdown else ""
        if not url or not raw_md:
            continue
        if r.status_code and r.status_code >= 400:
            logger.debug("skip %s (HTTP %d)", url, r.status_code)
            continue
        if is_garbage_content(raw_md):
            logger.debug("skip %s (garbage content)", url)
            continue

        clean_md = PERMALINK_PATTERN.sub('', raw_md)
        clean_md = re.sub(r'\n{3,}', '\n\n', clean_md).strip()

        filename = url_to_filename(url, seed_url)
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"<!-- source: {url} -->\n\n{clean_md}")

        saved += 1
        logger.debug("[%d] %s (%d chars)", saved, filename, len(clean_md))

    return saved


# Domain to filename prefix mapping
DOMAIN_PREFIX = {
    "docs.searxng.org": "searxng",
    "docs.crawl4ai.com": "crawl4ai",
    "playwright.dev": "playwright",
    "support.torproject.org": "tor",
    "www.cookieyes.com": "cookieyes",
    "developer.onetrust.com": "onetrust",
    "www.sitemaps.org": "sitemaps",
    "trafilatura.readthedocs.io": "trafilatura",
    "platform.claude.com": "anthropic",
    "www.cookiebot.com": "cookiebot",
}


# Convert URL to safe filename with domain prefix
def url_to_filename(url: str, seed_url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc
    prefix = DOMAIN_PREFIX.get(domain, domain.replace(".", "_"))

    path = parsed.path.strip("/")
    if not path:
        path = "index"

    path = path.replace(".html", "").replace(".htm", "")
    path = path.replace("/", "__")

    return f"{prefix}__{path}.md"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl a website and save as Markdown")
    parser.add_argument("--url", required=True, help="Seed URL to crawl")
    parser.add_argument("--output-dir", required=True, help="Directory to save markdown files")
    parser.add_argument("--depth", type=int, default=3, help="Max crawl depth (default: 3)")
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages to crawl (default: 100)")
    parser.add_argument("--exclude-patterns", type=str, default=None,
                        help="Comma-separated URL substrings to exclude (e.g. '/genindex,/search')")
    parser.add_argument("--include-patterns", type=str, default=None,
                        help="Comma-separated URL substrings to include (e.g. '/docs/,/api/')")
    parser.add_argument("--url-file", type=str, default=None,
                        help="Path to text file with URLs (one per line) — skips discovery entirely")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_S,
                        help=f"Render delay in seconds after domcontentloaded (default: {DEFAULT_DELAY_S})")
    parser.add_argument("--page-timeout", type=int, default=DEFAULT_PAGE_TIMEOUT_MS,
                        help=f"Page load timeout in ms (default: {DEFAULT_PAGE_TIMEOUT_MS})")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_DISCOVER_CONCURRENCY,
                        help=f"Concurrent discovery requests (default: {DEFAULT_DISCOVER_CONCURRENCY}; "
                             f">1 risks Cloudflare WAF 429, max recommended: 10)")
    parser.add_argument("--stealth", action="store_true",
                        help="Enable stealth mode (enable_stealth + UndetectedAdapter) to reduce 429s")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(crawl_site_workflow(
        args.url, args.output_dir, args.depth, args.max_pages,
        args.exclude_patterns, args.include_patterns, args.url_file,
        args.delay, args.page_timeout, args.concurrency, args.stealth,
    ))
