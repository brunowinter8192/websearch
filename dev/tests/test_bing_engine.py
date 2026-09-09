"""Tests for src/search/engines/bing.py pure result-parsing / URL-unwrap logic.

No network, no browser — covers the two seams factored out of the DOM-driven engine:
- _clean_url: bing.com/ck/a?...&u=<prefixed-base64> tracking redirect -> real destination URL
- _build_results: JSON items (as if already parsed from the page) -> SearchResult list

_classify_diagnosis was removed (the guessed-verdict-removal milestone): its output was one of
the EMPTY_* sub-statuses that no longer exist — the marker/ready_state facts it classified are
still available directly in the diagnosis snapshot.
"""
import json

import pytest

from src.search.engines.bing import _build_results, _clean_url, _parse_results


# ---------------------------------------------------------------------------
# _clean_url
# ---------------------------------------------------------------------------

def test_clean_url_unwraps_ck_a_redirect_to_real_destination():
    # Real sample captured live in dev/search_pipeline/28_bing_probe.py exploration —
    # u=a1<base64url(https://docs.python.org/3/library/asyncio.html)>
    wrapped = (
        "https://www.bing.com/ck/a?!&&p=3433f59b1e520073dfadefacf80bd715cd2b9ad5a31edea67e9ae0212fa91585"
        "&ptn=3&ver=2&hsh=4&fclid=2775937b-2388-6e7b-1e71-844822246f08"
        "&u=a1aHR0cHM6Ly9kb2NzLnB5dGhvbi5vcmcvMy9saWJyYXJ5L2FzeW5jaW8uaHRtbA&ntb=1"
    )
    assert _clean_url(wrapped) == "https://docs.python.org/3/library/asyncio.html"


def test_clean_url_passes_through_direct_url_with_no_u_param():
    assert _clean_url("https://example.com/page") == "https://example.com/page"


def test_clean_url_empty_href_returns_empty():
    assert _clean_url("") == ""


def test_clean_url_falls_back_to_raw_href_when_decode_raises(monkeypatch):
    import src.search.engines.bing as bing_mod

    def _raise(*a, **kw):
        raise ValueError("simulated decode failure")

    monkeypatch.setattr(bing_mod.base64, "urlsafe_b64decode", _raise)
    wrapped = "https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLmNvbQ&ntb=1"
    assert _clean_url(wrapped) == wrapped


# ---------------------------------------------------------------------------
# _build_results
# ---------------------------------------------------------------------------

def test_build_results_unwraps_url_and_maps_fields():
    items = [{
        "url": "https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9yZWFscHl0aG9uLmNvbS9hc3luYy1pby1weXRob24v&ntb=1",
        "title": "Python's asyncio: A Hands-On Walkthrough",
        "snippet": "Explore how...",
    }]
    results = _build_results(items, max_results=10)
    assert len(results) == 1
    assert results[0].url == "https://realpython.com/async-io-python/"
    assert results[0].title == "Python's asyncio: A Hands-On Walkthrough"
    assert results[0].engine == "bing"
    assert results[0].position == 1


def test_build_results_skips_items_without_url():
    items = [{"url": "", "title": "no url", "snippet": ""}, {"url": "https://example.com", "title": "ok", "snippet": ""}]
    results = _build_results(items, max_results=10)
    assert len(results) == 1
    assert results[0].url == "https://example.com"


def test_build_results_respects_max_results_cap():
    items = [{"url": f"https://example.com/{i}", "title": str(i), "snippet": ""} for i in range(20)]
    results = _build_results(items, max_results=5)
    assert len(results) == 5
    assert [r.position for r in results] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# _parse_results
# ---------------------------------------------------------------------------

class _FakeTab:
    def __init__(self, raw_value):
        self._raw_value = raw_value

    async def execute_script(self, script):
        return {"result": {"result": {"value": self._raw_value}}}


@pytest.mark.asyncio
async def test_parse_results_raises_on_invalid_json():
    """2026-09-09: the except (json.JSONDecodeError, TypeError): return [] handler was removed —
    no supporting observation (handler dates from the first engine commit, 0 ERROR_PARSE in 4566
    logged engine records, the value is always our own stringified JSON). A malformed value now
    raises out of _parse_results, propagating into search_web's own _classify_engine_exception
    (ERROR_PARSE) instead of masquerading as an empty page."""
    tab = _FakeTab("not valid json{")
    with pytest.raises(json.JSONDecodeError):
        await _parse_results(tab, max_results=10)
