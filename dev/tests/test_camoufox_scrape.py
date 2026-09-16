"""Tests for camoufox_scrape's calibrated core acquisition module — the second, parallel
acquisition lane (Camoufox/Playwright-Firefox) beside crawl4ai's chromium path. No CLI/logging
wiring exists yet (later milestones); this only tests the module boundary itself.

Runs without a real Camoufox browser: camoufox_scrape.AsyncCamoufox and camoufox_scrape.launch_options
are patched with fakes, isolating the module from the real binary/network. camoufox_scrape.AsyncWebCrawler
(the separate throwaway crawler used for raw: markdown conversion) is patched the same way
test_pipe_scraper.py fakes crawl4ai's own AsyncWebCrawler.
"""
import logging

import pytest
from camoufox.exceptions import CamoufoxNotInstalled

from src.scraper import camoufox_scrape
from dev.tests._camoufox_scrape_fakes import (
    _fake_launch_options, _make_fake_camoufox, _RaisingAsyncCamoufox, _HangingAsyncCamoufox,
    _FakeAsyncWebCrawler, _UrlsplitAsyncWebCrawler, _FAKE_MARKDOWN_TEXT,
)


# ---------------------------------------------------------------------------
# Normal fetch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_normal_fetch(monkeypatch):
    """A clean fetch: content, status, landed_url, raw_markdown_bytes, config/config_hash all
    populated; acquisition_error stays None."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    # asyncio.sleep(CAMOUFOX_RENDER_WAIT_S) is a real stdlib sleep, not interceptable by the fakes
    # above — zeroed so this test doesn't actually wait 5s.
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == _FAKE_MARKDOWN_TEXT
    assert meta["acquisition_error"] is None
    assert meta["status_code"] == 200
    assert meta["landed_url"] == "https://x.test/a"
    assert meta["raw_markdown_bytes"] == len(_FAKE_MARKDOWN_TEXT.encode("utf-8"))
    assert meta["config"]["executable_path"] == "/fake/camoufox/firefox-bin"
    assert meta["config_hash"] is not None


@pytest.mark.asyncio
async def test_try_scrape_camoufox_captures_landed_url_raw_on_redirect(monkeypatch):
    """landed_url reflects wherever the browser actually ended up — raw, no comparison, no
    verdict, even when it differs from the requested URL (host-change redirect shape)."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://platform.claude.com/docs/en/api/overview", status=301),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    content, meta = await camoufox_scrape.try_scrape_camoufox(
        "https://docs.anthropic.com/en/api/getting-started")

    assert meta["status_code"] == 301
    assert meta["landed_url"] == "https://platform.claude.com/docs/en/api/overview"
    # No verdict field of any kind — this module reports facts only
    assert "same_target" not in meta


