"""Tests for build_engine_pools in src/search/merge.py.

Guards the M2 fix: cross-engine dedup used to pick ONE winning engine per URL (lowest position,
random tie-break) and every other engine that had also returned that URL lost it entirely from its
own pool. Measured against the query log this cost duckduckgo/brave/bing/startpage/yandex 7-20% of
everything they returned, for a benefit (a URL shown once across all pools) that only pays off when
several engines get drilled per query — which the same log showed happens in roughly 1 of 6 drilled
searches. build_engine_pools now keeps one entry per engine that returned a URL; the cross-engine
knowledge (engine_positions) is preserved as an annotation on every one of those entries rather than
only on a single reassigned winner. Dedup WITHIN a single engine (same engine, same URL, returned
twice) still collapses to one entry.
"""
from src.search.merge import build_engine_pools
from src.search.result import SearchResult


def _r(url, engine, position, **kw):
    return SearchResult(url=url, title="T", snippet="S", engine=engine, position=position, **kw)


def test_url_shared_by_two_engines_is_kept_in_both_pools():
    results = [
        _r("https://x.com/a", "duckduckgo", 3),
        _r("https://x.com/a", "brave", 1),
    ]
    pools = build_engine_pools(results)
    assert "https://x.com/a" == pools["duckduckgo"][0].url
    assert "https://x.com/a" == pools["brave"][0].url


def test_url_shared_by_two_engines_carries_full_engine_positions_on_both_entries():
    results = [
        _r("https://x.com/a", "duckduckgo", 3),
        _r("https://x.com/a", "brave", 1),
    ]
    pools = build_engine_pools(results)
    expected = {"duckduckgo": 3, "brave": 1}
    assert pools["duckduckgo"][0].engine_positions == expected
    assert pools["brave"][0].engine_positions == expected


def test_url_shared_by_two_engines_keeps_each_engines_own_native_position():
    results = [
        _r("https://x.com/a", "duckduckgo", 3),
        _r("https://x.com/a", "brave", 1),
    ]
    pools = build_engine_pools(results)
    assert pools["duckduckgo"][0].position == 3
    assert pools["brave"][0].position == 1


def test_same_engine_duplicate_url_collapses_to_one_entry_at_better_position():
    results = [
        _r("https://x.com/a", "openalex", 5),
        _r("https://x.com/a", "openalex", 2),
    ]
    pools = build_engine_pools(results)
    assert len(pools["openalex"]) == 1
    assert pools["openalex"][0].position == 2


def test_url_unique_to_one_engine_unaffected():
    results = [_r("https://x.com/a", "yandex", 1)]
    pools = build_engine_pools(results)
    assert len(pools) == 1
    assert pools["yandex"][0].url == "https://x.com/a"
    assert pools["yandex"][0].engine_positions == {"yandex": 1}


def test_three_engines_sharing_a_url_all_keep_it():
    results = [
        _r("https://x.com/a", "duckduckgo", 4),
        _r("https://x.com/a", "brave", 2),
        _r("https://x.com/a", "bing", 9),
    ]
    pools = build_engine_pools(results)
    assert set(pools.keys()) == {"duckduckgo", "brave", "bing"}
    for eng in ("duckduckgo", "brave", "bing"):
        assert pools[eng][0].engine_positions == {"duckduckgo": 4, "brave": 2, "bing": 9}


def test_pool_still_sorted_by_own_native_position():
    results = [
        _r("https://x.com/a", "duckduckgo", 5),
        _r("https://x.com/b", "duckduckgo", 1),
        _r("https://x.com/c", "duckduckgo", 3),
    ]
    pools = build_engine_pools(results)
    assert [r.position for r in pools["duckduckgo"]] == [1, 3, 5]
