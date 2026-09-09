"""Tests for pipe_scraper's per-URL JSONL log (pipe_scrape_logger.py) and the config stamp
it carries.

Runs without a browser: _scrape_all's AsyncWebCrawler is patched with a fake crawler returning
synthetic results, isolating the logging path from the real network/browser call.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.crawler import pipe_scraper
from src.crawler import pipe_scraper_config
from src.crawler import pipe_scraper_acquisition
from src.crawler import pipe_scraper_constants
from src.crawler.pipe_scrape_logger import log_pipe_scrape
from src.crawler.pipe_scraper_acquisition import _onward_link_identity, _extract_onward_links
from src.crawler.pipe_scraper_report import _collect_onward_links, _write_onward_links_file, _print_summary


# log_janitor prunes any record whose "ts" falls outside the 14-day retention window (or is
# unparseable) on every write — records here must carry a real, current, ISO-parseable ts.
def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------------------
# _extract_pipe_config_stamp reads real objects, not re-declared literals
# ---------------------------------------------------------------------------

def test_extract_pipe_config_stamp_reads_real_objects():
    """The config stamp reflects the actual constructed BrowserConfig/CrawlerRunConfig values,
    not hardcoded copies — changing an object's value changes the stamp."""
    browser_cfg = pipe_scraper_config.BrowserConfig(headless=True, verbose=False, enable_stealth=True)
    run_cfg = pipe_scraper_config.CrawlerRunConfig(
        cache_mode=pipe_scraper_config.CacheMode.BYPASS,
        wait_until="networkidle",
        delay_before_return_html=1.25,
        page_timeout=9999,
    )
    stamp = pipe_scraper_config._extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay=2.0,
                                                             concurrency_per_domain=3)
    assert stamp["enable_stealth"] is True
    assert stamp["wait_until"] == "networkidle"
    assert stamp["page_timeout_ms"] == 9999
    assert stamp["delay_before_return_html_s"] == 1.25
    assert stamp["cache_mode"] == "bypass"
    assert stamp["download_delay_s"] == 2.0
    assert stamp["concurrency_per_domain"] == 3


def test_extract_pipe_config_stamp_reads_anti_bot_fields_off_real_objects():
    """simulate_user/override_navigator/magic/remove_consent_popups are read off the real
    CrawlerRunConfig, not re-declared — changing the object changes the stamp."""
    browser_cfg = pipe_scraper_config.BrowserConfig(headless=True, verbose=False)
    run_cfg = pipe_scraper_config.CrawlerRunConfig(
        simulate_user=True, override_navigator=True, magic=False, remove_consent_popups=True,
    )
    stamp = pipe_scraper_config._extract_pipe_config_stamp(browser_cfg, run_cfg, download_delay=1.0,
                                                             concurrency_per_domain=8)
    assert stamp["simulate_user"] is True
    assert stamp["override_navigator"] is True
    assert stamp["magic"] is False
    assert stamp["remove_consent_popups"] is True


# ---------------------------------------------------------------------------
# _build_configs: the fixed anti-bot posture this milestone sets
# ---------------------------------------------------------------------------

def test_build_configs_sets_fixed_anti_bot_posture():
    """_build_configs's real BrowserConfig/CrawlerRunConfig carry the milestone's exact
    calibration: stealth + simulate_user + override_navigator on, magic explicitly off,
    consent popups dismissed, pacing/timeout values untouched."""
    browser_cfg, run_cfg = pipe_scraper_config._build_configs()
    assert browser_cfg.enable_stealth is True
    assert run_cfg.simulate_user is True
    assert run_cfg.override_navigator is True
    assert run_cfg.magic is False
    assert run_cfg.remove_consent_popups is True
    # Unchanged pacing/timeout values — no extraction-side settings added
    assert run_cfg.page_timeout == pipe_scraper_constants.PAGE_TIMEOUT_MS
    assert run_cfg.delay_before_return_html == pipe_scraper_constants.DELAY_BEFORE_RETURN_HTML
    assert run_cfg.markdown_generator.content_filter is None


