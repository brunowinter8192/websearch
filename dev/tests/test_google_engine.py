"""Tests for src/search/engines/google.py's redirect-resolution fix (process-docs/search_pipeline/
google_goto_redirect_fix.md carries the investigation and the measurements behind the numbers
used here).

Two layers, following this project's established split for scraping engines (test_yandex_engine.py,
test_startpage_engine.py etc.): no engine's own DOM-parsing JS is ever run in this suite —
conftest.py's autouse _no_real_browser_launch fixture traps any real browser launch project-wide,
not just against real Google, so there is no path to exercising _JS_PARSE itself without violating
that trap. What IS tested:

- _build_results: pure Python, fed item dicts shaped exactly like what _JS_PARSE would produce
  (title/snippet/date/url), derived from the real HTML this milestone's investigation saved
  (dev/access_recovery/html/google_dom_probe_20260918_181820/
  best-noise-cancelling-headphones-2025_num10.html, gitignored — read directly during the
  investigation, its 8 organic results are reproduced as dev/search_pipeline/_google_fixture.py's
  HAPPY_SPECS).
- _resolve_urls: real local HTTP against dev/search_pipeline/_google_fixture.py's fixture server —
  real network I/O, but loopback-only, instant, never touches real Google.

The one exception is a source-level regression guard for the second bug found during this
milestone (the pre-existing .wHYlTd snippet-selector bug, unrelated to the redirect fix) — since
that fix lives entirely inside the _JS_PARSE JS string and is therefore just as untestable at
runtime as the rest of the JS, the guard checks the JS source text itself instead.
"""
import pytest

from src.search.engines import google as google_mod
from src.search.engines.google import _build_results, _resolve_urls
from dev.search_pipeline._google_fixture import (
    ResultSpec, HAPPY_SPECS, start_fixture_server, stop_fixture_server, goto_url,
)


# ---------------------------------------------------------------------------
# _build_results — pure Python, evidence-derived item dicts, no network
# ---------------------------------------------------------------------------

def test_build_results_maps_title_snippet_date_and_position():
    items = [
        {"url": "https://www.google.com/goto?url=ok1", "title": "The Best ANC Headphones to Buy in 2025",
         "snippet": "The Sennheiser HDB 630 is considered by many to be the best ANC headphone\xa0...",
         "date": "21 Nov 2025"},
        {"url": "https://www.google.com/goto?url=ok3", "title": "Best Noise Cancelling Headphones 2026 (50+ Tested!)",
         "snippet": "Our 2025 noise cancelling award winner from last year was the Sony XM6\xa0...",
         "date": None},
    ]
    results = _build_results(items, max_results=10)
    assert len(results) == 2
    assert results[0].title == "The Best ANC Headphones to Buy in 2025"
    assert results[0].date == "21 Nov 2025"
    assert results[0].position == 1
    assert results[1].date is None
    assert results[1].position == 2
    assert all(r.engine == "google" for r in results)


def test_build_results_drops_items_with_empty_url():
    items = [{"url": "", "title": "no url", "snippet": "", "date": None}]
    assert _build_results(items, max_results=10) == []


def test_build_results_respects_max_results_cap():
    items = [{"url": f"https://www.google.com/goto?url=ok{i}", "title": str(i), "snippet": "", "date": None}
             for i in range(20)]
    results = _build_results(items, max_results=5)
    assert len(results) == 5


def test_build_results_empty_items_produces_clean_empty_not_exception():
    assert _build_results([], max_results=10) == []


# ---------------------------------------------------------------------------
# The .wHYlTd snippet-selector bug — a second, independently found bug (real
# Google markup wraps the ENTIRE result block, title+cite+snippet, in a .wHYlTd
# div; it is an ancestor of the real snippet element .VwiC3b, not the snippet
# itself, so it was silently returning garbled composite text as the "snippet"
# for every Google result). Source-level guard since the JS cannot run here.
# ---------------------------------------------------------------------------

def test_js_parse_no_longer_prioritizes_wHYlTd_as_snippet_selector():
    assert ".wHYlTd" not in google_mod._JS_PARSE
    assert ".VwiC3b" in google_mod._JS_PARSE


