"""Tests for chromium_scrape's acquisition-facts contract: browser-launch/timeout classification, the
outer time-budget guard, the removed status-code/content-verdict gate, the new return shape that
surfaces facts (HTTP status, byte counts, crawl4ai's own diagnosis) alongside full content instead
of judging it, and the single cdp-headed-backgrounded acquisition route (self-launch + connect over
cdp_url) — the WEBSEARCH_HEADLESS escape hatch (old direct headless-shell launch) was removed.

Runs without a browser: try_scrape's AsyncWebCrawler is patched to raise a synthetic exception,
simulating a missing patchright/chromium executable, to hang past a (monkeypatched, shortened)
budget constant, or to return a synthetic result carrying an HTTP error status + real content.
Tests additionally patch the self-launch/port-wait/teardown mechanics
(`_patch_cdp_launch_mechanics`) so no real browser is spawned — those functions get their own
dedicated, unmocked tests further down.
"""
import asyncio
import logging

import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeMarkdown, _FakeResult, _meta


# ---------------------------------------------------------------------------
# is_browser_launch_error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("msg", [
    "BrowserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1208/chrome-linux/chrome",
    "Please run the following command to download new browsers:\n    playwright install",
    "Failed to launch chromium via BrowserType.launch",
    "DevToolsActivePort did not appear under /tmp/scrape-url-cdp-abc123 within 10.0s",
])
def test_is_browser_launch_error_detects_signatures(msg):
    """Known launch-failure signatures (both the old direct-launch and the new cdp self-launch's
    own timeout) are classified as browser_missing."""
    assert chromium_scrape.is_browser_launch_error(Exception(msg)) is True


@pytest.mark.parametrize("msg", [
    "Timeout 60000ms exceeded while waiting for load",
    "net::ERR_NAME_NOT_RESOLVED at https://nonexistent-domain-xyz.test",
    "Page.goto: net::ERR_CONNECTION_REFUSED",
    "",
])
def test_is_browser_launch_error_ignores_ordinary_errors(msg):
    """Ordinary per-URL network/timeout errors are NOT misclassified as browser problems."""
    assert chromium_scrape.is_browser_launch_error(Exception(msg)) is False


# ---------------------------------------------------------------------------
# try_scrape routes acquisition-level failures to meta["acquisition_error"]
# (renamed from garbage_type — these three states mean "acquisition produced no result at all",
# never a content-judgment verdict; that layer is removed). All exercise the DEFAULT cdp path
# unless noted, via _patch_cdp_launch_mechanics.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_maps_launch_failure_to_browser_missing(monkeypatch, caplog):
    """A browser-launch exception from AsyncWebCrawler yields acquisition_error=browser_missing at ERROR level."""
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
    """A non-launch exception (e.g. timeout) is classified as acquisition_error="exception" —
    named rather than silently collapsed into the same state as a real empty page."""
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


# ---------------------------------------------------------------------------
# The removed status-code gate: a real evidence case — an HTTP error status with real content
# must now come back AS content, not be discarded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_returns_content_on_http_403(monkeypatch):
    """trustpilot-shaped case: HTTP 403 with real content must be returned, not discarded — the
    old status>=400 early return is gone."""
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
    # crawl4ai's diagnosis is recorded, not acted on — content came through despite it
    assert meta["crawl4ai_error_message"] == "Blocked by anti-bot protection: Cloudflare JS challenge"



# ---------------------------------------------------------------------------
# content_type — M0 milestone (2026-09-15): read off result.response_headers, not the
# nonexistent result.headers attribute (hasattr(result, "headers") was False on every real
# CrawlResult, so this branch never once executed — a defect, not a structural gap; see
# process-docs/scrape_pipeline/ for the crawl4ai-source verification).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_extracts_content_type_from_response_headers(monkeypatch):
    """A real result carrying response_headers (the actual CrawlResult field) yields a real
    content_type — the fix this milestone makes."""
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
    """No response_headers at all (the _FakeResult default) still degrades to None gracefully —
    same neutral outcome as before this milestone, for the same reason (no headers present), not
    a new one."""
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


# ---------------------------------------------------------------------------
# crawl4ai_fallback_fetch_used — M0 milestone (2026-09-15): removed from the ad-hoc lane's own
# logged record. Structurally always False on this project's configuration (no
# fallback_fetch_function is ever set), confirmed against the installed crawl4ai source — see
# process-docs/scrape_pipeline/. extract_crawl4ai_diagnosis itself is UNCHANGED (still computes
# this key) since src/crawler/pipe_scraper_records.py reads the identical shared function's
# output for the batch lane's own log — only this lane's final log_scrape(...) dict stopped
# surfacing it.
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# og_published_time — read off crawl4ai's own already-parsed result.metadata (an og:-prefixed meta
# tag the page itself declares), never a third-party guess. Absent whenever the page declares
# nothing, exactly like every other fact in this module.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_reads_og_published_time_from_result_metadata(monkeypatch):
    """The page's OWN og:published_time meta tag, verbatim — crawl4ai already parses every
    og:-prefixed <head> tag into result.metadata (extract_metadata_using_lxml), so this is a real
    fact carried on the result this module already has in hand, not a new fetch or a guess."""
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
    """A page with real OpenGraph metadata but no published_time tag — null, not a guessed
    fallback (e.g. never derived from a last-modified footer or any other page text)."""
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
    """A result with no .metadata attribute at all must degrade to None, never raise."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="x" * 300)  # no .metadata set

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["og_published_time"] is None
