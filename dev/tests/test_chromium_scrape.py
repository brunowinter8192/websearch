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
import time

import pytest

from src.crawler import garbage_filter
from src.scraper import chromium_process, chromium_scrape


# ---------------------------------------------------------------------------
# Shared test helper: bypass the real self-launch/port-wait/teardown mechanics so the default cdp
# path can be exercised (AsyncWebCrawler mocked separately, per test) without spawning a real
# browser — mirrors how AsyncWebCrawler itself is already mocked throughout this file.
# ---------------------------------------------------------------------------

def _patch_cdp_launch_mechanics(monkeypatch):
    async def _fake_resolve_bundle():
        return chromium_process.Path("/fake/chromium-1228/Google Chrome for Testing.app")

    monkeypatch.setattr(chromium_scrape, "_resolve_chromium_bundle_path", _fake_resolve_bundle)
    monkeypatch.setattr(chromium_scrape, "_self_launch_chrome", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "_wait_for_devtools_port", lambda *a, **kw: 9999)
    monkeypatch.setattr(chromium_scrape, "_kill_by_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "_pids_on_profile", lambda *a, **kw: [])
    monkeypatch.setattr(chromium_scrape, "_reap_orphaned_scrapes", lambda: None)
    monkeypatch.setattr(chromium_scrape.death_pipe, "spawn_watchdog", lambda *a, **kw: None)


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
    _patch_cdp_launch_mechanics(monkeypatch)

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
    _patch_cdp_launch_mechanics(monkeypatch)

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

class _FakeMarkdown:
    def __init__(self, raw_markdown, fit_markdown=None):
        self.raw_markdown = raw_markdown
        self.fit_markdown = fit_markdown if fit_markdown is not None else raw_markdown


class _FakeResult:
    def __init__(self, raw_markdown, status_code=200, success=True, error_message=None, html="",
                 redirected_url=None):
        self.markdown = _FakeMarkdown(raw_markdown)
        self.status_code = status_code
        self.success = success
        self.error_message = error_message
        self.html = html
        self.headers = {}
        self.crawl_stats = {"attempts": 1, "resolved_by": "direct", "fallback_fetch_used": False}
        self.redirected_url = redirected_url


@pytest.mark.asyncio
async def test_try_scrape_returns_content_on_http_403(monkeypatch):
    """trustpilot-shaped case: HTTP 403 with real content must be returned, not discarded — the
    old status>=400 early return is gone."""
    _patch_cdp_launch_mechanics(monkeypatch)

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
# og_published_time — read off crawl4ai's own already-parsed result.metadata (an og:-prefixed meta
# tag the page itself declares), never a third-party guess. Absent whenever the page declares
# nothing, exactly like every other fact in this module.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_reads_og_published_time_from_result_metadata(monkeypatch):
    """The page's OWN og:published_time meta tag, verbatim — crawl4ai already parses every
    og:-prefixed <head> tag into result.metadata (extract_metadata_using_lxml), so this is a real
    fact carried on the result this module already has in hand, not a new fetch or a guess."""
    _patch_cdp_launch_mechanics(monkeypatch)

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
    _patch_cdp_launch_mechanics(monkeypatch)

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
    _patch_cdp_launch_mechanics(monkeypatch)

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


# ---------------------------------------------------------------------------
# The fit->raw fallback (MIN_CONTENT_THRESHOLD) is gone as of 2026-08-22 — content is ALWAYS
# fit_markdown, even when short and raw_markdown is longer. An operational-log analysis (69
# production chromium scrapes) found the fallback fired exactly once, on a degenerate page where
# both fit and raw were ~1 byte; the one near-threshold case did not fire and its raw excess was
# category-page link-chrome — exactly what the filter exists to remove.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_returns_short_fit_markdown_unconditionally(monkeypatch):
    """A short fit_markdown (well under the old 200-char threshold) with a much longer raw_markdown
    available is returned AS the short fit_markdown — no fallback to raw fires, because the
    mechanism no longer exists at all."""
    _patch_cdp_launch_mechanics(monkeypatch)
    fake_short_fit = "short fit"

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            result = _FakeResult(raw_markdown="x" * 2537)
            result.markdown.fit_markdown = fake_short_fit
            return result

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    content, meta = await chromium_scrape.try_scrape("https://example.com")

    assert content == fake_short_fit
    assert meta["raw_markdown_bytes"] == 2537


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_log_record_has_no_fallback_to_raw_field(monkeypatch):
    """The removed field must not reappear in the JSONL record — fallback_to_raw described a
    mechanism that no longer exists."""
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta()

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert "fallback_to_raw" not in captured
    assert captured["bytes_raw_markdown"] == 100  # raw_markdown_bytes still reported, as a fact


def test_format_scrape_output_has_no_raw_fallback_note():
    """The " + raw fallback" selection note is gone from the content-bytes line — there is no
    selection to note anymore, content is always the filtered fit_markdown."""
    text = chromium_scrape._format_scrape_output("https://x.test", "some content", _meta(), None)
    assert "raw fallback" not in text
    assert "Bytes (content below, after PruningContentFilter):" in text


# ---------------------------------------------------------------------------
# try_scrape captures meta["landed_url"] RAW from result.redirected_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_captures_landed_url_raw(monkeypatch):
    """meta["landed_url"] is result.redirected_url verbatim — no normalization, no verdict."""
    _patch_cdp_launch_mechanics(monkeypatch)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(
                raw_markdown="idealo-shaped: same numeric ID, rewritten slug, real content here.",
                redirected_url="https://www.idealo.de/preisvergleich/OffersOfProduct/"
                               "203078159_-woman-hybrid-jacket-fix-hood-33z6026-cmp-campagnolo.html",
            )

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape(
        "https://www.idealo.de/preisvergleich/OffersOfProduct/203078159_-fritz-box-7510-avm.html")

    assert meta["landed_url"] == (
        "https://www.idealo.de/preisvergleich/OffersOfProduct/"
        "203078159_-woman-hybrid-jacket-fix-hood-33z6026-cmp-campagnolo.html")


@pytest.mark.asyncio
async def test_try_scrape_landed_url_is_none_on_launch_failure(monkeypatch):
    """A path that never obtains a result object (browser_missing) carries landed_url=None, same
    as every other acquisition-error field — no result means no fact to read it off."""
    _patch_cdp_launch_mechanics(monkeypatch)

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("BrowserType.launch: Executable doesn't exist at /fake/chrome")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["landed_url"] is None


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_landed_url(monkeypatch):
    """scrape_url_chromium_workflow's log_scrape record carries the raw landed_url off meta — no verdict
    computed or stored alongside it (removed: an agent reading the log has both "url" and
    "landed_url" in the same record and compares them itself)."""
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta(
            landed_url="https://platform.claude.com/en/api/getting-started")

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://docs.anthropic.com/en/api/getting-started")

    assert captured["landed_url"] == "https://platform.claude.com/en/api/getting-started"
    assert "same_target" not in captured


# ---------------------------------------------------------------------------
# The log record no longer carries a computed outcome — acquisition_error is logged straight
# through as its own fact instead (the same precedent pipe_scraper_records.py's own outcome
# removal set), and og_published_time replaces the old guessed published_date/date field.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_log_record_has_no_outcome_field(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta()

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert "outcome" not in captured


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_acquisition_error_as_its_own_fact(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "", _meta(acquisition_error="budget_exhausted", status_code=None)

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert captured["acquisition_error"] == "budget_exhausted"


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_og_published_time(monkeypatch):
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta(og_published_time="2024-03-01T12:00:00+00:00")

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert captured["og_published_time"] == "2024-03-01T12:00:00+00:00"
    assert "published_date" not in captured
    assert "date" not in captured


# ---------------------------------------------------------------------------
# try_scrape enforces the budget constant as an outer guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_times_out_at_budget(monkeypatch, caplog):
    """A hang inside the acquisition (browser call never returns) is cut off at
    TOTAL_SCRAPE_BUDGET_S, yielding acquisition_error=budget_exhausted — not a hang, not a
    traceback. Budget shortened to keep this a fast regression guard; real-budget timing is
    verified separately (see completion checklist)."""
    _patch_cdp_launch_mechanics(monkeypatch)
    monkeypatch.setattr(chromium_scrape, "TOTAL_SCRAPE_BUDGET_S", 0.05)

    class _HangingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            await asyncio.sleep(10)
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, *a, **kw):
            await asyncio.sleep(10)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _HangingCrawler)

    with caplog.at_level(logging.WARNING, logger="src.scraper.chromium_scrape"):
        content, meta = await chromium_scrape.try_scrape("https://example.com")

    assert content == ""
    assert meta["acquisition_error"] == "budget_exhausted"
    assert any("budget exhausted" in m.lower() for m in caplog.messages)


