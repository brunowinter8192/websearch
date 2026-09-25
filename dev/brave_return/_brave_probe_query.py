# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from pydoll.commands import InputCommands, StorageCommands
from pydoll.protocol.input.types import MouseButton, MouseEventType

from _brave_probe_core import (
    STATE_BUTTON_PENDING, STATE_UNKNOWN,
    classify_page_state, classify_query_verdict, fingerprint_cookies, is_terminal_state,
)
from _brave_probe_js import build_facts_js, build_trigger_js
from _brave_probe_launch import kill_tab, new_tab

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.2
NAV_TIMEOUT_S = 15.0
QUERY_BUDGET_S = 30.0
COOKIE_DOMAIN_FILTER = "brave"

FACTS_JS = build_facts_js()
TRIGGER_JS = build_trigger_js()


# FUNCTIONS

async def verify_environment_reachable(handle, control_url: str) -> None:
    tab = await new_tab(handle)
    try:
        await tab.go_to(control_url, timeout=NAV_TIMEOUT_S)
        facts = await _eval_json(tab, FACTS_JS)
        if facts is None:
            raise RuntimeError(f"control page at {control_url} returned no readable DOM facts")
    except Exception as e:
        raise RuntimeError(
            f"Environment tripwire: control navigation to {control_url} failed ({e}) - aborting "
            "the whole probe rather than producing verdicts that cannot be trusted."
        ) from e
    finally:
        await kill_tab(handle, tab)


@dataclass
class QueryMeasurement:
    label: str
    url: str
    challenge_served: bool = False
    final_state: str = STATE_UNKNOWN
    verdict: str = ""
    trigger_attempted: bool = False
    trigger_mechanism: str | None = None
    trigger_found_button: bool = False
    button_in_shadow: bool | None = None
    result_link_count: int = 0
    page_title: str | None = None
    final_url: str | None = None
    nav_ms: float | None = None
    button_seen_ms: float | None = None
    trigger_fired_ms: float | None = None
    results_ms: float | None = None
    total_ms: float | None = None
    new_tab_ms: float | None = None
    kill_tab_ms: float | None = None
    first_poll_state: str | None = None
    state_trace: list = field(default_factory=list)
    cookies_before: list = field(default_factory=list)
    cookies_after_nav: list = field(default_factory=list)
    cookies_after_settle: list = field(default_factory=list)
    nav_error: str | None = None


async def run_query(handle, label: str, url: str, budget_s: float = QUERY_BUDGET_S) -> QueryMeasurement:
    measurement = QueryMeasurement(label=label, url=url)
    t_tab = time.perf_counter()
    tab = await new_tab(handle)
    measurement.new_tab_ms = (time.perf_counter() - t_tab) * 1000
    try:
        measurement.cookies_before = await read_cookie_fingerprints(tab)
        t0 = time.perf_counter()
        try:
            await tab.go_to(url, timeout=NAV_TIMEOUT_S)
        except Exception as e:
            measurement.nav_error = str(e)
            logger.warning("navigation to %s failed: %s", url, e)
        measurement.nav_ms = (time.perf_counter() - t0) * 1000
        measurement.cookies_after_nav = await read_cookie_fingerprints(tab)
        final_state = await _poll_until_settled(tab, measurement, t0, budget_s)
        measurement.total_ms = (time.perf_counter() - t0) * 1000
        measurement.final_state = final_state
        measurement.verdict = classify_query_verdict(measurement.challenge_served, final_state)
        measurement.cookies_after_settle = await read_cookie_fingerprints(tab)
        return measurement
    finally:
        t_kill = time.perf_counter()
        await kill_tab(handle, tab)
        measurement.kill_tab_ms = (time.perf_counter() - t_kill) * 1000


async def read_cookie_fingerprints(tab, domain_filter: str | None = COOKIE_DOMAIN_FILTER) -> list[dict]:
    response = await tab._execute_command(StorageCommands.get_cookies())
    cookies = response["result"]["cookies"]
    return fingerprint_cookies([dict(c) for c in cookies], domain_filter)


async def _poll_until_settled(tab, measurement: QueryMeasurement, t0: float, budget_s: float) -> str:
    deadline = t0 + budget_s
    state = STATE_UNKNOWN
    while True:
        facts = await _eval_json(tab, FACTS_JS)
        if facts is None:
            facts = {}
        state = _apply_facts(measurement, facts)
        if state == STATE_BUTTON_PENDING and measurement.button_seen_ms is None:
            measurement.button_seen_ms = (time.perf_counter() - t0) * 1000
        if state == STATE_BUTTON_PENDING and not measurement.trigger_attempted:
            await _attempt_trigger(tab, measurement, t0)
        if measurement.result_link_count > 0 and measurement.results_ms is None:
            measurement.results_ms = (time.perf_counter() - t0) * 1000
        if is_terminal_state(state) or time.perf_counter() >= deadline:
            return state
        await asyncio.sleep(POLL_INTERVAL_S)


def _apply_facts(measurement: QueryMeasurement, facts: dict) -> str:
    state = classify_page_state(facts)
    measurement.state_trace.append(state)
    if measurement.first_poll_state is None:
        measurement.first_poll_state = state
    measurement.result_link_count = facts.get("result_link_count", 0)
    measurement.page_title = facts.get("title")
    measurement.final_url = facts.get("url")
    if facts.get("button_candidates") or facts.get("pow_link_present") or facts.get("marker_present"):
        measurement.challenge_served = True
    return state


async def _attempt_trigger(tab, measurement: QueryMeasurement, t0: float) -> None:
    measurement.trigger_attempted = True
    result = await _eval_json(tab, TRIGGER_JS)
    if not result or not result.get("found"):
        measurement.trigger_mechanism = "none_found"
        return
    measurement.trigger_found_button = True
    measurement.button_in_shadow = result.get("in_shadow")
    if result.get("clicked"):
        measurement.trigger_mechanism = "js_click"
        measurement.trigger_fired_ms = (time.perf_counter() - t0) * 1000
        return
    rect = result.get("rect")
    if rect and rect.get("width") and rect.get("height"):
        await _dispatch_cdp_click(tab, rect)
        measurement.trigger_mechanism = "cdp_dispatch"
        measurement.trigger_fired_ms = (time.perf_counter() - t0) * 1000


async def _eval_json(tab, script: str) -> dict | list | None:
    raw = await tab.execute_script(script)
    value = _extract_value(raw)
    if not value:
        return None
    return json.loads(value)


async def _dispatch_cdp_click(tab, rect: dict) -> None:
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    await tab._execute_command(InputCommands.dispatch_mouse_event(
        type=MouseEventType.MOUSE_PRESSED, x=int(x), y=int(y), button=MouseButton.LEFT, click_count=1,
    ))
    await tab._execute_command(InputCommands.dispatch_mouse_event(
        type=MouseEventType.MOUSE_RELEASED, x=int(x), y=int(y), button=MouseButton.LEFT, click_count=1,
    ))


def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None
