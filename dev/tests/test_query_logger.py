import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_engine_with_reason(
    name: str, results: list, delay: float = 0.0, empty_reason: str | None = None, diagnosis: dict | None = None,
    partial_facts: dict | None = None,
):
    eng = MagicMock()
    eng.name = name

    async def _search_with_reason(query, language, max_results, partial=None):
        if partial_facts is not None and partial is not None:
            partial.update(partial_facts)
        if delay:
            await asyncio.sleep(delay)
        return results, empty_reason, diagnosis

    eng.search_with_reason = _search_with_reason
    return eng


async def _fake_prewarm_browser() -> None:
    return None


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _fake_result(url: str = "https://example.com", title: str = "T", snippet: str = "S", engine: str = "mock"):
    from src.search.result import SearchResult
    return SearchResult(url=url, title=title, snippet=snippet, engine=engine, position=1)


def test_log_query_writes_jsonl(tmp_path, monkeypatch):
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    import src.search.query_logger as ql
    ql.log_query({"ts": _now_ts(), "query": "hello", "total_wall_ms": 42})

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["query"] == "hello"
    assert record["total_wall_ms"] == 42


def test_log_query_appends(tmp_path, monkeypatch):
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    import src.search.query_logger as ql
    ql.log_query({"ts": _now_ts(), "query": "a"})
    ql.log_query({"ts": _now_ts(), "query": "b"})

    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["query"] == "a"
    assert json.loads(lines[1])["query"] == "b"


def test_log_query_unwritable_path_raises(tmp_path, monkeypatch):
    import src.search.query_logger as ql

    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file")
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(blocker / "nested" / "query_log.jsonl"))

    with pytest.raises(OSError):
        ql.log_query({"query": "must not be swallowed"})


@pytest.mark.asyncio
async def test_engine_with_timing_ok():
    from src.search.search_web import _engine_with_timing

    r = _fake_result("https://x.com", engine="fast")
    fast = _make_mock_engine_with_reason("fast", [r])

    results, rate_wait_ms, search_ms, status, drop_reason, diagnosis = await _engine_with_timing(
        fast, "query", "en", 10, timeout=3.6
    )

    assert len(results) == 1
    assert status == "OK"
    assert drop_reason is None
    assert diagnosis is None
    assert isinstance(rate_wait_ms, int) and rate_wait_ms >= 0
    assert isinstance(search_ms, int) and search_ms >= 0


@pytest.mark.asyncio
async def test_engine_with_timing_timeout():
    from src.search.search_web import _engine_with_timing

    slow = _make_mock_engine_with_reason("slow_eng", [], delay=5.0)

    results, rate_wait_ms, search_ms, status, drop_reason, diagnosis = await _engine_with_timing(
        slow, "query", "en", 10, timeout=0.05
    )

    assert results == []
    assert status == "TIMEOUT_WATCHDOG"
    assert drop_reason is not None and "watchdog" in drop_reason
    assert diagnosis is None
    assert isinstance(rate_wait_ms, int)
    assert isinstance(search_ms, int)


@pytest.mark.asyncio
async def test_engine_with_timing_timeout_preserves_facts_written_before_cancellation():
    from src.search.search_web import _engine_with_timing

    slow = _make_mock_engine_with_reason(
        "slow_eng", [], delay=5.0,
        partial_facts={"containers_found": False, "pow_link": True, "http_status": 429},
    )

    results, rate_wait_ms, search_ms, status, drop_reason, diagnosis = await _engine_with_timing(
        slow, "query", "en", 10, timeout=0.05
    )

    assert results == []
    assert status == "TIMEOUT_WATCHDOG"
    assert diagnosis == {
        "containers_found": False, "pow_link": True, "http_status": 429, "diagnosis_partial": True,
    }


@pytest.mark.asyncio
async def test_engine_with_timing_empty():
    from src.search.search_web import _engine_with_timing

    empty = _make_mock_engine_with_reason("empty_eng", [])

    results, _, _, status, drop_reason, diagnosis = await _engine_with_timing(
        empty, "query", "en", 10, timeout=3.6
    )

    assert results == []
    assert status == "EMPTY"
    assert drop_reason is None
    assert diagnosis is None


async def _run_search_web_workflow_and_get_log_lines(tmp_path, monkeypatch, mock_engines, default_engines,
                                                     query="test query"):
    from src.search import search_web
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    with (
        patch.object(search_web, "ENGINES", mock_engines),
        patch.object(search_web, "_DEFAULT_ENGINES", default_engines),
        patch.object(search_web, "cache_write"),
        patch.object(search_web, "_prewarm_browser", _fake_prewarm_browser),
    ):
        await search_web.search_web_workflow(query, language="en")

    return log_file.read_text().splitlines()