def test_acquisition_error_messages_has_actionable_browser_missing_fix():
    """The acquisition-error description for browser_missing names the concrete install command."""
    msg = chromium_scrape._ACQUISITION_ERROR_MESSAGES["browser_missing"]
    assert "patchright install chromium" in msg


def test_acquisition_error_message_budget_exhausted_reads_real_budget():
    """budget_exhausted's message reads the REAL budget that was in effect for that call
    (config.total_budget_s) — not a re-declared literal."""
    msg = chromium_scrape._acquisition_error_message(
        "budget_exhausted", {"total_budget_s": chromium_scrape.TOTAL_SCRAPE_BUDGET_S})
    assert str(chromium_scrape.TOTAL_SCRAPE_BUDGET_S) in msg
    assert "budget" in msg.lower()


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
# is_garbage_content stays importable/functioning — src/crawler/crawl_site.py depends on it for
# its own (different, unattended) batch-crawl filter; this module just stops CALLING it as a gate
# ---------------------------------------------------------------------------

def test_is_garbage_content_still_importable_and_functioning():
    """Guard against accidentally deleting the function itself — only its use as a gate inside
    this module's own try_scrape/scrape_url_chromium_workflow was removed."""
    assert garbage_filter.is_garbage_content("short") == "minimal_content"
    assert garbage_filter.is_garbage_content("A" * 5000 + " ordinary long real content " * 20) is None


