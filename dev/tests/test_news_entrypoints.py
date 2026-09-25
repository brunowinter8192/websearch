# INFRASTRUCTURE
import argparse
import asyncio
import logging

import pytest

from src.news import __main__ as news_main
from src.news import discover_only, scrape_only
from src.news.registry import get


# FUNCTIONS

def test_registry_returns_each_registered_platform_by_name():
    assert get("coindesk").name == "coindesk"
    assert get("theblock").name == "theblock"


def test_registry_unknown_name_lists_available_platforms():
    with pytest.raises(ValueError) as exc:
        get("nope")
    assert str(exc.value) == "Unknown platform 'nope'. Available: coindesk, theblock"


def test_apply_timeframe_keeps_skip_index_for_delta():
    platform = _StubPlatform()
    assert news_main._apply_timeframe(platform, _args()) is False
    assert platform.timeframe == "delta"


def test_apply_timeframe_auto_skips_index_for_non_delta_full_run(capsys):
    platform = _StubPlatform()
    assert news_main._apply_timeframe(platform, _args(timeframe="full")) is True
    assert platform.timeframe == "full"
    out = capsys.readouterr().out
    assert "Non-delta timeframe ('full') — RAG index auto-skipped." in out
    assert "rag-cli index --collection stubcoll" in out


def test_apply_timeframe_does_not_auto_skip_for_scrape_only(capsys):
    platform = _StubPlatform()
    assert news_main._apply_timeframe(platform, _args(timeframe="30", scrape_only=True)) is False
    assert capsys.readouterr().out == ""


def test_year_together_with_date_range_is_rejected():
    parser = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        news_main._require_exclusive_date_filters(parser, argparse.Namespace(year="2024", from_date="2024-01-01", to_date=None))
    news_main._require_exclusive_date_filters(parser, argparse.Namespace(year="2024", from_date=None, to_date=None))


def test_discover_only_persists_master_list_only_for_platforms_that_use_it(monkeypatch, tmp_path):
    calls = []
    log = logging.getLogger("t")
    monkeypatch.setattr(discover_only, "start_run", lambda platform, label: calls.append(("start", label)) or log)
    monkeypatch.setattr(discover_only, "master_list_path", lambda platform: tmp_path / "master.txt")
    monkeypatch.setattr(discover_only, "persist_master_list", lambda entries, path, lg: calls.append(("persist", len(entries))))
    monkeypatch.setattr(discover_only, "write_marker", lambda name, lg: calls.append(("marker", name)))
    monkeypatch.setattr(discover_only, "log_run_complete", lambda lg, platform, label: calls.append(("complete", label)))

    asyncio.run(discover_only.discover_only_workflow(_StubPlatform(entries=[{"url": "u"}])))
    assert calls == [("start", "discover-only started"), ("marker", "stub"), ("complete", "discover-only complete")]

    calls.clear()
    platform = _StubPlatform(entries=[{"url": "u"}, {"url": "v"}])
    platform.uses_master_list = True
    asyncio.run(discover_only.discover_only_workflow(platform))
    assert calls == [("start", "discover-only started"), ("persist", 2), ("marker", "stub"), ("complete", "discover-only complete")]


def test_scrape_only_without_candidates_writes_marker_and_stops(monkeypatch):
    calls = []
    log = logging.getLogger("t")
    monkeypatch.setattr(scrape_only, "_scrape_only_preamble", lambda *a: (log, "job1", "all"))
    monkeypatch.setattr(scrape_only, "write_marker", lambda name, lg: calls.append(("marker", name)))
    monkeypatch.setattr(scrape_only, "_prepare_raw_dir", lambda platform: calls.append("raw_dir"))
    asyncio.run(scrape_only.scrape_only_workflow(_StubPlatform(entries=[])))
    assert calls == [("marker", "stub")]


def test_scrape_only_with_everything_already_in_raw_writes_marker_and_stops(monkeypatch, tmp_path):
    calls = []
    log = logging.getLogger("t")
    monkeypatch.setattr(scrape_only, "_scrape_only_preamble", lambda *a: (log, "job1", "all"))
    monkeypatch.setattr(scrape_only, "write_marker", lambda name, lg: calls.append(("marker", name)))
    monkeypatch.setattr(scrape_only, "_prepare_raw_dir", lambda platform: tmp_path)
    monkeypatch.setattr(scrape_only, "filter_new_entries", lambda entries, raw_dir, name, mode, raw_ext: ([], len(entries), 0))

    async def _must_not_run(*a, **kw):
        calls.append("scrape")

    monkeypatch.setattr(scrape_only, "_run_scrape_only_browser", _must_not_run)
    monkeypatch.setattr(scrape_only, "_run_scrape_only_riding", _must_not_run)
    asyncio.run(scrape_only.scrape_only_workflow(_StubPlatform(entries=[{"url": "u"}])))
    assert calls == [("marker", "stub")]


class _StubPlatform:
    name = "stub"
    collection = "stubcoll"
    timeframe = "delta"
    uses_master_list = False
    supports_scrape_only = True
    scrape_engine = "browser"

    def __init__(self, entries=None):
        self.entries = entries or []

    async def discover(self):
        return self.entries

    def load_scrape_entries(self, year=None, from_date=None, to_date=None, limit=None):
        return self.entries


def _args(**overrides):
    base = dict(skip_index=False, timeframe="delta", discover_only=False, scrape_only=False)
    base.update(overrides)
    return argparse.Namespace(**base)
