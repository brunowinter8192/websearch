"""Tests for _cap_pools in src/search/search_web.py.

Guards the M1 fix: the pool cap used to anchor K to google's own pool size, falling back to 10
only when google returned zero. Google now returns zero in the overwhelming majority of real
queries, and on the rare query where it returns 1 or 2, K collapsed to 1 or 2 and cut every other
engine's pool down with it, even ones that had returned 40+ results. The cap is now a fixed 10 for
every engine, independent of what google (or any other engine) returned.
"""
from src.search.result import SearchResult
from src.search.search_web import POOL_CAP, _cap_pools


def _pool(engine: str, n: int) -> list[SearchResult]:
    return [
        SearchResult(url=f"https://{engine}.example/{i}", title="T", snippet="S",
                     engine=engine, position=i)
        for i in range(1, n + 1)
    ]


def test_pool_cap_is_fixed_ten():
    assert POOL_CAP == 10


def test_google_with_one_result_no_longer_drags_other_engines_down():
    pools = {
        "google": _pool("google", 1),
        "duckduckgo": _pool("duckduckgo", 10),
        "openalex": _pool("openalex", 44),
    }
    capped = _cap_pools(pools)
    assert len(capped["google"]) == 1
    assert len(capped["duckduckgo"]) == 10
    assert len(capped["openalex"]) == 10


def test_google_with_two_results_no_longer_drags_other_engines_down():
    pools = {
        "google": _pool("google", 2),
        "duckduckgo": _pool("duckduckgo", 10),
        "brave": _pool("brave", 10),
        "openalex": _pool("openalex", 132),
    }
    capped = _cap_pools(pools)
    assert len(capped["google"]) == 2
    assert len(capped["duckduckgo"]) == 10
    assert len(capped["brave"]) == 10
    assert len(capped["openalex"]) == 10


def test_google_absent_still_caps_every_engine_at_ten():
    pools = {
        "duckduckgo": _pool("duckduckgo", 10),
        "openalex": _pool("openalex", 289),
    }
    capped = _cap_pools(pools)
    assert len(capped["duckduckgo"]) == 10
    assert len(capped["openalex"]) == 10


def test_engine_below_cap_is_unaffected():
    pools = {"yandex": _pool("yandex", 6)}
    capped = _cap_pools(pools)
    assert len(capped["yandex"]) == 6


def test_espressomaschine_case_from_query_log():
    pools = {
        "duckduckgo": _pool("duckduckgo", 10),
        "mojeek": _pool("mojeek", 10),
        "openalex": _pool("openalex", 10),
        "startpage": _pool("startpage", 10),
        "brave": _pool("brave", 6),
        "bing": _pool("bing", 1),
        "yandex": _pool("yandex", 0),
    }
    capped = _cap_pools(pools)
    counts = {eng: len(pool) for eng, pool in capped.items()}
    assert counts == {
        "duckduckgo": 10, "mojeek": 10, "openalex": 10, "startpage": 10,
        "brave": 6, "bing": 1, "yandex": 0,
    }