@pytest.mark.asyncio
async def test_try_scrape_does_not_call_is_garbage_content(monkeypatch):
    """The content classifier is never invoked from try_scrape anymore — a page shaped exactly
    like a historical garbage category (short 403-flavored text) must come back as content."""
    _patch_cdp_launch_mechanics(monkeypatch)
    called = []
    monkeypatch.setattr(garbage_filter, "is_garbage_content",
                         lambda content: called.append(content) or "http_error")

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            return _FakeResult(raw_markdown="403 forbidden — but this project no longer discards "
                                             "on that basis, the agent judges now" + "x" * 200,
                                status_code=403)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    await chromium_scrape.try_scrape("https://example.com")
    assert called == []


# ---------------------------------------------------------------------------
# _format_scrape_output: facts always precede content, crawl4ai's diagnosis reads as an
# observation not a verdict, zero content is explicit and never a substituted message
# ---------------------------------------------------------------------------

def _meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "content_type": "text/html",
        "raw_markdown_bytes": 100, "og_published_time": None,
        "crawl4ai_success": True, "crawl4ai_error_message": None,
        "crawl4ai_attempts": 1, "crawl4ai_resolved_by": "direct",
        "crawl4ai_fallback_fetch_used": False, "landed_url": None,
        "document_status_chain": [200], "config": {},
    }
    base.update(overrides)
    return base


def test_format_scrape_output_facts_precede_content():
    text = chromium_scrape._format_scrape_output("https://x.test", "the real page content here",
                                              _meta(), None)
    facts_idx = text.index("## Acquisition facts")
    content_idx = text.index("## Content")
    body_idx = text.index("the real page content here")
    assert facts_idx < content_idx < body_idx


def test_format_scrape_output_never_replaces_content_with_a_message():
    """Content appears verbatim in the output — not summarized, not replaced."""
    real_content = "SPECIFIC_MARKER_TEXT_12345 that must appear byte-for-byte in the output"
    text = chromium_scrape._format_scrape_output("https://x.test", real_content, _meta(), None)
    assert real_content in text


def test_format_scrape_output_zero_content_is_explicit_not_suppressed():
    """Zero content renders as an explicit fact, not a discard message standing in for the page."""
    text = chromium_scrape._format_scrape_output(
        "https://x.test", "", _meta(status_code=None, raw_markdown_bytes=0,
                                     acquisition_error="budget_exhausted",
                                     config={"total_budget_s": chromium_scrape.TOTAL_SCRAPE_BUDGET_S}), None)
    assert "(no content returned)" in text
    assert (f"Acquisition error: scrape exceeded the total time budget "
            f"({chromium_scrape.TOTAL_SCRAPE_BUDGET_S}s)") in text
    assert "Error scraping" not in text  # the old discard-message phrasing must not reappear


