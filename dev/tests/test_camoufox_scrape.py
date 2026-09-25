# INFRASTRUCTURE
import logging

import pytest
from camoufox.exceptions import CamoufoxNotInstalled

from src.scraper import camoufox_scrape
from dev.tests._camoufox_scrape_fakes import (
    _fake_launch_options, _make_fake_camoufox, _RaisingAsyncCamoufox, _HangingAsyncCamoufox,
    _FakeAsyncWebCrawler, _UrlsplitAsyncWebCrawler, _FAKE_MARKDOWN_TEXT,
)


# FUNCTIONS

@pytest.mark.asyncio
async def test_try_scrape_camoufox_normal_fetch(monkeypatch):
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _make_fake_camoufox(landed_url="https://x.test/a", status=200))
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _FakeAsyncWebCrawler)
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
    assert "same_target" not in meta


@pytest.mark.asyncio
async def test_try_scrape_camoufox_budget_exhausted(monkeypatch, caplog):
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
    monkeypatch.setattr(camoufox_scrape, "launch_options", _fake_launch_options)
    monkeypatch.setattr(camoufox_scrape, "AsyncCamoufox",
                         _RaisingAsyncCamoufox(RuntimeError("simulated browser crash")))

    content, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert content == ""
    assert meta["acquisition_error"] == "exception"
    assert meta["landed_url"] is None
    assert meta["status_code"] is None


@pytest.mark.asyncio
async def test_html_to_markdown_survives_bracket_before_first_slash(monkeypatch):
    monkeypatch.setattr(camoufox_scrape, "AsyncWebCrawler", _UrlsplitAsyncWebCrawler)
    html = "<html><head><script>var a = [1,2,3];</script></head><body>content</body></html>"

    content, error = await camoufox_scrape._html_to_markdown(html)

    assert error is None
    assert content == _FAKE_MARKDOWN_TEXT


@pytest.mark.asyncio
async def test_try_scrape_camoufox_conversion_failure_yields_empty_content(monkeypatch):
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


@pytest.mark.asyncio
async def test_acquire_camoufox_last_document_response_overrides_goto_status(monkeypatch):
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
    def _raise(**kwargs):
        raise CamoufoxNotInstalled(
            "official/stable is not installed. Please run `camoufox fetch` to install.")
    monkeypatch.setattr(camoufox_scrape, "launch_options", _raise)

    _, meta = await camoufox_scrape.try_scrape_camoufox("https://x.test/a")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["document_status_chain"] == []
