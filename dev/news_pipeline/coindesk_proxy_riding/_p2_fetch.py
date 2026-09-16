# INFRASTRUCTURE

import hashlib
import sys
import time
import uuid
from pathlib import Path

from crawl4ai import (
    AsyncWebCrawler, CrawlerRunConfig, CacheMode, ProxyConfig,
)
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Regwall signals checked on result.markdown.raw_markdown (browser-rendered visible text).
# NOT on result.html — signals are embedded as hidden React components in all CoinDesk pages.
REGWALL_SIGNALS: list[str] = [
    "from_regwall",
    "Create a FREE account to continue reading",
    "You've reached your monthly limit",
]

DELAY_BEFORE_HTML = 0.5      # s wait after domcontentloaded

# Playwright error substrings that indicate a proxy-side failure (not CoinDesk)
_PROXY_ERR = ("timeout", "proxy", "err_proxy", "tunnel", "socks",
              "err_empty", "connection refused", "connection failed", "net::err")

RAW_SUBDIR = "raw"


# FUNCTIONS

# Fetch one URL via per-context proxy; return (status, char_count, markdown_len, elapsed, html, err).
async def _fetch_one_url(
    crawler:         AsyncWebCrawler,
    url:             str,
    proxy_str:       str,
    page_timeout_ms: int,
) -> tuple[str, int | None, int | None, float, str, str | None]:
    sid     = str(uuid.uuid4())
    run_cfg = CrawlerRunConfig(
        session_id=sid,
        proxy_config=ProxyConfig(server=proxy_str),
        cache_mode=CacheMode.BYPASS,
        page_timeout=page_timeout_ms,
        wait_until="domcontentloaded",
        delay_before_return_html=DELAY_BEFORE_HTML,
        markdown_generator=DefaultMarkdownGenerator(),
        verbose=False,
    )

    t0           = time.perf_counter()
    status       = "failed"
    html         = ""
    err          = None
    markdown_len = None

    try:
        result  = await crawler.arun(url=url, config=run_cfg)
        elapsed = time.perf_counter() - t0
        status, html, err, markdown_len = _classify_fetch_result(result)

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        status  = "connect_fail"
        err     = str(exc)

    finally:
        try:
            await crawler.crawler_strategy.browser_manager.kill_session(sid)
        except Exception as exc:
            print(f"[rider] kill_session warn: {exc}", file=sys.stderr)

    return status, len(html) if html else None, markdown_len, elapsed, html, err


def _classify_fetch_result(result) -> tuple:
    if not result.success:
        emsg   = (result.error_message or "").lower()
        status = "connect_fail" if any(k in emsg for k in _PROXY_ERR) else "failed"
        return status, "", result.error_message, None
    if not result.html:
        return "empty", "", None, None
    raw_md = (result.markdown.raw_markdown or "") if result.markdown else ""
    if _is_regwall(raw_md):
        return "regwall", "", None, None
    return "ok", result.html, None, len(raw_md)


# Return True if markdown contains any REGWALL_SIGNALS.
def _is_regwall(markdown: str) -> bool:
    return any(sig in markdown for sig in REGWALL_SIGNALS)


# Write raw HTML to output_dir/raw/{url_hash}.html; return path.
def _write_raw(url_hash: str, html: str, output_dir: Path) -> Path:
    path = output_dir / RAW_SUBDIR / f"{url_hash}.html"
    path.write_text(html, encoding="utf-8")
    return path


# SHA-256 URL hash (12 hex chars) — matches scrape.py convention.
def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]