# ---------------------------------------------------------------------------
# _format_scrape_output: the landed-URL line is UNCONDITIONAL — rendered on every scrape, exactly
# like HTTP status, whether the landed URL matches the requested one, differs, or is absent. No
# code-side verdict decides whether the agent gets to see this fact (milestone 5: same_target and
# the conditional render it drove were both removed — see the module's own comment on this line).
# ---------------------------------------------------------------------------

def test_format_scrape_output_renders_landed_url_line_when_it_differs():
    """A landed URL on a genuinely different host renders as an explicit, readable fact — wording
    makes no claim about "redirect" or "different target", since nothing decides that anymore."""
    text = chromium_scrape._format_scrape_output(
        "https://docs.anthropic.com/en/api/getting-started",
        "the real landed page content",
        _meta(landed_url="https://platform.claude.com/en/api/getting-started"),
        None)
    assert ("Landed URL (the URL the browser actually returned content from): "
            "https://platform.claude.com/en/api/getting-started") in text


def test_format_scrape_output_renders_landed_url_line_when_it_matches():
    """landed_url identical to the requested URL — the overwhelming majority case — still renders
    the line, unconditionally, exactly like HTTP status does."""
    text = chromium_scrape._format_scrape_output(
        "https://www.rfc-editor.org/info/rfc2616/", "the rfc content",
        _meta(landed_url="https://www.rfc-editor.org/info/rfc2616/"), None)
    assert ("Landed URL (the URL the browser actually returned content from): "
            "https://www.rfc-editor.org/info/rfc2616/") in text


def test_format_scrape_output_renders_landed_url_line_when_absent():
    """No landed_url at all (e.g. acquisition failed before a result existed) still renders the
    line — the absence itself is the fact, rendered literally (None), matching how every other
    absent value in this block reads (e.g. HTTP status on a budget_exhausted record) rather than
    being suppressed into a missing line."""
    text = chromium_scrape._format_scrape_output(
        "https://x.test/a", "", _meta(landed_url=None, acquisition_error="browser_missing"), None)
    assert "Landed URL (the URL the browser actually returned content from): None" in text


def test_format_scrape_output_renders_og_published_time_when_present():
    """The page's own declared date renders verbatim, labeled as its own claim, not a guess."""
    text = chromium_scrape._format_scrape_output(
        "https://x.test", "the real page content", _meta(), "2024-03-01T12:00:00+00:00")
    assert "og:published_time" in text
    assert "2024-03-01T12:00:00+00:00" in text
    assert "the page's OWN declared value" in text


def test_format_scrape_output_renders_og_published_time_line_unconditionally_when_absent():
    """Same unconditional-fact treatment as landed_url/HTTP status — the line itself always
    renders, even when the page declared nothing, rather than being suppressed."""
    text = chromium_scrape._format_scrape_output(
        "https://x.test", "the real page content", _meta(), None)
    assert "og:published_time" in text


def test_format_scrape_output_crawl4ai_diagnosis_labeled_as_observation_not_verdict():
    """The diagnosis line itself carries the observation-not-verdict caveat — a caller reading
    only the output text (not the source) must see this, not just a code comment."""
    text = chromium_scrape._format_scrape_output(
        "https://x.test", "full product page content here, well past any thin-page threshold",
        _meta(status_code=403,
              crawl4ai_error_message="Blocked by anti-bot protection: Cloudflare JS challenge"),
        None)
    assert "OBSERVATION" in text
    assert "NOT a verdict" in text
    assert "Cloudflare JS challenge" in text
    # And the content is still there despite the diagnosis claiming a block
    assert "full product page content here" in text


# ---------------------------------------------------------------------------
# launch_mode is a fixed LAUNCH_MODE constant now that try_scrape unconditionally runs the
# cdp-headed path — the WEBSEARCH_HEADLESS escape hatch and its dispatch are gone.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_launch_mode_truthful_on_cdp_path(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch)

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