@pytest.mark.asyncio
async def test_build_configs_produces_live_stealth_adapter():
    """Wiring test, not a dict comparison: constructs the REAL crawl4ai
    AsyncPlaywrightCrawlerStrategy from _build_configs's real BrowserConfig and asserts against
    crawl4ai's own BrowserManager/StealthAdapter state. No network — __init__ only builds state,
    never launches a browser. This is what a flag-only check (`browser_cfg.enable_stealth is
    True`) would NOT catch: StealthAdapter._check_stealth_availability swallows an ImportError
    and silently degrades `apply_stealth` to a no-op with no error raised anywhere (exactly what
    happened on crawl4ai 0.8.6 + playwright-stealth 2.0.2, see
    process-docs/scrape_pipeline/crawl4ai_stealth_stack_2026-05-31.md) — a dict check would still
    pass in that broken state, this test would not."""
    from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
    from playwright_stealth import Stealth

    browser_cfg, _ = pipe_scraper_config._build_configs()
    strategy = AsyncPlaywrightCrawlerStrategy(browser_config=browser_cfg)

    # use_undetected resolves False (default PlaywrightAdapter, pipe_scraper passes no adapter) —
    # the precondition browser_manager.py requires to build the stealth adapter at all
    assert strategy.browser_manager.use_undetected is False
    assert strategy.browser_manager._stealth_adapter is not None
    assert strategy.browser_manager._stealth_adapter._stealth_available is True
    assert isinstance(strategy.browser_manager._stealth_adapter._stealth, Stealth)



# ---------------------------------------------------------------------------
# log_pipe_scrape: fail-soft + real write
# ---------------------------------------------------------------------------

def test_log_pipe_scrape_writes_jsonl_record(tmp_path, monkeypatch):
    """A record appended via log_pipe_scrape is a valid JSONL line with the expected keys."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    log_pipe_scrape({"ts": _now_ts(), "run_id": "abc123", "url": "https://x.test",
                      "domain": "x.test", "http_status": 200, "bytes": 500,
                      "wall_ms": 100, "config_hash": "deadbeef00", "config": {"headless": True}})

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_id"] == "abc123"
    assert record["http_status"] == 200


def test_log_pipe_scrape_appends(tmp_path, monkeypatch):
    """Successive calls append, not overwrite."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    for i in range(3):
        log_pipe_scrape({"ts": _now_ts(), "run_id": "r", "url": f"https://x.test/{i}", "domain": "x.test",
                          "http_status": 200, "bytes": 1, "wall_ms": 1,
                          "config_hash": "h", "config": {}})

    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 3


