import hashlib
from pathlib import Path

import pytest

from src.news.engine.dedup import filter_new_entries, pub_date_str, url_hash


def _entry(url: str) -> dict:
    return {"url": url, "publication_date": ""}


def _write_raw(raw_dir: Path, url: str) -> None:
    h = url_hash(url)
    (raw_dir / f"{h}.md").write_text("stub", encoding="utf-8")


URL_A = "https://www.theblock.co/post/1/article-a"
URL_B = "https://www.theblock.co/post/2/article-b"
URL_C = "https://www.theblock.co/post/3/article-c"
URL_D = "https://www.theblock.co/post/4/article-d"


def test_excluded_url_no_raw_is_not_new(tmp_path):
    raw_dir = tmp_path
    entries = [_entry(URL_A)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls={URL_A}
    )
    assert new == []
    assert n_excluded == 1
    assert n_skip_raw == 0


def test_non_excluded_url_no_raw_is_new(tmp_path):
    raw_dir = tmp_path
    entries = [_entry(URL_B)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls={URL_A}
    )
    assert len(new) == 1
    assert new[0]["url"] == URL_B
    assert n_excluded == 0
    assert n_skip_raw == 0


def test_non_excluded_url_with_raw_is_skipped(tmp_path):
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_C)
    entries = [_entry(URL_C)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls={URL_A}
    )
    assert new == []
    assert n_skip_raw == 1
    assert n_excluded == 0


def test_excluded_url_with_raw_counts_as_excluded_not_skipped(tmp_path):
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_D)
    entries = [_entry(URL_D)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls={URL_D}
    )
    assert new == []
    assert n_excluded == 1
    assert n_skip_raw == 0


def test_mixed_entries_counts(tmp_path):
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_C)
    _write_raw(raw_dir, URL_D)
    entries = [_entry(URL_A), _entry(URL_B), _entry(URL_C), _entry(URL_D)]
    exclude = {URL_A, URL_D}
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls=exclude
    )
    assert [e["url"] for e in new] == [URL_B]
    assert n_skip_raw == 1
    assert n_excluded == 2


def test_exclude_urls_none_default_unchanged(tmp_path):
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_C)
    entries = [_entry(URL_A), _entry(URL_B), _entry(URL_C)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw"
    )
    new_urls = {e["url"] for e in new}
    assert new_urls == {URL_A, URL_B}
    assert n_skip_raw == 1
    assert n_excluded == 0


def test_empty_exclusion_set_no_exclusions(tmp_path):
    raw_dir = tmp_path
    entries = [_entry(URL_A), _entry(URL_B)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls=set()
    )
    assert len(new) == 2
    assert n_excluded == 0


def test_pub_date_str_returns_unknown_when_no_date_found():
    entry = {"url": "https://x.test/no-date-here", "publication_date": ""}
    assert pub_date_str(entry) == "unknown"


def test_filter_new_entries_pubdate_mode_matches_unknown_filename(tmp_path):
    url = "https://x.test/no-date-here"
    h = url_hash(url)
    (tmp_path / f"theblock__unknown__{h}.md").write_text("stub", encoding="utf-8")
    entries = [{"url": url, "publication_date": ""}]
    new, n_skip_raw, n_excluded = filter_new_entries(entries, tmp_path, "theblock", mode="pubdate")
    assert new == []
    assert n_skip_raw == 1
