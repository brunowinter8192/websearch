# INFRASTRUCTURE
import asyncio
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
from src.scraper.chromium_scrape import hash_config
from src.scraper.scrape_logger import log_scrape, write_sidecar

logger = logging.getLogger(__name__)

_PLAYWRIGHT_DEFAULT_TIMEOUT_MS = 30000
_GOTO_WAIT_UNTIL = "domcontentloaded"
CAMOUFOX_RENDER_WAIT_S = 5.0
TOTAL_CAMOUFOX_BUDGET_S = 245.0


# ORCHESTRATOR

async def scrape_url_camoufox_workflow(url: str, block_images: bool = False) -> list[TextContent]:
    t_total = time.perf_counter()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    domain = (urlparse(url).hostname or "").removeprefix("www.")
    logger.info("Scraping via camoufox: %s", url)

    content, meta = await try_scrape_camoufox(url, block_images=block_images)
    total_wall = round((time.perf_counter() - t_total) * 1000)

    content_path = write_sidecar(url, ts, content, "markdown", "camoufox")
    log_scrape({
        "ts": ts, "url": url, "domain": domain, "mode": "markdown",
        "engine": "camoufox",
        "acquisition_error": meta.get("acquisition_error"),
        "timings_ms": {"total_wall": total_wall},
        "http_status": meta.get("status_code"),
        "bytes_returned": len(content.encode("utf-8")) if content else 0,
        "bytes_raw_markdown": meta.get("raw_markdown_bytes", 0),
        "content_path": content_path,
        "landed_url": meta.get("landed_url"),
        "markdown_conversion_error": meta.get("markdown_conversion_error"),
        "document_status_chain": meta.get("document_status_chain"),
        "config_hash": meta.get("config_hash"), "config": meta.get("config"),
    })
    logger.info("Camoufox scrape complete: %s (%d chars, acquisition_error=%s)",
                url, len(content), meta.get("acquisition_error"))
    return [TextContent(type="text", text=_format_camoufox_output(url, content))]


# FUNCTIONS

def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


def _ensure_no_focus_steal(executable_path: str | None) -> None:
    if sys.platform != "darwin" or not executable_path:
        return
    app_path = _find_app_bundle(executable_path)
    if app_path is None:
        return
    plist_path = app_path / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    if data.get("LSUIElement") is True:
        return
    data["LSUIElement"] = True
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f)


def _resolve_system_locale() -> str:
    result = subprocess.run(
        ["defaults", "read", "-g", "AppleLocale"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    apple_locale = result.stdout.strip()
    if not apple_locale:
        raise RuntimeError("defaults read -g AppleLocale returned empty output")
    return apple_locale.replace("_", "-")


def _build_camoufox_kwargs(block_images: bool) -> dict:
    return {
        "headless": False,
        "os": "macos",
        "locale": _resolve_system_locale(),
        "block_images": block_images,
        "timeout": _PLAYWRIGHT_DEFAULT_TIMEOUT_MS,
        "ignore_default_args": ["-foreground"],
    }


def _extract_camoufox_config_stamp(kwargs: dict, resolved: dict) -> dict:
    return {
        **kwargs,
        "executable_path": resolved.get("executable_path"),
        "total_budget_s": TOTAL_CAMOUFOX_BUDGET_S,
    }


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
        document_status_chain: list = []
        page.on("response", _make_document_status_listener(page, document_status_chain))
        response = await page.goto(
            url, timeout=_PLAYWRIGHT_DEFAULT_TIMEOUT_MS, wait_until=_GOTO_WAIT_UNTIL
        )
        await asyncio.sleep(CAMOUFOX_RENDER_WAIT_S)
        landed_url = page.url
        if document_status_chain:
            status_code = document_status_chain[-1]
        else:
            status_code = response.status if response else None
        html = await page.content()

    content, conversion_error = await _html_to_markdown(html)
    if conversion_error:
        logger.warning("Camoufox markdown conversion failed for %s: %s", url, conversion_error)

    meta.update({
        "status_code": status_code, "landed_url": landed_url,
        "raw_markdown_bytes": len(content.encode("utf-8")),
        "markdown_conversion_error": conversion_error,
        "document_status_chain": list(document_status_chain),
    })
    return content, meta


async def try_scrape_camoufox(url: str, block_images: bool = False) -> tuple[str, dict]:
    kwargs = _build_camoufox_kwargs(block_images)
    _empty_meta: dict = {
        "acquisition_error": None, "status_code": None, "landed_url": None,
        "raw_markdown_bytes": 0, "markdown_conversion_error": None,
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


def _format_camoufox_output(url: str, content: str) -> str:
    lines = [f"# Content from: {url}", "", "## Content", "", content if content else "(no content returned)"]
    return "\n".join(lines)
