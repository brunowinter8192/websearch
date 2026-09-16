"""Tests for pipe_scraper's per-URL JSONL log (pipe_scrape_logger.py) and the config stamp
it carries.

Runs without a browser: _scrape_all's AsyncWebCrawler is patched with a fake crawler returning
synthetic results, isolating the logging path from the real network/browser call.
"""
import json
from datetime import datetime, timezone

import pytest

from src.crawler import pipe_scraper
from src.crawler import pipe_scraper_config
from src.crawler import pipe_scraper_acquisition
from src.crawler.pipe_scrape_logger import log_pipe_scrape
from dev.tests._pipe_scraper_fakes import _now_ts, _FakeResult, _FakeCrawler


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


# ---------------------------------------------------------------------------
# _scrape_all(headed=...): M3 — the -g flag's wiring into _build_configs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_all_threads_headed_into_build_configs(tmp_path, monkeypatch):
    """_scrape_all's own headed parameter reaches _build_configs unchanged — the wiring this
    milestone adds, proven the same way the camoufox lane's block_images wiring already is."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    captured = []
    real_build_configs = pipe_scraper_config._build_configs
    def _capturing_build_configs(headed=False):
        captured.append(headed)
        return real_build_configs(headed=headed)
    monkeypatch.setattr(pipe_scraper, "_build_configs", _capturing_build_configs)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=8, headed=True)

    assert captured == [True]


@pytest.mark.asyncio
async def test_scrape_all_default_headed_is_false(tmp_path, monkeypatch):
    """headed omitted at the _scrape_all level -> False reaches _build_configs, today's
    behavior unchanged."""
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    captured = []
    real_build_configs = pipe_scraper_config._build_configs
    def _capturing_build_configs(headed=False):
        captured.append(headed)
        return real_build_configs(headed=headed)
    monkeypatch.setattr(pipe_scraper, "_build_configs", _capturing_build_configs)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=8)

    assert captured == [False]


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
