"""Tests for src/search/engines/mojeek.py — the ALTCHA-challenge plumbing, the parse-readiness
rule, and the result parse.

No network, no browser. Two seams are exercised directly: the pure functions (_is_ready_to_parse,
_should_fire_verify, _build_results) and _await_results driven by a scripted fake tab that
dispatches on script content and records every call, so "verify() was dispatched exactly once" and
"the loop stopped at the deadline" are observable.

Mojeek is the one engine that solves its own challenge, so the plumbing is what breaks silently:
the engine deliberately has NO block-detection early-exit branch. Mojeek's challenge page carries
its boilerplate from the first poll and keeps it there for the whole verification sequence, so any
verdict keyed on that text fires on iteration zero and the challenge is never solved — that defect
cost two wrong live runs in the engine_reduction area. test_block_boilerplate_from_first_poll_does
_not_short_circuit is the regression guard for it.
"""
import json
import time

import pytest

import src.search.engines.mojeek as mojeek_mod
from src.search.engines.mojeek import (
    _await_results, _build_results, _diagnose, _is_ready_to_parse, _parse_results,
    _parse_target, _should_fire_verify,
)


class _ScriptedTab:
    """Returns a queued value per _JS_POLL call; every other script gets a fixed reply.

    Poll replies are dicts (serialised on the way out, the way the real page does). The last entry
    repeats once exhausted, so a test only has to describe the states it cares about.
    """

    def __init__(self, poll_replies, parse_value=None, diagnose_reply=None):
        self.poll_replies = list(poll_replies)
        self.parse_value = parse_value
        self.diagnose_reply = diagnose_reply or {}
        self.verify_calls = 0
        self.poll_calls = 0

    async def execute_script(self, script):
        if script is mojeek_mod._JS_POLL:
            self.poll_calls += 1
            reply = self.poll_replies[min(self.poll_calls - 1, len(self.poll_replies) - 1)]
            return {"result": {"result": {"value": json.dumps(reply)}}}
        if script is mojeek_mod._JS_VERIFY:
            self.verify_calls += 1
            return {"result": {"result": {"value": json.dumps({"fired": True})}}}
        if script is mojeek_mod._JS_DIAGNOSE:
            return {"result": {"result": {"value": json.dumps(self.diagnose_reply)}}}
        return {"result": {"result": {"value": self.parse_value}}}


def _page(links=0, widget=False, verify_ready=False, state=None, note=None):
    return {
        "links": links, "challenge_widget": widget, "verify_ready": verify_ready,
        "challenge_state": state, "captcha_note": note,
    }


async def _run_await_results(tab, deadline, target, partial=None):
    return await _await_results(tab, deadline, target, [], time.perf_counter(), partial)


@pytest.fixture(autouse=True)
def _fast_polls(monkeypatch):
    monkeypatch.setattr(mojeek_mod, "WAIT_INTERVAL", 0.001)


# ---------------------------------------------------------------------------
# _is_ready_to_parse — the sufficiency-or-stability rule
# ---------------------------------------------------------------------------

def test_not_ready_while_no_links_present():
    assert _is_ready_to_parse(0, previous=-1, target=10) is False


def test_ready_immediately_once_a_full_page_is_present():
    assert _is_ready_to_parse(10, previous=-1, target=10) is True


def test_not_ready_on_a_partially_rendered_list():
    """Observed three times live (M1 phase A, both runs, plus the challenge capture): at the
    instant the poll first matches after a solved challenge the link count is 1, not 10."""
    assert _is_ready_to_parse(1, previous=-1, target=10) is False


def test_ready_once_a_growing_list_settles_below_target():
    assert _is_ready_to_parse(3, previous=3, target=10) is True


def test_still_not_ready_while_the_list_is_still_growing():
    assert _is_ready_to_parse(4, previous=1, target=10) is False


def test_target_is_capped_at_one_page_of_results():
    assert _parse_target(100) == 10
    assert _parse_target(5) == 5


