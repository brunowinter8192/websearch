import argparse
import asyncio
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, ContentTypeFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUTPUT_DIR = Path(__file__).parent / "md"

STRATEGIES = {
    "baseline_domcontentloaded": {
        "wait_until": "domcontentloaded",
        "prefetch": False,
        "markdown_generator": True,
    },
    "prefetch_domcontentloaded": {
        "wait_until": "domcontentloaded",
        "prefetch": True,
        "markdown_generator": False,
    },
    "prefetch_no_wait": {
        "wait_until": None,
        "prefetch": True,
        "markdown_generator": False,
    },
}


async def main(url: str, depth: int, max_pages: int):
    domain = urlparse(url).netloc
    results = {}

    for name, config in STRATEGIES.items():
        print(f"\n{'=' * 60}")
        print(f"Strategy: {name}")
        print(f"{'=' * 60}")

        start = time.time()
        crawl_results = await run_strategy(url, domain, depth, max_pages, config)
        elapsed = time.time() - start

        stats = build_stats(crawl_results, config["prefetch"])
        stats["elapsed_seconds"] = round(elapsed, 1)
        stats["per_page_ms"] = round((elapsed / max(stats["unique_pages"], 1)) * 1000)
        results[name] = stats

        print(f"  Pages: {stats['unique_pages']} | Time: {stats['elapsed_seconds']}s | Per page: {stats['per_page_ms']}ms")

    report = format_report(url, depth, max_pages, results)
    save_report(report, domain)
    print(f"\n{report}")


async def run_strategy(url: str, domain: str, depth: int, max_pages: int, strategy_config: dict) -> list:
    filter_chain = FilterChain([
        DomainFilter(allowed_domains=[domain]),
        ContentTypeFilter(allowed_types=["text/html"]),
    ])

    strategy = BFSDeepCrawlStrategy(
        max_depth=depth,
        include_external=False,
        filter_chain=filter_chain,
        max_pages=max_pages,
    )

    browser_config = BrowserConfig(headless=True, verbose=False)

    run_kwargs = {
        "deep_crawl_strategy": strategy,
        "cache_mode": CacheMode.BYPASS,
    }

    if strategy_config["wait_until"]:
        run_kwargs["wait_until"] = strategy_config["wait_until"]

    if strategy_config["prefetch"]:
        run_kwargs["prefetch"] = True

    if strategy_config["markdown_generator"]:
        run_kwargs["markdown_generator"] = DefaultMarkdownGenerator()

    run_config = CrawlerRunConfig(**run_kwargs)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(url=url, config=run_config)

    if not isinstance(results, list):
        results = [results]

    return results


def build_stats(results: list, is_prefetch: bool) -> dict:
    seen = set()
    depth_counts = defaultdict(int)

    for r in results:
        url = r.url.rstrip('/') if hasattr(r, 'url') and r.url else None
        if not url or url in seen:
            continue
        seen.add(url)
        depth = r.metadata.get("depth", -1) if r.metadata else -1
        depth_counts[depth] += 1

    return {
        "total_fetched": len(results),
        "unique_pages": len(seen),
        "duplicates": len(results) - len(seen),
        "depth_distribution": dict(sorted(depth_counts.items())),
    }


def format_report(url: str, depth: int, max_pages: int, results: dict) -> str:
    lines = [
        f"# Explore Strategy Comparison",
        f"",
        f"URL: {url}",
        f"Depth: {depth} | Max Pages: {max_pages}",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## Results",
        f"",
        f"| Strategy | Pages | Time (s) | Per Page (ms) | Duplicates |",
        f"|----------|-------|----------|---------------|------------|",
    ]

    for name, stats in results.items():
        lines.append(
            f"| {name} | {stats['unique_pages']} | {stats['elapsed_seconds']} | {stats['per_page_ms']} | {stats['duplicates']} |"
        )

    baseline = results.get("baseline_domcontentloaded")
    if baseline:
        lines.extend(["", "## Speedup vs Baseline", ""])
        for name, stats in results.items():
            if name == "baseline_domcontentloaded":
                continue
            if baseline["elapsed_seconds"] > 0:
                speedup = round(baseline["elapsed_seconds"] / max(stats["elapsed_seconds"], 0.1), 1)
                lines.append(f"- **{name}**: {speedup}x faster")

    lines.extend(["", "## Depth Distribution", ""])
    for name, stats in results.items():
        lines.append(f"### {name}")
        for depth_val, count in stats["depth_distribution"].items():
            lines.append(f"- Depth {depth_val}: {count} pages")
        lines.append("")

    return "\n".join(lines)


def save_report(report: str, domain: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"03_explore_strategies_{domain}_{timestamp}.md"
    with open(path, 'w') as f:
        f.write(report)
    print(f"Report saved: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare explore_site crawl strategies")
    parser.add_argument("url", nargs="?", default="https://docs.crawl4ai.com", help="Test URL (default: docs.crawl4ai.com)")
    parser.add_argument("--depth", type=int, default=2, help="Max crawl depth (default: 2)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages (default: 50)")
    args = parser.parse_args()

    asyncio.run(main(args.url, args.depth, args.max_pages))
