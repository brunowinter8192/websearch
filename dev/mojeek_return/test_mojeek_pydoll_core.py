# INFRASTRUCTURE
import asyncio
import functools
import http.server
import logging
import shutil
import socket
import tempfile
import threading
from pathlib import Path

from _mojeek_pydoll_check_result import check, report_outcome
from _mojeek_pydoll_probe_core import (
    STATE_BLOCKED, STATE_CHALLENGE_PENDING, STATE_IN_FLIGHT, STATE_RESULTS,
    VERDICT_BLOCKED, VERDICT_STILL_PENDING, VERDICT_SUCCESS_CHALLENGED,
    VERDICT_SUCCESS_UNCHALLENGED, diff_cookie_fingerprints,
)
from _mojeek_pydoll_pure_checks import run_pure_function_checks
from _mojeek_pydoll_probe_launch import kill_tab, launch_browser, new_tab, teardown
from _mojeek_pydoll_probe_report import build_report_md
from mojeek_pydoll_probe import Phase, build_persistence_record, count_live_requests, snapshot_cookie_store
from _mojeek_pydoll_probe_query import read_cookie_fingerprints, run_query, verify_environment_reachable

SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = SCRIPT_DIR / "fixtures"

SET_COOKIE_PATH = "/setcookie"
SET_COOKIE_HTML = b"<!doctype html><html><head><title>cookie fixture</title></head><body><p>cookie set</p></body></html>"
PERSISTENT_COOKIE = "fixture_gate=persistent-value; Path=/; Max-Age=3600"
SESSION_COOKIE = "fixture_session=session-value; Path=/"

STUCK_BUDGET_S = 5.0
BLOCKED_BUDGET_S = 10.0
FIXTURE_BUDGET_S = 15.0

_fixture_measurements: dict = {}


class _FixtureHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith(SET_COOKIE_PATH):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Set-Cookie", PERSISTENT_COOKIE)
            self.send_header("Set-Cookie", SESSION_COOKIE)
            self.send_header("Content-Length", str(len(SET_COOKIE_HTML)))
            self.end_headers()
            self.wfile.write(SET_COOKIE_HTML)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        return


# ORCHESTRATOR

async def test_workflow() -> int:
    run_pure_function_checks()
    server, base_url = start_fixture_server()
    profile_dir = tempfile.mkdtemp(prefix="mojeek-fixture-profile-")
    handle = await launch_browser(profile_dir)
    try:
        await check_tripwire_aborts_on_dead_control(handle)
        await check_tripwire_passes_on_live_control(handle, base_url)
        await check_results_page_without_challenge(handle, base_url)
        await check_challenge_success_path(handle, base_url)
        await check_stuck_challenge_is_not_blocked(handle, base_url)
        await check_genuine_block(handle, base_url)
        await check_cookie_capture_and_diff(handle, base_url)
        check_report_builds_from_fixture_measurements(profile_dir)
    finally:
        await teardown(handle)
        shutil.rmtree(profile_dir, ignore_errors=True)
        server.shutdown()
    return report_outcome()


# FUNCTIONS

