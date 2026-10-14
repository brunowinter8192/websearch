# INFRASTRUCTURE
from pathlib import Path

import pytest

from src.scraper import chromium_process, chromium_scrape
from src.scraper.chromium_scrape import (
    CONTENT_SOURCE_FIT,
    CONTENT_SOURCE_RAW_FALLBACK,
    select_content,
)
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeResult, _meta

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "scrape"
BGN_RAW = (FIXTURE_DIR / "bgn_a35_raw_markdown.md").read_text(encoding="utf-8")
DBIS_RAW_HEAD = (FIXTURE_DIR / "dbis_resources_raw_markdown_head.md").read_text(encoding="utf-8")


# FUNCTIONS

def test_whitespace_only_fit_falls_back_to_the_real_bgn_raw_markdown():
    content, source = select_content("\n", BGN_RAW)

    assert content == BGN_RAW
    assert source == CONTENT_SOURCE_RAW_FALLBACK
    assert "Sterilisationsvorrichtungen" in content


def test_whitespace_only_fit_falls_back_to_the_dbis_raw_markdown_too():
    content, source = select_content("\n", DBIS_RAW_HEAD)

    assert content == DBIS_RAW_HEAD
    assert source == CONTENT_SOURCE_RAW_FALLBACK


def test_fit_with_text_is_kept_even_when_raw_is_much_larger():
    content, source = select_content("short fit", "x" * 2537)

    assert content == "short fit"
    assert source == CONTENT_SOURCE_FIT


def test_fit_and_raw_without_text_keep_fit_and_swap_nothing():
    content, source = select_content("\n", "\n")

    assert content == "\n"
    assert source == CONTENT_SOURCE_FIT


def test_missing_fit_falls_back_to_raw_with_text():
    content, source = select_content(None, "real text")

    assert content == "real text"
    assert source == CONTENT_SOURCE_RAW_FALLBACK


@pytest.mark.asyncio
async def test_try_scrape_returns_raw_and_marks_the_source_when_the_filter_empties_the_page(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            result = _FakeResult(raw_markdown=BGN_RAW)
            result.markdown.fit_markdown = "\n"
            return result

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    content, meta = await chromium_scrape.try_scrape("https://vorschriften.bgn-branchenwissen.de/daten/gv/eg_2004_853/a35.htm")

    assert content == BGN_RAW
    assert meta["content_source"] == CONTENT_SOURCE_RAW_FALLBACK
    assert meta["raw_markdown_bytes"] == len(BGN_RAW.encode("utf-8"))


@pytest.mark.asyncio
async def test_workflow_logs_the_content_source_and_returns_the_fallback_content(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return BGN_RAW, _meta(raw_markdown_bytes=len(BGN_RAW.encode("utf-8")), content_source=CONTENT_SOURCE_RAW_FALLBACK)

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    [output] = await chromium_scrape.scrape_url_chromium_workflow("https://vorschriften.bgn-branchenwissen.de/daten/gv/eg_2004_853/a35.htm")

    assert captured["content_source"] == CONTENT_SOURCE_RAW_FALLBACK
    assert captured["bytes_returned"] == captured["bytes_raw_markdown"] == len(BGN_RAW.encode("utf-8"))
    assert "Sterilisationsvorrichtungen" in output.text


@pytest.mark.asyncio
async def test_workflow_logs_no_content_source_when_acquisition_produced_no_markdown(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "", _meta(acquisition_error="exception", content_source=None)

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert captured["content_source"] is None