def test_log_pipe_scrape_fail_soft(monkeypatch, caplog):
    """A write failure (unwritable path) is swallowed, not raised — logging must never break a scrape."""
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", "/nonexistent-root-dir/x/pipe_scrape_log.jsonl")

    with caplog.at_level("WARNING", logger="src.crawler.pipe_scrape_logger"):
        log_pipe_scrape({"ts": _now_ts(), "run_id": "r", "url": "https://x.test", "domain": "x.test",
                          "http_status": 200, "bytes": 1, "wall_ms": 1,
                          "config_hash": "h", "config": {}})
    # No exception raised (call above completing is the primary assertion) + a warning was logged
    assert any("pipe_scrape_log write failed" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# _scrape_all: one run_id shared across all URLs, success + exception paths both logged
# ---------------------------------------------------------------------------

class _FakeMarkdown:
    def __init__(self, raw_markdown):
        self.raw_markdown = raw_markdown


class _FakeResult:
    def __init__(self, raw_markdown, status_code=200, success=True, error_message=None,
                 redirected_url=None, links=None):
        self.markdown = _FakeMarkdown(raw_markdown)
        self.status_code = status_code
        self.success = success
        self.error_message = error_message
        self.crawl_stats = {"attempts": 1, "resolved_by": "direct", "fallback_fetch_used": False}
        self.redirected_url = redirected_url
        self.links = links if links is not None else {"internal": [], "external": []}


class _FakeCrawler:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        if "fail" in url:
            raise Exception("simulated network failure")
        return _FakeResult(raw_markdown="x" * 500)


@pytest.mark.asyncio
async def test_scrape_all_logs_shared_run_id_across_urls(tmp_path, monkeypatch):
    """Every record from one _scrape_all invocation carries the same run_id."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    urls = ["https://x.test/a", "https://x.test/b", "https://x.test/fail"]
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    run_ids = {r["run_id"] for r in records}
    assert len(run_ids) == 1

    by_url = {r["url"]: r for r in records}
    assert by_url["https://x.test/a"]["http_status"] == 200
    assert by_url["https://x.test/fail"]["http_status"] is None
    assert by_url["https://x.test/fail"]["crawl4ai_success"] is None
    assert by_url["https://x.test/a"]["crawl4ai_success"] is True


@pytest.mark.asyncio
async def test_scrape_one_exception_becomes_tripwire_record(tmp_path, monkeypatch):
    """2026-09-09: both curl_cffi fallback paths (a and b) were removed — a hard crawler exception
    is now a pure tripwire, not a rescue by a second fetch method. The except block logs a
    None-status/0-byte record and returns the same dict shape, the run continues past the failure,
    no file is written for the failed URL, and the log record carries no pipe_fallback_* keys at
    all (the mechanism they described no longer exists)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    urls = ["https://x.test/a", "https://x.test/fail"]
    results = await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.01, concurrency_per_domain=8)

    by_url_result = {r["url"]: r for r in results}
    assert by_url_result["https://x.test/fail"]["status_code"] is None
    assert by_url_result["https://x.test/fail"]["bytes"] == 0
    assert by_url_result["https://x.test/a"]["status_code"] == 200  # run continues past the failure

    assert not (output_dir / pipe_scraper_acquisition._url_to_filename("https://x.test/fail")).exists()

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    by_url_record = {r["url"]: r for r in records}
    fail_record = by_url_record["https://x.test/fail"]
    assert fail_record["http_status"] is None
    assert fail_record["bytes"] == 0
    assert "pipe_fallback_used" not in fail_record
    assert "pipe_fallback_resolved" not in fail_record


@pytest.mark.asyncio
async def test_scrape_one_ts_reflects_request_start_not_queue_time(tmp_path, monkeypatch):
    """Regression guard: ts must be stamped AFTER the per-domain gate, not when asyncio.gather
    queues the coroutine. concurrency_per_domain=1 fully serializes 6 same-domain URLs through
    the gate at download_delay=0.05s (jitter 0.025-0.075s/hop) — real elapsed request-start times
    must spread across the run. A ts taken before the gate collapses to one identical value for
    all 6 records regardless of this pacing (the bug this guards against)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    urls = [f"https://x.test/{i}" for i in range(6)]
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.05, concurrency_per_domain=1)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 6
    timestamps = [datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in records]
    distinct = {t for t in timestamps}
    assert len(distinct) > 1, "all records share one ts — ts is being stamped at queue time, not request start"
    spread_s = (max(timestamps) - min(timestamps)).total_seconds()
    # 5 gate hops at >=0.025s jitter each (serialized, concurrency_per_domain=1) — real lower bound ~0.125s
    assert spread_s > 0.1, f"ts spread too small ({spread_s}s) for a gated 6-URL/concurrency=1 run"


@pytest.mark.asyncio
async def test_scrape_all_records_carry_config_hash_and_config(tmp_path, monkeypatch):
    """Every record carries the same config_hash + config dict for one run (same config in effect)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    urls = ["https://x.test/a", "https://x.test/b"]
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    hashes = {r["config_hash"] for r in records}
    assert len(hashes) == 1
    assert records[0]["config"]["download_delay_s"] == 0.01
    assert records[0]["config"]["concurrency_per_domain"] == 8
    # Fixed anti-bot posture flows through into the logged stamp, not just the in-memory config
    assert records[0]["config"]["enable_stealth"] is True
    assert records[0]["config"]["simulate_user"] is True
    assert records[0]["config"]["override_navigator"] is True
    assert records[0]["config"]["magic"] is False
    assert records[0]["config"]["remove_consent_popups"] is True


# ---------------------------------------------------------------------------
# landed_url on the plain success route. No same_target verdict is computed anywhere in this
# module (milestone 5: removed — an agent reading a record has both "url" and "landed_url" and
# compares them itself).
# ---------------------------------------------------------------------------