# ---------------------------------------------------------------------------
# cdp-headed teardown fires on every exit path — the self-launched Chrome must be killed even
# when acquisition raises or the outer budget times out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cdp_headed_teardown_fires_on_exception(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch)
    kill_calls = []
    monkeypatch.setattr(chromium_scrape, "_kill_by_profile", lambda d: kill_calls.append(d))

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("Timeout 60000ms exceeded while waiting for load")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    await chromium_scrape.try_scrape("https://example.com")

    assert len(kill_calls) == 1


@pytest.mark.asyncio
async def test_cdp_headed_teardown_fires_on_budget_timeout(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch)
    kill_calls = []
    monkeypatch.setattr(chromium_scrape, "_kill_by_profile", lambda d: kill_calls.append(d))
    monkeypatch.setattr(chromium_scrape, "TOTAL_SCRAPE_BUDGET_S", 0.05)

    class _HangingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            await asyncio.sleep(10)
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _HangingCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["acquisition_error"] == "budget_exhausted"
    assert len(kill_calls) == 1


# ---------------------------------------------------------------------------
# Self-launch mechanics — real functions, no mocking (subprocess/filesystem only)
# ---------------------------------------------------------------------------

def test_wait_for_devtools_port_reads_real_port_file(tmp_path):
    port_file = tmp_path / "DevToolsActivePort"
    port_file.write_text("54321\n/devtools/browser/fake-uuid\n")
    port = chromium_process._wait_for_devtools_port(str(tmp_path), timeout_s=2.0)
    assert port == 54321


def test_wait_for_devtools_port_times_out_when_file_never_appears(tmp_path):
    with pytest.raises(TimeoutError, match="DevToolsActivePort did not appear"):
        chromium_process._wait_for_devtools_port(str(tmp_path), timeout_s=0.3)


