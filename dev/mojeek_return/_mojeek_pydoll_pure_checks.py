# INFRASTRUCTURE
from _mojeek_pydoll_check_result import check
from _mojeek_pydoll_probe_core import (
    CARRY_OVER_CONFOUNDED, CARRY_OVER_INCONCLUSIVE, CARRY_OVER_NO_COLD_CHALLENGE, CARRY_OVER_NONE,
    CARRY_OVER_WITHIN_AND_ACROSS, CARRY_OVER_WITHIN_ONLY,
    STATE_BLOCKED, STATE_CHALLENGE_PENDING, STATE_IN_FLIGHT, STATE_RESULTS, STATE_UNKNOWN,
    VERDICT_BLOCKED, VERDICT_CHALLENGE_UNRESOLVED, VERDICT_STILL_PENDING,
    VERDICT_SUCCESS_CHALLENGED, VERDICT_SUCCESS_UNCHALLENGED,
    classify_carry_over, classify_page_state, classify_query_verdict, cookie_is_session_scoped,
    count_over_budget, diff_cookie_fingerprints, extract_pow_time_ms, fingerprint_cookies,
    is_terminal_state, summarize_durations,
)


# FUNCTIONS

def run_pure_function_checks() -> None:
    boilerplate_at_start = {
        "result_link_count": 0, "block_marker_present": True,
        "in_flight_marker_present": False, "widget_present": True,
    }
    check(
        "classifier does not call BLOCKED while the widget is on screen",
        classify_page_state(boilerplate_at_start) == STATE_CHALLENGE_PENDING,
        f"got {classify_page_state(boilerplate_at_start)}",
    )
    check(
        "classifier does not call BLOCKED while the server round trip is open",
        classify_page_state({
            "result_link_count": 0, "block_marker_present": True,
            "in_flight_marker_present": True, "widget_present": False,
        }) == STATE_IN_FLIGHT,
    )
    check(
        "classifier calls RESULTS on result links even with boilerplate still in the body",
        classify_page_state({
            "result_link_count": 10, "block_marker_present": True,
            "in_flight_marker_present": False, "widget_present": False,
        }) == STATE_RESULTS,
    )
    check(
        "classifier calls BLOCKED only once widget and in-flight marker are both gone",
        classify_page_state({
            "result_link_count": 0, "block_marker_present": True,
            "in_flight_marker_present": False, "widget_present": False,
        }) == STATE_BLOCKED,
    )
    check(
        "CHALLENGE_PENDING and IN_FLIGHT are not terminal, RESULTS and BLOCKED are",
        not is_terminal_state(STATE_CHALLENGE_PENDING)
        and not is_terminal_state(STATE_IN_FLIGHT)
        and not is_terminal_state(STATE_UNKNOWN)
        and is_terminal_state(STATE_RESULTS)
        and is_terminal_state(STATE_BLOCKED),
    )
    check(
        "verdict separates challenged from unchallenged success",
        classify_query_verdict(True, STATE_RESULTS) == VERDICT_SUCCESS_CHALLENGED
        and classify_query_verdict(False, STATE_RESULTS) == VERDICT_SUCCESS_UNCHALLENGED,
    )
    check(
        "verdict keeps a stalled round trip distinct from a refusal",
        classify_query_verdict(True, STATE_IN_FLIGHT) == VERDICT_STILL_PENDING
        and classify_query_verdict(True, STATE_BLOCKED) == VERDICT_BLOCKED
        and classify_query_verdict(True, STATE_CHALLENGE_PENDING) == VERDICT_CHALLENGE_UNRESOLVED,
    )
    check(
        "session-scoped cookie detection keys on expires",
        cookie_is_session_scoped({"expires": -1})
        and cookie_is_session_scoped({})
        and not cookie_is_session_scoped({"expires": 1789669939.0}),
    )
    run_cookie_diff_checks()
    run_payload_and_stats_checks()
    run_carry_over_checks()


def run_carry_over_checks() -> None:
    check(
        "challenge on the cold query only, gone warm and gone after relaunch, fresh challenged again",
        classify_carry_over([True, False, False, False], [False, False], [True]) == CARRY_OVER_WITHIN_AND_ACROSS,
    )
    check(
        "gone warm within the run but back after the process kill is within-run only",
        classify_carry_over([True, False, False, False], [True, False], [True]) == CARRY_OVER_WITHIN_ONLY,
    )
    check(
        "challenged on every query is no carry-over",
        classify_carry_over([True, True, True], [True, True], [True]) == CARRY_OVER_NONE,
    )
    check(
        "an unchallenged fresh profile makes any quiet warm phase confounded, not a carry-over",
        classify_carry_over([True, False, False], [False, False], [False]) == CARRY_OVER_CONFOUNDED,
    )
    check(
        "a cold profile that was never challenged makes carry-over unmeasurable",
        classify_carry_over([False, False, False], [False], [False]) == CARRY_OVER_NO_COLD_CHALLENGE,
    )
    check(
        "too few queries is inconclusive rather than a verdict",
        classify_carry_over([True], [], []) == CARRY_OVER_INCONCLUSIVE,
    )


def run_cookie_diff_checks() -> None:
    before = fingerprint_cookies(
        [{"name": "a", "domain": ".mojeek.com", "path": "/", "value": "one", "expires": -1},
         {"name": "b", "domain": ".other.com", "path": "/", "value": "two", "expires": 100.0}],
        "mojeek",
    )
    after = fingerprint_cookies(
        [{"name": "a", "domain": ".mojeek.com", "path": "/", "value": "changed", "expires": -1},
         {"name": "c", "domain": ".mojeek.com", "path": "/", "value": "three", "expires": 100.0}],
        "mojeek",
    )
    check("cookie fingerprint filters by domain", len(before) == 1 and before[0]["name"] == "a")
    check("cookie fingerprint hides the raw value", "value" not in before[0] and before[0]["value_length"] == 3)
    diff = diff_cookie_fingerprints(before, after)
    check(
        "cookie diff reports added, removed and changed separately",
        [c["name"] for c in diff["added"]] == ["c"]
        and diff["removed"] == []
        and [c["name"] for c in diff["changed"]] == ["a"],
        f"got {diff}",
    )
    same = diff_cookie_fingerprints(before, before)
    check(
        "an unchanged cookie is reported as carried over, not as added",
        [c["name"] for c in same["unchanged"]] == ["a"] and same["added"] == [] and same["changed"] == [],
    )


def run_payload_and_stats_checks() -> None:
    payload = "eyJzb2x1dGlvbiI6IHsiY291bnRlciI6IDIyMywgInRpbWUiOiAxMjguMX19"
    events = [{"event": "verified", "t_ms": 1, "detail": '{"payload": "' + payload + '"}'}]
    check("PoW time is read out of the ALTCHA payload", extract_pow_time_ms(events) == 128.1)
    check("missing payload yields no PoW time rather than a crash", extract_pow_time_ms([]) is None)
    stats = summarize_durations([1000.0, 3000.0, 2000.0, None])
    check(
        "duration summary reports n, min, median and max",
        stats == {"n": 3, "min_ms": 1000, "median_ms": 2000, "max_ms": 3000},
        f"got {stats}",
    )
    check(
        "over-budget counting is per query, not an average",
        count_over_budget([5000.0, 6001.0, 12000.0, None], 6000.0) == 2,
    )
