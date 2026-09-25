# INFRASTRUCTURE
import asyncio
import logging
import re
import time
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

logger = logging.getLogger(__name__)

EMPTY_THRESHOLD_BYTES = 100


# ORCHESTRATOR

async def scrape_urls(
    urls: list[str],
    delay_s: float = 1.0,
    page_timeout_ms: int = 15000,
    concurrency: int = 5,
    output_dir: Path | None = None,
) -> list[dict]:
    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="domcontentloaded",
        delay_before_return_html=delay_s,
        page_timeout=page_timeout_ms,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    sem = asyncio.Semaphore(concurrency)

    raw = await _scrape_all(urls, browser_cfg, run_cfg, sem, output_dir)

    return _replace_exceptions(raw, urls)


# FUNCTIONS

async def _scrape_all(urls, browser_cfg, run_cfg, sem, output_dir):
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        tasks = [_scrape_one(crawler, url, run_cfg, sem, output_dir) for url in urls]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
    return raw


def _replace_exceptions(raw, urls):
    return [r if isinstance(r, dict) else {'url': urls[i], 'outcome': 'error',
                                            'wall_ms': 0, 'bytes': 0, 'status_code': None}
            for i, r in enumerate(raw)]


async def _scrape_one(
    crawler: AsyncWebCrawler,
    url: str,
    run_cfg: CrawlerRunConfig,
    sem: asyncio.Semaphore,
    output_dir: Path | None,
) -> dict:
    async with sem:
        t0 = time.time()
        try:
            result = await crawler.arun(url=url, config=run_cfg)
        except Exception as exc:
            return {
                'url': url, 'wall_ms': int((time.time() - t0) * 1000),
                'bytes': 0, 'status_code': None, 'outcome': 'error',
            }
        wall_ms = int((time.time() - t0) * 1000)

    raw_md = (result.markdown.raw_markdown if result.markdown else '') or ''
    status = getattr(result, 'status_code', None)
    byte_count = len(raw_md.encode('utf-8'))

    if status == 429:
        outcome = 'waf_429'
    elif status and status >= 400:
        outcome = 'http_error'
    elif byte_count < EMPTY_THRESHOLD_BYTES:
        outcome = 'empty'
    else:
        outcome = 'ok'

    if output_dir is not None and raw_md:
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = url_to_filename(url)
        (output_dir / fname).write_text(
            f"<!-- source: {url} -->\n\n{raw_md}", encoding='utf-8'
        )

    return {
        'url': url,
        'wall_ms': wall_ms,
        'bytes': byte_count,
        'status_code': status,
        'outcome': outcome,
    }


def url_to_filename(url: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]', '_', url.split('://')[-1])
    slug = re.sub(r'_+', '_', slug).strip('_')[:100]
    return f"{slug}.md"