def test_find_app_bundle_walks_up_to_app_suffix():
    bundle = chromium_process._find_app_bundle(
        "/Users/x/Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
    assert str(bundle).endswith("Google Chrome for Testing.app")


def test_find_app_bundle_returns_none_when_no_app_ancestor():
    assert chromium_process._find_app_bundle("/usr/local/bin/chrome") is None


# ---------------------------------------------------------------------------
# Flag-parity mechanism — build_browser_flags() is called LIVE (never pinned), so its own
# existence/signature is a hard, loud-failure guard: if crawl4ai ever renames/removes/reshapes it,
# this test goes red instead of the self-launch silently losing its flag surface.
# ---------------------------------------------------------------------------

def test_build_browser_flags_symbol_resolves_and_is_callable():
    """Guard against a silent posture change on a crawl4ai upgrade: if ManagedBrowser.
    build_browser_flags disappears, gets renamed, or its signature changes incompatibly, THIS
    test fails loudly — no try/except swallowing the import or the call."""
    from crawl4ai.browser_manager import ManagedBrowser
    import inspect

    assert hasattr(ManagedBrowser, "build_browser_flags")
    sig = inspect.signature(ManagedBrowser.build_browser_flags)
    params = list(sig.parameters)
    assert params, "build_browser_flags must accept at least one parameter (the BrowserConfig)"

    # Real call, real BrowserConfig — not mocked. Raises loudly if the signature is incompatible.
    flags = ManagedBrowser.build_browser_flags(chromium_scrape.BrowserConfig(enable_stealth=True))
    assert isinstance(flags, list)
    assert all(isinstance(f, str) for f in flags)
    assert len(flags) > 0


def test_build_self_launch_flags_keeps_gpu_on_under_stealth():
    """enable_stealth=True must NOT carry --disable-gpu/--disable-gpu-compositing/
    --disable-software-rasterizer — build_browser_flags() gates these behind `not enable_stealth`
    (its own comment: keep WebGL working under stealth). Deliberate 3-flag deviation from literal
    parity with the old direct-launch path's cmdline, confirmed here so it can't silently regress
    back to disabling GPU."""
    flags = chromium_process._build_self_launch_flags(chromium_scrape.BrowserConfig(enable_stealth=True))
    assert "--disable-gpu" not in flags
    assert "--disable-gpu-compositing" not in flags
    assert "--disable-software-rasterizer" not in flags
    assert "--disable-blink-features=AutomationControlled" in flags


def test_build_self_launch_flags_includes_window_size_when_viewport_set():
    config = chromium_scrape.BrowserConfig(enable_stealth=True, viewport_width=1080, viewport_height=600)
    flags = chromium_process._build_self_launch_flags(config)
    assert "--window-size=1080,600" in flags


# ---------------------------------------------------------------------------
# Net 2 — death_pipe watchdog spawned once the cdp port resolves, with this call's real PIDs and
# its own throwaway profile dir as cleanup_dir (unlike the search lane, which never deletes its
# persistent session profile)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch)
    monkeypatch.setattr(chromium_scrape, "_pids_on_profile", lambda d: [555, 666])
    calls = []
    monkeypatch.setattr(chromium_scrape.death_pipe, "spawn_watchdog", lambda pids, cleanup_dir=None: calls.append((pids, cleanup_dir)))

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

    await chromium_scrape.try_scrape("https://example.com")

    assert len(calls) == 1
    pids, cleanup_dir = calls[0]
    assert pids == [555, 666]
    assert cleanup_dir is not None  # this call's own tempfile.mkdtemp(prefix="scrape-url-cdp-") dir


# ---------------------------------------------------------------------------
# _pids_on_profile — pgrep output parsing, shared by _kill_by_profile and the watchdog spawn
# ---------------------------------------------------------------------------

def test_pids_on_profile_parses_pgrep_output(monkeypatch):
    class _FakeCompleted:
        stdout = "111\n222\n"

    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert chromium_process._pids_on_profile("/tmp/some-dir") == [111, 222]


def test_pids_on_profile_empty_when_no_match(monkeypatch):
    class _FakeCompleted:
        stdout = ""

    monkeypatch.setattr(chromium_process.subprocess, "run", lambda *a, **kw: _FakeCompleted())
    assert chromium_process._pids_on_profile("/tmp/some-dir") == []


def test_kill_by_profile_delegates_to_death_pipe_terminate_then_kill(monkeypatch):
    monkeypatch.setattr(chromium_process, "_pids_on_profile", lambda d: [42])
    calls = []
    monkeypatch.setattr(chromium_process.death_pipe, "_terminate_then_kill", lambda pids, timeout_s=5.0: calls.append((pids, timeout_s)))
    chromium_process._kill_by_profile("/tmp/some-dir")
    assert calls == [([42], 3.0)]


def test_kill_by_profile_noop_when_no_pids(monkeypatch):
    monkeypatch.setattr(chromium_process, "_pids_on_profile", lambda d: [])
    calls = []
    monkeypatch.setattr(chromium_process.death_pipe, "_terminate_then_kill", lambda *a, **kw: calls.append(1))
    chromium_process._kill_by_profile("/tmp/some-dir")
    assert calls == []


# ---------------------------------------------------------------------------
# Net 3 — _reap_orphaned_scrapes: kill only processes older than TOTAL_SCRAPE_BUDGET_S (parallel
# scrapes under budget are legitimate, never killed), sweep dirs with zero live processes
# ---------------------------------------------------------------------------

def test_reap_orphaned_scrapes_kills_only_pids_older_than_budget(monkeypatch, tmp_path):
    now = time.time()
    young_pid, old_pid = 1001, 1002

    class _FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            return now - (10.0 if self.pid == young_pid else chromium_process.TOTAL_SCRAPE_BUDGET_S + 5.0)

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [young_pid, old_pid])
    monkeypatch.setattr(chromium_process.psutil, "Process", _FakeProc)
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: set())
    killed = []
    monkeypatch.setattr(chromium_process.death_pipe, "_terminate_then_kill", lambda pids: killed.append(pids))
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert killed == [[old_pid]]


def test_reap_orphaned_scrapes_never_kills_pid_under_budget_even_if_only_candidate(monkeypatch, tmp_path):
    now = time.time()

    class _FakeProc:
        def create_time(self):
            return now - 5.0  # well under TOTAL_SCRAPE_BUDGET_S — a legitimate in-flight scrape

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [2001])
    monkeypatch.setattr(chromium_process.psutil, "Process", lambda pid: _FakeProc())
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: {"/tmp/scrape-url-cdp-live"})
    killed = []
    monkeypatch.setattr(chromium_process.death_pipe, "_terminate_then_kill", lambda pids: killed.append(pids))
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert killed == []


