# INFRASTRUCTURE
import logging

import pytest

from src.news import pipeline
from src.news.engine.proxy_riding.scrape import RidingScrapeConfig
from src.news.platform import Platform
from src.news.platforms.coindesk import CoinDeskPlatform
from src.news.platforms.theblock import TheBlockPlatform


# FUNCTIONS

def test_protocol_defaults_are_declared():
    p = _MinimalPlatform()
    assert p.timeframe == "delta"
    assert p.uses_master_list is False
    assert p.supports_scrape_only is False
    assert p.riding_scrape_config is None


def test_default_load_scrape_entries_raises():
    with pytest.raises(NotImplementedError):
        _MinimalPlatform().load_scrape_entries()


def test_coindesk_values_match_previous_getattr_results():
    p = CoinDeskPlatform()
    assert p.uses_master_list is False
    assert p.supports_scrape_only is True
    assert isinstance(p.riding_scrape_config, RidingScrapeConfig)
    assert p.timeframe == "30"


def test_theblock_values_match_previous_getattr_results():
    p = TheBlockPlatform()
    assert p.uses_master_list is True
    assert p.supports_scrape_only is False
    assert p.riding_scrape_config is None
    assert p.timeframe == "delta"


def test_scrape_only_preamble_exits_for_platform_without_support(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "_setup_logging", lambda name: logging.getLogger("t"))
    monkeypatch.setattr(pipeline, "_check_internet", lambda platform, log: True)
    with pytest.raises(SystemExit):
        pipeline._scrape_only_preamble(TheBlockPlatform(), None, None, None)


def test_scrape_only_preamble_passes_for_supporting_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "_setup_logging", lambda name: logging.getLogger("t"))
    monkeypatch.setattr(pipeline, "_check_internet", lambda platform, log: True)
    log, job_id, desc = pipeline._scrape_only_preamble(CoinDeskPlatform(), "2024", None, None)
    assert desc == "year=2024"


class _MinimalPlatform(Platform):
    name = "minimal"