class _FakeRedirectingCrawler:
    """Plain success route (no fallback engaged either way) — result carries a real
    redirected_url, differing from the requested URL on a different host."""
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        return _FakeResult(raw_markdown="x" * 500,
                            redirected_url="https://platform.claude.com/docs/en/api/overview")


@pytest.mark.asyncio
async def test_landed_url_recorded_on_plain_success_with_redirect(tmp_path, monkeypatch):
    """The plain success route (neither fallback engaged) gets a real landed_url — a deviating
    redirect (different host) is recorded raw, no verdict computed alongside it."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeRedirectingCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://docs.anthropic.com/en/api/getting-started"],
                                    output_dir, download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["landed_url"] == "https://platform.claude.com/docs/en/api/overview"
    assert "same_target" not in r


@pytest.mark.asyncio
async def test_landed_url_recorded_on_plain_success_no_redirect(tmp_path, monkeypatch):
    """No redirect on the plain success route: landed_url reflects whatever crawl4ai reported
    (None here — _FakeResult's own default, no redirected_url set)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["landed_url"] is None  # _FakeResult's own default — no redirected_url set
    assert "same_target" not in r


# ---------------------------------------------------------------------------
# Engine switch — milestone 3 of the camoufox_lane area: a per-RUN choice between the chromium
# engine (default, unchanged) and the camoufox engine (try_scrape_camoufox), never per-URL, never
# auto-selected. pipe_scraper_acquisition.try_scrape_camoufox is faked at the module boundary (same convention
# as camoufox_scrape's own tests faking AsyncCamoufox) — no real browser launched here either.
# ---------------------------------------------------------------------------

def _camoufox_meta(**overrides):
    base = {
        "acquisition_error": None, "status_code": 200, "landed_url": "https://x.test/a",
        "raw_markdown_bytes": 100, "markdown_conversion_error": None, "content_is_raw_html": False,
        "document_status_chain": [200],
        "config": {"headless": False, "os": "macos"}, "config_hash": "cafef00d00",
    }
    base.update(overrides)
    return base


def test_camoufox_concurrency_default_is_conservative():
    """No measurement exists yet for how many concurrent Camoufox instances this machine
    tolerates — the default must be the most conservative value (fully serialized), unlike the
    chromium engine's measured/validated 8."""
    assert pipe_scraper_constants.CAMOUFOX_CONCURRENCY_PER_DOMAIN == 1
    assert pipe_scraper_constants.CAMOUFOX_CONCURRENCY_PER_DOMAIN < pipe_scraper_constants.CONCURRENCY_PER_DOMAIN


@pytest.mark.asyncio
async def test_scrape_all_default_engine_is_chromium_and_unchanged(tmp_path, monkeypatch):
    """engine defaulted/omitted -> the existing chromium path runs, untouched: AsyncWebCrawler is
    used, try_scrape_camoufox is never called at all."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append(url)
        return "should never be reached", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    assert called == []
    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["engine"] == "chromium"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_engine_dispatches_to_try_scrape_camoufox(tmp_path, monkeypatch):
    """engine="camoufox" -> try_scrape_camoufox is called per URL; AsyncWebCrawler/AsyncCamoufox
    (the chromium engine's own machinery) is never touched."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    class _UnreachableCrawler:
        def __init__(self, *a, **kw):
            raise AssertionError("chromium engine's AsyncWebCrawler must not be constructed")
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _UnreachableCrawler)

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append((url, block_images))
        return "# real markdown, non-trivial content" * 2, _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(
        ["https://x.test/a"], output_dir, download_delay=0.01,
        concurrency_per_domain=None, engine="camoufox", block_images=True,
    )

    assert called == [("https://x.test/a", True)]
    assert results[0]["status_code"] == 200
    assert (output_dir / pipe_scraper_acquisition._url_to_filename("https://x.test/a")).exists()


@pytest.mark.asyncio
async def test_scrape_all_camoufox_default_block_images_is_false(tmp_path, monkeypatch):
    """block_images omitted -> defaults to False, unified with the ad-hoc lane's own default
    (settled decision: stealth over bandwidth, per Camoufox's own LeakWarning on image-blocking
    as a WAF detection signal) — no longer True as the pipe engine used to default."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    called = []
    async def _fake_try_scrape_camoufox(url, block_images=False):
        called.append((url, block_images))
        return "# real markdown, non-trivial content" * 2, _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(
        ["https://x.test/a"], output_dir, download_delay=0.01,
        concurrency_per_domain=None, engine="camoufox",
    )

    assert called == [("https://x.test/a", False)]


@pytest.mark.asyncio
async def test_scrape_all_camoufox_engine_resolves_own_concurrency_default(tmp_path, monkeypatch):
    """concurrency_per_domain=None + engine="camoufox" -> resolves to
    CAMOUFOX_CONCURRENCY_PER_DOMAIN, not the chromium default. Proven via timing: 3 same-domain
    URLs at concurrency=1 must serialize through the pacing gate (spread > 0), unlike the
    chromium default of 8 which would let them all start together."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "# content", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    urls = [f"https://x.test/{i}" for i in range(3)]
    await pipe_scraper._scrape_all(urls, output_dir, download_delay=0.05,
                                    concurrency_per_domain=None, engine="camoufox")

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    timestamps = [datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) for r in records]
    spread_s = (max(timestamps) - min(timestamps)).total_seconds()
    assert spread_s > 0.05, f"records did not serialize (spread={spread_s}s) — concurrency default was not 1"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_record_shape_engine_specific_fields(tmp_path, monkeypatch):
    """The camoufox-engine record carries engine="camoufox", landed_url,
    markdown_conversion_error, content_is_raw_html, acquisition_error (try_scrape_camoufox's own
    fact field, logged directly — None here since this meta doesn't set it) — and does NOT carry
    the chromium-only crawl4ai_* fields at all (absent, not null/false)."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "<html>raw</html>", _camoufox_meta(
            content_is_raw_html=True, markdown_conversion_error="Invalid IPv6 URL",
            landed_url="https://landed.test/a",
        )
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=1, engine="camoufox")

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["engine"] == "camoufox"
    assert r["landed_url"] == "https://landed.test/a"
    assert r["markdown_conversion_error"] == "Invalid IPv6 URL"
    assert r["content_is_raw_html"] is True
    assert r["acquisition_error"] is None
    for chromium_only_key in ("crawl4ai_success", "crawl4ai_error_message", "crawl4ai_attempts",
                              "crawl4ai_resolved_by", "crawl4ai_fallback_fetch_used"):
        assert chromium_only_key not in r


@pytest.mark.asyncio
async def test_scrape_all_chromium_record_shape_camoufox_fields_absent(tmp_path, monkeypatch):
    """The chromium-engine record does NOT carry the camoufox-only markdown_conversion_error/
    content_is_raw_html/acquisition_error fields at all (absent, not null/false) — symmetric with
    the test above."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["engine"] == "chromium"
    for camoufox_only_key in ("markdown_conversion_error", "content_is_raw_html", "acquisition_error"):
        assert camoufox_only_key not in r


