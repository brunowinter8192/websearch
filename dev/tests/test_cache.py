# INFRASTRUCTURE
import src.search.cache as cache_mod
from src.search.cache import cache_write, cache_read, format_engine_pool
from src.search.result import SearchResult


# FUNCTIONS

def test_cache_write_read_round_trip_preserves_engine_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    pools = {"duckduckgo": _pool({"duckduckgo": 1, "brave": 4})}
    key = "roundtrip_key"

    cache_write(key, pools, "query", "en", None, None)
    hit = cache_read(key)

    assert hit is not None
    entry = hit["pools"]["duckduckgo"][0]
    assert entry["engine_positions"] == {"duckduckgo": 1, "brave": 4}


def test_cache_write_read_round_trip_preserves_empty_engine_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    pools = {"yandex": _pool({"yandex": 1})}
    key = "roundtrip_key_single"

    cache_write(key, pools, "query", "en", None, None)
    hit = cache_read(key)

    entry = hit["pools"]["yandex"][0]
    assert entry["engine_positions"] == {"yandex": 1}


def test_format_engine_pool_does_not_render_engine_positions():
    pool = [{
        "position": 1, "title": "T", "url": "https://x.com/a", "snippet": "",
        "engine_positions": {"duckduckgo": 1, "brave": 4},
    }]
    out = format_engine_pool(pool, "duckduckgo", "q")
    assert "brave" not in out
    assert "engine_positions" not in out


def _pool(engine_positions):
    return [
        SearchResult(
            url="https://x.com/a", title="T", snippet="S", engine="duckduckgo", position=1,
            engine_positions=engine_positions,
        )
    ]
