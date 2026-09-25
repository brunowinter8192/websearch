# INFRASTRUCTURE
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUTPUT_DIR = Path(__file__).parent / "md"
PARALLEL_URLS = 5

CONFIGS = {
    "baseline": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="domcontentloaded",
    ),
    "networkidle": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="networkidle",
    ),
    "wait_2s": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="networkidle",
        delay_before_return_html=2.0,
    ),
    "css_selector": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="networkidle",
        wait_for="css:main, article, .content, #content",
    ),
    "full_page": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until="networkidle",
        scan_full_page=True,
    ),
}

JS_TEST_URLS = [
    "https://docs.trychroma.com/docs/overview/telemetry",
    "https://react.dev/reference/react/useState",
]


# ORCHESTRATOR

async def main():
    urls = get_urls()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    browser_config = BrowserConfig(headless=True, verbose=False)
    semaphore = asyncio.Semaphore(PARALLEL_URLS)

    results = await _open_crawler(browser_config, semaphore, urls)

    _run_browser_checks(urls, results)

    _print_output_saved_to()


# FUNCTIONS

def get_urls():
    if len(sys.argv) > 1:
        return sys.argv[1:]
    return JS_TEST_URLS


async def _open_crawler(browser_config, semaphore, urls):
    results = {}
    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [
            scrape_url_configs(semaphore, crawler, url, results)
            for url in urls
        ]
        await asyncio.gather(*tasks)
    return results


def _run_browser_checks(urls, results):
    for url in urls:
        domain = url.split("//")[-1].split("/")[0].replace(".", "_")
        slug = url_to_slug(url)
        prefix = f"{domain}_{slug}"

        print(f"\n{'=' * 70}")
        print(f"URL: {url}")
        print(f"{'=' * 70}")
        print(f"{'Config':<16} {'chars':>10} {'words':>10}")
        print(f"{'-' * 36}")

        for config_name in CONFIGS:
            chars, words = results.get((url, config_name), (0, 0))
            print(f"{config_name:<16} {chars:>10,} {words:>10,}")


def _print_output_saved_to():
    print(f"\nOutput saved to: {OUTPUT_DIR}")


async def scrape_url_configs(sem, crawler, url, results):
    async with sem:
        domain = url.split("//")[-1].split("/")[0].replace(".", "_")
        slug = url_to_slug(url)
        prefix = f"{domain}_{slug}"

        for name, config in CONFIGS.items():
            result = await crawler.arun(url=url, config=config)
            raw_md = result.markdown.raw_markdown if result.markdown else ""
            word_count = len(raw_md.split()) if raw_md else 0

            out_path = OUTPUT_DIR / f"03_{prefix}_{name}.md"
            out_path.write_text(raw_md, encoding="utf-8")

            results[(url, name)] = (len(raw_md), word_count)


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
    asyncio.run(main())