@pytest.mark.asyncio
async def test_scrape_all_camoufox_acquisition_error_is_logged_as_its_own_fact(tmp_path, monkeypatch):
    """A hard acquisition failure (budget_exhausted/browser_missing/exception) is logged verbatim
    as its own fact, not collapsed into a computed verdict — try_scrape_camoufox already knows
    exactly which of the three it was; that specific value is what lands in the record, alongside
    the plain status_code=None/bytes=0 facts a total acquisition failure naturally produces."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "", _camoufox_meta(acquisition_error="browser_missing", status_code=None,
                                   landed_url=None)
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert results[0]["status_code"] is None
    assert results[0]["bytes"] == 0

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["acquisition_error"] == "browser_missing"


@pytest.mark.asyncio
async def test_scrape_all_camoufox_resolved_challenge_status_flows_through_as_recorded_fact(tmp_path, monkeypatch):
    """M2: try_scrape_camoufox now reports the LAST main-frame document response's status, not a
    stale challenge-page status. A meta shaped like a resolved Cloudflare challenge (status_code=200
    from the corrected acquisition primitive, document_status_chain=[403, 302, 200] as the fact
    trail) must flow through as the recorded http_status=200 — no special-casing of the chain
    anywhere in this module, it only ever reads meta['status_code'] and passes it straight to the
    log. The JSONL record also carries the chain field."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return ("# real page content" * 3,
                _camoufox_meta(status_code=200, document_status_chain=[403, 302, 200]))
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert results[0]["status_code"] == 200
    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    assert records[0]["http_status"] == 200
    assert records[0]["document_status_chain"] == [403, 302, 200]


