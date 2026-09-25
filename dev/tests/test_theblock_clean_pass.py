# INFRASTRUCTURE
import hashlib
import logging
from pathlib import Path

import pytest

from src.news.clean_pass import _run_clean_pass
from src.news.platforms.theblock import TheBlockPlatform

GOOD_URL = "https://www.theblock.co/post/12345/good-article"
BODYLESS_URL = "https://www.theblock.co/post/99999/bodyless-article"
GOOD_HASH = hashlib.sha256(GOOD_URL.encode()).hexdigest()[:12]
BODYLESS_HASH = hashlib.sha256(BODYLESS_URL.encode()).hexdigest()[:12]

GOOD_HTML = """\
<html><head>
<script type="application/ld+json">
{"@type": "NewsArticle", "articleBody": "<p>The Block reports on crypto markets.</p>", "datePublished": "2024-03-15T10:00:00Z"}
</script>
</head><body></body></html>
"""

BODYLESS_HTML = """\
<html><head>
<script type="application/ld+json">
{"@type": "NewsArticle", "articleBody": "", "datePublished": "2024-04-01T12:00:00Z"}
</script>
</head><body></body></html>
"""

_PLATFORM = TheBlockPlatform()
_LOG = logging.getLogger("test_clean_pass")


# FUNCTIONS

def test_good_article_clean_file_written(dirs):
    raw_dir, collection_dir = dirs
    stats = _run_clean_pass(_PLATFORM, _entries(), raw_dir, collection_dir, _LOG)
    expected = collection_dir / f"theblock__2024-03-15__{GOOD_HASH}.md"
    assert expected.exists(), f"expected clean file not found: {expected}"
    assert expected.read_text(encoding="utf-8").strip(), "clean file must not be empty"


def test_bodyless_no_clean_file_url_recorded(dirs):
    raw_dir, collection_dir = dirs
    _run_clean_pass(_PLATFORM, _entries(), raw_dir, collection_dir, _LOG)
    bodyless_clean = list(collection_dir.glob(f"*{BODYLESS_HASH}*")) if collection_dir.exists() else []
    assert not bodyless_clean, f"body-less article must not produce a clean file: {bodyless_clean}"
    bodyless_path = raw_dir.parent / "clean" / "bodyless_urls.txt"
    assert bodyless_path.exists(), "bodyless_urls.txt must be created"
    assert BODYLESS_URL in bodyless_path.read_text(encoding="utf-8")


def test_raw_files_unchanged_after_pass(dirs):
    raw_dir, collection_dir = dirs
    good_before = (raw_dir / f"{GOOD_HASH}.md").read_text(encoding="utf-8")
    bodyless_before = (raw_dir / f"{BODYLESS_HASH}.md").read_text(encoding="utf-8")
    _run_clean_pass(_PLATFORM, _entries(), raw_dir, collection_dir, _LOG)
    assert (raw_dir / f"{GOOD_HASH}.md").read_text(encoding="utf-8") == good_before
    assert (raw_dir / f"{BODYLESS_HASH}.md").read_text(encoding="utf-8") == bodyless_before


def test_stats_correct(dirs):
    raw_dir, collection_dir = dirs
    stats = _run_clean_pass(_PLATFORM, _entries(), raw_dir, collection_dir, _LOG)
    assert stats == {"n_cleaned": 1, "n_bodyless": 1, "total": 2}


def test_empty_entries_returns_zero_stats(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    collection_dir = tmp_path / "collection"
    stats = _run_clean_pass(_PLATFORM, [], raw_dir, collection_dir, _LOG)
    assert stats == {"n_cleaned": 0, "n_bodyless": 0, "total": 0}
    assert not collection_dir.exists(), "collection_dir must not be created for empty entries"


def test_bodyless_urls_union_merged(dirs):
    raw_dir, collection_dir = dirs
    _run_clean_pass(_PLATFORM, _entries(), raw_dir, collection_dir, _LOG)

    extra_url = "https://www.theblock.co/post/11111/another-bodyless"
    extra_hash = _hash(extra_url)
    (raw_dir / f"{extra_hash}.md").write_text(BODYLESS_HTML, encoding="utf-8")
    extra_entries = [{"url": extra_url, "hash": extra_hash, "publication_date": ""}]
    _run_clean_pass(_PLATFORM, extra_entries, raw_dir, collection_dir, _LOG)

    bodyless_path = raw_dir.parent / "clean" / "bodyless_urls.txt"
    lines = [l for l in bodyless_path.read_text(encoding="utf-8").splitlines() if l]
    assert BODYLESS_URL in lines
    assert extra_url in lines
    assert lines == sorted(lines), "bodyless_urls.txt must be sorted"


def test_missing_raw_file_raises(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        _run_clean_pass(_PLATFORM, _entries(), raw_dir, tmp_path / "collection", _LOG)


@pytest.fixture()
def dirs(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    collection_dir = tmp_path / "collection"
    (raw_dir / f"{GOOD_HASH}.md").write_text(GOOD_HTML, encoding="utf-8")
    (raw_dir / f"{BODYLESS_HASH}.md").write_text(BODYLESS_HTML, encoding="utf-8")
    return raw_dir, collection_dir


def _entries():
    return [
        {"url": GOOD_URL, "hash": GOOD_HASH, "publication_date": ""},
        {"url": BODYLESS_URL, "hash": BODYLESS_HASH, "publication_date": ""},
    ]


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]
