# INFRASTRUCTURE
import asyncio
import hashlib
import json
import logging
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from mcp.types import TextContent
# From scrape_logger.py: per-URL JSONL log + sidecar content file
from src.scraper.scrape_logger import log_scrape, write_sidecar
# From death_pipe.py: net-2 crash backstop (per-call watchdog) — net-3 orphan reap reuses its
# terminate/kill primitive
from src import death_pipe
from src.scraper.chromium_process import (
    CDP_PORT_WAIT_TIMEOUT_S, TOTAL_SCRAPE_BUDGET_S, _build_self_launch_flags,
    _focus_steal_watchdog, _kill_by_profile, _pids_on_profile, _reap_orphaned_scrapes,
    _resolve_chromium_bundle_path, _self_launch_chrome, _wait_for_devtools_port,
)

logger = logging.getLogger(__name__)

# The single-value posture stamp for extract_config_stamp's "launch_mode" field — kept as a
# constant (not a param) since the escape hatch removal (process-docs/browser_posture/) leaves only
# one acquisition path; still recorded in the log as a truthful discriminator for browser_config.
# headless, which is dead on the cdp path (never read inside crawl4ai's cdp_url branch).
LAUNCH_MODE = "cdp_headed_backgrounded"

_ACQUISITION_ERROR_MESSAGES = {
    "browser_missing": "browser binary missing — run `./venv/bin/python -m patchright install chromium` to install it",
}

_BROWSER_LAUNCH_SIGNATURES = (
    "executable doesn't exist",
    "playwright install",
    "browsertype.launch",
    "devtoolsactiveport did not appear",  # this module's own self-launch bounded-wait timeout (cdp path)
)


# ORCHESTRATOR

# Scrape one URL end to end: acquire, log, render — returns content as-is plus acquisition facts
async def scrape_url_chromium_workflow(url: str) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    logger.info("Scraping: %s", url)

    content, meta = await try_scrape(url)
    total_wall = round((time.perf_counter() - t_total) * 1000)
    config = meta.get("config") or {"config_incomplete": True}
    config_hash = hash_config(config)
    og_published_time = meta.get("og_published_time")

    content_path = write_sidecar(url, ts, content, "filtered", "chromium")
    log_scrape({
        "ts": ts, "url": url, "domain": domain, "mode": "filtered",
        "engine": "chromium",
        "acquisition_error": meta.get("acquisition_error"),
        "timings_ms": {"total_wall": total_wall},
        "http_status": meta.get("status_code"), "content_type": meta.get("content_type"),
        "bytes_returned": len(content.encode("utf-8")) if content else 0,
        "bytes_raw_markdown": meta.get("raw_markdown_bytes", 0),
        "content_path": content_path,
        "og_published_time": og_published_time,
        "landed_url": meta.get("landed_url"),
        "crawl4ai_success": meta.get("crawl4ai_success"),
        "crawl4ai_error_message": meta.get("crawl4ai_error_message"),
        "crawl4ai_attempts": meta.get("crawl4ai_attempts"),
        "crawl4ai_resolved_by": meta.get("crawl4ai_resolved_by"),
        "crawl4ai_fallback_fetch_used": meta.get("crawl4ai_fallback_fetch_used"),
        "document_status_chain": meta.get("document_status_chain"),
        "config_hash": config_hash, "config": config,
    })
    logger.info("Scrape complete: %s (%d chars, acquisition_error=%s)",
                url, len(content), meta.get("acquisition_error"))
    return [TextContent(type="text", text=_format_scrape_output(url, content, meta, og_published_time))]


# FUNCTIONS

# Run one browser acquisition + date extraction + content selection, the guarded span inside try_scrape's budget
async def _acquire_scrape(
    url: str, browser_config: BrowserConfig, crawler_strategy: AsyncPlaywrightCrawlerStrategy,
    run_config: CrawlerRunConfig, empty_meta: dict, document_status_chain: list,
) -> tuple[str, dict]:
    async with AsyncWebCrawler(config=browser_config, crawler_strategy=crawler_strategy) as crawler:
        result = await crawler.arun(url=url, config=run_config)
    status_code = result.status_code if hasattr(result, "status_code") else None
    # The LAST main-frame document response (document_status_chain, collected by the before_goto
    # hook set below) is the response of the page whose content was actually captured — overrides
    # crawl4ai's own status_code, which keeps only the EARLIEST goto-redirect-chain hop and is
    # never updated by a same-document JS navigation happening later (e.g. a Cloudflare challenge
    # resolving during delay_before_return_html). Empty chain (e.g. raw: input, no navigation at
    # all) falls back to crawl4ai's value unchanged — never invents a status.
    if document_status_chain:
        status_code = document_status_chain[-1]
    ct = None
    if hasattr(result, "headers") and result.headers:
        ct = result.headers.get("content-type") or result.headers.get("Content-Type")
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


