"""Tests for filter_new_entries exclude_urls param (failure-URL diff exclusion).

No network, no corpus. Covers:
- URL in exclusion set, no raw MD  → excluded (not new)
- URL not in exclusion set, no raw MD → new
- URL not in exclusion set, raw MD exists → skipped (already in raw)
- URL in exclusion set AND raw MD exists → excluded (exclusion checked first)
- exclude_urls=None (default) → unchanged behaviour, no exclusions
- n_excluded and n_skip_raw counts are correct
"""
import hashlib
from pathlib import Path

import pytest

from src.news.engine.dedup import filter_new_entries, pub_date_str, url_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(url: str) -> dict:
    return {"url": url, "publication_date": ""}


def _write_raw(raw_dir: Path, url: str) -> None:
    """Write a stub raw file for url into raw_dir (simulates already-scraped)."""
    h = url_hash(url)
    (raw_dir / f"{h}.md").write_text("stub", encoding="utf-8")


URL_A = "https://www.theblock.co/post/1/article-a"   # will be in exclusion set
URL_B = "https://www.theblock.co/post/2/article-b"   # no raw, not excluded → new
URL_C = "https://www.theblock.co/post/3/article-c"   # raw exists, not excluded → skipped
URL_D = "https://www.theblock.co/post/4/article-d"   # raw exists AND in exclusion set


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_excluded_url_no_raw_is_not_new(tmp_path):
    """URL in exclusion set with no raw file → excluded, not in new_entries."""
    raw_dir = tmp_path
    entries = [_entry(URL_A)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls={URL_A}
    )
    assert new == []
    assert n_excluded == 1
    assert n_skip_raw == 0


def test_non_excluded_url_no_raw_is_new(tmp_path):
    """URL not in exclusion set, no raw file → appears in new_entries."""
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
    """URL not excluded but raw file exists → counted in n_skip_raw, not in new_entries."""
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
    """Exclusion check fires before raw-exist check; URL in both → n_excluded, not n_skip_raw."""
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
    """Four entries covering all cases; verify new, n_skip_raw, n_excluded tallies."""
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_C)
    _write_raw(raw_dir, URL_D)
    entries = [_entry(URL_A), _entry(URL_B), _entry(URL_C), _entry(URL_D)]
    exclude = {URL_A, URL_D}
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls=exclude
    )
    assert [e["url"] for e in new] == [URL_B]   # only B is new
    assert n_skip_raw == 1                       # C has raw
    assert n_excluded == 2                       # A and D excluded


def test_exclude_urls_none_default_unchanged(tmp_path):
    """exclude_urls=None (default) → no exclusions; backward-compat for all existing callers."""
    raw_dir = tmp_path
    _write_raw(raw_dir, URL_C)
    entries = [_entry(URL_A), _entry(URL_B), _entry(URL_C)]
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw"  # no exclude_urls
    )
    new_urls = {e["url"] for e in new}
    assert new_urls == {URL_A, URL_B}   # A is new (no exclusion, no raw)
    assert n_skip_raw == 1              # C has raw
    assert n_excluded == 0


def test_empty_exclusion_set_no_exclusions(tmp_path):
    """Passing an empty set should exclude nothing (same as None for behaviour)."""
    raw_dir = tmp_path
    entries = [_entry(URL_A), _entry(URL_B)]
    # pass empty set explicitly
    new, n_skip_raw, n_excluded = filter_new_entries(
        entries, raw_dir, "theblock", mode="raw", exclude_urls=set()
    )
    assert len(new) == 2
    assert n_excluded == 0


# ---------------------------------------------------------------------------
# pub_date_str / mode="pubdate" — consolidated 2026-09-09 (was also defined, with a diverging
# "" fallback, in src/news/clean_pass.py; that copy is gone, this is the one surviving definition)
# ---------------------------------------------------------------------------

def test_pub_date_str_returns_unknown_when_no_date_found():
    """The "unknown" fallback (not "") — the same fallback clean_pass.py's own filenames already
    used, so pubdate-mode dedup lookups now match what clean_pass actually writes for date-less
    entries."""
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
