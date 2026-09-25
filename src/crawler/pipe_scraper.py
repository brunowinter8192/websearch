# INFRASTRUCTURE
import argparse
import asyncio
import time
import uuid
from pathlib import Path

from crawl4ai import AsyncWebCrawler

from src.scraper.chromium_scrape import hash_config
from src.crawler.pipe_scraper_constants import DOWNLOAD_DELAY, CONCURRENCY_PER_DOMAIN, CAMOUFOX_CONCURRENCY_PER_DOMAIN
from src.crawler.pipe_scraper_config import build_configs, extract_pipe_config_stamp
from src.crawler.pipe_scraper_acquisition import scrape_one, scrape_one_camoufox
from src.crawler.pipe_scraper_report import (
    domain_from_urls, write_tmp_report, print_summary, collect_onward_links,
    write_onward_links_file,
)


# ORCHESTRATOR

def run_cli() -> None:
    args = _parse_args()
    urls = _read_url_file(args.url_file)
    asyncio.run(scrape_urls_workflow(
        urls, Path(args.output_dir), args.download_delay, args.concurrency_per_domain,
        args.engine, args.block_images, args.headed,
    ))


# FUNCTIONS

def _parse_args() -> argparse.Namespace:
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
    parser.add_argument('-g', '--headed', action='store_true', default=False,
                         help='chromium engine only: run the browser visible instead of headless '
                              '(default: headless, unchanged)')
    return parser.parse_args()


def _read_url_file(url_file: str) -> list[str]:
    return [ln.strip() for ln in Path(url_file).read_text(encoding='utf-8').splitlines()
            if ln.strip()]


async def scrape_urls_workflow(
    urls: list[str],
    output_dir: Path,
    download_delay: float = DOWNLOAD_DELAY,
    concurrency_per_domain: int | None = None,
    engine: str = "chromium",
    block_images: bool = False,
    headed: bool = False,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results = await _scrape_all(urls, output_dir, download_delay, concurrency_per_domain,
                                 engine, block_images, headed)
    wall_s = _elapsed_since(t0)
    domain = domain_from_urls(urls)
    onward_links = collect_onward_links(urls, results, engine)
    print_summary(results, wall_s, onward_links)
    write_tmp_report(domain, results)
    write_onward_links_file(domain, onward_links)
    return results


async def _scrape_all(
    urls: list[str],
    output_dir: Path,
    download_delay: float,
    concurrency_per_domain: int | None,
    engine: str = "chromium",
    block_images: bool = False,
    headed: bool = False,
) -> list[dict]:
    resolved_concurrency = concurrency_per_domain if concurrency_per_domain is not None else (
        CAMOUFOX_CONCURRENCY_PER_DOMAIN if engine == "camoufox" else CONCURRENCY_PER_DOMAIN
    )
    domain_states: dict = {}

    if engine == "camoufox":
        run_ctx = {"run_id": str(uuid.uuid4())}
        raw = await asyncio.gather(
            *[scrape_one_camoufox(url, domain_states, download_delay, resolved_concurrency,
                                  output_dir, run_ctx, block_images)
              for url in urls],
        )
    else:
        browser_cfg, run_cfg = build_configs(headed=headed)
        config_stamp = extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay, resolved_concurrency)
        run_ctx = {
            "run_id": str(uuid.uuid4()),
            "config_hash": hash_config(config_stamp),
            "config": config_stamp,
        }
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            raw = await asyncio.gather(
                *[scrape_one(crawler, url, run_cfg, domain_states,
                             download_delay, resolved_concurrency, output_dir, run_ctx)
                  for url in urls],
            )
    return list(raw)


def _elapsed_since(t0: float) -> float:
    return time.time() - t0


if __name__ == '__main__':
    run_cli()