# ---------------------------------------------------------------------------
# _onward_link_identity — the query/fragment-stripped comparison key onward-link collection uses.
# Deliberately NOT seed_feeders_scope.normalize_url (which keeps the query on purpose) — see the
# function's own docstring for why this file's worst case inverts that reasoning.
# ---------------------------------------------------------------------------

def test_onward_link_identity_strips_query_and_fragment():
    assert (_onward_link_identity("https://x.test/docs/guide?tab=2#section")
            == "https://x.test/docs/guide")


def test_onward_link_identity_lowercases_scheme_and_host():
    assert _onward_link_identity("HTTPS://X.TEST/docs") == "https://x.test/docs"


def test_onward_link_identity_collapses_query_variants_to_one_key():
    # The real motivating case: 50 scraped pages each linked the SAME login page with a different
    # returnTo= query string — a plain string-dedup kept all 50 distinct.
    a = _onward_link_identity("https://platform.claude.com/login?returnTo=%2Fdocs%2Fen%2Fa")
    b = _onward_link_identity("https://platform.claude.com/login?returnTo=%2Fdocs%2Fen%2Fb")
    assert a == b == "https://platform.claude.com/login"


def test_onward_link_identity_none_for_hostless_url():
    assert _onward_link_identity("mailto:someone@example.com") is None
    assert _onward_link_identity("javascript:void(0)") is None


# ---------------------------------------------------------------------------
# _extract_onward_links — union of crawl4ai's internal/external buckets, host_key-restricted to
# the page's own host, non-page extensions dropped, deduped within the page
# ---------------------------------------------------------------------------

class _FakeLinksResult:
    def __init__(self, internal=(), external=()):
        self.links = {"internal": list(internal), "external": list(external)}


def test_extract_onward_links_unions_internal_and_external_buckets():
    result = _FakeLinksResult(
        internal=[{"href": "https://x.test/a"}],
        external=[{"href": "https://x.test/b"}],
    )
    assert sorted(_extract_onward_links(result, "x.test")) == [
        "https://x.test/a", "https://x.test/b",
    ]


def test_extract_onward_links_restricts_to_page_host_www_apex_collapsed():
    result = _FakeLinksResult(internal=[
        {"href": "https://www.x.test/a"},   # same host, www. — kept (host_key collapses it)
        {"href": "https://other.test/b"},   # different host entirely — dropped
        {"href": "https://sub.x.test/c"},   # a child subdomain — dropped, not the same host
    ])
    assert _extract_onward_links(result, "x.test") == ["https://www.x.test/a"]


def test_extract_onward_links_drops_non_page_extensions():
    result = _FakeLinksResult(internal=[
        {"href": "https://x.test/docs/images/diagram.gif"},
        {"href": "https://x.test/docs/guide"},
    ])
    assert _extract_onward_links(result, "x.test") == ["https://x.test/docs/guide"]


def test_extract_onward_links_collapses_query_variant_duplicates_within_the_page():
    result = _FakeLinksResult(internal=[
        {"href": "https://x.test/login?returnTo=%2Fa"},
        {"href": "https://x.test/login?returnTo=%2Fb"},
    ])
    assert _extract_onward_links(result, "x.test") == ["https://x.test/login"]


def test_extract_onward_links_empty_when_result_has_no_links_attribute():
    class _NoLinks:
        pass
    assert _extract_onward_links(_NoLinks(), "x.test") == []


# ---------------------------------------------------------------------------
# _collect_onward_links — run-wide dedup, exclude the run's own input URLs, camoufox -> None
# ---------------------------------------------------------------------------

def test_collect_onward_links_excludes_urls_already_in_the_input_list():
    urls = ["https://x.test/a"]
    results = [{"links": ["https://x.test/a", "https://x.test/new"]}]
    assert _collect_onward_links(urls, results, "chromium") == ["https://x.test/new"]