def start_fixture_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_FixtureHandler, directory=str(FIXTURE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


async def check_tripwire_aborts_on_dead_control(handle) -> None:
    dead_url = f"http://127.0.0.1:{_free_port()}/"
    raised = None
    try:
        await verify_environment_reachable(handle, dead_url)
    except RuntimeError as e:
        raised = e
    check(
        "tripwire aborts loudly when the control URL is unreachable",
        raised is not None and "Environment tripwire" in str(raised),
        f"got {raised!r}",
    )


async def check_tripwire_passes_on_live_control(handle, base_url: str) -> None:
    passed = True
    try:
        await verify_environment_reachable(handle, f"{base_url}/results_no_challenge.html")
    except RuntimeError:
        passed = False
    check("tripwire stays silent when the control URL is reachable", passed)


async def check_results_page_without_challenge(handle, base_url: str) -> None:
    m = await run_query(handle, "fixture_results", f"{base_url}/results_no_challenge.html", FIXTURE_BUDGET_S)
    _fixture_measurements["results"] = m
    check(
        "an unchallenged results page is SUCCESS_UNCHALLENGED",
        m.verdict == VERDICT_SUCCESS_UNCHALLENGED and not m.challenge_served,
        f"got {m.verdict}, challenge_served={m.challenge_served}",
    )
    check("result links are counted", m.result_link_count == 3, f"got {m.result_link_count}")
    check("the results clock stops", m.results_ms is not None and m.results_ms <= m.total_ms)


async def check_challenge_success_path(handle, base_url: str) -> None:
    m = await run_query(handle, "fixture_challenge", f"{base_url}/challenge_success.html", FIXTURE_BUDGET_S)
    _fixture_measurements["challenge"] = m
    check(
        "verify() fired through pydoll reaches a page-defined custom element method",
        m.verify_fired,
        f"widget_detail={m.widget_detail}",
    )
    check(
        "a solved challenge ending in results is SUCCESS_CHALLENGED",
        m.verdict == VERDICT_SUCCESS_CHALLENGED and m.challenge_served,
        f"got {m.verdict}",
    )
    check(
        "the first poll is not a terminal verdict although the block text is present from t0",
        m.first_poll_state not in (STATE_RESULTS, STATE_BLOCKED),
        f"got {m.first_poll_state}",
    )
    check(
        "widget states are observed through the event buffer",
        "verifying" in m.widget_states_observed and "verified" in m.widget_states_observed,
        f"got {m.widget_states_observed}",
    )
    check("PoW time is captured from the live widget payload", m.pow_time_ms == 128.1, f"got {m.pow_time_ms}")
    check(
        "timing marks are ordered nav -> widget -> verify -> verified -> results",
        _marks_are_ordered(m),
        f"nav={m.nav_ms} widget={m.widget_seen_ms} verify={m.verify_fired_ms} "
        f"verified={m.verified_ms} results={m.results_ms}",
    )
    check(
        "getConfiguration is captured off the widget",
        (m.widget_detail.get("configuration") or {}).get("humanInteractionSignature") is True,
        f"got {m.widget_detail}",
    )


def _marks_are_ordered(m) -> bool:
    marks = [m.nav_ms, m.widget_seen_ms, m.verify_fired_ms, m.verified_ms, m.results_ms]
    if any(mark is None for mark in marks):
        return False
    return all(marks[i] <= marks[i + 1] for i in range(len(marks) - 1))


async def check_stuck_challenge_is_not_blocked(handle, base_url: str) -> None:
    m = await run_query(handle, "fixture_stuck", f"{base_url}/challenge_stuck.html", STUCK_BUDGET_S)
    _fixture_measurements["stuck"] = m
    check(
        "a still-open server round trip is INCONCLUSIVE_STILL_PENDING, never BLOCKED",
        m.verdict == VERDICT_STILL_PENDING and m.final_state == STATE_IN_FLIGHT,
        f"got {m.verdict}/{m.final_state}",
    )
    check(
        "the stuck run actually spent its budget instead of exiting on iteration zero",
        m.total_ms >= STUCK_BUDGET_S * 1000 * 0.9,
        f"got {m.total_ms}ms for a {STUCK_BUDGET_S}s budget",
    )


async def check_genuine_block(handle, base_url: str) -> None:
    m = await run_query(handle, "fixture_blocked", f"{base_url}/challenge_blocked.html", BLOCKED_BUDGET_S)
    _fixture_measurements["blocked"] = m
    check(
        "a refusal after the in-flight marker clears is BLOCKED",
        m.verdict == VERDICT_BLOCKED and m.final_state == STATE_BLOCKED,
        f"got {m.verdict}/{m.final_state}",
    )
    check(
        "the blocked run passed through the non-terminal states first",
        STATE_CHALLENGE_PENDING in m.state_trace and STATE_IN_FLIGHT in m.state_trace,
        f"got {m.state_trace}",
    )
    check(
        "a genuine block terminates before the budget runs out",
        m.total_ms < BLOCKED_BUDGET_S * 1000,
        f"got {m.total_ms}ms",
    )


async def check_cookie_capture_and_diff(handle, base_url: str) -> None:
    tab = await new_tab(handle)
    try:
        await tab.go_to(f"{base_url}/results_no_challenge.html", timeout=15)
        before = await read_cookie_fingerprints(tab, "127.0.0.1")
        await tab.go_to(f"{base_url}{SET_COOKIE_PATH}", timeout=15)
        after = await read_cookie_fingerprints(tab, "127.0.0.1")
    finally:
        await kill_tab(handle, tab)
    diff = diff_cookie_fingerprints(before, after)
    added = {c["name"]: c for c in diff["added"]}
    check(
        "a cookie set by the server shows up in the after-navigation diff",
        set(added) == {"fixture_gate", "fixture_session"},
        f"got {sorted(added)}",
    )
    check(
        "a Max-Age cookie is reported as not session-scoped",
        "fixture_gate" in added and added["fixture_gate"]["session_scoped"] is False,
        f"got {added.get('fixture_gate')}",
    )
    check(
        "a cookie without expiry is reported as session-scoped",
        "fixture_session" in added and added["fixture_session"]["session_scoped"] is True,
        f"got {added.get('fixture_session')}",
    )
    await check_cookies_are_visible_from_a_blank_tab(handle)


async def check_cookies_are_visible_from_a_blank_tab(handle) -> None:
    tab = await new_tab(handle)
    try:
        blank = await read_cookie_fingerprints(tab, "127.0.0.1")
    finally:
        await kill_tab(handle, tab)
    check(
        "cookies are read browser-wide, not scoped to whatever the tab currently shows",
        {c["name"] for c in blank} >= {"fixture_gate", "fixture_session"},
        f"a fresh about:blank tab reported {[c['name'] for c in blank]} - if this is empty the "
        "reader is scoped to the current page and every before-navigation snapshot is void",
    )


def check_report_builds_from_fixture_measurements(profile_dir: str) -> None:
    cold = Phase("A cold", "fixture phase", profile_dir, [
        _fixture_measurements["challenge"], _fixture_measurements["results"],
    ])
    warm = Phase("C warm after relaunch", "fixture phase", profile_dir, [
        _fixture_measurements["results"],
    ])
    fresh = Phase("D fresh control", "fixture phase", profile_dir, [
        _fixture_measurements["blocked"], _fixture_measurements["stuck"],
    ])
    phases = [cold, warm, fresh]
    persistence = build_persistence_record(
        cold, warm, snapshot_cookie_store(profile_dir), snapshot_cookie_store(profile_dir)
    )
    report = build_report_md(phases, persistence, count_live_requests(phases), 20.0, 60.0)
    Path("/tmp/mojeek_pydoll_probe_fixture_report.md").write_text(report)
    check("the report builder runs end to end on real measurement objects", len(report) > 2000)
    check(
        "the report carries the per-query table, all three question sections and the limits",
        all(marker in report for marker in (
            "## Per-query result", "## Q1", "## Q2", "## Q3",
            "## What this run does not measure", "## Methodology",
        )),
    )
    check(
        "the report never prints a raw cookie value",
        "persistent-value" not in report and "session-value" not in report,
    )
    check("live request count is the number of Mojeek navigations", count_live_requests(phases) == 5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(asyncio.run(test_workflow()))