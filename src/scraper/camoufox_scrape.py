# INFRASTRUCTURE
import asyncio
import locale
import logging
import plistlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from camoufox import launch_options
from camoufox.async_api import AsyncCamoufox
from camoufox.exceptions import CamoufoxNotInstalled

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from mcp.types import TextContent
# From src/scraper/chromium_scrape.py: same config-hash algorithm used across all scrape paths
from src.scraper.chromium_scrape import hash_config
# From src/scraper/scrape_logger.py: per-URL JSONL log + sidecar content file, shared with chromium_scrape.py
from src.scraper.scrape_logger import log_scrape, write_sidecar

logger = logging.getLogger(__name__)

_PLAYWRIGHT_DEFAULT_TIMEOUT_MS = 30000
_GOTO_WAIT_UNTIL = "domcontentloaded"
CAMOUFOX_RENDER_WAIT_S = 5.0
TOTAL_CAMOUFOX_BUDGET_S = 245.0

_CAMOUFOX_ACQUISITION_ERROR_MESSAGES = {
    "browser_missing": "camoufox browser binary missing — run `./venv/bin/python -m camoufox fetch` to install it",
    "budget_exhausted": f"camoufox acquisition exceeded the total time budget ({TOTAL_CAMOUFOX_BUDGET_S}s)",
}


# ORCHESTRATOR

# Run the Camoufox lane end to end for one URL: acquisition, JSONL logging, sidecar content, rendered facts
async def scrape_url_camoufox_workflow(url: str, block_images: bool = False) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    logger.info("Scraping via camoufox: %s", url)

    content, meta = await try_scrape_camoufox(url, block_images=block_images)
    total_wall = round((time.perf_counter() - t_total) * 1000)

    mode = "raw_html" if meta.get("content_is_raw_html") else "markdown"
    content_path = write_sidecar(url, ts, content, mode, "camoufox")
    log_scrape({
        "ts": ts, "url": url, "domain": domain, "mode": mode,
        "engine": "camoufox",
        "acquisition_error": meta.get("acquisition_error"),
        "timings_ms": {"total_wall": total_wall},
        "http_status": meta.get("status_code"),
        "bytes_returned": len(content.encode("utf-8")) if content else 0,
        "bytes_raw_markdown": meta.get("raw_markdown_bytes", 0),
        "content_path": content_path,
        "landed_url": meta.get("landed_url"),
        "markdown_conversion_error": meta.get("markdown_conversion_error"),
        "content_is_raw_html": meta.get("content_is_raw_html", False),
        "document_status_chain": meta.get("document_status_chain"),
        "config_hash": meta.get("config_hash"), "config": meta.get("config"),
    })
    logger.info("Camoufox scrape complete: %s (%d chars, acquisition_error=%s)",
                url, len(content), meta.get("acquisition_error"))
    return [TextContent(type="text", text=_format_camoufox_output(url, content, meta))]


# FUNCTIONS

# Walk up from a bundle-internal executable path (.../Foo.app/Contents/MacOS/bin) to the .app root
def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


# Set LSUIElement=true on the resolved Camoufox .app bundle so its launch does not steal focus
def _ensure_no_focus_steal(executable_path: str | None) -> None:
    if sys.platform != "darwin" or not executable_path:
        return
    app_path = _find_app_bundle(executable_path)
    if app_path is None:
        return
    plist_path = app_path / "Contents" / "Info.plist"
    try:
        with open(plist_path, "rb") as f:
            data = plistlib.load(f)
        if data.get("LSUIElement") is True:
            return
        data["LSUIElement"] = True
        with open(plist_path, "wb") as f:
            plistlib.dump(data, f)
    except Exception as e:
        logger.warning("Could not set LSUIElement on %s (no-focus-steal not applied): %s", plist_path, e)


# Resolve this machine's own system locale as a BCP-47 tag (e.g. "de-DE"), at runtime, so both
# lanes request the same language Chromium already gets for free from the OS. `defaults read -g
# AppleLocale` reflects the real macOS System Settings language — independent of the shell's own
# LANG env var, which can disagree with it (observed on this machine: LANG=en_US.UTF-8 vs.
# AppleLocale=de_DE, the latter being what an unconfigured Chromium actually renders). Falls back
# to Python's own locale module off-macOS or if that command fails.
def _resolve_system_locale() -> str:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLocale"],
                capture_output=True, text=True, timeout=5, check=True,
            )
            apple_locale = result.stdout.strip()
            if apple_locale:
                return apple_locale.replace("_", "-")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    language_tag, _ = locale.getlocale()
    return language_tag.replace("_", "-") if language_tag else "en-US"