# ---------------------------------------------------------------------------
# _resolve_urls — real local HTTP, dev/search_pipeline/_google_fixture.py's server, loopback only
# ---------------------------------------------------------------------------

def _items_from_specs(specs: list[ResultSpec], port: int) -> list[dict]:
    return [
        {"url": goto_url(port, s.token), "title": s.title, "snippet": s.snippet, "date": s.date}
        for s in specs
    ]


@pytest.mark.asyncio
async def test_eight_results_from_fixture_each_have_title_snippet_and_resolved_url():
    server, thread, port = start_fixture_server(HAPPY_SPECS)
    try:
        items = _items_from_specs(HAPPY_SPECS, port)
        parsed = _build_results(items, max_results=10)
        resolved, _ = await _resolve_urls(parsed)
    finally:
        stop_fixture_server(server, thread)

    assert len(resolved) == 8
    for spec, r in zip(HAPPY_SPECS, resolved):
        assert r.title == spec.title
        assert r.snippet == spec.snippet
        assert r.url == f"http://127.0.0.1:{port}/target/{spec.target}"
        assert r.date == spec.date
    assert [r.position for r in resolved] == list(range(1, 9))


@pytest.mark.asyncio
async def test_each_unhappy_goto_case_drops_only_its_own_result():
    specs = [
        ResultSpec(title="ok-a", snippet="", date=None, token="ok_a", behavior="ok", target="ta"),
        ResultSpec(title="bad-status", snippet="", date=None, token="bad1", behavior="bad_status"),
        ResultSpec(title="ok-b", snippet="", date=None, token="ok_b", behavior="ok", target="tb"),
        ResultSpec(title="no-location", snippet="", date=None, token="bad2", behavior="no_location"),
        ResultSpec(title="ok-c", snippet="", date=None, token="ok_c", behavior="ok", target="tc"),
        ResultSpec(title="bad-location", snippet="", date=None, token="bad3", behavior="bad_location"),
    ]
    server, thread, port = start_fixture_server(specs)
    try:
        items = _items_from_specs(specs, port)
        parsed = _build_results(items, max_results=10)
        resolved, _ = await _resolve_urls(parsed)
    finally:
        stop_fixture_server(server, thread)

    titles = {r.title for r in resolved}
    assert titles == {"ok-a", "ok-b", "ok-c"}
    assert len(resolved) == 3


@pytest.mark.asyncio
async def test_two_goto_blobs_resolving_to_same_destination_collapse_to_one():
    specs = [
        ResultSpec(title="dup-a", snippet="", date=None, token="dup_a", behavior="ok", target="shared"),
        ResultSpec(title="dup-b", snippet="", date=None, token="dup_b", behavior="ok", target="shared"),
        ResultSpec(title="unique", snippet="", date=None, token="uniq", behavior="ok", target="only"),
    ]
    server, thread, port = start_fixture_server(specs)
    try:
        items = _items_from_specs(specs, port)
        parsed = _build_results(items, max_results=10)
        resolved, _ = await _resolve_urls(parsed)
    finally:
        stop_fixture_server(server, thread)

    assert len(resolved) == 2
    urls = [r.url for r in resolved]
    assert len(set(urls)) == 2
    assert f"http://127.0.0.1:{port}/target/shared" in urls
    assert f"http://127.0.0.1:{port}/target/only" in urls


@pytest.mark.asyncio
async def test_all_results_failing_to_resolve_produces_clean_empty_not_exception():
    specs = [
        ResultSpec(title="bad-status", snippet="", date=None, token="bad1", behavior="bad_status"),
        ResultSpec(title="no-location", snippet="", date=None, token="bad2", behavior="no_location"),
    ]
    server, thread, port = start_fixture_server(specs)
    try:
        items = _items_from_specs(specs, port)
        parsed = _build_results(items, max_results=10)
        resolved, _ = await _resolve_urls(parsed)
    finally:
        stop_fixture_server(server, thread)

    assert resolved == []


@pytest.mark.asyncio
async def test_resolve_urls_on_empty_input_is_a_clean_noop():
    resolved, stats = await _resolve_urls([])
    assert resolved == []
    assert stats == {"found": 0, "resolved": 0, "dropped": 0, "reasons": {}}