# ---------------------------------------------------------------------------
# _should_fire_verify
# ---------------------------------------------------------------------------

def test_fires_when_a_triggerable_widget_is_present():
    assert _should_fire_verify(_page(widget=True, verify_ready=True), already_triggered=False) is True


def test_does_not_fire_twice():
    assert _should_fire_verify(_page(widget=True, verify_ready=True), already_triggered=True) is False


def test_does_not_fire_before_the_widget_exposes_verify():
    assert _should_fire_verify(_page(widget=True, verify_ready=False), already_triggered=False) is False


def test_does_not_fire_when_there_is_no_challenge():
    assert _should_fire_verify(_page(links=10), already_triggered=False) is False


# ---------------------------------------------------------------------------
# _await_results — the common unchallenged path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unchallenged_page_parses_on_the_first_poll_without_firing_verify():
    tab = _ScriptedTab([_page(links=10)])
    trace = await _run_await_results(tab, time.monotonic() + 5, 10)
    assert trace["ready"] is True
    assert trace["poll_count"] == 1
    assert tab.verify_calls == 0
    assert trace["challenge_triggered"] is False


# ---------------------------------------------------------------------------
# _await_results — the challenged path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_challenged_page_fires_verify_once_and_waits_out_the_partial_render():
    tab = _ScriptedTab([
        _page(widget=True, verify_ready=True, state="unverified", note="Waiting for verification."),
        _page(widget=True, verify_ready=True, state="verifying", note="Waiting for verification."),
        _page(widget=True, verify_ready=True, state="verified", note="Checking verification with server..."),
        _page(links=1),
        _page(links=10),
    ])
    trace = await _run_await_results(tab, time.monotonic() + 5, 10)
    assert trace["ready"] is True
    assert trace["challenge_triggered"] is True
    assert tab.verify_calls == 1
    assert trace["link_count"] == 10
    assert trace["poll_count"] == 5


@pytest.mark.asyncio
async def test_block_boilerplate_from_first_poll_does_not_short_circuit():
    """The regression guard. Every poll here carries a live challenge widget and its note text —
    the condition that is true from iteration zero — and the results only arrive on poll 3. An
    engine that treated the challenge page as a terminal verdict would return empty here."""
    tab = _ScriptedTab([
        _page(widget=True, verify_ready=True, state="unverified", note="Waiting for verification."),
        _page(widget=True, verify_ready=True, state="verified", note="Verified successfully. Reloading..."),
        _page(links=10),
    ])
    trace = await _run_await_results(tab, time.monotonic() + 5, 10)
    assert trace["ready"] is True
    assert trace["link_count"] == 10


# ---------------------------------------------------------------------------
# _await_results — budget behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsolved_challenge_gives_up_at_the_deadline_and_reports_it_was_triggered():
    tab = _ScriptedTab([_page(widget=True, verify_ready=True, state="verifying", note="Waiting for verification.")])
    trace = await _run_await_results(tab, time.monotonic() + 0.05, 10)
    assert trace["ready"] is False
    assert trace["challenge_triggered"] is True
    assert tab.verify_calls == 1


@pytest.mark.asyncio
async def test_spent_budget_polls_nothing_at_all():
    tab = _ScriptedTab([_page(links=10)])
    trace = await _run_await_results(tab, time.monotonic() - 1, 10)
    assert trace["ready"] is False
    assert trace["poll_count"] == 0
    assert tab.poll_calls == 0


@pytest.mark.asyncio
async def test_empty_poll_read_is_treated_as_no_facts_yet_not_as_results():
    tab = _ScriptedTab([])
    tab.poll_replies = [{}]
    trace = await _run_await_results(tab, time.monotonic() + 0.05, 10)
    assert trace["ready"] is False
    assert trace["link_count"] == 0


