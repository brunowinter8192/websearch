import logging

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError, Timeout

from src.search.engines import google as google_mod
from src.search.engines.google import _build_results, _resolve_one, _resolve_urls
from src.search.result import SearchResult
from dev.search_pipeline._google_fixture import (
    ResultSpec, start_fixture_server, stop_fixture_server, goto_url,
)


def _spec(token, behavior, target=None):
    return ResultSpec(title=token, snippet="", date=None, token=token, behavior=behavior, target=target)


async def _run(specs):
    server, thread, port = start_fixture_server(specs)
    try:
        items = [{"url": goto_url(port, s.token), "title": s.title, "snippet": "", "date": None} for s in specs]
        return await _resolve_urls(_build_results(items, max_results=10))
    finally:
        stop_fixture_server(server, thread)


class _RaisingSession:
    def __init__(self, exc):
        self.exc = exc

    async def get(self, *args, **kwargs):
        raise self.exc


def _result():
    return SearchResult(url="http://127.0.0.1:1/goto?url=x", title="t", snippet="", engine="google", position=1)


@pytest.mark.asyncio
async def test_non_302_is_counted_with_status():
    resolved, stats = await _run([_spec("a", "ok", "ta"), _spec("b", "bad_status")])
    assert len(resolved) == 1
    assert stats == {"found": 2, "resolved": 1, "dropped": 1, "reasons": {"non_302_404": 1}}


@pytest.mark.asyncio
async def test_missing_location_is_counted():
    resolved, stats = await _run([_spec("a", "no_location")])
    assert resolved == []
    assert stats == {"found": 1, "resolved": 0, "dropped": 1, "reasons": {"no_location": 1}}


@pytest.mark.asyncio
async def test_relative_location_is_counted():
    resolved, stats = await _run([_spec("a", "bad_location")])
    assert resolved == []
    assert stats["reasons"] == {"relative_location": 1}


@pytest.mark.asyncio
async def test_duplicate_destination_is_counted():
    resolved, stats = await _run([_spec("a", "ok", "same"), _spec("b", "ok", "same"), _spec("c", "ok", "other")])
    assert len(resolved) == 2
    assert stats == {"found": 3, "resolved": 2, "dropped": 1, "reasons": {"duplicate_destination": 1}}


@pytest.mark.asyncio
async def test_mixed_page_arithmetic_and_reason_counts():
    specs = [
        _spec("a", "ok", "ta"), _spec("b", "bad_status"), _spec("c", "bad_status"),
        _spec("d", "no_location"), _spec("e", "bad_location"), _spec("f", "ok", "tf"),
    ]
    resolved, stats = await _run(specs)
    assert stats["found"] == 6 and stats["resolved"] == 2 and stats["dropped"] == 4
    assert stats["reasons"] == {"non_302_404": 2, "no_location": 1, "relative_location": 1}
    assert sum(stats["reasons"].values()) == stats["dropped"]


@pytest.mark.asyncio
async def test_timeout_is_classified_via_stub_session():
    outcome = await _resolve_one(_RaisingSession(Timeout("stub")), _result())
    assert outcome == (None, "timeout")


@pytest.mark.asyncio
async def test_other_request_error_is_classified_via_stub_session():
    outcome = await _resolve_one(_RaisingSession(CurlConnectionError("stub")), _result())
    assert outcome == (None, "request_error")


def test_log_drops_warns_only_when_something_dropped(caplog):
    with caplog.at_level(logging.DEBUG, logger=google_mod.logger.name):
        google_mod._log_drops({"found": 3, "resolved": 3, "dropped": 0, "reasons": {}})
        assert caplog.records == []
        google_mod._log_drops({"found": 3, "resolved": 1, "dropped": 2, "reasons": {"timeout": 2}})
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert "2 of 3" in caplog.records[0].getMessage()


class _FakeTab:
    async def go_to(self, url, timeout=None):
        return None

    @property
    async def current_url(self):
        return "https://www.google.com/search?q=x"


@pytest.mark.asyncio
async def test_search_with_reason_attaches_goto_resolution_to_diagnosis(monkeypatch):
    async def fake_new_tab():
        return _FakeTab()

    async def noop(*args, **kwargs):
        return None

    async def wait_ok(*args, **kwargs):
        return True

    async def parse(tab, max_results):
        return [_result(), _result()], {"anchor": {"0": 2}}

    async def resolve(results):
        return [], {"found": 2, "resolved": 0, "dropped": 2, "reasons": {"timeout": 2}}

    async def diagnose(tab):
        return {"title": "", "url": "", "ready_state": "", "marker": None}

    async def capture(tab):
        return [200]

    monkeypatch.setattr(google_mod, "new_tab", fake_new_tab)
    monkeypatch.setattr(google_mod, "kill_tab", noop)
    monkeypatch.setattr(google_mod, "_inject_socs_cookie", noop)
    monkeypatch.setattr(google_mod, "start_document_status_capture", capture)
    monkeypatch.setattr(google_mod, "_wait_for_results", wait_ok)
    monkeypatch.setattr(google_mod, "_parse_results", parse)
    monkeypatch.setattr(google_mod, "_resolve_urls", resolve)
    monkeypatch.setattr(google_mod, "_diagnose", diagnose)
    results, reason, diag = await google_mod.GoogleEngine().search_with_reason("x")
    assert results == []
    assert diag["goto_resolution"] == {"found": 2, "resolved": 0, "dropped": 2, "reasons": {"timeout": 2}}
    assert diag["containers_found"] is True
