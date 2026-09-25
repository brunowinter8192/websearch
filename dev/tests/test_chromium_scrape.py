# INFRASTRUCTURE
import asyncio
import logging

import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeMarkdown, _FakeResult, _meta


# FUNCTIONS

@pytest.mark.parametrize("msg", [
    "BrowserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1208/chrome-linux/chrome",
    "Please run the following command to download new browsers:\n    playwright install",
    "Failed to launch chromium via BrowserType.launch",
    "DevToolsActivePort did not appear under /tmp/scrape-url-cdp-abc123 within 10.0s",
])
def test_is_browser_launch_error_detects_signatures(msg):
    assert chromium_scrape.is_browser_launch_error(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "Timeout 60000ms exceeded while waiting for load",
    "net::ERR_NAME_NOT_RESOLVED at https://nonexistent-domain-xyz.test",
    "Page.goto: net::ERR_CONNECTION_REFUSED",
    "",
])
def test_is_browser_launch_error_ignores_ordinary_errors(msg):
    assert chromium_scrape.is_browser_launch_error(Exception(msg)) is False


@pytest.mark.asyncio
async def test_try_scrape_maps_launch_failure_to_browser_missing(monkeypatch, caplog):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("BrowserType.launch: Executable doesn't exist at /fake/chrome")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    with caplog.at_level(logging.ERROR, logger="src.scraper.chromium_scrape"):
        content, meta = await chromium_scrape.try_scrape("https://example.com")

    assert content == ""
    assert meta["acquisition_error"] == "browser_missing"
    assert any("Browser binary missing" in m or "launch" in m.lower() for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_names_the_generic_exception_state(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("Timeout 60000ms exceeded while waiting for load")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    content, meta = await chromium_scrape.try_scrape("https://example.com")

    assert content == ""
    assert meta["acquisition_error"] == "exception"


@pytest.mark.asyncio
async def test_try_scrape_returns_content_on_http_403(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="# Real review content, returned as fit_markdown "
                                             "unconditionally — no fit/raw selection exists anymore.",
                                status_code=403,
                                error_message="Blocked by anti-bot protection: Cloudflare JS challenge")

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    content, meta = await chromium_scrape.try_scrape("https://de.trustpilot.com/review/entega.de")

    assert content.startswith("# Real review content")
    assert meta["status_code"] == 403
    assert meta["acquisition_error"] is None
    assert meta["crawl4ai_error_message"] == "Blocked by anti-bot protection: Cloudflare JS challenge"


@pytest.mark.asyncio
async def test_try_scrape_extracts_content_type_from_response_headers(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="x" * 300,
                                response_headers={"content-type": "text/html; charset=utf-8"})

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["content_type"] == "text/html; charset=utf-8"


@pytest.mark.asyncio
async def test_try_scrape_content_type_none_when_response_headers_empty(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="x" * 300)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["content_type"] is None


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_log_record_has_no_fallback_fetch_used_field(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta()

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert "crawl4ai_fallback_fetch_used" not in captured


@pytest.mark.asyncio
async def test_try_scrape_reads_og_published_time_from_result_metadata(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            result = _FakeResult(raw_markdown="x" * 300)
            result.metadata = {"og:title": "Example", "og:published_time": "2024-03-01T12:00:00+00:00"}
            return result

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["og_published_time"] == "2024-03-01T12:00:00+00:00"


@pytest.mark.asyncio
async def test_try_scrape_og_published_time_null_when_page_declares_none(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            result = _FakeResult(raw_markdown="x" * 300)
            result.metadata = {"og:title": "Example"}
            return result

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["og_published_time"] is None


@pytest.mark.asyncio
async def test_try_scrape_og_published_time_null_when_result_has_no_metadata_attribute(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="x" * 300)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["og_published_time"] is None
