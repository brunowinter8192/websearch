# INFRASTRUCTURE
import argparse
import asyncio
import time
import uuid
from pathlib import Path

from crawl4ai import AsyncWebCrawler

from src.scraper.chromium_scrape import hash_config
from src.crawler.pipe_scraper_constants import DOWNLOAD_DELAY, CONCURRENCY_PER_DOMAIN, CAMOUFOX_CONCURRENCY_PER_DOMAIN
from src.crawler.pipe_scraper_config import _build_configs, _extract_pipe_config_stamp
from src.crawler.pipe_scraper_acquisition import _scrape_one, _scrape_one_camoufox
from src.crawler.pipe_scraper_report import (
    _domain_from_urls, _write_tmp_report, _print_summary, _collect_onward_links,
    _write_onward_links_file,
)

# ORCHESTRATOR

async def scrape_urls_workflow(
    urls: list[str],
    output_dir: Path,
    download_delay: float = DOWNLOAD_DELAY,
    concurrency_per_domain: int | None = None,
    engine: str = "chromium",
    block_images: bool = False,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results = await _scrape_all(urls, output_dir, download_delay, concurrency_per_domain,
                                 engine, block_images)
    wall_s = time.time() - t0
    domain = _domain_from_urls(urls)
    onward_links = _collect_onward_links(urls, results, engine)
    _print_summary(results, wall_s, onward_links)
    _write_tmp_report(domain, results)
    _write_onward_links_file(domain, onward_links)
    return results


# FUNCTIONS

async def _scrape_all(
    urls: list[str],
    output_dir: Path,
    download_delay: float,
    concurrency_per_domain: int | None,
    engine: str = "chromium",
    block_images: bool = False,
) -> list[dict]:
    resolved_concurrency = concurrency_per_domain if concurrency_per_domain is not None else (
        CAMOUFOX_CONCURRENCY_PER_DOMAIN if engine == "camoufox" else CONCURRENCY_PER_DOMAIN
    )
    domain_states: dict = {}

    if engine == "camoufox":
        run_ctx = {"run_id": str(uuid.uuid4())}
        raw = await asyncio.gather(
            *[_scrape_one_camoufox(url, domain_states, download_delay, resolved_concurrency,
                                    output_dir, run_ctx, block_images)
              for url in urls],
            return_exceptions=True,
        )
    else:
        browser_cfg, run_cfg = _build_configs()
        config_stamp = _extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay, resolved_concurrency)
        run_ctx = {
            "run_id": str(uuid.uuid4()),
            "config_hash": hash_config(config_stamp),
            "config": config_stamp,
        }
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            raw = await asyncio.gather(
                *[_scrape_one(crawler, url, run_cfg, domain_states,
                              download_delay, resolved_concurrency, output_dir, run_ctx)
                  for url in urls],
                return_exceptions=True,
            )
    return [
        r if isinstance(r, dict)
        else {'url': urls[i], 'wall_ms': 0, 'bytes': 0, 'status_code': None}
        for i, r in enumerate(raw)
    ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Pipe scraper — crawl URL list to markdown with Scrapy-style per-domain pacing')
    parser.add_argument('--url-file', required=True, help='Text file with URLs (one per line)')
    parser.add_argument('--output-dir', required=True, help='Directory to write per-URL markdown files')
    parser.add_argument('--download-delay', type=float, default=DOWNLOAD_DELAY,
                        help=f'Scrapy per-domain base delay in seconds (default: {DOWNLOAD_DELAY}); actual jitter = uniform(0.5×, 1.5×)')
    parser.add_argument('--concurrency-per-domain', type=int, default=None,
                         help=f'Per-domain in-flight request cap (default: {CONCURRENCY_PER_DOMAIN} '
                              f'chromium / {CAMOUFOX_CONCURRENCY_PER_DOMAIN} camoufox — resolved by --engine when omitted)')
    parser.add_argument('--engine', choices=['chromium', 'camoufox'], default='chromium',
                         help='Acquisition engine, chosen per RUN not per URL: "chromium" (crawl4ai, '
                              'default, current behavior) or "camoufox" (Playwright-Firefox, a '
                              'deliberate second lane — not a fallback of chromium)')
    parser.add_argument('--block-images', dest='block_images', action='store_true', default=False,
                         help='camoufox engine only: block image requests (default: off — stealth '
                              'wins over bandwidth; Camoufox\'s own LeakWarning documents '
                              'image-blocking as a WAF detection signal)')
    parser.add_argument('--no-block-images', dest='block_images', action='store_false',
                         help='camoufox engine only: allow image requests (default)')
    args = parser.parse_args()

    urls = [ln.strip() for ln in Path(args.url_file).read_text(encoding='utf-8').splitlines()
            if ln.strip()]
    asyncio.run(scrape_urls_workflow(
        urls, Path(args.output_dir), args.download_delay, args.concurrency_per_domain,
        args.engine, args.block_images,
    ))
