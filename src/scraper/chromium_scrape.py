# INFRASTRUCTURE
import asyncio
import hashlib
import json
import logging
import shutil
import tempfile
import time
from typing import Callable

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from mcp.types import TextContent
from src.scraper.scrape_logger import domain_of, elapsed_ms, log_scrape, utc_timestamp, write_sidecar
from src import watchdog_spawn
from src.config import CDP_PORT_WAIT_TIMEOUT_S, TOTAL_SCRAPE_BUDGET_S
from src.scraper.chromium_process import (
    build_self_launch_flags,
    focus_steal_watchdog, kill_by_profile, pids_on_profile, reap_orphaned_scrapes,
    resolve_chromium_bundle_path, self_launch_chrome, wait_for_devtools_port,
)

logger = logging.getLogger(__name__)

LAUNCH_MODE = "cdp_headed_backgrounded"

_BROWSER_LAUNCH_SIGNATURES = (
    "executable doesn't exist",
    "playwright install",
    "browsertype.launch",
    "devtoolsactiveport did not appear",
)


# ORCHESTRATOR

async def scrape_url_chromium_workflow(url: str) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = utc_timestamp()
    domain = domain_of(url)
    logger.info("Scraping: %s", url)

    content, meta = await try_scrape(url)
    total_wall = elapsed_ms(t_total)
    config = _config_of(meta)
    config_hash = hash_config(config)

    content_path = write_sidecar(url, ts, content, "filtered", "chromium")
    log_scrape(_build_scrape_record(ts, url, domain, content, meta, total_wall, content_path, config_hash, config))
    _log_scrape_complete(url, content, meta)
    return [_scrape_text_content(url, content)]


# FUNCTIONS

async def try_scrape(url: str) -> tuple[str, dict]:
    await asyncio.to_thread(reap_orphaned_scrapes)
    run_config = _build_run_config()
    budget_s = TOTAL_SCRAPE_BUDGET_S
    _empty_meta: dict = {
        "acquisition_error": None, "status_code": None, "content_type": None,
        "raw_markdown_bytes": 0, "og_published_time": None,
        "crawl4ai_success": None, "crawl4ai_error_message": None,
        "crawl4ai_attempts": None, "crawl4ai_resolved_by": None,
        "landed_url": None,
        "document_status_chain": [],
        "config": {"config_incomplete": True, "launch_mode": LAUNCH_MODE, "total_budget_s": budget_s},
    }
    try:
        return await asyncio.wait_for(
            _acquire_cdp_headed(url, run_config, _empty_meta, budget_s), timeout=budget_s
        )
    except asyncio.TimeoutError:
        logger.warning("Scrape budget exhausted (%.1fs, launch_mode=%s): %s", budget_s, LAUNCH_MODE, url)
        return "", {**_empty_meta, "acquisition_error": "budget_exhausted"}
    except Exception as e:
        if is_browser_launch_error(e):
            logger.error("Browser binary missing/failed to launch for %s: %s", url, e)
            return "", {**_empty_meta, "acquisition_error": "browser_missing"}
        logger.warning("Failed to scrape %s: %s", url, e)
        return "", {**_empty_meta, "acquisition_error": "exception"}


def _build_run_config() -> CrawlerRunConfig:
    return CrawlerRunConfig(
        magic=True,
        wait_until="load",
        page_timeout=30000,
        delay_before_return_html=5.0,
        max_retries=0,
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.48, preserve_tags=["pre", "code"])
        ),
        remove_consent_popups=True,
        verbose=False,
    )


async def _acquire_cdp_headed(
    url: str, run_config: CrawlerRunConfig, empty_meta: dict, budget_s: float,
) -> tuple[str, dict]:
    flags = build_self_launch_flags(BrowserConfig(enable_stealth=True))
    bundle_path = await resolve_chromium_bundle_path()
    user_data_dir = tempfile.mkdtemp(prefix="scrape-url-cdp-")
    watchdog_task = asyncio.create_task(focus_steal_watchdog(bundle_path.stem))
    try:
        self_launch_chrome(bundle_path, user_data_dir, flags)
        port = await asyncio.to_thread(wait_for_devtools_port, user_data_dir, CDP_PORT_WAIT_TIMEOUT_S)
        pids = await asyncio.to_thread(pids_on_profile, user_data_dir)
        watchdog_spawn.spawn_watchdog(pids, cleanup_dir=user_data_dir)
        browser_config = BrowserConfig(
            cdp_url=f"http://127.0.0.1:{port}",
            browser_mode="custom",
            enable_stealth=True,
            cdp_cleanup_on_close=True,
            verbose=False,
        )
        adapter = UndetectedAdapter()
        crawler_strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_config, browser_adapter=adapter)
        crawler_strategy.set_hook("on_page_context_created", _reject_popup_pages)
        document_status_chain: list = []
        crawler_strategy.set_hook("before_goto", _make_document_status_listener(document_status_chain))
        config_stamp = extract_config_stamp(browser_config, adapter, crawler_strategy, run_config, budget_s)
        empty_meta = {**empty_meta, "config": config_stamp}
        return await _acquire_scrape(
            url, browser_config, crawler_strategy, run_config, empty_meta, document_status_chain
        )
    finally:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(kill_by_profile, user_data_dir)
        shutil.rmtree(user_data_dir, ignore_errors=True)


def _reject_popup_pages(main_page, context=None, config=None) -> None:
    def _on_new_page(new_page) -> None:
        if new_page is main_page:
            return
        asyncio.create_task(_close_popup_page(new_page))
    context.on("page", _on_new_page)