def test_reap_orphaned_scrapes_sweeps_dirs_with_no_live_process(monkeypatch, tmp_path):
    live_dir = tmp_path / "scrape-url-cdp-live"
    orphan_dir = tmp_path / "scrape-url-cdp-orphan"
    live_dir.mkdir()
    orphan_dir.mkdir()

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [])
    monkeypatch.setattr(chromium_process, "_live_scrape_profile_dirs", lambda: {str(live_dir)})
    monkeypatch.setattr(chromium_process, "tempfile", type("T", (), {"gettempdir": staticmethod(lambda: str(tmp_path))}))

    chromium_process._reap_orphaned_scrapes()

    assert live_dir.exists()
    assert not orphan_dir.exists()


def test_live_scrape_profile_dirs_reads_user_data_dir_from_cmdline(monkeypatch):
    class _FakeProc:
        def cmdline(self):
            return ["/fake/Chrome", "--remote-debugging-port=0", "--user-data-dir=/tmp/scrape-url-cdp-abc123", "--flag"]

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [7777])
    monkeypatch.setattr(chromium_process.psutil, "Process", lambda pid: _FakeProc())

    assert chromium_process._live_scrape_profile_dirs() == {"/tmp/scrape-url-cdp-abc123"}


def test_live_scrape_profile_dirs_skips_already_dead_pid(monkeypatch):
    def raise_no_such_process(pid):
        raise chromium_process.psutil.NoSuchProcess(pid)

    monkeypatch.setattr(chromium_process, "_pids_matching_scrape_profiles", lambda: [8888])
    monkeypatch.setattr(chromium_process.psutil, "Process", raise_no_such_process)

    assert chromium_process._live_scrape_profile_dirs() == set()


# ---------------------------------------------------------------------------
# document_status_chain — the before_goto hook (_make_document_status_listener) collects the
# ordered chain of main-frame document response statuses; the LAST entry overrides meta["status_code"]
# (the page whose content was actually captured), and an empty chain falls back to crawl4ai's own
# result.status_code unchanged. Exercised through the real _acquire_cdp_headed/_acquire_scrape
# machinery: the fake crawler invokes crawler_strategy.execute_hook("before_goto", ...) itself
# (the same call crawl4ai's own async_crawler_strategy.py makes right before page.goto), against a
# fake page whose .on("response", ...) registers the real listener, then fires fake response events.
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, resource_type, frame):
        self.resource_type = resource_type
        self._frame = frame

    @property
    def frame(self):
        return self._frame


class _FakeResponse:
    def __init__(self, status, request):
        self.status = status
        self.request = request


class _FakeMainFrame:
    pass


class _FakePage:
    def __init__(self):
        self.main_frame = _FakeMainFrame()
        self._response_handlers = []

    def on(self, event, handler):
        if event == "response":
            self._response_handlers.append(handler)

    def fire_response(self, status, resource_type="document", frame=None):
        request = _FakeRequest(resource_type, frame if frame is not None else self.main_frame)
        response = _FakeResponse(status, request)
        for h in self._response_handlers:
            h(response)


def _fake_crawler_with_document_responses(statuses, crawl4ai_status_code=403):
    """Builds a fake AsyncWebCrawler class whose arun() invokes the real before_goto hook
    registered on the crawler_strategy passed in, fires one fake main-frame document response per
    status in `statuses` (in order), then returns a result carrying crawl4ai_status_code as its
    OWN status_code (simulating crawl4ai's earliest-hop value, distinct from the chain's last)."""
    class _FakeCrawler:
        def __init__(self, *a, **kw):
            self.crawler_strategy = kw.get("crawler_strategy")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            page = _FakePage()
            await self.crawler_strategy.execute_hook(
                "before_goto", page, context=None, url=url, config=config
            )
            for status in statuses:
                page.fire_response(status)
            return _FakeResult(raw_markdown="x" * 300, status_code=crawl4ai_status_code)

    return _FakeCrawler


