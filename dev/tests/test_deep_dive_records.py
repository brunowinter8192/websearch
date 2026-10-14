# INFRASTRUCTURE
import json
from pathlib import Path

import pytest

from src.crawler import pipe_scraper
from src.crawler.deep_dive_logger import log_deep_dive
from src.crawler.deep_dive_records import host_of, log_discovery_record
from src.crawler.discovery import DiscoveredURL, DiscoveryResult
from dev.tests._pipe_scraper_fakes import _FakeCrawler, _install_fake_pacing


# FUNCTIONS

def test_log_deep_dive_appends_record_with_code_version(tmp_path, monkeypatch):
    log_file = tmp_path / "deep_dive_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_DEEP_DIVE_LOG_PATH", str(log_file))

    log_deep_dive({"ts": "2026-10-15T10:00:00.000Z", "record_type": "discovery"})
    log_deep_dive({"ts": "2026-10-15T10:00:01.000Z", "record_type": "closing"})

    records = _read(log_file)
    assert [r["record_type"] for r in records] == ["discovery", "closing"]
    assert all(r["code_version"] for r in records)


def test_discovery_record_holds_counts_by_source_and_failed_feeders(tmp_path, monkeypatch):
    log_file = tmp_path / "deep_dive_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_DEEP_DIVE_LOG_PATH", str(log_file))
    result = DiscoveryResult(
        urls=[DiscoveredURL("https://www.sre.google/", "seed"), DiscoveredURL("https://sre.google/a", "sitemap"),
              DiscoveredURL("https://sre.google/b", "sitemap")],
        wall_s=12.34, failed_feeders={"navtree": "boom"}, dropped=2,
    )

    log_discovery_record("https://www.sre.google/", "/tmp/sre.google_urls.txt", result)

    record = _read(log_file)[0]
    assert record["record_type"] == "discovery"
    assert record["host"] == "sre.google"
    assert record["total"] == 3
    assert record["by_source"] == {"seed": 1, "sitemap": 2}
    assert record["failed_feeders"] == {"navtree": "boom"}
    assert record["dropped"] == 2
    assert record["wall_s"] == 12.3
    assert record["url_file"] == "/tmp/sre.google_urls.txt"


def test_failed_discovery_is_recorded_with_its_error(tmp_path, monkeypatch):
    log_file = tmp_path / "deep_dive_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_DEEP_DIVE_LOG_PATH", str(log_file))

    log_discovery_record("not a url", "/tmp/x_urls.txt", DiscoveryResult(ok=False, error="seed_url has no host: 'not a url'"))

    record = _read(log_file)[0]
    assert record["ok"] is False
    assert record["error"] == "seed_url has no host: 'not a url'"
    assert record["host"] is None
    assert record["total"] == 0


def test_host_of_drops_www_and_lowercases():
    assert host_of("https://WWW.Example.com/a") == "example.com"


@pytest.mark.asyncio
async def test_scrape_round_record_links_to_pipe_records_by_run_id(tmp_path, monkeypatch):
    pipe_log = tmp_path / "pipe_scrape_log.jsonl"
    dive_log = tmp_path / "deep_dive_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(pipe_log))
    monkeypatch.setenv("WEBSEARCH_DEEP_DIVE_LOG_PATH", str(dive_log))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeCrawler)
    _install_fake_pacing(monkeypatch)
    urls = ["https://x.test/a", "https://x.test/b", "https://x.test/fail"]

    await pipe_scraper.scrape_urls_workflow(urls, tmp_path / "out", 0.01, 8, url_file="/tmp/x.test_urls_culled.txt")

    round_record = _read(dive_log)[0]
    pipe_run_ids = {r["run_id"] for r in _read(pipe_log)}
    assert round_record["record_type"] == "scrape_round"
    assert pipe_run_ids == {round_record["run_id"]}
    assert round_record["host"] == "x.test"
    assert round_record["urls_requested"] == 3
    assert round_record["files_written"] == 2
    assert round_record["bytes"] == 1000
    assert round_record["onward_links"] == 0
    assert round_record["url_file"] == "/tmp/x.test_urls_culled.txt"
    assert round_record["output_dir"] == str(tmp_path / "out")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
