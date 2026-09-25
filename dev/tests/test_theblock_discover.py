# INFRASTRUCTURE
import httpx
import pytest

from src.news.platforms.theblock import discover as theblock_discover
from src.news.platforms.theblock.discover import _subs_in_range, _sub_by_index, _fetch_direct, _parse_url_blocks


# FUNCTIONS

def _make_urls(indices: list[int]) -> list[str]:
    return [
        f"https://www.theblock.co/sitemap_tbco_post_type_post_{i}.xml"
        for i in indices
    ]


def test_range_selects_correct_subs():
    result = _subs_in_range(_ALL_URLS, 24, 26)
    import re
    nums = [int(re.search(r"_(\d+)\.xml$", u).group(1)) for u in result]
    assert sorted(nums) == [24, 25, 26]


def test_range_includes_both_endpoints():
    result = _subs_in_range(_ALL_URLS, 0, 2)
    import re
    nums = sorted(int(re.search(r"_(\d+)\.xml$", u).group(1)) for u in result)
    assert nums == [0, 1, 2]


def test_range_single_element_via_equal_bounds():
    result = _subs_in_range(_ALL_URLS, 5, 5)
    assert len(result) == 1
    assert "_5.xml" in result[0]


def test_range_returns_descending_order():
    result = _subs_in_range(_ALL_URLS, 10, 13)
    import re
    nums = [int(re.search(r"_(\d+)\.xml$", u).group(1)) for u in result]
    assert nums == [13, 12, 11, 10]


def test_range_full_set():
    result = _subs_in_range(_ALL_URLS, 0, 26)
    assert len(result) == 27
    import re
    nums = [int(re.search(r"_(\d+)\.xml$", u).group(1)) for u in result]
    assert nums == list(range(26, -1, -1))


def test_range_no_match_raises():
    with pytest.raises(RuntimeError, match="matched no post_type_post"):
        _subs_in_range(_ALL_URLS, 50, 60)


def test_range_partial_overlap_selects_only_matching():
    result = _subs_in_range(_ALL_URLS, 24, 99)
    import re
    nums = sorted(int(re.search(r"_(\d+)\.xml$", u).group(1)) for u in result)
    assert nums == [24, 25, 26]


def test_single_sub_by_index():
    result = _sub_by_index(_ALL_URLS, 26)
    assert "_26.xml" in result


def test_single_sub_by_index_not_found():
    with pytest.raises(RuntimeError, match="sub:99 not found"):
        _sub_by_index(_ALL_URLS, 99)


def test_single_sub_by_index_zero():
    result = _sub_by_index(_ALL_URLS, 0)
    assert "_0.xml" in result


def test_range_a_greater_than_b_raises():
    import asyncio
    from unittest.mock import patch, AsyncMock

    fake_index = (
        b"<?xml version='1.0'?><sitemapindex>"
        + b"".join(
            b"<sitemap><loc>https://www.theblock.co/sitemap_tbco_post_type_post_"
            + str(i).encode()
            + b".xml</loc></sitemap>"
            for i in range(27)
        )
        + b"</sitemapindex>"
    )

    with patch("src.news.platforms.theblock.discover._fetch_xml", return_value=fake_index):
        with pytest.raises(RuntimeError, match=r"A \(27\) must be ≤ B \(24\)"):
            asyncio.run(__import__("src.news.platforms.theblock.discover", fromlist=["discover"]).discover("sub:27-24"))


def test_range_non_int_raises():
    import asyncio
    from unittest.mock import patch

    fake_index = (
        b"<?xml version='1.0'?><sitemapindex>"
        b"<sitemap><loc>https://www.theblock.co/sitemap_tbco_post_type_post_1.xml</loc></sitemap>"
        b"</sitemapindex>"
    )

    with patch("src.news.platforms.theblock.discover._fetch_xml", return_value=fake_index):
        with pytest.raises(RuntimeError, match="expected two integers"):
            asyncio.run(__import__("src.news.platforms.theblock.discover", fromlist=["discover"]).discover("sub:x-y"))


def test_range_no_existing_sub_in_range_raises():
    import asyncio
    from unittest.mock import patch

    fake_index = (
        b"<?xml version='1.0'?><sitemapindex>"
        + b"".join(
            b"<sitemap><loc>https://www.theblock.co/sitemap_tbco_post_type_post_"
            + str(i).encode()
            + b".xml</loc></sitemap>"
            for i in range(5)
        )
        + b"</sitemapindex>"
    )

    with patch("src.news.platforms.theblock.discover._fetch_xml", return_value=fake_index):
        with pytest.raises(RuntimeError, match="matched no post_type_post"):
            asyncio.run(__import__("src.news.platforms.theblock.discover", fromlist=["discover"]).discover("sub:10-20"))