# Build the plain kwargs this module hands to camoufox.launch_options()/AsyncCamoufox — the calibrated core surface
def _build_camoufox_kwargs(block_images: bool) -> dict:
    return {
        "headless": False,
        "os": "macos",
        "locale": _resolve_system_locale(),
        "block_images": block_images,
        "timeout": _PLAYWRIGHT_DEFAULT_TIMEOUT_MS,
        # Playwright's Firefox launcher unconditionally injects "-foreground" whenever headless=False
        # (confirmed by reading the installed playwright driver bundle) — an explicit macOS Cocoa
        # activation call that overrides _ensure_no_focus_steal's LSUIElement plist patch below (that
        # patch only changes the PASSIVE default activation policy; -foreground is an active override
        # of it). ignore_default_args is Playwright's own public mechanism for dropping a specific
        # default-injected arg by exact string match; camoufox.launch_options() passes it straight
        # through to playwright.firefox.launch(). Leaves -wait-for-browser, -profile, and camoufox's
        # own fingerprint/window-size/position args (appended separately, never part of this filtered
        # set) untouched.
        "ignore_default_args": ["-foreground"],
    }


# Read the config stamp back off the REAL resolved launch_options() output plus this module's own input kwargs
def _extract_camoufox_config_stamp(kwargs: dict, resolved: dict) -> dict:
    return {
        **kwargs,
        "executable_path": resolved.get("executable_path"),
        "total_budget_s": TOTAL_CAMOUFOX_BUDGET_S,
    }


# A plain page.on("response") listener (this lane drives Playwright directly, no crawl4ai hook
# system to attach through) collecting the ORDERED chain of main-frame document response statuses —
# same filter and guard as chromium_scrape.py's _make_document_status_listener (M1), duplicated here
# per this project's own precedent of not sharing small lane-specific mechanisms across independent
# lanes: request.resource_type == "document" AND request.frame is page.main_frame (not
# is_navigation_request() alone, which is also true for iframe navigations); request.frame access is
# guarded — it raises for a navigation request issued before its own frame exists (iframes/popups).
def _make_document_status_listener(page, status_chain: list) -> Callable:
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
    return _on_response


# Run one Camoufox launch + goto + capture + markdown conversion, the guarded span inside try_scrape_camoufox's budget
async def _acquire_camoufox(url: str, kwargs: dict, empty_meta: dict) -> tuple[str, dict]:
    resolved = await asyncio.get_event_loop().run_in_executor(
        None, partial(launch_options, **kwargs)
    )
    await asyncio.get_event_loop().run_in_executor(
        None, _ensure_no_focus_steal, resolved.get("executable_path")
    )
    config_stamp = _extract_camoufox_config_stamp(kwargs, resolved)
    meta: dict = {**empty_meta, "config": config_stamp, "config_hash": hash_config(config_stamp)}

    async with AsyncCamoufox(from_options=resolved) as browser:
        page = await browser.new_page()
        # Registered BEFORE page.goto so the goto response itself is the chain's first entry — a
        # same-document JS navigation during the render wait below (e.g. a Cloudflare challenge
        # resolving) fires its own response event here even though the goto Response object never
        # updates. A FACT, not a verdict — nothing here decides "challenge solved"/"blocked".
        document_status_chain: list = []
        page.on("response", _make_document_status_listener(page, document_status_chain))
        response = await page.goto(
            url, timeout=_PLAYWRIGHT_DEFAULT_TIMEOUT_MS, wait_until=_GOTO_WAIT_UNTIL
        )
        await asyncio.sleep(CAMOUFOX_RENDER_WAIT_S)
        landed_url = page.url
        # The LAST main-frame document response is the page whose content was actually captured —
        # overrides the goto Response's own (possibly stale) status. Empty chain (goto itself never
        # fired one, e.g. a navigation error) falls back to the goto Response unchanged.
        if document_status_chain:
            status_code = document_status_chain[-1]
        else:
            status_code = response.status if response else None
        html = await page.content()

    content, content_is_raw_html, raw_markdown, conversion_error = await _convert_camoufox_html(url, html)

    meta.update({
        "status_code": status_code, "landed_url": landed_url,
        "raw_markdown_bytes": len(raw_markdown.encode("utf-8")),
        "markdown_conversion_error": conversion_error,
        "content_is_raw_html": content_is_raw_html,
        "document_status_chain": list(document_status_chain),
    })
    return content, meta


