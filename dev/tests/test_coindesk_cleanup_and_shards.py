# INFRASTRUCTURE
import logging

import pytest

from src.news.platforms.coindesk.cleanup import cleanup
from src.news.platforms.coindesk.shards import load_discover_filtered


# FUNCTIONS

def test_cleanup_without_h1_returns_empty_and_logs(caplog):
    with caplog.at_level(logging.WARNING, logger="src.news.platforms.coindesk.cleanup"):
        out = cleanup("nav\nsome text\nfooter", {"url": "https://x.test/a"})
    assert out == ""
    assert any("no H1 start anchor" in m and "https://x.test/a" in m for m in caplog.messages)


def test_cleanup_without_end_anchor_logs_and_keeps_tail(caplog):
    with caplog.at_level(logging.WARNING, logger="src.news.platforms.coindesk.cleanup"):
        out = cleanup("# Title\n\nBody text here.", {"url": "https://x.test/b"})
    assert "Body text here." in out
    assert any("no end anchor" in m for m in caplog.messages)


def test_cleanup_with_end_anchor_logs_nothing(caplog):
    with caplog.at_level(logging.WARNING, logger="src.news.platforms.coindesk.cleanup"):
        out = cleanup("# Title\n\nBody.\n\n## More For You\nnoise", {"url": "https://x.test/c"})
    assert "noise" not in out
    assert caplog.messages == []


def test_load_discover_filtered_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="directory missing"):
        load_discover_filtered(tmp_path / "nope")


def test_load_discover_filtered_missing_year_shard_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="year 2019"):
        load_discover_filtered(tmp_path, year="2019")


def test_load_discover_filtered_reads_existing_year_shard(tmp_path):
    (tmp_path / "coindesk_2024.txt").write_text("2024-01-02\thttps://x.test/a\n", encoding="utf-8")
    assert load_discover_filtered(tmp_path, year="2024") == [
        {"url": "https://x.test/a", "publication_date": "2024-01-02T00:00:00+00:00"}
    ]