def test_fetch_direct_403_without_xml_marker_returns_none_for_pool_fallback(monkeypatch):
    monkeypatch.setattr(theblock_discover.httpx, "get", lambda *a, **kw: _FakeHttpResponse(403, b"<html>blocked</html>"))
    assert _fetch_direct("https://www.theblock.co/sitemap_tbco_index.xml") is None


def test_fetch_direct_200_with_xml_marker_returns_content(monkeypatch):
    body = b'<?xml version="1.0"?><sitemapindex/>'
    monkeypatch.setattr(theblock_discover.httpx, "get", lambda *a, **kw: _FakeHttpResponse(200, body))
    assert _fetch_direct("https://www.theblock.co/sitemap_tbco_index.xml") == body


def test_fetch_direct_network_exception_propagates(monkeypatch):
    def _raise(*a, **kw):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(theblock_discover.httpx, "get", _raise)
    with pytest.raises(httpx.ConnectError):
        _fetch_direct("https://www.theblock.co/sitemap_tbco_index.xml")


def test_parse_url_blocks_reads_iso_lastmod():
    results = _parse_url_blocks(_url_block("2026-06-15T10:00:00Z"))
    assert [(u, m.isoformat()) for u, m in results] == [("https://www.theblock.co/post/1/a", "2026-06-15T10:00:00+00:00")]


def test_parse_url_blocks_unparseable_lastmod_raises():
    with pytest.raises(ValueError):
        _parse_url_blocks(_url_block("not-a-date"))


def test_fetch_direct_failure_logs_status_and_url(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(theblock_discover.httpx, "get", lambda *a, **kw: _FakeHttpResponse(403, b"<html>blocked</html>"))
    with caplog.at_level(logging.WARNING, logger="src.news.platforms.theblock.discover"):
        assert _fetch_direct("https://www.theblock.co/x.xml") is None
    assert any("status=403" in m and "https://www.theblock.co/x.xml" in m for m in caplog.messages)


def test_fetch_xml_logs_which_route_served(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(theblock_discover, "_fetch_direct", lambda url: None)
    monkeypatch.setattr(theblock_discover, "load_backfill_pool", lambda: ([("http", "1.2.3.4:80")], []))
    monkeypatch.setattr(theblock_discover, "fetch_url", lambda *a: ("ok", b"<urlset/>", None))
    with caplog.at_level(logging.INFO, logger="src.news.platforms.theblock.discover"):
        assert theblock_discover._fetch_xml("https://www.theblock.co/s.xml", []) == b"<urlset/>"
    assert any("served via proxy http://1.2.3.4:80" in m for m in caplog.messages)


def test_fetch_xml_records_attempt_reason_on_the_acquire_logger(monkeypatch):
    recorded = []

    class _Rec:
        def record_attempt(self, proto, hp, url, ok, reason=None):
            recorded.append((ok, reason))

    monkeypatch.setattr(theblock_discover, "_fetch_direct", lambda url: None)
    monkeypatch.setattr(theblock_discover, "fetch_url", lambda *a: ("fail", b"", "ConnectTimeout"))
    theblock_discover._fetch_xml("https://www.theblock.co/s.xml", [("http", "h:1")], _Rec())
    assert recorded == [(False, "ConnectTimeout")]


def test_failed_sub_sitemap_raises_like_the_index():
    import asyncio
    from unittest.mock import patch

    index = (b"<?xml version='1.0'?><sitemapindex><sitemap><loc>https://www.theblock.co/sitemap_tbco_post_type_post_1.xml</loc></sitemap></sitemapindex>")
    replies = {"https://www.theblock.co/sitemap_tbco_index.xml": index}
    with patch("src.news.platforms.theblock.discover._fetch_xml", side_effect=lambda url, pc, lg=None: replies.get(url)):
        with pytest.raises(RuntimeError, match="sub-sitemap fetch failed"):
            asyncio.run(theblock_discover.discover("full"))


class _FakeHttpResponse:
    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content


def _url_block(lastmod: str) -> bytes:
    return f"<url><loc>https://www.theblock.co/post/1/a</loc><lastmod>{lastmod}</lastmod></url>".encode()


_ALL_URLS = _make_urls(list(range(27)))