# Convert captured HTML to markdown via _html_to_markdown; fall back to raw HTML on any conversion failure.
async def _convert_camoufox_html(url: str, html: str) -> tuple[str, bool, str, str | None]:
    try:
        raw_markdown, conversion_error = await _html_to_markdown(html)
    except Exception as e:
        raw_markdown, conversion_error = "", str(e)

    if conversion_error:
        logger.warning("Camoufox markdown conversion failed for %s: %s", url, conversion_error)
        content, content_is_raw_html = html, True
    else:
        content, content_is_raw_html = raw_markdown, False

    return content, content_is_raw_html, raw_markdown, conversion_error


# Single-call Camoufox (Playwright-Firefox) acquisition; returns (content, meta) unconditionally, no content judgment
async def try_scrape_camoufox(url: str, block_images: bool = False) -> tuple[str, dict]:
    kwargs = _build_camoufox_kwargs(block_images)
    _empty_meta: dict = {
        "acquisition_error": None, "status_code": None, "landed_url": None,
        "raw_markdown_bytes": 0, "markdown_conversion_error": None, "content_is_raw_html": False,
        "document_status_chain": [],
        "config": {"config_incomplete": True}, "config_hash": None,
    }

    try:
        return await asyncio.wait_for(
            _acquire_camoufox(url, kwargs, _empty_meta), timeout=TOTAL_CAMOUFOX_BUDGET_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Camoufox acquisition budget exhausted (%.1fs): %s", TOTAL_CAMOUFOX_BUDGET_S, url)
        return "", {**_empty_meta, "acquisition_error": "budget_exhausted"}
    except CamoufoxNotInstalled as e:
        logger.error(
            "Camoufox browser binary missing for %s — run "
            "`./venv/bin/python -m camoufox fetch` to install it: %s", url, e,
        )
        return "", {**_empty_meta, "acquisition_error": "browser_missing"}
    except Exception as e:
        logger.warning("Failed to scrape %s via camoufox: %s", url, e)
        return "", {**_empty_meta, "acquisition_error": "exception"}


# HTML -> markdown via crawl4ai's own raw: pipeline, reused exactly as pipe_scraper's own fallback rescue does
async def _html_to_markdown(html: str) -> tuple[str, str | None]:
    browser_config = BrowserConfig(headless=True, verbose=False)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=f"raw:{html}", config=run_config)
    except Exception as e:
        return "", str(e)
    if result.markdown and result.markdown.raw_markdown:
        return result.markdown.raw_markdown, None
    return "", (getattr(result, "error_message", None) or "crawl4ai raw: conversion produced no markdown")


# Render acquisition facts + full content into one fixed-shape text block, a sibling to _format_scrape_output
def _format_camoufox_output(url: str, content: str, meta: dict) -> str:
    lines = [
        f"# Content from: {url}", "",
        "## Acquisition facts",
        "- Engine: camoufox",
        f"- HTTP status: {meta.get('status_code')}",
        f"- Document status chain (ordered main-frame document response statuses observed before "
        f"capture; a fact, not a verdict — never read as challenge-solved/blocked): "
        f"{meta.get('document_status_chain')}",
        f"- Landed URL (the URL the browser actually returned content from): {meta.get('landed_url')}",
        f"- Bytes (raw markdown from crawl4ai's raw: conversion): {meta.get('raw_markdown_bytes', 0)}",
        f"- Bytes (content below): {len(content.encode('utf-8')) if content else 0}",
    ]
    if meta.get("content_is_raw_html"):
        lines.append(
            "- Content format: RAW HTML, NOT markdown — the markdown-conversion step failed "
            "(an OBSERVATION off crawl4ai's own raw: pipeline, not a verdict on this page; the "
            f"page already captured is returned as-is rather than discarded): "
            f"{meta.get('markdown_conversion_error')}"
        )
    if meta.get("acquisition_error"):
        reason = _CAMOUFOX_ACQUISITION_ERROR_MESSAGES.get(meta["acquisition_error"], meta["acquisition_error"])
        lines.append(f"- Acquisition error: {reason}")
    lines += ["", "## Content", "", content if content else "(no content returned)"]
    return "\n".join(lines)
