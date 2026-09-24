import json
from pathlib import Path

import pytest

from src.crawler import pipe_scraper
from src.crawler import pipe_scraper_acquisition
from src.crawler.pipe_scraper_acquisition import _onward_link_identity, _extract_onward_links
from src.crawler.pipe_scraper_report import _collect_onward_links, _write_onward_links_file, _print_summary
from dev.tests._pipe_scraper_fakes import _FakeResult, _camoufox_meta


def test_onward_link_identity_strips_query_and_fragment():
    assert (_onward_link_identity("https://x.test/docs/guide?tab=2#section")
            == "https://x.test/docs/guide")


def test_onward_link_identity_lowercases_scheme_and_host():
    assert _onward_link_identity("HTTPS://X.TEST/docs") == "https://x.test/docs"


def test_onward_link_identity_collapses_query_variants_to_one_key():
    a = _onward_link_identity("https://platform.claude.com/login?returnTo=%2Fdocs%2Fen%2Fa")
    b = _onward_link_identity("https://platform.claude.com/login?returnTo=%2Fdocs%2Fen%2Fb")
    assert a == b == "https://platform.claude.com/login"


def test_onward_link_identity_none_for_hostless_url():
    assert _onward_link_identity("mailto:someone@example.com") is None
    assert _onward_link_identity("javascript:void(0)") is None


class _FakeLinksResult:
    def __init__(self, internal=(), external=()):
        self.links = {"internal": list(internal), "external": list(external)}


def test_extract_onward_links_unions_internal_and_external_buckets():
    result = _FakeLinksResult(
        internal=[{"href": "https://x.test/a"}],
        external=[{"href": "https://x.test/b"}],
    )
    assert sorted(_extract_onward_links(result, "x.test")) == [
        "https://x.test/a", "https://x.test/b",
    ]


def test_extract_onward_links_restricts_to_page_host_www_apex_collapsed():
    result = _FakeLinksResult(internal=[
        {"href": "https://www.x.test/a"},
        {"href": "https://other.test/b"},
        {"href": "https://sub.x.test/c"},
    ])
    assert _extract_onward_links(result, "x.test") == ["https://www.x.test/a"]


def test_extract_onward_links_drops_non_page_extensions():
    result = _FakeLinksResult(internal=[
        {"href": "https://x.test/docs/images/diagram.gif"},
        {"href": "https://x.test/docs/guide"},
    ])
    assert _extract_onward_links(result, "x.test") == ["https://x.test/docs/guide"]


def test_extract_onward_links_collapses_query_variant_duplicates_within_the_page():
    result = _FakeLinksResult(internal=[
        {"href": "https://x.test/login?returnTo=%2Fa"},
        {"href": "https://x.test/login?returnTo=%2Fb"},
    ])
    assert _extract_onward_links(result, "x.test") == ["https://x.test/login"]


def test_extract_onward_links_empty_when_result_has_no_links_attribute():
    class _NoLinks:
        pass
    assert _extract_onward_links(_NoLinks(), "x.test") == []


def test_collect_onward_links_excludes_urls_already_in_the_input_list():
    urls = ["https://x.test/a"]
    results = [{"links": ["https://x.test/a", "https://x.test/new"]}]
    assert _collect_onward_links(urls, results, "chromium") == ["https://x.test/new"]


def test_collect_onward_links_excludes_input_url_regardless_of_its_own_query_string():
    urls = ["https://x.test/docs/guide?utm_source=foo"]
    results = [{"links": ["https://x.test/docs/guide"]}]
    assert _collect_onward_links(urls, results, "chromium") == []


def test_collect_onward_links_dedups_across_pages_order_preserving():
    urls = ["https://x.test/a", "https://x.test/b"]
    results = [
        {"links": ["https://x.test/new1", "https://x.test/shared"]},
        {"links": ["https://x.test/shared", "https://x.test/new2"]},
    ]
    assert _collect_onward_links(urls, results, "chromium") == [
        "https://x.test/new1", "https://x.test/shared", "https://x.test/new2",
    ]


def test_collect_onward_links_ignores_results_with_no_links_key():
    urls = ["https://x.test/a"]
    results = [{"url": "https://x.test/b"}, {"links": ["https://x.test/new"]}]
    assert _collect_onward_links(urls, results, "chromium") == ["https://x.test/new"]


def test_collect_onward_links_returns_none_for_camoufox_engine():
    urls = ["https://x.test/a"]
    results = [{"links": ["https://x.test/new"]}]
    assert _collect_onward_links(urls, results, "camoufox") is None


@pytest.fixture
def onward_links_scratch_path():
    path = Path("/tmp/pipe_scraper_test_onward_domain_scrape_links.txt")
    yield path
    path.unlink(missing_ok=True)


def test_write_onward_links_file_writes_one_url_per_line(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain",
                              ["https://x.test/a", "https://x.test/b"])
    assert onward_links_scratch_path.read_text(encoding="utf-8") == "https://x.test/a\nhttps://x.test/b\n"


def test_write_onward_links_file_writes_empty_file_for_empty_list(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain", [])
    assert onward_links_scratch_path.read_text(encoding="utf-8") == ""


def test_write_onward_links_file_writes_nothing_when_none(onward_links_scratch_path):
    _write_onward_links_file("pipe_scraper_test_onward_domain", None)
    assert not onward_links_scratch_path.exists()


def _summary_result(status_code=200, byte_count=100):
    return {"status_code": status_code, "bytes": byte_count}


def test_print_summary_reports_onward_link_count(capsys):
    _print_summary([_summary_result()], 1.0, ["https://x.test/a", "https://x.test/b"])
    out = capsys.readouterr().out
    assert "2 onward links collected" in out


def test_print_summary_reports_camoufox_cannot_collect_not_a_bare_zero(capsys):
    _print_summary([_summary_result()], 1.0, None)
    out = capsys.readouterr().out
    assert "onward links not collected (camoufox engine)" in out
    assert "0 onward links" not in out


class _FakeLinksCrawler:
    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def arun(self, url, config=None):
        return _FakeResult(raw_markdown="x" * 500, links={
            "internal": [{"href": "https://x.test/new"}, {"href": "https://other.test/x"}],
            "external": [],
        })


@pytest.mark.asyncio
async def test_scrape_one_populates_links_key_from_the_real_result(tmp_path, monkeypatch):
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))
    monkeypatch.setattr(pipe_scraper, "AsyncWebCrawler", _FakeLinksCrawler)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir,
                                              download_delay=0.01, concurrency_per_domain=8)

    assert results[0]["links"] == ["https://x.test/new"]


@pytest.mark.asyncio
async def test_scrape_one_camoufox_never_produces_a_links_key(tmp_path, monkeypatch):
    log_file = tmp_path / "pipe_scrape_log.jsonl"
    monkeypatch.setenv("WEBSEARCH_PIPE_SCRAPE_LOG_PATH", str(log_file))

    async def _fake_try_scrape_camoufox(url, block_images=False):
        return "# real markdown, non-trivial content", _camoufox_meta()
    monkeypatch.setattr(pipe_scraper_acquisition, "try_scrape_camoufox", _fake_try_scrape_camoufox)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    results = await pipe_scraper._scrape_all(["https://x.test/a"], output_dir, download_delay=0.01,
                                              concurrency_per_domain=1, engine="camoufox")

    assert "links" not in results[0]