# ---------------------------------------------------------------------------
# _diagnose — the empty-record contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnosis_separates_an_unsolved_challenge_from_a_page_with_no_challenge():
    challenged = _ScriptedTab([], diagnose_reply={
        "title": "Captcha", "url": "https://www.mojeek.com/search?q=x&safe=1", "ready_state": "complete",
        "challenge_widget": True, "challenge_state": "verifying", "captcha_note": "Waiting for verification.",
    })
    diag = await _diagnose(challenged, {"challenge_triggered": True})
    assert diag["challenge_widget"] is True
    assert diag["challenge_triggered"] is True
    assert diag["challenge_state"] == "verifying"
    assert diag["captcha_note"] == "Waiting for verification."

    plain = _ScriptedTab([], diagnose_reply={
        "title": "x - Mojeek Search", "url": "https://www.mojeek.com/search?q=x&safe=1",
        "ready_state": "complete", "challenge_widget": False, "challenge_state": None, "captcha_note": None,
    })
    diag = await _diagnose(plain, {"challenge_triggered": False})
    assert diag["challenge_widget"] is False
    assert diag["challenge_triggered"] is False
    assert diag["captcha_note"] is None


@pytest.mark.asyncio
async def test_diagnosis_leaves_marker_null_because_mojeeks_signal_is_structural():
    """marker is the common text-based block field. Mojeek's own signal is the presence of the
    altcha-widget element, not a keyword, so marker stays None here the way it does for google (a
    URL path) and duckduckgo (an element count). The engine matches no page literal at all: the
    challenge copy was observed served in English on a page whose html lang is 'de', and the
    results page body would contain those same words for anyone who searched them."""
    tab = _ScriptedTab([], diagnose_reply={"title": "Captcha", "challenge_widget": True})
    diag = await _diagnose(tab, {"challenge_triggered": True})
    assert diag["marker"] is None


@pytest.mark.asyncio
async def test_diagnosis_survives_an_unreadable_dom_read():
    tab = _ScriptedTab([], diagnose_reply=None)
    tab.diagnose_reply = {}
    diag = await _diagnose(tab, {})
    assert diag["challenge_triggered"] is False
    assert diag["title"] == ""


# ---------------------------------------------------------------------------
# _build_results / _parse_results
# ---------------------------------------------------------------------------

def test_build_results_maps_fields_and_position():
    items = [
        {"url": "https://realpython.com/async-io-python/", "title": "Asyncio Walkthrough", "snippet": "Explore how..."},
        {"url": "https://docs.python.org/3/library/asyncio.html", "title": "asyncio docs", "snippet": "Reference."},
    ]
    results = _build_results(items, max_results=10)
    assert len(results) == 2
    assert results[0].url == "https://realpython.com/async-io-python/"
    assert results[0].title == "Asyncio Walkthrough"
    assert results[0].snippet == "Explore how..."
    assert results[0].engine == "mojeek"
    assert results[0].position == 1
    assert results[1].position == 2


def test_build_results_skips_items_without_url_without_leaving_a_position_gap():
    items = [{"url": "", "title": "no url", "snippet": ""}, {"url": "https://example.com", "title": "ok", "snippet": ""}]
    results = _build_results(items, max_results=10)
    assert len(results) == 1
    assert results[0].url == "https://example.com"
    assert results[0].position == 1


def test_build_results_respects_max_results_cap():
    items = [{"url": f"https://example.com/{i}", "title": str(i), "snippet": ""} for i in range(20)]
    results = _build_results(items, max_results=5)
    assert len(results) == 5
    assert [r.position for r in results] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_parse_results_raises_on_invalid_json():
    """Matches the 2026-09-09 decision recorded in src/search/engines/DOCS.md: the swallowing
    handler was removed from the browser engines so a parse failure surfaces as ERROR_PARSE
    instead of masquerading as an empty page."""
    tab = _ScriptedTab([], parse_value="not valid json{")
    with pytest.raises(json.JSONDecodeError):
        await _parse_results(tab, max_results=10)


@pytest.mark.asyncio
async def test_parse_results_returns_empty_on_an_unreadable_read():
    tab = _ScriptedTab([], parse_value=None)
    assert await _parse_results(tab, max_results=10) == []
