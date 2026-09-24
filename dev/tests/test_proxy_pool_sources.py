import json

from src.news.engine.proxy_pool.janitor import (
    _compute_stats,
    _group_pool_sources,
    _write_md,
)
from dev.tests._proxy_pool_fakes import _attempt, _write_and_read_md


def _md(tmp_path, events, target=10, done=5):
    return _write_and_read_md(_compute_stats, _write_md, tmp_path, events, target, done)


def test_record_pool_source_writes_jsonl_event(tmp_path):
    from src.news.engine.proxy_pool.logger import AcquireLogger

    log_dir = tmp_path / "logs"
    logger  = AcquireLogger(total_urls=0, log_dir=log_dir)
    logger.record_pool_source("https://raw.githubusercontent.com/monosans/proxies.json", True, 4521)
    logger.record_pool_source("https://raw.githubusercontent.com/r00tee/Https.txt", False, 0)
    logger.close()

    lines  = list(log_dir.iterdir())[0].read_text().splitlines()
    events = [json.loads(l) for l in lines]

    assert events[0]["event"] == "pool_source"
    assert events[0]["url"]   == "https://raw.githubusercontent.com/monosans/proxies.json"
    assert events[0]["ok"]    is True
    assert events[0]["count"] == 4521
    assert "ts" in events[0]

    assert events[1]["ok"]    is False
    assert events[1]["count"] == 0


def _pool_source(url: str, ok: bool, count: int, ts: str = "2026-01-01T00:00:00Z") -> dict:
    return {"event": "pool_source", "url": url, "ok": ok, "count": count, "ts": ts}


def _pool_refresh(size: int, ts: str = "2026-01-01T00:00:00Z") -> dict:
    return {"event": "pool_refresh", "size": size, "ts": ts}


def test_group_pool_sources_single_refresh():
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src1.com", True,  50, "2026-01-01T00:00:01Z"),
        _pool_source("https://src2.com", False,  0, "2026-01-01T00:00:02Z"),
    ]
    batches = _group_pool_sources(events)
    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0]["url"] == "https://src1.com"
    assert batches[0][1]["ok"] is False


def test_group_pool_sources_two_refreshes():
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src1.com", True, 50, "2026-01-01T00:00:01Z"),
        _attempt("http://p1:1", "https://target.com", "2026-01-01T00:05:00Z"),
        _pool_refresh(90, "2026-01-01T01:00:00Z"),
        _pool_source("https://src1.com", True, 48, "2026-01-01T01:00:01Z"),
        _pool_source("https://src2.com", False,  0, "2026-01-01T01:00:02Z"),
    ]
    batches = _group_pool_sources(events)
    assert len(batches) == 2
    assert len(batches[0]) == 1
    assert len(batches[1]) == 2


def test_group_pool_sources_empty_events():
    events = [_attempt("http://p1:1", "https://t.com", "2026-01-01T00:00:01Z")]
    batches = _group_pool_sources(events)
    assert batches == []


def test_job_md_source_section_present(tmp_path):
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://raw.githubusercontent.com/monosans/proxies.json", True,  50, "2026-01-01T00:00:01Z"),
        _pool_source("https://raw.githubusercontent.com/r00tee/Https.txt",      False,  0, "2026-01-01T00:00:02Z"),
    ]
    md = _md(tmp_path, events)
    assert "## Pool source breakdown" in md
    assert "### Refresh 0 (startup)"  in md
    assert "monosans"  in md
    assert "r00tee"    in md
    assert "| ok |"    in md
    assert "| fail |"  in md


def test_job_md_source_section_dedup_note(tmp_path):
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/a", True, 50, "2026-01-01T00:00:01Z"),
    ]
    md = _md(tmp_path, events)
    assert "cross-repo dedup" in md or "deduped" in md


def test_job_md_source_section_two_refreshes(tmp_path):
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/a", True, 50, "2026-01-01T00:00:01Z"),
        _pool_refresh(90,  "2026-01-01T01:00:00Z"),
        _pool_source("https://src.com/a", True, 48, "2026-01-01T01:00:01Z"),
    ]
    md = _md(tmp_path, events)
    assert "### Refresh 0 (startup)" in md
    assert "### Refresh 1"           in md


def test_job_md_source_section_absent_without_pool_source_events(tmp_path):
    events = [
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:01:00Z"),
    ]
    md = _md(tmp_path, events)
    assert "## Pool source breakdown" not in md


def test_job_md_source_count_values(tmp_path):
    events = [
        _attempt("http://p1:1", "https://t.com/a", "2026-01-01T00:00:00Z"),
        _pool_refresh(100, "2026-01-01T00:00:00Z"),
        _pool_source("https://src.com/big",  True, 7832, "2026-01-01T00:00:01Z"),
        _pool_source("https://src.com/dead", False,   0, "2026-01-01T00:00:02Z"),
    ]
    md = _md(tmp_path, events)
    assert "7832" in md
    assert "| fail | 0 |" in md


def test_record_pool_source_writes_error_when_given(tmp_path):
    from src.news.engine.proxy_pool.logger import AcquireLogger

    logger = AcquireLogger(total_urls=0, log_dir=tmp_path / "logs")
    logger.record_pool_source("https://a.test", False, 0, "ConnectError")
    logger.record_attempt("http", "h:1", "https://t.test", False, "http_403")
    logger.record_attempt("http", "h:1", "https://t.test", True)
    logger.close()
    events = [json.loads(l) for l in list((tmp_path / "logs").iterdir())[0].read_text().splitlines()]
    assert events[0]["error"] == "ConnectError"
    assert events[1]["reason"] == "http_403"
    assert "reason" not in events[2]