# The run-governing config (unchanged by this milestone)
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


# Single-call crawl4ai scrape with native anti-bot baseline; returns (content, meta) unconditionally,
# no content judgment. Acquisition is always the cdp-headed-backgrounded route (self-launched
# chromium, connected over cdp_url).
async def try_scrape(url: str) -> tuple[str, dict]:
    await asyncio.to_thread(_reap_orphaned_scrapes)
    run_config = _build_run_config()
    budget_s = TOTAL_SCRAPE_BUDGET_S
    _empty_meta: dict = {
        "acquisition_error": None, "status_code": None, "content_type": None,
        "raw_markdown_bytes": 0, "og_published_time": None,
        "crawl4ai_success": None, "crawl4ai_error_message": None,
        "crawl4ai_attempts": None, "crawl4ai_resolved_by": None,
        "crawl4ai_fallback_fetch_used": None, "landed_url": None,
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


# The default route (probe 05's proven shape): self-launch chromium-1228 headed-but-backgrounded via
# macOS `open -g -n -a`, wait for its DevToolsActivePort, connect crawl4ai over cdp_url. Teardown
# (kill by profile-dir substring + remove the throwaway dir) runs in `finally` so it fires on every
# exit path, including the outer budget's cancellation and any exception raised above (net 1). A
# death_pipe watchdog is ALSO spawned once the port resolves (net 2) — the crash backstop for when
# this whole CLI process dies before the `finally` below ever gets a chance to run at all.
async def _acquire_cdp_headed(
    url: str, run_config: CrawlerRunConfig, empty_meta: dict, budget_s: float,
) -> tuple[str, dict]:
    flags = _build_self_launch_flags(BrowserConfig(enable_stealth=True))
    bundle_path = await _resolve_chromium_bundle_path()
    user_data_dir = tempfile.mkdtemp(prefix="scrape-url-cdp-")
    watchdog_task = asyncio.create_task(_focus_steal_watchdog(bundle_path.stem))
    try:
        _self_launch_chrome(bundle_path, user_data_dir, flags)
        port = await asyncio.to_thread(_wait_for_devtools_port, user_data_dir, CDP_PORT_WAIT_TIMEOUT_S)
        pids = await asyncio.to_thread(_pids_on_profile, user_data_dir)
        death_pipe.spawn_watchdog(pids, cleanup_dir=user_data_dir)
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
        # before_goto is unused by crawl4ai itself and fires before EVERY navigation attempt
        # (including page.goto's own response) — the one place that arms the response listener
        # early enough without touching the on_page_context_created slot _reject_popup_pages owns.
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
        await asyncio.to_thread(_kill_by_profile, user_data_dir)
        shutil.rmtree(user_data_dir, ignore_errors=True)


# crawl4ai's on_page_context_created hook target: closes any page the context creates BEYOND the
# one main_page crawl4ai itself asked for (ad/consent-flow popups, window.open) — each such extra
# page is an independent window-creation event that can trigger the same playwright#42343 activation
# the focus-steal watchdog above guards against; closing it fast shrinks that window further
def _reject_popup_pages(main_page, context=None, config=None) -> None:
    def _on_new_page(new_page) -> None:
        if new_page is main_page:
            return
        asyncio.create_task(_close_popup_page(new_page))
    context.on("page", _on_new_page)


# crawl4ai's before_goto hook target: arms a page.on("response") listener before navigation
# begins (so it also catches page.goto's own response), collecting the ORDERED chain of main-frame
# document response statuses — a same-document JS navigation after goto returns (e.g. a Cloudflare
# challenge resolving during delay_before_return_html) fires its own response event here even
# though crawl4ai's own status_code never sees it. A FACT, not a verdict — nothing here decides
# "challenge solved"/"blocked". request.frame can raise for a navigation request issued before its
# frame exists (iframes/popups) — guarded, not filtered on is_navigation_request() alone (which is
# also true for iframe navigations; comparing the frame to page.main_frame is the real filter).
def _make_document_status_listener(status_chain: list) -> Callable:
    def _on_before_goto(page, context=None, url=None, config=None) -> None:
        def _on_response(response) -> None:
            request = response.request
            if request.resource_type != "document":
                return
            try:
                frame = request.frame
            except Exception:
                return
            if frame is not page.main_frame:
                return
            status_chain.append(response.status)
        page.on("response", _on_response)
    return _on_before_goto


# Best-effort popup close — the page may already be gone/closing; logged, not raised, since a stray
# popup failing to close must degrade gracefully, never fail the main scrape it has nothing to do with
async def _close_popup_page(page) -> None:
    try:
        await page.close()
    except Exception as e:
        logger.debug("Popup page close failed (non-fatal): %s", e)


# Read the scrape-governing config back off the actual constructed objects, never re-declared.
# launch_mode is the truthful posture discriminator (browser_config.headless is DEAD on the cdp
# path — never read inside crawl4ai's cdp_url branch, confirmed by source — so it is not stamped at
# all; LAUNCH_MODE is a fixed module constant now that only one acquisition path exists).
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


# Stable short hash over the config record — cheap "same config" grouping key
def hash_config(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


# Read crawl4ai's own anti-bot diagnosis off the result object, verbatim — an OBSERVATION, not a verdict
def extract_crawl4ai_diagnosis(result) -> dict:
    stats = getattr(result, "crawl_stats", None) or {}
    return {
        "crawl4ai_success": getattr(result, "success", None),
        "crawl4ai_error_message": getattr(result, "error_message", None) or None,
        "crawl4ai_attempts": stats.get("attempts"),
        "crawl4ai_resolved_by": stats.get("resolved_by"),
        "crawl4ai_fallback_fetch_used": stats.get("fallback_fetch_used"),
    }


# Detect browser-launch/executable-missing failure (environment defect) vs. an ordinary per-URL error
def is_browser_launch_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(sig in msg for sig in _BROWSER_LAUNCH_SIGNATURES)


# Render acquisition facts + full content into one fixed-shape text block
def _format_scrape_output(url: str, content: str, meta: dict, og_published_time: str | None) -> str:
    lines = [f"# Content from: {url}", ""]
    lines += [
        "## Acquisition facts",
        f"- HTTP status: {meta.get('status_code')}",
        f"- Document status chain (ordered main-frame document response statuses observed before "
        f"capture; a fact, not a verdict — never read as challenge-solved/blocked): "
        f"{meta.get('document_status_chain')}",
        f"- Landed URL (the URL the browser actually returned content from): {meta.get('landed_url')}",
        f"- og:published_time (the page's OWN declared value, verbatim from its <head> meta tag — "
        f"null when the page declares none; never a third-party guess): {og_published_time}",
        f"- Bytes (raw markdown from crawl4ai): {meta.get('raw_markdown_bytes', 0)}",
        f"- Bytes (content below, after PruningContentFilter): "
        f"{len(content.encode('utf-8')) if content else 0}",
        "- crawl4ai diagnosis (an OBSERVATION off crawl4ai's own anti-bot detector, NOT a "
        "verdict — it has documented false positives and is not acted on by this scraper): "
        f"success={meta.get('crawl4ai_success')}, resolved_by={meta.get('crawl4ai_resolved_by')}, "
        f"attempts={meta.get('crawl4ai_attempts')}, "
        f"error_message={meta.get('crawl4ai_error_message') or 'none'}",
    ]
    if meta.get("acquisition_error"):
        reason = _acquisition_error_message(meta["acquisition_error"], meta.get("config") or {})
        lines.append(f"- Acquisition error: {reason}")
    lines += ["", "## Content", "", content if content else "(no content returned)"]
    return "\n".join(lines)


# The rendered acquisition-error description — budget_exhausted reads the REAL budget that was in
# effect for this call (config.total_budget_s) rather than a re-declared literal
def _acquisition_error_message(acquisition_error: str, config: dict) -> str:
    if acquisition_error == "budget_exhausted":
        budget = config.get("total_budget_s", "?")
        return f"scrape exceeded the total time budget ({budget}s)"
    return _ACQUISITION_ERROR_MESSAGES.get(acquisition_error, acquisition_error)
