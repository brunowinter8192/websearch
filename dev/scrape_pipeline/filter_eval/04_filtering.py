# INFRASTRUCTURE
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter

OUTPUT_DIR = Path(__file__).parent / "03_filter_comparison"
PARALLEL_URLS = 5

CONFIGS = {
    "raw": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
    ),
    "pruning_048": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48,
                threshold_type="fixed",
                min_word_threshold=0
            )
        ),
    ),
    "pruning_030": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.30,
                threshold_type="fixed",
                min_word_threshold=0
            )
        ),
    ),
    "pruning_070": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.70,
                threshold_type="fixed",
                min_word_threshold=0
            )
        ),
    ),
    "bm25": CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=BM25ContentFilter()
        ),
    ),
}

DOMAINS_FILE = Path(__file__).parent.parent / "domains.txt"


# ORCHESTRATOR

async def main():
    urls = get_urls()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    browser_config = BrowserConfig(headless=True, verbose=False)
    semaphore = asyncio.Semaphore(PARALLEL_URLS)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = [process_url_with_semaphore(semaphore, crawler, url) for url in urls]
        await asyncio.gather(*tasks)

    print(f"\nOutput saved to: {OUTPUT_DIR}")


# FUNCTIONS

def get_urls():
    if len(sys.argv) > 1:
        return [sys.argv[1]]
    urls = []
    with open(DOMAINS_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


async def process_url_with_semaphore(sem, crawler, url):
    async with sem:
        domain = url.split("//")[-1].split("/")[0].replace(".", "_")
        slug = url_to_slug(url)
        prefix = f"{domain}_{slug}"

        print(f"\n{'=' * 70}")
        print(f"URL: {url}")
        print(f"{'=' * 70}")
        print(f"{'Config':<16} {'raw_md':>10} {'fit_md':>10} {'Code OK':>10}")
        print(f"{'-' * 46}")

        for name, config in CONFIGS.items():
            result = await crawler.arun(url=url, config=config)

            raw_md = result.markdown.raw_markdown if result.markdown else ""
            fit_md = result.markdown.fit_markdown if result.markdown else ""

            use_md = fit_md if fit_md else raw_md
            code_check = check_code_integrity(use_md)
            code_status = "YES" if not code_check["mangled"] else "NO"

            (OUTPUT_DIR / f"{prefix}_{name}_raw.md").write_text(raw_md)
            if fit_md:
                (OUTPUT_DIR / f"{prefix}_{name}_fit.md").write_text(fit_md)

            print(f"{name:<16} {len(raw_md):>10,} {len(fit_md):>10,} {code_status:>10}")


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


def check_code_integrity(md: str) -> dict:
    in_code = False
    code_blocks = 0
    mangled_blocks = 0
    for line in md.split('\n'):
        if line.startswith('```'):
            if not in_code:
                in_code = True
                code_blocks += 1
            else:
                in_code = False
            continue
        if in_code and line.strip():
            if '$' in line and ' ' not in line and len(line) > 20:
                mangled_blocks += 1
                break
    return {"code_blocks": code_blocks, "mangled": mangled_blocks > 0}


if __name__ == "__main__":
    asyncio.run(main())