# ---------------------------------------------------------------------------
# acquisition_error states
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_budget_exhausted(monkeypatch, caplog):
    """A hang inside the acquisition (Camoufox never returns) is cut off at
    TOTAL_CAMOUFOX_BUDGET_S, yielding acquisition_error=budget_exhausted — not a hang."""
    monkeypatch.setattr(camoufox_scrape, "TOTAL_CAMOUFOX_BUDGET_S", 0.05)
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox", _HangingAsyncCamoufox())

    with caplog.at_level(logging.WARNING, logger="src.scraper.camoufox_scrape"):
        content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "budget_exhausted"
    assert any("budget exhausted" in m.lower() for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_camoufox_detects_binary_missing(monkeypatch, caplog):
    """CamoufoxNotInstalled (raised from launch_options -> launch_path when the browser binary
    hasn't been fetched) maps to acquisition_error=browser_missing, with the fix command named in
    the logged message."""
    def _raise(**kwargs):
        raise CamoufoxNotInstalled(
            "official/stable is not installed. Please run `camoufox fetch` to install.")
    monkeypatch.setattr(camoufox_scrape, "launch_options", _raise)

    with caplog.at_level(logging.ERROR, logger="src.scraper.camoufox_scrape"):
        content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "browser_missing"
    assert any("camoufox fetch" in m for m in caplog.messages)


@pytest.mark.asyncio
async def test_try_scrape_camoufox_exception_fail_soft(monkeypatch):
    """A non-launch-missing exception (e.g. a real browser-launch crash) degrades to
    acquisition_error=exception — never propagates to the caller."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _RaisingAsyncCamoufox(RuntimeError("simulated browser crash")))

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "exception"
    assert meta["landed_url"] is None
    assert meta["status_code"] is None


# ---------------------------------------------------------------------------
# Regression: HTML with a bare "[" before the first "/" (e.g. an early inline <script> JS array
# literal, extremely common) used to make crawl4ai's own urlsplit() raise "Invalid IPv6 URL" on a
# raw://<html> pseudo-URL. _html_to_markdown uses "raw:" instead, which carries no netloc and is
# not subject to that parsing at all.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_html_to_markdown_survives_bracket_before_first_slash(monkeypatch):
    """Real trigger shape (idealo.de): an inline <script> with a JS array literal puts "[" before
    the document's first "/". _html_to_markdown must produce a pseudo-URL that survives crawl4ai's
    own urlsplit() call unchanged, converting real content instead of failing."""
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _UrlsplitAsyncWebCrawler)
    html = "<html><head><script>var a = [1,2,3];</script></head><body>content</body></html>"

    content, error = await camoufox_scrape._html_to_markdown(html)

    assert error is None
    assert content == _FAKE_MARKDOWN_TEXT


# ---------------------------------------------------------------------------
# Markdown-conversion failure: acquisition SUCCEEDED (real HTML captured) but crawl4ai's raw:
# pipeline failed. REMOVED 2026-09-09: the raw-HTML-as-content fallback (returning the captured
# HTML as content when conversion failed) — no supporting observation (the only real trigger was
# the raw:// urlsplit bug, fixed 2026-08-07 by the switch to "raw:"; 112 production records since,
# zero with the old content_is_raw_html=True). Conversion failure now surfaces as empty content
# plus markdown_conversion_error, and acquisition_error MUST stay None — acquisition itself
# produced a real result, this is a downstream conversion failure.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_camoufox_conversion_failure_yields_empty_content(monkeypatch):
    """On a markdown-conversion failure, content is now "" (never the raw captured HTML) and
    markdown_conversion_error carries the fact; acquisition_error stays None; content_is_raw_html
    no longer exists in meta at all."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=200,
                             html="<html><body>real captured page</body></html>"),
    )
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    async def _fake_html_to_markdown(html):
        return "", "simulated conversion failure"
    monkeypatch.setattr(camoufox_scrape, "_html_to_markdown", _fake_html_to_markdown)

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["markdown_conversion_error"] == "simulated conversion failure"
    assert meta["acquisition_error"] is None
    assert "content_is_raw_html" not in meta


# ---------------------------------------------------------------------------
# document_status_chain — _make_document_status_listener (registered on the page BEFORE page.goto)
# collects the ordered chain of main-frame document response statuses; the LAST entry overrides
# status_code (the page whose content was actually captured), and an empty chain falls back to the
# goto Response's own status unchanged. Same contract as chromium_scrape.py's M1 fix, driven
# directly through plain Playwright rather than a crawl4ai hook.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_camoufox_last_document_response_overrides_goto_status(monkeypatch):
    """403 -> 302 -> 200 chain (self-resolving challenge shape): status_code becomes the LAST
    response's status (200), the chain is recorded in full, and the goto Response's own (stale) 403
    is overridden — the page whose content was actually captured is the 200 one."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=403,
                             document_statuses=[403, 302, 200]),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [403, 302, 200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_camoufox_single_response_chain(monkeypatch):
    """An ordinary page with no challenge/redirect: one main-frame document response, chain has
    exactly one entry, status_code equals today's (unchanged) behavior."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_camoufox_falls_back_to_goto_status_when_listener_saw_nothing(monkeypatch):
    """The listener sees no main-frame document response at all — chain stays empty, status_code
    falls back to the goto Response's own status, never invented."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(landed_url="https://x.test/a", status=403, document_statuses=[]),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == []
    assert meta["status_code"] == 403


@pytest.mark.asyncio
async def test_acquire_camoufox_ignores_non_document_and_non_main_frame_responses(monkeypatch):
    """A stylesheet response and a document response on a DIFFERENT frame (e.g. an iframe) must not
    enter the chain — only main-frame document responses count."""
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(
        camoufox_scrape, "AsyncCamoufox",
        _make_fake_camoufox(
            landed_url="https://x.test/a", status=200,
            document_statuses=[(999, "stylesheet", None), (500, "document", object()), 200],
        ),
    )
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
    monkeypatch.setattr(camoufox_scrape, "CAMOUFOX_RENDER_WAIT_S", 0)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["document_status_chain"] == [200]


@pytest.mark.asyncio
async def test_try_scrape_camoufox_document_status_chain_empty_on_launch_failure(monkeypatch):
    """A path that never obtains a page/response (browser_missing) carries an empty chain, same
    treatment as every other acquisition-error field."""
    def _raise(**kwargs):
        raise CamoufoxNotInstalled(
            "official/stable is not installed. Please run `camoufox fetch` to install.")
    monkeypatch.setattr(camoufox_scrape, "launch_options", _raise)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["document_status_chain"] == []
