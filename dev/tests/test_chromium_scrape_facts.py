import asyncio
import logging

import pytest

from src.scraper import chromium_process, chromium_scrape
from dev.tests._chromium_scrape_fakes import _patch_cdp_launch_mechanics, _FakeResult, _meta


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
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
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


# ---------------------------------------------------------------------------
# try_scrape captures meta["landed_url"] RAW from result.redirected_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_try_scrape_captures_landed_url_raw(monkeypatch):
    """meta["landed_url"] is result.redirected_url verbatim — no normalization, no verdict."""
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

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
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)

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
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
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


# ---------------------------------------------------------------------------
# cdp-headed teardown fires on every exit path — the self-launched Chrome must be killed even
# when acquisition raises or the outer budget times out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cdp_headed_teardown_fires_on_exception(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
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
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
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
# Net 2 — death_pipe watchdog spawned once the cdp port resolves, with this call's real PIDs and
# its own throwaway profile dir as cleanup_dir (unlike the search lane, which never deletes its
# persistent session profile)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir(monkeypatch):
    _patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)
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
