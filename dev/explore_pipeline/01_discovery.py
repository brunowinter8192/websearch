import argparse
import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, DomainFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUTPUT_DIR = Path(__file__).parent / "md"
DOMAINS_FILE = Path(__file__).parent / "domains.txt"
TRAILING_SLASH = re.compile(r'/$')


async def main(url: str, depth: int, max_pages: int, label: str):
    domain = urlparse(url).netloc
    results = await crawl_website(url, domain, depth, max_pages)
    unique = deduplicate(results)
    report = build_report(url, domain, depth, max_pages, len(results), unique)
    save_report(report, label)
    print_report(report)


async def crawl_website(url: str, domain: str, depth: int, max_pages: int) -> list:
    filter_chain = FilterChain([
        DomainFilter(allowed_domains=[domain])
    ])

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
        markdown_generator=DefaultMarkdownGenerator(),
    )

    print(f"Crawling {url} (depth={depth}, max_pages={max_pages}, domain={domain})")

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun(url=url, config=run_config)

    if not isinstance(results, list):
        results = [results]

    print(f"Fetched {len(results)} pages")
    return results


def deduplicate(results: list) -> list:
    seen = set()
    unique = []
    for r in results:
        normalized = TRAILING_SLASH.sub('', r.url) if hasattr(r, 'url') else None
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(r)
    return unique


def build_report(seed_url, domain, depth, max_pages, total_fetched, unique_results):
    urls = []
    for r in unique_results:
        url = TRAILING_SLASH.sub('', r.url) if hasattr(r, 'url') else "unknown"
        has_content = bool(r.markdown and r.markdown.raw_markdown)
        char_count = len(r.markdown.raw_markdown) if has_content else 0
        urls.append({"url": url, "has_content": has_content, "chars": char_count})

    with_content = [u for u in urls if u["has_content"]]
    empty = [u for u in urls if not u["has_content"]]

    return {
        "timestamp": datetime.now().isoformat(),
        "seed_url": seed_url,
        "domain": domain,
        "config": {"depth": depth, "max_pages": max_pages},
        "summary": {
            "total_fetched": total_fetched,
            "unique_urls": len(urls),
            "duplicates_removed": total_fetched - len(urls),
            "with_content": len(with_content),
            "empty": len(empty),
            "total_chars": sum(u["chars"] for u in urls),
        },
        "urls": sorted(urls, key=lambda u: u["url"]),
    }


def save_report(report, label):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"01_{label}_{timestamp}.json"
    with open(path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {path}")


def print_report(report):
    s = report["summary"]
    print(f"\n{'=' * 60}")
    print(f"CRAWL REPORT: {report['seed_url']}")
    print(f"{'=' * 60}")
    print(f"  Fetched:    {s['total_fetched']}")
    print(f"  Unique:     {s['unique_urls']} ({s['duplicates_removed']} duplicates removed)")
    print(f"  Content:    {s['with_content']} pages with content")
    print(f"  Empty:      {s['empty']} pages empty")
    print(f"  Total size: {s['total_chars']:,} chars")
    print(f"\nURLs ({s['unique_urls']}):")
    for u in report["urls"]:
        status = f"{u['chars']:>8,} chars" if u["has_content"] else "   EMPTY"
        print(f"  {status}  {u['url']}")


def load_domains():
    entries = []
    with open(DOMAINS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("|")
                entries.append({
                    "label": parts[0],
                    "url": parts[1],
                    "depth": int(parts[2]),
                    "max_pages": int(parts[3]),
                })
    return entries


async def run_all():
    domains = load_domains()
    print(f"Batch crawl: {len(domains)} domains from domains.txt\n")
    tasks = [main(d["url"], d["depth"], d["max_pages"], d["label"]) for d in domains]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl a website and report URL discovery metrics")
    parser.add_argument("url", nargs="?", help="Seed URL to crawl")
    parser.add_argument("--label", help="Report filename prefix (default: derived from domain)")
    parser.add_argument("--depth", type=int, default=2, help="Max crawl depth (default: 2)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to crawl (default: 50)")
    parser.add_argument("--all", action="store_true", help="Crawl all domains from domains.txt")
    args = parser.parse_args()

    if args.all:
        asyncio.run(run_all())
    elif args.url:
        label = args.label or urlparse(args.url).netloc.replace('.', '_')
        asyncio.run(main(args.url, args.depth, args.max_pages, label))
    else:
        parser.error("Either provide a URL or use --all")
