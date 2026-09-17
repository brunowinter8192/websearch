# INFRASTRUCTURE
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from pydoll.commands import StorageCommands

from _mojeek_pydoll_probe_core import (
    BLOCK_MARKER_TEXT, IN_FLIGHT_MARKER_TEXT, RESULT_LINK_SELECTOR,
    STATE_CHALLENGE_PENDING, STATE_RESULTS, STATE_UNKNOWN,
    classify_page_state, classify_query_verdict, extract_pow_time_ms, extract_widget_states,
    fingerprint_cookies, is_terminal_state,
)
from _mojeek_pydoll_probe_js import (
    DRAIN_EVENTS_JS, FIRE_VERIFY_JS, WIDGET_DETAIL_JS, build_attach_events_js, build_facts_js,
)
from _mojeek_pydoll_probe_launch import kill_tab, new_tab

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.2
NAV_TIMEOUT_S = 30.0
QUERY_BUDGET_S = 60.0
COOKIE_DOMAIN_FILTER = "mojeek"

FACTS_JS = build_facts_js(RESULT_LINK_SELECTOR, BLOCK_MARKER_TEXT, IN_FLIGHT_MARKER_TEXT)
ATTACH_EVENTS_JS = build_attach_events_js()


@dataclass
class QueryMeasurement:
    label: str
    url: str
    challenge_served: bool = False
    final_state: str = STATE_UNKNOWN
    verdict: str = ""
    verify_fired: bool = False
    result_link_count: int = 0
    sample_hrefs: list = field(default_factory=list)
    page_title: str | None = None
    final_url: str | None = None
    widget_state: str | None = None
    widget_states_observed: list = field(default_factory=list)
    pow_time_ms: float | None = None
    widget_detail: dict = field(default_factory=dict)
    nav_ms: float | None = None
    widget_seen_ms: float | None = None
    verify_fired_ms: float | None = None
    verifying_ms: float | None = None
    verified_ms: float | None = None
    results_ms: float | None = None
    total_ms: float | None = None
    new_tab_ms: float | None = None
    kill_tab_ms: float | None = None
    first_poll_state: str | None = None
    state_trace: list = field(default_factory=list)
    events: list = field(default_factory=list)
    event_clock_offset_ms: float | None = None
    cookies_before: list = field(default_factory=list)
    cookies_after_nav: list = field(default_factory=list)
    cookies_after_settle: list = field(default_factory=list)
    nav_error: str | None = None


# FUNCTIONS

def _extract_value(result):
    try:
        return result["result"]["result"]["value"]
    except (KeyError, TypeError):
        return None


async def _eval_json(tab, script: str) -> dict | list | None:
    raw = await tab.execute_script(script)
    value = _extract_value(raw)
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


async def read_cookie_fingerprints(tab, domain_filter: str | None = COOKIE_DOMAIN_FILTER) -> list[dict]:
    response = await tab._execute_command(StorageCommands.get_cookies())
    cookies = response["result"]["cookies"]
    return fingerprint_cookies([dict(c) for c in cookies], domain_filter)


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


async def _drain_events(tab, measurement: QueryMeasurement) -> None:
    drained = await _eval_json(tab, DRAIN_EVENTS_JS)
    if drained:
        measurement.events.extend(drained)


def _record_state(record: dict) -> str | None:
    if record.get("event") != "statechange":
        return None
    detail = record.get("detail")
    if not detail:
        return None
    try:
        return json.loads(detail).get("state")
    except (json.JSONDecodeError, TypeError):
        return None


def _event_rel_ms(measurement: QueryMeasurement, record: dict, poll_ms: float) -> float:
    if measurement.event_clock_offset_ms is None or record.get("t_ms") is None:
        return poll_ms
    return record["t_ms"] + measurement.event_clock_offset_ms


def _record_event_marks(measurement: QueryMeasurement, t0: float) -> None:
    poll_ms = (time.perf_counter() - t0) * 1000
    measurement.widget_states_observed = extract_widget_states(measurement.events)
    for record in measurement.events:
        if measurement.verifying_ms is None and _record_state(record) == "verifying":
            measurement.verifying_ms = _event_rel_ms(measurement, record, poll_ms)
        if measurement.verified_ms is None and record.get("event") == "verified":
            measurement.verified_ms = _event_rel_ms(measurement, record, poll_ms)


async def _fire_verify(tab, measurement: QueryMeasurement, t0: float) -> None:
    fired = await _eval_json(tab, FIRE_VERIFY_JS)
    if fired and fired.get("fired"):
        measurement.verify_fired = True
        measurement.verify_fired_ms = (time.perf_counter() - t0) * 1000
        logger.info("verify() dispatched for %s", measurement.label)


async def _capture_widget_detail(tab, measurement: QueryMeasurement) -> None:
    if measurement.widget_detail:
        return
    detail = await _eval_json(tab, WIDGET_DETAIL_JS)
    if detail:
        measurement.widget_detail = detail


def _apply_facts(measurement: QueryMeasurement, facts: dict) -> str:
    state = classify_page_state(facts)
    measurement.state_trace.append(state)
    if measurement.first_poll_state is None:
        measurement.first_poll_state = state
    measurement.result_link_count = facts.get("result_link_count", 0)
    measurement.sample_hrefs = facts.get("sample_hrefs") or []
    measurement.page_title = facts.get("title")
    measurement.final_url = facts.get("url")
    measurement.widget_state = facts.get("widget_state")
    if facts.get("widget_present"):
        measurement.challenge_served = True
    return state


async def _poll_until_settled(tab, measurement: QueryMeasurement, t0: float, budget_s: float) -> str:
    deadline = t0 + budget_s
    state = STATE_UNKNOWN
    attached = False
    while True:
        facts = await _eval_json(tab, FACTS_JS)
        if facts is None:
            facts = {}
        state = _apply_facts(measurement, facts)
        if measurement.challenge_served and measurement.widget_seen_ms is None:
            measurement.widget_seen_ms = (time.perf_counter() - t0) * 1000
        if facts.get("widget_present") and not attached:
            await _capture_widget_detail(tab, measurement)
            attached_result = await _eval_json(tab, ATTACH_EVENTS_JS)
            attached = bool(attached_result and attached_result.get("attached"))
            if attached and attached_result.get("now") is not None:
                rel_ms = (time.perf_counter() - t0) * 1000
                measurement.event_clock_offset_ms = rel_ms - attached_result["now"]
        if attached:
            await _drain_events(tab, measurement)
            _record_event_marks(measurement, t0)
        if (
            not measurement.verify_fired
            and state == STATE_CHALLENGE_PENDING
            and facts.get("verify_is_function")
        ):
            await _fire_verify(tab, measurement, t0)
        if state == STATE_RESULTS and measurement.results_ms is None:
            measurement.results_ms = (time.perf_counter() - t0) * 1000
        if is_terminal_state(state) or time.perf_counter() >= deadline:
            return state
        await asyncio.sleep(POLL_INTERVAL_S)


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
        measurement.pow_time_ms = extract_pow_time_ms(measurement.events)
        measurement.cookies_after_settle = await read_cookie_fingerprints(tab)
        return measurement
    finally:
        t_kill = time.perf_counter()
        await kill_tab(handle, tab)
        measurement.kill_tab_ms = (time.perf_counter() - t_kill) * 1000