async def _close_popup_page(page) -> None:
    try:
        await page.close()
    except Exception as e:
        logger.debug("Popup page close failed (non-fatal): %s", e)


def _make_document_status_listener(status_chain: list) -> Callable:
    def _on_before_goto(page, context=None, url=None, config=None) -> None:
        def _on_response(response) -> None:
            request = response.request
            if request.resource_type != "document":
                return
            try:
                frame = request.frame
            except Exception as e:
                logger.debug("Document response dropped, request.frame unavailable: %s (%s)", response.url, e)
                return
            if frame is not page.main_frame:
                return
            status_chain.append(response.status)
        page.on("response", _on_response)
    return _on_before_goto


def extract_config_stamp(
    browser_config, adapter, crawler_strategy, run_config, total_budget_s: float,
) -> dict:
    content_filter = run_config.markdown_generator.content_filter
    return {
        "launch_mode": LAUNCH_MODE,
        "enable_stealth": browser_config.enable_stealth,
        "adapter": type(adapter).__name__,
        "crawler_strategy": type(crawler_strategy).__name__,
        "magic": run_config.magic,
        "wait_until": run_config.wait_until,
        "page_timeout_ms": run_config.page_timeout,
        "delay_before_return_html_s": run_config.delay_before_return_html,
        "max_retries": run_config.max_retries,
        "cache_mode": run_config.cache_mode.value,
        "content_filter": type(content_filter).__name__,
        "content_filter_threshold": content_filter.threshold,
        "content_filter_preserve_tags": sorted(content_filter.preserve_tags),
        "remove_consent_popups": run_config.remove_consent_popups,
        "total_budget_s": total_budget_s,
    }


async def _acquire_scrape(
    url: str, browser_config: BrowserConfig, crawler_strategy: AsyncPlaywrightCrawlerStrategy,
    run_config: CrawlerRunConfig, empty_meta: dict, document_status_chain: list,
) -> tuple[str, dict]:
    async with AsyncWebCrawler(config=browser_config, crawler_strategy=crawler_strategy) as crawler:
        result = await crawler.arun(url=url, config=run_config)
    status_code = result.status_code if hasattr(result, "status_code") else None
    if document_status_chain:
        status_code = document_status_chain[-1]
    ct = None
    if hasattr(result, "response_headers") and result.response_headers:
        ct = result.response_headers.get("content-type")
    landed_url = getattr(result, "redirected_url", None)
    meta: dict = {**empty_meta, "status_code": status_code, "content_type": ct,
                  "landed_url": landed_url, "document_status_chain": list(document_status_chain)}
    meta.update(extract_crawl4ai_diagnosis(result))
    if not result.markdown:
        return "", meta
    meta["raw_markdown_bytes"] = len((result.markdown.raw_markdown or "").encode("utf-8"))
    meta["og_published_time"] = (getattr(result, "metadata", None) or {}).get("og:published_time")
    content = result.markdown.fit_markdown or ""
    return content, meta


def extract_crawl4ai_diagnosis(result) -> dict:
    stats = getattr(result, "crawl_stats", None) or {}
    return {
        "crawl4ai_success": getattr(result, "success", None),
        "crawl4ai_error_message": getattr(result, "error_message", None) or None,
        "crawl4ai_attempts": stats.get("attempts"),
        "crawl4ai_resolved_by": stats.get("resolved_by"),
        "crawl4ai_fallback_fetch_used": stats.get("fallback_fetch_used"),
    }


def is_browser_launch_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(sig in msg for sig in _BROWSER_LAUNCH_SIGNATURES)


def _config_of(meta: dict) -> dict:
    return meta.get("config") or {"config_incomplete": True}


def hash_config(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def _build_scrape_record(
    ts: str, url: str, domain: str, content: str, meta: dict,
    total_wall: int, content_path: str | None, config_hash: str, config: dict,
) -> dict:
    return {
        "ts": ts, "url": url, "domain": domain, "mode": "filtered",
        "engine": "chromium",
        "acquisition_error": meta.get("acquisition_error"),
        "timings_ms": {"total_wall": total_wall},
        "http_status": meta.get("status_code"), "content_type": meta.get("content_type"),
        "bytes_returned": len(content.encode("utf-8")) if content else 0,
        "bytes_raw_markdown": meta.get("raw_markdown_bytes", 0),
        "content_path": content_path,
        "og_published_time": meta.get("og_published_time"),
        "landed_url": meta.get("landed_url"),
        "crawl4ai_success": meta.get("crawl4ai_success"),
        "crawl4ai_error_message": meta.get("crawl4ai_error_message"),
        "crawl4ai_attempts": meta.get("crawl4ai_attempts"),
        "crawl4ai_resolved_by": meta.get("crawl4ai_resolved_by"),
        "document_status_chain": meta.get("document_status_chain"),
        "config_hash": config_hash, "config": config,
    }


def _log_scrape_complete(url: str, content: str, meta: dict) -> None:
    logger.info("Scrape complete: %s (%d chars, acquisition_error=%s)",
                url, len(content), meta.get("acquisition_error"))


def _scrape_text_content(url: str, content: str) -> TextContent:
    return TextContent(type="text", text=_format_scrape_output(url, content))


def _format_scrape_output(url: str, content: str) -> str:
    lines = [f"# Content from: {url}", ""]
    lines += ["## Content", "", content if content else "(no content returned)"]
    return "\n".join(lines)