@pytest.mark.asyncio
async def test_search_web_workflow_writes_log(tmp_path, monkeypatch):
    result_a = _fake_result("https://a.com", engine="google")
    result_b = _fake_result("https://b.com", engine="duckduckgo")

    mock_engines = {
        "google": _make_mock_engine_with_reason("google", [result_a]),
        "duckduckgo": _make_mock_engine_with_reason("duckduckgo", [result_b]),
    }

    lines = await _run_search_web_workflow_and_get_log_lines(
        tmp_path, monkeypatch, mock_engines, {"google", "duckduckgo"})

    assert len(lines) == 2, f"Expected 2 log lines (engine_run + workflow_summary), got {len(lines)}: {lines}"

    records = [json.loads(l) for l in lines]
    summary_records = [r for r in records if r["record_type"] == "workflow_summary"]
    assert len(summary_records) == 1
    rec = summary_records[0]

    assert rec["query"] == "test query"
    assert rec["language"] == "en"
    assert "ts" in rec and rec["ts"].endswith("Z")
    assert rec["total_wall_ms"] >= 0
    assert set(rec["engines_requested"]) == {"google", "duckduckgo"}
    assert "google" in rec["engines"]
    assert "duckduckgo" in rec["engines"]

    for eng_name, stats in rec["engines"].items():
        assert "rate_wait_ms" in stats, f"{eng_name} missing rate_wait_ms"
        assert "search_ms" in stats, f"{eng_name} missing search_ms"
        assert "result_count" in stats, f"{eng_name} missing result_count"
        assert "drop_reason" in stats, f"{eng_name} missing drop_reason"
        assert stats["status"] == "OK", f"{eng_name} bad status: {stats['status']}"

    assert rec["bottleneck_engine"] in ("google", "duckduckgo")
    assert "search_key" in rec
    assert "engines_excluded" not in rec


@pytest.mark.asyncio
async def test_search_web_workflow_propagates_diagnosis_into_both_records(tmp_path, monkeypatch):
    from src.search import search_web
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    diag = {"marker": "captcha", "title": "Attention Required", "url": "https://example.com/blocked", "ready_state": "complete"}
    result_a = _fake_result("https://a.com", engine="google")
    mock_engines = {
        "google": _make_mock_engine_with_reason("google", [result_a]),
        "duckduckgo": _make_mock_engine_with_reason("duckduckgo", [], empty_reason=None, diagnosis=diag),
    }

    with (
        patch.object(search_web, "ENGINES", mock_engines),
        patch.object(search_web, "_DEFAULT_ENGINES", {"google", "duckduckgo"}),
        patch.object(search_web, "cache_write"),
        patch.object(search_web, "_prewarm_browser", _fake_prewarm_browser),
    ):
        await search_web.search_web_workflow("test query", language="en")

    records = [json.loads(l) for l in log_file.read_text().splitlines()]
    for rec in records:
        assert rec["engines"]["google"]["diagnosis"] is None
        assert rec["engines"]["duckduckgo"]["diagnosis"] == diag
        assert rec["engines"]["duckduckgo"]["status"] == "EMPTY"


def test_log_query_accepts_drilldown_record_shape(tmp_path, monkeypatch):
    import src.search.query_logger as ql
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    ql.log_query({
        "record_type": "drilldown", "ts": _now_ts(),
        "query": "fritzbox 7510", "language": "en", "engine": "google",
        "search_key": "abc123def456", "cache_status": "hit", "engine_in_pools": True,
        "result_count": 2, "urls": ["https://a.com", "https://b.com"],
    })

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["record_type"] == "drilldown"
    assert rec["search_key"] == "abc123def456"
    assert rec["urls"] == ["https://a.com", "https://b.com"]


@pytest.mark.asyncio
async def test_search_web_workflow_writes_search_key_matching_cache_key(tmp_path, monkeypatch):
    from src.search import search_web
    from src.search.cache import cache_key as real_cache_key
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    result_a = _fake_result("https://a.com", engine="google")
    mock_engines = {"google": _make_mock_engine_with_reason("google", [result_a])}

    with (
        patch.object(search_web, "ENGINES", mock_engines),
        patch.object(search_web, "_DEFAULT_ENGINES", {"google"}),
        patch.object(search_web, "cache_write"),
        patch.object(search_web, "_prewarm_browser", _fake_prewarm_browser),
    ):
        await search_web.search_web_workflow("test query", language="en")

    lines = log_file.read_text().splitlines()
    records = [json.loads(l) for l in lines]
    summary_records = [r for r in records if r["record_type"] == "workflow_summary"]
    assert len(summary_records) == 1
    rec = summary_records[0]
    expected_key = real_cache_key("test query", "en", None, None)
    assert rec["search_key"] == expected_key


def test_log_drilldown_all_cache_status_and_pool_combinations(tmp_path):
    import os
    import subprocess
    import sys

    log_file = tmp_path / "query_log.jsonl"
    repo_root = Path(__file__).parent.parent.parent
    script = f"""
import sys
sys.path.insert(0, {str(repo_root)!r})
import cli
cli._log_drilldown("fritzbox 7510", "en", "google", "searchkey123", "hit", True,
                    ["https://a.com", "https://b.com"])
cli._log_drilldown("fritzbox 7510", "en", "obscure_engine", "searchkey123", "hit", False, [])
cli._log_drilldown("never searched", "en", "google", "searchkey999",
                    "miss_then_search_failed", False, [])
"""
    env = {**os.environ, "WEBSEARCH_QUERY_LOG_PATH": str(log_file)}
    result = subprocess.run([sys.executable, "-c", script], cwd=repo_root, env=env,
                             capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    lines = log_file.read_text().splitlines()
    assert len(lines) == 3
    recs = [json.loads(l) for l in lines]

    hit_with_urls = recs[0]
    assert hit_with_urls["cache_status"] == "hit"
    assert hit_with_urls["engine_in_pools"] is True
    assert hit_with_urls["result_count"] == 2
    assert hit_with_urls["urls"] == ["https://a.com", "https://b.com"]
    assert hit_with_urls["search_key"] == "searchkey123"

    hit_engine_absent = recs[1]
    assert hit_engine_absent["engine_in_pools"] is False
    assert hit_engine_absent["result_count"] == 0
    assert hit_engine_absent["urls"] == []

    miss_failed = recs[2]
    assert miss_failed["cache_status"] == "miss_then_search_failed"
    assert miss_failed["engine_in_pools"] is False
    assert miss_failed["urls"] == []
