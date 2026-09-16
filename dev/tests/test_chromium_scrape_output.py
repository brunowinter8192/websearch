import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeResult, _meta


# ---------------------------------------------------------------------------
# extract_config_stamp — launch_mode is a fixed constant (LAUNCH_MODE) now that the
# WEBSEARCH_HEADLESS escape hatch is gone; replaces the dead-on-the-cdp-path browser_config.headless
# field. total_budget_s stays an explicit param (read off the real constant, never re-declared).
# ---------------------------------------------------------------------------

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
    """The config stamp reads total_budget_s off the value passed in, not a re-declared literal."""
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert stamp["total_budget_s"] == chromium_scrape.TOTAL_SCRAPE_BUDGET_S


def test_extract_config_stamp_carries_launch_mode_not_headless():
    """launch_mode is the truthful posture discriminator (LAUNCH_MODE, a fixed constant now that
    only one acquisition path exists); the old "headless" boolean field is gone entirely (it was
    dead on the cdp path — never read inside crawl4ai's cdp_url branch)."""
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert stamp["launch_mode"] == chromium_scrape.LAUNCH_MODE
    assert "headless" not in stamp


def test_extract_config_stamp_no_longer_carries_max_content_length():
    """max_content_length is gone (the parameter it described no longer exists) — build_config_record
    removed, its only job was merging it in."""
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "max_content_length" not in stamp
    assert not hasattr(chromium_scrape, "build_config_record")


def test_extract_config_stamp_no_longer_carries_min_content_threshold():
    """The fit->raw fallback mechanism (MIN_CONTENT_THRESHOLD) was removed entirely as of
    2026-08-22 — content is always fit_markdown; the stamp no longer carries a field for a
    selection mechanism that no longer exists."""
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "min_content_threshold" not in stamp
    assert not hasattr(chromium_scrape, "MIN_CONTENT_THRESHOLD")


def test_htmldate_removed_entirely():
    """The guessed-date mechanism (htmldate, extract_date, HTMLDATE_TIMEOUT_S) is gone, not just
    unused — the declared date now comes from crawl4ai's own already-parsed result.metadata,
    at zero extra acquisition time."""
    assert not hasattr(chromium_scrape, "extract_date")
    assert not hasattr(chromium_scrape, "HTMLDATE_TIMEOUT_S")
    assert not hasattr(chromium_scrape, "find_date")


def test_extract_config_stamp_no_longer_carries_excluded_selector_hash():
    """The hand-maintained COOKIE_CONSENT_SELECTOR list was removed — crawl4ai's own
    remove_consent_popups=True (a vendor-maintained clicker, verified a strict superset) carries
    consent handling alone now. The stamp no longer hashes an excluded_selector that no longer
    exists."""
    args = _real_stamp_args()
    stamp = chromium_scrape.extract_config_stamp(*args, chromium_scrape.TOTAL_SCRAPE_BUDGET_S)
    assert "excluded_selector_hash" not in stamp
    assert not hasattr(chromium_scrape, "COOKIE_CONSENT_SELECTOR")


# ---------------------------------------------------------------------------
# _format_scrape_output: facts always precede content, crawl4ai's diagnosis reads as an
# observation not a verdict, zero content is explicit and never a substituted message
# ---------------------------------------------------------------------------

def test_format_scrape_output_never_replaces_content_with_a_message():
    """Content appears verbatim in the output — not summarized, not replaced."""
    real_content = "SPECIFIC_MARKER_TEXT_12345 that must appear byte-for-byte in the output"
    text = chromium_scrape._format_scrape_output("https://x.test", real_content)
    assert real_content in text


def test_format_scrape_output_zero_content_is_explicit_not_suppressed():
    """Zero content renders as an explicit fact, not a discard message standing in for the page."""
    text = chromium_scrape._format_scrape_output("https://x.test", "")
    assert "(no content returned)" in text
    assert "Error scraping" not in text  # the old discard-message phrasing must not reappear


# ---------------------------------------------------------------------------
# M2 milestone (2026-09-15): the printed acquisition-facts block is removed entirely — the facts
# still exist, they just stop being printed. Output shrinks; the log record does not.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# launch_mode is a fixed LAUNCH_MODE constant now that try_scrape unconditionally runs the
# cdp-headed path — the WEBSEARCH_HEADLESS escape hatch and its dispatch are gone.
# ---------------------------------------------------------------------------

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
