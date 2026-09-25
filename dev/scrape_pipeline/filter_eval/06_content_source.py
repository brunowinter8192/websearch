# INFRASTRUCTURE
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

CRAWL_REPORTS_DIR = Path(__file__).parent.parent.parent / "explore_pipeline" / "md"
OUTPUT_DIR = Path(__file__).parent / "05_content_source"
MAX_URLS_PER_DOMAIN = 20
PARALLEL_URLS = 5

CONFIGS = {
    "cleaned_html": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(),
    ),
    "cleaned_html_pruning": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48, threshold_type="fixed", min_word_threshold=0
            )
        ),
    ),
    "raw_html": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(content_source="raw_html"),
    ),
    "raw_html_pruning": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(
            content_source="raw_html",
            content_filter=PruningContentFilter(
                threshold=0.48, threshold_type="fixed", min_word_threshold=0
            ),
        ),
    ),
    "fit_html": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(content_source="fit_html"),
    ),
    "fit_html_pruning": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",
        markdown_generator=DefaultMarkdownGenerator(
            content_source="fit_html",
            content_filter=PruningContentFilter(
                threshold=0.48, threshold_type="fixed", min_word_threshold=0
            ),
        ),
    ),
}

MARKDOWN_FIELD = {
    "cleaned_html": "raw_markdown",
    "cleaned_html_pruning": "fit_markdown",
    "raw_html": "raw_markdown",
    "raw_html_pruning": "fit_markdown",
    "fit_html": "raw_markdown",
    "fit_html_pruning": "fit_markdown",
}


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare content_source configs across crawled domains")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--domain", help="Test single domain by crawl report label")
    group.add_argument("--url", help="Test single URL directly")
    group.add_argument("--all", action="store_true", help="Test all domains from crawling reports")
    args = parser.parse_args()

    if args.url:
        asyncio.run(run_content_source_comparison([args.url], "single_url"))
    elif args.domain:
        crawl_report = find_crawl_report(args.domain)
        if not crawl_report:
            _print_no_crawl_report(args)
            _list_crawl_reports()
            exit(1)
        urls = load_urls_from_crawl_report(crawl_report)
        _print_domain_urls_max(args, urls)
        asyncio.run(run_content_source_comparison(urls, args.domain))
    else:
        crawl_reports = find_all_crawl_reports()
        if not crawl_reports:
            _print_no_crawl_reports()
            print("Run explore pipeline first: python dev/explore_pipeline/01_discovery.py --all")
            exit(1)
        _compare_reports(crawl_reports)


# FUNCTIONS

def find_crawl_report(label: str) -> Path | None:
    matches = sorted(CRAWL_REPORTS_DIR.glob(f"{label}_*.json"))
    return matches[-1] if matches else None


def _print_no_crawl_report(args):
    print(f"No crawl report found for: {args.domain}")
    print(f"Available reports in {CRAWL_REPORTS_DIR}:")


def _list_crawl_reports():
    for p in sorted(CRAWL_REPORTS_DIR.glob("*.json")):
        print(f"  {p.name}")


def _print_domain_urls_max(args, urls):
    print(f"Domain: {args.domain} ({len(urls)} URLs, max {MAX_URLS_PER_DOMAIN})")


def find_all_crawl_reports() -> list[tuple[str, Path]]:
    reports = []
    for path in sorted(CRAWL_REPORTS_DIR.glob("*.json")):
        label = path.stem.rsplit("_", 2)[0]
        reports.append((label, path))
    return reports


def _print_no_crawl_reports():
    print(f"No crawl reports found in {CRAWL_REPORTS_DIR}")


def _compare_reports(crawl_reports):
    for label, path in crawl_reports:
        urls = load_urls_from_crawl_report(path)
        print(f"\nDomain: {label} ({len(urls)} URLs, max {MAX_URLS_PER_DOMAIN})")
        asyncio.run(run_content_source_comparison(urls, label))


async def run_content_source_comparison(urls: list[str], label: str):
    browser_config = BrowserConfig(headless=True, verbose=False)
    domain_dir = OUTPUT_DIR / label

    for config_name in CONFIGS:
        (domain_dir / config_name).mkdir(parents=True, exist_ok=True)

    indexed_urls = list(enumerate(urls, 1))
    semaphore = asyncio.Semaphore(PARALLEL_URLS)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [
            scrape_with_semaphore(semaphore, crawler, url, domain_dir, idx, len(urls))
            for idx, url in indexed_urls
        ]
        await asyncio.gather(*tasks)

    print(f"  Output: {domain_dir}/")


def load_urls_from_crawl_report(report_path: Path) -> list[str]:
    with open(report_path) as f:
        data = json.load(f)
    urls = [u["url"] for u in data["urls"] if u["has_content"]]
    return urls[:MAX_URLS_PER_DOMAIN]


async def scrape_with_semaphore(sem, crawler, url, domain_dir, index, total):
    async with sem:
        print(f"  [{index}/{total}] {url}")
        await scrape_and_save(crawler, url, domain_dir, index)


async def scrape_and_save(crawler, url: str, domain_dir: Path, index: int):
    slug = url_to_slug(url)
    filename = f"{index:02d}_{slug}.md"

    async def scrape_config(config_name, run_config):
        result = await crawler.arun(url=url, config=run_config)
        field = MARKDOWN_FIELD[config_name]
        md = getattr(result.markdown, field, "") if result.markdown else ""
        out_path = domain_dir / config_name / filename
        out_path.write_text(md, encoding="utf-8")

    config_tasks = [
        scrape_config(name, config) for name, config in CONFIGS.items()
    ]
    await asyncio.gather(*config_tasks)


def url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path and not parsed.query:
        return parsed.netloc.replace(".", "_")
    parts = path.replace("/", "_").replace(".", "_")
    if parsed.query:
        query_slug = parsed.query.replace("&", "_").replace("=", "_").replace(".", "_")
        parts = f"{parts}_{query_slug}" if parts else query_slug
    return parts[:80]


if __name__ == "__main__":
    main()
