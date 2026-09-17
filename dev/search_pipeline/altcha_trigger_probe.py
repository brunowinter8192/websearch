# INFRASTRUCTURE
import asyncio
import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from patchright.async_api import async_playwright

from _altcha_trigger_probe_cdp import cdp_find_widget_node, cdp_click_node, locate_interactive_element
from _altcha_trigger_probe_js import VERIFY_IS_FUNCTION_JS, FIRE_VERIFY_JS, INSPECTION_JS, build_init_script, build_outcome_js
from _altcha_trigger_probe_launch import (
    resolve_chromium_bundle_path, build_launch_flags, self_launch_chrome,
    wait_for_devtools_port, focus_steal_watchdog, kill_by_profile,
)
from _altcha_trigger_probe_report import build_report_md, write_report

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "md"

CONTROL_URL = "https://example.org/"
SEARCH_URL = "https://www.mojeek.com/search?q=python+asyncio+tutorial"

NAV_TIMEOUT_S = 30.0
READY_TIMEOUT_S = 15.0
EVENT_WAIT_TIMEOUT_S = 30.0
SETTLE_TIMEOUT_S = 60.0
SETTLE_POLL_INTERVAL_S = 1.0
PAUSE_BETWEEN_RUNS_S = 30.0
CDP_PORT_WAIT_TIMEOUT_S = 10.0

RESULT_LINK_SELECTOR = "ul.results-standard > li > a.ob"
BLOCK_MARKER_TEXT = "Verification required"
IN_FLIGHT_MARKER_TEXT = "Checking verification with server..."

ALTCHA_DOCUMENTED_DEFAULTS = {
    "minDuration": 500,
    "timeout": 90000,
    "humanInteractionSignature": True,
}

TRIGGER_ORDER = ["verify_call", "auto_onload", "real_click"]


@dataclass
class ProbeSession:
    profile_dir: str
    bundle_stem: str
    watchdog_task: asyncio.Task
    playwright: object
    browser: object
    context: object
    page: object
    cdp: object
    events: list = field(default_factory=list)
    new_event: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class InspectionResult:
    widget_found: bool
    attributes: dict = field(default_factory=dict)
    configuration: dict | None = None
    state: str | None = None
    shadow_mode: str | None = None
    interactive_element_selector: str | None = None
    interactive_element_tag: str | None = None
    form_outer_html: str | None = None
    widget_outer_html: str | None = None
    his_enabled: bool | None = None
    config_diffs: list = field(default_factory=list)
    page_title: str | None = None
    events: list = field(default_factory=list)
    error: str | None = None


@dataclass
class TriggerResult:
    trigger: str
    events: list = field(default_factory=list)
    element_found: bool = False
    load_event_observed: bool = False
    verify_is_function: bool | None = None
    computation_started: bool = False
    verified_fired: bool = False
    final_state: str | None = None
    page_outcome: str = "UNKNOWN"
    page_outcome_detail: dict = field(default_factory=dict)
    click_target: dict | None = None
    click_delivered: bool | None = None
    verdict: str = "NEVER_STARTED"
    error: str | None = None


# ORCHESTRATOR

async def probe_workflow() -> None:
    inspection = await run_inspection()
    await asyncio.sleep(PAUSE_BETWEEN_RUNS_S)
    trigger_results = []
    for trigger in TRIGGER_ORDER:
        result = await run_trigger_attempt(trigger)
        trigger_results.append(result)
        await asyncio.sleep(PAUSE_BETWEEN_RUNS_S)
    report = build_report_md(
        inspection, trigger_results, SEARCH_URL, PAUSE_BETWEEN_RUNS_S,
        RESULT_LINK_SELECTOR, BLOCK_MARKER_TEXT, IN_FLIGHT_MARKER_TEXT, SETTLE_TIMEOUT_S,
    )
    write_report(report, REPORT_DIR)


# FUNCTIONS

async def _open_probe_session(profile_prefix: str, set_auto_onload: bool) -> ProbeSession:
    profile_dir = tempfile.mkdtemp(prefix=profile_prefix)
    try:
        bundle_path = await resolve_chromium_bundle_path()
        flags = build_launch_flags()
        watchdog_task = asyncio.create_task(focus_steal_watchdog(bundle_path.stem))
        self_launch_chrome(bundle_path, profile_dir, flags)
        port = await asyncio.to_thread(wait_for_devtools_port, profile_dir, CDP_PORT_WAIT_TIMEOUT_S)
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        session = ProbeSession(
            profile_dir=profile_dir, bundle_stem=bundle_path.stem, watchdog_task=watchdog_task,
            playwright=playwright, browser=browser, context=context, page=page, cdp=cdp,
        )

        async def _forward(payload: str) -> None:
            session.events.append(json.loads(payload))
            session.new_event.set()

        await page.expose_function("__probeForward", _forward)
        await page.add_init_script(build_init_script(set_auto_onload))
        return session
    except Exception:
        await asyncio.to_thread(kill_by_profile, profile_dir)
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise


