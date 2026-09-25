import json
from datetime import datetime, timezone

import pytest

from src.crawler import pipe_scraper
from src.crawler import pipe_scraper_config
from src.crawler import pipe_scraper_acquisition
from src.crawler.pipe_scrape_logger import log_pipe_scrape
from dev.tests._pipe_scraper_fakes import _now_ts, _FakeResult, _FakeCrawler, _install_fake_pacing


def test_log_pipe_scrape_writes_jsonl_record(tmp_path, monkeypatch):
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
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    for i in range(3):
        log_pipe_scrape({"ts": _now_ts(), "run_id": "r", "url": f"https://x.test/{i}", "domain": "x.test",
                          "http_status": 200, "bytes": 1, "wall_ms": 1,
                          "config_hash": "h", "config": {}})

    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 3


def test_log_pipe_scrape_unwritable_path_raises(tmp_path, monkeypatch):
    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file")
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(blocker / "nested" / "pipe_scrape_log.jsonl"))

    with pytest.raises(OSError):
        log_pipe_scrape({"ts": _now_ts(), "run_id": "r", "url": "https://x.test", "domain": "x.test",
                          "http_status": 200, "bytes": 1, "wall_ms": 1,
                          "config_hash": "h", "config": {}})


@pytest.mark.asyncio
async def test_scrape_all_logs_shared_run_id_across_urls(tmp_path, monkeypatch):
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
async def test_scrape_all_threads_headed_into_build_configs(tmp_path, monkeypatch):
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    captured = []
    real_build_configs = pipe_scraper_config.build_configs
    def _capturing_build_configs(headed=False):
        captured.append(headed)
        return real_build_configs(headed=headed)
    monkeypatch.setattr(pipe_scraper, "build_configs", _capturing_build_configs)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=8, headed=True)

    assert captured == [True]


@pytest.mark.asyncio
async def test_scrape_all_default_headed_is_false(tmp_path, monkeypatch):
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    captured = []
    real_build_configs = pipe_scraper_config.build_configs
    def _capturing_build_configs(headed=False):
        captured.append(headed)
        return real_build_configs(headed=headed)
    monkeypatch.setattr(pipe_scraper, "build_configs", _capturing_build_configs)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                    concurrency_per_domain=8)

    assert captured == [False]


@pytest.mark.asyncio
async def test_scrape_one_exception_becomes_tripwire_record(tmp_path, monkeypatch):
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
    assert by_url_result["https://x.test/a"]["status_code"] == 200

    assert not (output_dir / pipe_scraper_acquisition.url_to_filename("https://x.test/fail")).exists()

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    by_url_record = {r["url"]: r for r in records}
    fail_record = by_url_record["https://x.test/fail"]
    assert fail_record["http_status"] is None
    assert fail_record["bytes"] == 0
    assert "pipe_fallback_used" not in fail_record
    assert "pipe_fallback_resolved" not in fail_record
    assert fail_record["error"] == "Exception: simulated network failure"
    assert by_url_record["https://x.test/a"]["error"] is None


@pytest.mark.asyncio
async def test_scrape_all_camoufox_executor_exception_propagates(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(tmp_path / "log.jsonl"))

    async def _boom(url, block_images=False):
        raise RuntimeError("executor bug")
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _boom)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with pytest.raises(RuntimeError, match="executor bug"):
        await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                        concurrency_per_domain=1, engine="camoufox")


@pytest.mark.asyncio
async def test_scrape_one_ts_reflects_request_start_not_queue_time(tmp_path, monkeypatch):
    clock = _install_fake_pacing(monkeypatch)
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
    assert clock.sleeps == pytest.approx([0.05] * 5)
    assert spread_s == pytest.approx(0.25, abs=0.002), f"ts spread wrong ({spread_s}s) for a gated 6-URL/concurrency=1 run"


@pytest.mark.asyncio
async def test_scrape_all_records_carry_config_hash_and_config(tmp_path, monkeypatch):
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
    assert records[0]["config"]["enable_stealth"] is True
    assert records[0]["config"]["simulate_user"] is True
    assert records[0]["config"]["override_navigator"] is True
    assert records[0]["config"]["magic"] is False
    assert records[0]["config"]["remove_consent_popups"] is True


class _FakeRedirectingCrawler:
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
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                    download_delay=0.01, concurrency_per_domain=8)

    records = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines()]
    r = records[0]
    assert r["landed_url"] is None
    assert "same_target" not in r
