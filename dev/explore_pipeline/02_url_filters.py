# INFRASTRUCTURE
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter, URLPatternFilter, ContentTypeFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUTPUT_DIR = Path(__file__).parent / "md"


# FUNCTIONS

async def main(url: str, depth: int, max_pages: int, exclude_patterns: str, label: str):
    domain = urlparse(url).netloc

    baseline_results = await crawl(url, domain, depth, max_pages, exclude_patterns=None)
    filtered_results = await crawl(url, domain, depth, max_pages, exclude_patterns=exclude_patterns)

    baseline_urls = extract_urls(baseline_results)
    filtered_urls = extract_urls(filtered_results)
    removed_urls = baseline_urls - filtered_urls

    report = build_report(url, domain, depth, max_pages, exclude_patterns,
                          baseline_urls, filtered_urls, removed_urls)
    save_report(report, label)


async def crawl(url: str, domain: str, depth: int, max_pages: int,
                exclude_patterns: str = None) -> list:
    filters = [
        DomainFilter(allowed_domains=[domain]),
        ContentTypeFilter(allowed_types=["text/html"]),
    ]
    if exclude_patterns:
        filters.append(URLPatternFilter(patterns=exclude_patterns.split(","), reverse=True))
    filter_chain = FilterChain(filters)

    strategy = BFSDeepCrawlStrategy(
        max_depth=depth,
        include_external=False,
        filter_chain=filter_chain,
        max_pages=max_pages
    )

    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        deep_crawl_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(),
    )

    mode = f"filtered ({exclude_patterns})" if exclude_patterns else "baseline"
    print(f"Crawling {url} [{mode}]")

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(url=url, config=run_config)

    if not isinstance(results, list):
        results = [results]

    print(f"  -> {len(results)} pages")
    return results


def extract_urls(results: list) -> set:
    urls = set()
    for r in results:
        if hasattr(r, 'url') and r.url:
            urls.add(r.url.rstrip('/'))
    return urls


def build_report(url, domain, depth, max_pages, exclude_patterns,
                 baseline_urls, filtered_urls, removed_urls):
    return {
        "timestamp": datetime.now().isoformat(),
        "seed_url": url,
        "domain": domain,
        "config": {
            "depth": depth,
            "max_pages": max_pages,
            "exclude_patterns": exclude_patterns,
        },
        "summary": {
            "baseline_count": len(baseline_urls),
            "filtered_count": len(filtered_urls),
            "removed_count": len(removed_urls),
        },
        "baseline_urls": sorted(baseline_urls),
        "filtered_urls": sorted(filtered_urls),
        "removed_urls": sorted(removed_urls),
    }


def save_report(report, label):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"02_{label}_{timestamp}.md"

    s = report["summary"]
    lines = [
        f"# Filter Test: {report['seed_url']}",
        "",
        f"**Timestamp:** {report['timestamp']}",
        f"**Depth:** {report['config']['depth']} | **Max Pages:** {report['config']['max_pages']}",
        f"**Exclude Patterns:** `{report['config']['exclude_patterns']}`",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Baseline | {s['baseline_count']} |",
        f"| Filtered | {s['filtered_count']} |",
        f"| Removed | {s['removed_count']} |",
        "",
        "## Removed URLs",
        "",
    ]

    if report["removed_urls"]:
        for url in report["removed_urls"]:
            lines.append(f"- {url}")
    else:
        lines.append("_No URLs removed by filter._")

    lines += [
        "",
        "## Baseline URLs",
        "",
    ]
    for url in report["baseline_urls"]:
        marker = " **[REMOVED]**" if url in report["removed_urls"] else ""
        lines.append(f"- {url}{marker}")

    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"\nReport saved: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare crawl results with and without URL filters")
    parser.add_argument("url", help="Seed URL to crawl")
    parser.add_argument("--exclude-patterns", required=True,
                        help="Comma-separated URL patterns to exclude (e.g. '/genindex*,/search*')")
    parser.add_argument("--label", help="Report filename prefix (default: derived from domain)")
    parser.add_argument("--depth", type=int, default=2, help="Max crawl depth (default: 2)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to crawl (default: 50)")
    args = parser.parse_args()

    label = args.label or urlparse(args.url).netloc.replace('.', '_')
    asyncio.run(main(args.url, args.depth, args.max_pages, args.exclude_patterns, label))