async def _close_probe_session(session: ProbeSession) -> None:
    session.watchdog_task.cancel()
    try:
        await session.watchdog_task
    except asyncio.CancelledError:
        pass
    try:
        await session.browser.close()
    except Exception as e:
        logger.warning("browser.close() failed (expected to fall through to pkill): %s", e)
    try:
        await session.playwright.stop()
    except Exception as e:
        logger.warning("playwright.stop() failed: %s", e)
    await asyncio.to_thread(kill_by_profile, session.profile_dir)
    shutil.rmtree(session.profile_dir, ignore_errors=True)


async def _verify_environment_reachable(session: ProbeSession) -> None:
    try:
        await session.page.goto(CONTROL_URL, wait_until="load", timeout=NAV_TIMEOUT_S * 1000)
    except Exception as e:
        raise RuntimeError(
            f"Environment tripwire: control navigation to {CONTROL_URL} failed ({e}) — "
            "aborting the whole probe rather than producing verdicts that cannot be trusted."
        ) from e


async def _navigate(session: ProbeSession, url: str) -> str | None:
    try:
        await session.page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_S * 1000)
        return None
    except Exception as e:
        return str(e)


async def _wait_for_event(session: ProbeSession, predicate, timeout_s: float) -> dict | None:
    deadline = time.monotonic() + timeout_s
    while True:
        for record in session.events:
            if predicate(record):
                return record
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            await asyncio.wait_for(session.new_event.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            return None
        session.new_event.clear()


async def _confirm_widget_ready(session: ProbeSession) -> dict:
    try:
        await session.page.wait_for_selector("altcha-widget", state="attached", timeout=READY_TIMEOUT_S * 1000)
        element_found = True
    except Exception as e:
        logger.info("altcha-widget selector wait did not resolve: %s", e)
        element_found = False
    load_record = await _wait_for_event(session, lambda r: r["event"] == "load", READY_TIMEOUT_S)
    verify_is_function = None
    if element_found:
        verify_is_function = await session.page.evaluate(VERIFY_IS_FUNCTION_JS, isolated_context=False)
    return {
        "element_found": element_found,
        "load_event_observed": load_record is not None,
        "verify_is_function": verify_is_function,
    }


def _extract_state(record: dict) -> str | None:
    if record.get("event") != "statechange":
        return None
    detail = record.get("detail")
    if not detail:
        return None
    parsed = json.loads(detail)
    return parsed.get("state")


def _diff_against_documented_defaults(configuration: dict | None) -> list[str]:
    if not configuration:
        return ["configuration unavailable (getConfiguration() returned nothing)"]
    diffs = []
    for key, expected in ALTCHA_DOCUMENTED_DEFAULTS.items():
        if key not in configuration:
            diffs.append(f"{key}: absent from getConfiguration() output (documented default {expected!r})")
            continue
        actual = configuration[key]
        if actual != expected:
            diffs.append(f"{key}: {actual!r} (documented default {expected!r})")
    return diffs


async def run_inspection() -> InspectionResult:
    session = await _open_probe_session("altcha-probe-inspect-", set_auto_onload=False)
    try:
        await _verify_environment_reachable(session)
        nav_error = await _navigate(session, SEARCH_URL)
        if nav_error:
            return InspectionResult(widget_found=False, events=list(session.events), error=nav_error)
        readiness = await _confirm_widget_ready(session)
        if not readiness["element_found"]:
            return InspectionResult(
                widget_found=False, events=list(session.events),
                error="altcha-widget not found in DOM within the ready timeout",
            )
        details = await session.page.evaluate(INSPECTION_JS, isolated_context=False)
        widget_node_id = await cdp_find_widget_node(session.cdp)
        locate = await locate_interactive_element(session.cdp, widget_node_id) if widget_node_id else {}
        configuration = details.get("configuration")
        his_enabled = configuration.get("humanInteractionSignature") if configuration else None
        diffs = _diff_against_documented_defaults(configuration)
        return InspectionResult(
            widget_found=True,
            attributes=details.get("attributes") or {},
            configuration=configuration,
            state=details.get("state"),
            shadow_mode=locate.get("shadow_mode"),
            interactive_element_selector=locate.get("used_selector"),
            interactive_element_tag=locate.get("target_tag"),
            form_outer_html=details.get("form_outer_html"),
            widget_outer_html=details.get("widget_outer_html"),
            his_enabled=his_enabled,
            config_diffs=diffs,
            page_title=details.get("title"),
            events=list(session.events),
            error=None,
        )
    finally:
        await _close_probe_session(session)


async def _fire_verify_call(session: ProbeSession) -> None:
    await session.page.evaluate(FIRE_VERIFY_JS, isolated_context=False)


async def _fire_real_click(session: ProbeSession) -> dict:
    widget_node_id = await cdp_find_widget_node(session.cdp)
    if widget_node_id is None:
        return {"found": False}
    locate = await locate_interactive_element(session.cdp, widget_node_id)
    await cdp_click_node(session.cdp, locate["target_node_id"])
    locate.pop("target_node_id", None)
    return locate


async def _detect_page_outcome(page) -> dict:
    return await page.evaluate(
        build_outcome_js(RESULT_LINK_SELECTOR, BLOCK_MARKER_TEXT, IN_FLIGHT_MARKER_TEXT),
        isolated_context=False,
    )


def _classify_page_outcome(facts: dict) -> str:
    if facts.get("result_link_count", 0) > 0 and not facts.get("block_marker_present"):
        return "RESULTS"
    if facts.get("in_flight_marker_present"):
        return "IN_FLIGHT"
    if facts.get("block_marker_present"):
        return "BLOCKED"
    return "UNKNOWN"


async def _wait_for_page_settle(page) -> dict:
    deadline = time.monotonic() + SETTLE_TIMEOUT_S
    facts = await _detect_page_outcome(page)
    while _classify_page_outcome(facts) in ("UNKNOWN", "IN_FLIGHT") and time.monotonic() < deadline:
        await asyncio.sleep(SETTLE_POLL_INTERVAL_S)
        facts = await _detect_page_outcome(page)
    return facts


def _classify_verdict(computation_started: bool, verified_fired: bool, page_outcome: str) -> str:
    if not computation_started and not verified_fired:
        return "NEVER_STARTED"
    if page_outcome == "RESULTS":
        return "SUCCESS"
    if page_outcome == "IN_FLIGHT":
        return "INCONCLUSIVE_STILL_PENDING"
    return "RAN_REJECTED"


async def run_trigger_attempt(trigger: str) -> TriggerResult:
    set_auto = trigger == "auto_onload"
    session = await _open_probe_session(f"altcha-probe-{trigger}-", set_auto_onload=set_auto)
    try:
        await _verify_environment_reachable(session)
        nav_error = await _navigate(session, SEARCH_URL)
        if nav_error:
            return TriggerResult(trigger=trigger, events=list(session.events), error=nav_error)
        readiness = await _confirm_widget_ready(session)
        if not readiness["element_found"]:
            return TriggerResult(
                trigger=trigger, events=list(session.events),
                element_found=False,
                load_event_observed=readiness["load_event_observed"],
                verify_is_function=readiness["verify_is_function"],
                error="altcha-widget not found in DOM within the ready timeout",
            )
        click_target = None
        if trigger == "verify_call":
            await _fire_verify_call(session)
        elif trigger == "real_click":
            click_target = await _fire_real_click(session)
        await _wait_for_event(
            session,
            lambda r: r["event"] == "verified" or _extract_state(r) in ("verified", "error", "expired"),
            EVENT_WAIT_TIMEOUT_S,
        )
        facts = await _wait_for_page_settle(session.page)
        page_outcome = _classify_page_outcome(facts)
        states = [s for s in (_extract_state(r) for r in session.events) if s]
        computation_started = "verifying" in states
        verified_fired = any(r["event"] == "verified" for r in session.events)
        final_state = states[-1] if states else None
        verdict = _classify_verdict(computation_started, verified_fired, page_outcome)
        click_delivered = None
        if trigger == "real_click":
            click_delivered = any(r["event"] in ("mousedown", "mouseup", "click") for r in session.events)
        return TriggerResult(
            trigger=trigger, events=list(session.events),
            element_found=True,
            load_event_observed=readiness["load_event_observed"],
            verify_is_function=readiness["verify_is_function"],
            computation_started=computation_started,
            verified_fired=verified_fired,
            final_state=final_state,
            page_outcome=page_outcome,
            page_outcome_detail=facts,
            click_target=click_target,
            click_delivered=click_delivered,
            verdict=verdict,
            error=None,
        )
    finally:
        await _close_probe_session(session)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(probe_workflow())