@pytest.mark.asyncio
async def test_acquire_cdp_headed_last_document_response_overrides_crawl4ai_status(monkeypatch):
    """403 -> 302 -> 200 chain (self-resolving challenge shape): status_code becomes the LAST
    response's status (200), the chain is recorded in full, and crawl4ai's own (earliest-hop) 403
    is overridden — the page whose content was actually captured is the 200 one."""
    _patch_cdp_launch_mechanics(monkeypatch)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([403, 302, 200], crawl4ai_status_code=403),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [403, 302, 200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_cdp_headed_single_response_chain(monkeypatch):
    """An ordinary page with no challenge/redirect: one main-frame document response, chain has
    exactly one entry, status_code equals today's (unchanged) behavior."""
    _patch_cdp_launch_mechanics(monkeypatch)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([200], crawl4ai_status_code=200),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [200]
    assert meta["status_code"] == 200


@pytest.mark.asyncio
async def test_acquire_cdp_headed_falls_back_to_crawl4ai_status_when_listener_saw_nothing(monkeypatch):
    """The listener sees no main-frame document response at all (e.g. a raw: input, or a
    navigation that never fires one) — chain stays empty, status_code falls back to crawl4ai's own
    result.status_code, never invented."""
    _patch_cdp_launch_mechanics(monkeypatch)
    monkeypatch.setattr(
        chromium_scrape, "AsyncWebCrawler",
        _fake_crawler_with_document_responses([], crawl4ai_status_code=403),
    )

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == []
    assert meta["status_code"] == 403


@pytest.mark.asyncio
async def test_document_status_listener_ignores_non_document_and_non_main_frame_responses(monkeypatch):
    """A stylesheet/script response and a document response on a DIFFERENT frame (e.g. an iframe)
    must not enter the chain — only main-frame document responses count."""
    _patch_cdp_launch_mechanics(monkeypatch)

    class _FakeCrawler:
        def __init__(self, *a, **kw):
            self.crawler_strategy = kw.get("crawler_strategy")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def arun(self, url, config=None):
            page = _FakePage()
            await self.crawler_strategy.execute_hook(
                "before_goto", page, context=None, url=url, config=config
            )
            page.fire_response(999, resource_type="stylesheet")
            page.fire_response(500, resource_type="document", frame=object())  # iframe, not main
            page.fire_response(200, resource_type="document")
            return _FakeResult(raw_markdown="x" * 300, status_code=200)

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _FakeCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["document_status_chain"] == [200]


@pytest.mark.asyncio
async def test_try_scrape_document_status_chain_empty_on_launch_failure(monkeypatch):
    """A path that never obtains a result object (browser_missing) carries an empty chain, same
    treatment as every other acquisition-error field."""
    _patch_cdp_launch_mechanics(monkeypatch)

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("BrowserType.launch: Executable doesn't exist at /fake/chrome")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)

    _, meta = await chromium_scrape.try_scrape("https://example.com")

    assert meta["acquisition_error"] == "browser_missing"
    assert meta["document_status_chain"] == []


@pytest.mark.asyncio
async def test_scrape_url_chromium_workflow_logs_document_status_chain(monkeypatch):
    """scrape_url_chromium_workflow's log_scrape record carries the new fact field."""
    captured = {}

    async def _fake_try_scrape(url):
        return "real content", _meta(document_status_chain=[403, 302, 200])

    monkeypatch.setattr(chromium_scrape, "try_scrape", _fake_try_scrape)
    monkeypatch.setattr(chromium_scrape, "write_sidecar", lambda *a, **kw: None)
    monkeypatch.setattr(chromium_scrape, "log_scrape", lambda record: captured.update(record))

    await chromium_scrape.scrape_url_chromium_workflow("https://example.com")

    assert captured["document_status_chain"] == [403, 302, 200]


def test_format_scrape_output_renders_document_status_chain_line():
    text = chromium_scrape._format_scrape_output(
        "https://x.test", "the real page content",
        _meta(status_code=200, document_status_chain=[403, 302, 200]), None)
    assert "Document status chain" in text
    assert "[403, 302, 200]" in text


@pytest.mark.asyncio
async def test_try_scrape_calls_reap_orphaned_scrapes_at_start(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch)
    calls = []
    monkeypatch.setattr(chromium_scrape, "_reap_orphaned_scrapes", lambda: calls.append(1))

    class _RaisingCrawler:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            raise Exception("boom")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chromium_scrape, "AsyncWebCrawler", _RaisingCrawler)
    await chromium_scrape.try_scrape("https://example.com")

    assert calls == [1]
