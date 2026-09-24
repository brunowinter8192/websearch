import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeResult, _meta


def _real_stamp_args():
    browser_config = chromium_scrape.BrowserConfig(headless=True, verbose=False, enable_stealth=True)
    adapter = chromium_scrape.UndetectedAdapter()
    crawler_strategy = chromium_scrape.AsyncPlaywrightCrawlerStrategy(
        browser_config=browser_config, browser_adapter=adapter
    )
    run_config = chromium_scrape.CrawlerRunConfig(
        markdown_generator=chromium_scrape.DefaultMarkdownGenerator(
            content_filter=chromium_scrape.PruningContentFilter(threshold=0.48, preserve_tags=["pre", "code"])
        ),
    )
    return browser_config, adapter, crawler_strategy, run_config


def test_extract_config_stamp_carries_total_budget_s():
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert stamp["total_budget_s"] == chromium_scrape.TOTAL_SCRAPE_BUDGET_S


def test_extract_config_stamp_carries_launch_mode_not_headless():
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert stamp["launch_mode"] == chromium_scrape.LAUNCH_MODE
    assert "headless" not in stamp


def test_extract_config_stamp_no_longer_carries_max_content_length():
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "max_content_length" not in stamp
    assert not hasattr(chromium_scrape, "build_config_record")


def test_extract_config_stamp_no_longer_carries_min_content_threshold():
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "min_content_threshold" not in stamp
    assert not hasattr(chromium_scrape, "MIN_CONTENT_THRESHOLD")


def test_htmldate_removed_entirely():
    assert not hasattr(chromium_scrape, "extract_date")
    assert not hasattr(chromium_scrape, "HTMLDATE_TIMEOUT_S")
    assert not hasattr(chromium_scrape, "find_date")


def test_extract_config_stamp_no_longer_carries_excluded_selector_hash():
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "excluded_selector_hash" not in stamp
    assert not hasattr(chromium_scrape, "COOKIE_CONSENT_SELECTOR")


def test_format_scrape_output_never_replaces_content_with_a_message():
    real_content = "SPECIFIC_MARKER_TEXT_12345 that must appear byte-for-byte in the output"
    text = chromium_scrape._format_scrape_output("https://x.test", real_content)
    assert real_content in text


def test_format_scrape_output_zero_content_is_explicit_not_suppressed():
    text = chromium_scrape._format_scrape_output("https://x.test", "")
    assert "(no content returned)" in text
    assert "Error scraping" not in text


def test_format_scrape_output_carries_no_acquisition_facts_preamble():
    text = chromium_scrape._format_scrape_output("https://x.test", "the real page content")
    assert "Acquisition facts" not in text
    assert "the real page content" in text


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_full_field_set_unchanged(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta()

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    expected_fields = {
        "ts", "url", "domain", "mode", "engine", "acquisition_error", "timings_ms",
        "http_status", "content_type", "bytes_returned", "bytes_raw_markdown",
        "content_path", "og_published_time", "landed_url", "crawl4ai_success",
        "crawl4ai_error_message", "crawl4ai_attempts", "crawl4ai_resolved_by",
        "document_status_chain", "config_hash", "config",
    }
    assert expected_fields <= captured.keys()


@pytest.mark.asyncio
async def test_launch_mode_truthful_on_cdp_path(monkeypatch):
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
    assert meta["config"]["launch_mode"] == chromium_scrape.LAUNCH_MODE
    assert meta["config"]["total_budget_s"] == chromium_scrape.TOTAL_SCRAPE_BUDGET_S