def test_collect_onward_links_excludes_input_url_regardless_of_its_own_query_string():
    # The input URL carries a query string different from any exact discovered href — the SAME
    # normalization must apply to both sides for the comparison to mean anything.
    urls = ["https://x.test/docs/guide?utm_source=foo"]
    results = [{"links": ["https://x.test/docs/guide"]}]
    assert _collect_onward_links(urls, results, "chromium") == []


def test_collect_onward_links_dedups_across_pages_order_preserving():
    urls = ["https://x.test/a", "https://x.test/b"]
    results = [
        {"links": ["https://x.test/new1", "https://x.test/shared"]},
        {"links": ["https://x.test/shared", "https://x.test/new2"]},
    ]
    assert _collect_onward_links(urls, results, "chromium") == [
        "https://x.test/new1", "https://x.test/shared", "https://x.test/new2",
    ]


def test_collect_onward_links_ignores_results_with_no_links_key():
    # A rescued/exception-path result never carries a 'links' key at all (see
    # pipe_scraper_acquisition.py's own Gotchas) — must not raise, contributes nothing.
    urls = ["https://x.test/a"]
    results = [{"url": "https://x.test/b"}, {"links": ["https://x.test/new"]}]
    assert _collect_onward_links(urls, results, "chromium") == ["https://x.test/new"]


def test_collect_onward_links_returns_none_for_camoufox_engine():
    urls = ["https://x.test/a"]
    results = [{"links": ["https://x.test/new"]}]  # even if a result somehow carried links
    assert _collect_onward_links(urls, results, "camoufox") is None


# ---------------------------------------------------------------------------
# _write_onward_links_file — real /tmp write (same convention _write_tmp_report already uses),
# cleaned up after each test
# ---------------------------------------------------------------------------

@pytest.fixture
def onward_links_scratch_path():
    path = Path("/tmp/pipe_scraper_test_onward_domain_scrape_links.txt")
    yield path
    path.unlink(missing_ok=True)


def test_write_onward_links_file_writes_one_url_per_line(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain",
                              ["https://x.test/a", "https://x.test/b"])
    assert onward_links_scratch_path.read_text(encoding="utf-8") == "https://x.test/a\nhttps://x.test/b\n"


def test_write_onward_links_file_writes_empty_file_for_empty_list(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain", [])
    assert onward_links_scratch_path.read_text(encoding="utf-8") == ""


def test_write_onward_links_file_writes_nothing_when_none(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain", None)
    assert not onward_links_scratch_path.exists()


# ---------------------------------------------------------------------------
# _print_summary — the new onward-link count wording, and the explicit camoufox distinction
# ---------------------------------------------------------------------------

def _summary_result(status_code=200, byte_count=100):
    return {"status_code": status_code, "bytes": byte_count}


def test_print_summary_reports_onward_link_count(capsys):
    _print_summary([_summary_result()], 1.0, ["https://x.test/a", "https://x.test/b"])
    out = capsys.readouterr().out
    assert "2 onward links collected" in out


def test_print_summary_reports_camoufox_cannot_collect_not_a_bare_zero(capsys):
    _print_summary([_summary_result()], 1.0, None)
    out = capsys.readouterr().out
    assert "onward links not collected (camoufox engine)" in out
    assert "0 onward links" not in out


# ---------------------------------------------------------------------------
# Wiring: _scrape_one populates 'links' from the real crawl4ai result; the camoufox executor never
# produces the key at all — the engine-scope distinction this milestone requires
# ---------------------------------------------------------------------------

class _FakeLinksCrawler:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        return _FakeResult(raw_markdown="x" * 500, links={
            "internal": [{"href": "https://x.test/new"}, {"href": "https://other.test/x"}],
            "external": [],
        })


@pytest.mark.asyncio
async def test_scrape_one_populates_links_key_from_the_real_result(tmp_path, monkeypatch):
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeLinksCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                              download_delay=0.01, concurrency_per_domain=8)

    assert results[0]["links"] == ["https://x.test/new"]  # other.test dropped, off-host


@pytest.mark.asyncio
async def test_scrape_one_camoufox_never_produces_a_links_key(tmp_path, monkeypatch):
    """A camoufox run must not be able to look like a chromium run that found nothing — the key
    itself is absent, never present-and-empty."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "# real markdown, non-trivial content", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert "links" not in results[0]
