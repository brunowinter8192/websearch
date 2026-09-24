import pytest

from src.news.platforms.theblock.discover import _subs_in_range, _sub_by_index


def _make_urls(indices: list[int]) -> list[str]:
    return [
        f"https://www.theblock.co/sitemap_tbco_post_type_post_{i}.xml"
        for i in indices
    ]


_ALL_URLS = _make_urls(list(range(27)))


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
