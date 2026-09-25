import pytest

from src.search import rate_limiter
from src.search.rate_limiter import ENGINE_LIMITS, MAX_REQUESTS, WINDOW_SECONDS, get_limiter


@pytest.fixture(autouse=True)
def _fresh_limiters(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_limiters", {})


@pytest.mark.parametrize("engine_name", sorted(ENGINE_LIMITS))
def test_registered_engine_gets_its_configured_limit(engine_name):
    limiter = get_limiter(engine_name)
    max_requests, window_seconds = ENGINE_LIMITS[engine_name]
    assert limiter._max_requests == max_requests
    assert limiter._window_seconds == window_seconds


def test_registered_engines_use_four_requests_per_minute():
    assert set(ENGINE_LIMITS) == {"google", "duckduckgo", "mojeek", "openalex", "startpage", "brave", "bing", "yandex"}
    assert set(ENGINE_LIMITS.values()) == {(4, 60)}


def test_unregistered_engine_gets_the_default_limit():
    limiter = get_limiter("google_scholar")
    assert limiter._max_requests == MAX_REQUESTS
    assert limiter._window_seconds == WINDOW_SECONDS


def test_limiter_is_created_once_per_engine():
    assert get_limiter("bing") is get_limiter("bing")
