"""Tests for query_logger + per-engine stats capture in search_web_workflow.

Runs without network: mock engines return fixed results immediately.
Uses tmp_path (via WEBSEARCH_QUERY_LOG_PATH) so production log is never touched.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_engine_with_reason(
    name: str, results: list, delay: float = 0.0, empty_reason: str | None = None, diagnosis: dict | None = None,
    partial_facts: dict | None = None,
):
    """Mock engine matching the current _engine_with_timing interface:
    engine.search_with_reason(query, language, max_results, partial) -> (results, empty_reason, diagnosis).
    partial_facts, if given, is written into the caller-supplied partial dict before the delay —
    simulating a poll-loop checkpoint reached before a cancellation."""
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


# Current-time ts — log_janitor prunes lines with a "ts" older than the 14-day retention window on every write.
def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _fake_result(url: str = "https://example.com", title: str = "T", snippet: str = "S", engine: str = "mock"):
    from src.search.result import SearchResult
    return SearchResult(url=url, title=title, snippet=snippet, engine=engine, position=1)


# ---------------------------------------------------------------------------
# test_log_query_writes_jsonl
# ---------------------------------------------------------------------------

def test_log_query_writes_jsonl(tmp_path, monkeypatch):
    """log_query appends exactly one JSONL line with the provided record."""
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
    """Two log_query calls produce two JSONL lines."""
    log_file = tmp_path / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(log_file))

    import src.search.query_logger as ql
    ql.log_query({"ts": _now_ts(), "query": "a"})
    ql.log_query({"ts": _now_ts(), "query": "b"})

    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["query"] == "a"
    assert json.loads(lines[1])["query"] == "b"


def test_log_query_fail_soft(tmp_path, caplog, monkeypatch):
    """log_query does NOT raise when write fails — logs a warning instead."""
    import src.search.query_logger as ql

    # Create a FILE where the parent dir should be, so mkdir fails
    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file")
    bad_path = blocker / "nested" / "query_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", str(bad_path))

    with caplog.at_level(logging.WARNING, logger="src.search.query_logger"):
        ql.log_query({"query": "should not crash"})

    assert any("query_log write failed" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# test_engine_with_timing (unit tests, no workflow)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_with_timing_ok():
    """_engine_with_timing returns (results, rate_wait_ms, search_ms, OK, None) on success."""
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
    """_engine_with_timing returns TIMEOUT_WATCHDOG + drop_reason when engine exceeds watchdog.
    diagnosis stays None when the engine never wrote anything into partial before cancellation —
    the same "don't invent a fact" rule the guessed-verdict-removal milestone settled."""
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
    """A poll-loop checkpoint reached before the watchdog fires survives the cancellation, merged
    with diagnosis_partial=True — the mechanism this milestone adds. asyncio.wait_for cancels the
    engine's own Task, not _engine_with_timing itself, so a mutable dict handed to the engine by
    reference and written into before that cancellation is the only thing that can still be read
    afterward; this proves exactly that channel."""
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
    """_engine_with_timing returns EMPTY status when engine returns []."""
    from src.search.search_web import _engine_with_timing

    empty = _make_mock_engine_with_reason("empty_eng", [])

    results, _, _, status, drop_reason, diagnosis = await _engine_with_timing(
        empty, "query", "en", 10, timeout=3.6
    )

    assert results == []
    assert status == "EMPTY"
    assert drop_reason is None
    assert diagnosis is None


# ---------------------------------------------------------------------------
# test_search_web_workflow_writes_log (integration, no network)
# ---------------------------------------------------------------------------

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
    """search_web_workflow writes 2 JSONL records — "engine_run" (from _query_engines_concurrent)
    then "workflow_summary" (from _build_query_log_entry); this test checks the workflow_summary
    one's full field shape (current shape: record_type/ts/query/language/engines_requested/
    engines_excluded/total_wall_ms/bottleneck_engine/engines/search_key — no preview pipeline,
    that was removed from search_web_workflow)."""
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
    assert rec["engines_excluded"] == {}


@pytest.mark.asyncio
async def test_search_web_workflow_propagates_diagnosis_into_both_records(tmp_path, monkeypatch):
    """A browser-engine-shaped mock returning (results, empty_reason, diagnosis) has that diagnosis
    dict land unchanged in engines[name]['diagnosis'] for BOTH the engine_run record (written by
    _query_engines_concurrent) and the workflow_summary record (written by _build_query_log_entry).
    empty_reason is None here — every real engine's search_with_reason returns None as of the
    guessed-verdict-removal milestone — so status falls through to the generic "EMPTY"; the point
    this test guards is that an empty result still carries its observation snapshot, not just the
    bare status string. The OK-status engine's diagnosis stays None."""
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


# ---------------------------------------------------------------------------
# record_type = "drilldown" — schema + search_key correlation
# ---------------------------------------------------------------------------

def test_log_query_accepts_drilldown_record_shape(tmp_path, monkeypatch):
    """log_query writes a well-shaped drilldown record — the generic writer, exercised with the
    new record_type's fields (mirrors test_log_query_writes_jsonl's pattern for engine_run/
    workflow_summary)."""
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
    """workflow_summary's search_key equals the real cache.cache_key(...) output for the same
    call — the exact join value a drilldown record must reproduce to correlate back to this
    search. Real engine fanout mocked (no network); cache_write mocked (no real cache-dir write);
    cache_key itself is NOT mocked — it must be the real function for this assertion to mean
    anything."""
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


# ---------------------------------------------------------------------------
# cli.py's _log_drilldown — real function, isolated subprocess (importing cli.py in-process
# reconfigures the root logger via logging.basicConfig and registers an atexit chrome-kill hook;
# side effects that must not bleed into the rest of this test suite)
# ---------------------------------------------------------------------------

def test_log_drilldown_all_cache_status_and_pool_combinations(tmp_path):
    """Real cli.py._log_drilldown, exercised for the sub-cases that matter: a hit with the engine
    present (real urls, result_count matches); a hit with the engine absent from pools
    (engine_in_pools=False, urls empty — distinguishing 'excluded upstream' from 'zero results');
    and a cache-miss-then-search-failure (cache_status names the failure explicitly rather than
    looking like an ordinary hit)."""
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
