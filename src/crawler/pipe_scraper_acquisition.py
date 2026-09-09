# INFRASTRUCTURE
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

from src.crawler.pipe_scraper_pacing import _ensure_domain_state, _gate_domain
from src.crawler.pipe_scraper_records import _log_pipe_record, _log_pipe_camoufox_record
from src.crawler.seed_feeders_scope import host_key
from src.scraper.chromium_scrape import extract_crawl4ai_diagnosis
from src.scraper.camoufox_scrape import try_scrape_camoufox

_NON_PAGE_EXTENSIONS = (
    ".gif", ".jpg", ".jpeg", ".png", ".webp", ".svg", ".ico", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".mp4", ".mp3",
)

# FUNCTIONS

def _url_to_filename(url: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]', '_', url.split('://')[-1])
    slug = re.sub(r'_+', '_', slug).strip('_')[:100]
    return f"{slug}.md"

def _onward_link_identity(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if not parsed.hostname:
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", ""))

def _extract_onward_links(result, page_host: str) -> list[str]:
    seed_key = host_key(page_host)
    raw_links = getattr(result, "links", None) or {}
    hrefs = [
        item.get("href") for bucket in ("internal", "external")
        for item in (raw_links.get(bucket) or []) if item.get("href")
    ]
    seen = set()
    onward = []
    for href in hrefs:
        identity = _onward_link_identity(href)
        if identity is None:
            continue
        if host_key(urlsplit(identity).hostname or "") != seed_key:
            continue
        if identity.lower().endswith(_NON_PAGE_EXTENSIONS):
            continue
        if identity in seen:
            continue
        seen.add(identity)
        onward.append(identity)
    return onward

async def _scrape_one(
    crawler: AsyncWebCrawler,
    url: str,
    run_cfg: CrawlerRunConfig,
    domain_states: dict,
    download_delay: float,
    concurrency_per_domain: int,
    output_dir: Path,
    run_ctx: dict,
) -> dict:
    domain = urlparse(url).netloc
    state = _ensure_domain_state(domain_states, domain, concurrency_per_domain)
    async with state['sem']:
        await _gate_domain(state, download_delay)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        t0 = time.time()
        try:
            result = await crawler.arun(url=url, config=run_cfg)
        except Exception:
            wall_ms = int((time.time() - t0) * 1000)
            _log_pipe_record(run_ctx, ts, url, domain, None, 0, wall_ms, {})
            return {'url': url, 'wall_ms': wall_ms, 'bytes': 0, 'status_code': None}
        wall_ms = int((time.time() - t0) * 1000)

    raw_md = (result.markdown.raw_markdown if result.markdown else '') or ''
    status = getattr(result, 'status_code', None)
    byte_count = len(raw_md.encode('utf-8'))

    if raw_md:
        fname = _url_to_filename(url)
        (output_dir / fname).write_text(f"<!-- source: {url} -->\n\n{raw_md}", encoding='utf-8')

    diagnosis = extract_crawl4ai_diagnosis(result)
    landed_url = getattr(result, "redirected_url", None)
    links = _extract_onward_links(result, urlparse(url).hostname or domain)
    _log_pipe_record(run_ctx, ts, url, domain, status, byte_count, wall_ms, diagnosis,
                      landed_url=landed_url)

    return {'url': url, 'wall_ms': wall_ms, 'bytes': byte_count, 'status_code': status,
            'links': links}

async def _scrape_one_camoufox(
    url: str,
    domain_states: dict,
    download_delay: float,
    concurrency_per_domain: int,
    output_dir: Path,
    run_ctx: dict,
    block_images: bool,
) -> dict:
    domain = urlparse(url).netloc
    state = _ensure_domain_state(domain_states, domain, concurrency_per_domain)
    async with state['sem']:
        await _gate_domain(state, download_delay)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        t0 = time.time()
        content, meta = await try_scrape_camoufox(url, block_images=block_images)
        wall_ms = int((time.time() - t0) * 1000)

    status = meta.get('status_code')
    byte_count = len(content.encode('utf-8')) if content else 0

    if content:
        fname = _url_to_filename(url)
        (output_dir / fname).write_text(f"<!-- source: {url} -->\n\n{content}", encoding='utf-8')

    _log_pipe_camoufox_record(run_ctx, ts, url, domain, status, byte_count, wall_ms, meta)

    return {'url': url, 'wall_ms': wall_ms, 'bytes': byte_count, 'status_code': status}
