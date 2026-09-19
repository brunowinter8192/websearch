# INFRASTRUCTURE
from _brave_probe_check_result import check
from _brave_probe_core import (
    CARRY_OVER_CONFOUNDED, CARRY_OVER_INCONCLUSIVE, CARRY_OVER_NO_COLD_CHALLENGE, CARRY_OVER_NONE,
    CARRY_OVER_WITHIN_AND_ACROSS, CARRY_OVER_WITHIN_ONLY,
    STATE_BLOCKED, STATE_BUTTON_PENDING, STATE_BUTTON_VERIFYING, STATE_POW_LINK_BLOCK, STATE_RESULTS,
    STATE_UNKNOWN, VERDICT_BLOCKED, VERDICT_BUTTON_UNRESOLVED, VERDICT_POW_LINK_BLOCKED,
    VERDICT_STILL_VERIFYING, VERDICT_SUCCESS_CHALLENGED, VERDICT_SUCCESS_UNCHALLENGED,
    classify_carry_over, classify_page_state, classify_query_verdict, cookie_is_session_scoped,
    count_over_budget, diff_cookie_fingerprints, fingerprint_cookies, pow_link_rate,
    summarize_durations,
)


# FUNCTIONS

def run_pure_function_checks() -> None:
    check(
        "a button candidate keeps the state at BUTTON_PENDING, not BLOCKED",
        classify_page_state({
            "result_link_count": 0, "marker_present": True, "pow_link_present": False,
            "verifying_marker_present": False, "button_candidates": [{"tag": "button"}],
        }) == STATE_BUTTON_PENDING,
    )
    check(
        "an in-flight marker outranks a button candidate that is still in the DOM",
        classify_page_state({
            "result_link_count": 0, "marker_present": True, "pow_link_present": False,
            "verifying_marker_present": True, "button_candidates": [{"tag": "button"}],
        }) == STATE_BUTTON_VERIFYING,
    )
    check(
        "result links win over every marker, even with block text still in the body",
        classify_page_state({
            "result_link_count": 3, "marker_present": True, "pow_link_present": True,
            "verifying_marker_present": False, "button_candidates": [],
        }) == STATE_RESULTS,
    )
    check(
        "a pow-link with no clickable candidate is POW_LINK_BLOCK, not BLOCKED",
        classify_page_state({
            "result_link_count": 0, "marker_present": True, "pow_link_present": True,
            "verifying_marker_present": False, "button_candidates": [],
        }) == STATE_POW_LINK_BLOCK,
    )
    check(
        "a marker with no button and no pow-link is BLOCKED",
        classify_page_state({
            "result_link_count": 0, "marker_present": True, "pow_link_present": False,
            "verifying_marker_present": False, "button_candidates": [],
        }) == STATE_BLOCKED,
    )
    check(
        "nothing present at all is UNKNOWN",
        classify_page_state({
            "result_link_count": 0, "marker_present": False, "pow_link_present": False,
            "verifying_marker_present": False, "button_candidates": [],
        }) == STATE_UNKNOWN,
    )
    check(
        "BUTTON_PENDING and BUTTON_VERIFYING are not terminal, RESULTS/POW_LINK_BLOCK/BLOCKED are",
        classify_page_state({"result_link_count": 0, "button_candidates": [{"tag": "button"}]}) == STATE_BUTTON_PENDING,
    )
    run_verdict_checks()
    run_cookie_diff_checks()
    run_stats_checks()
    run_carry_over_checks()
    run_pow_link_rate_checks()


def run_verdict_checks() -> None:
    check(
        "verdict separates challenged from unchallenged success",
        classify_query_verdict(True, STATE_RESULTS) == VERDICT_SUCCESS_CHALLENGED
        and classify_query_verdict(False, STATE_RESULTS) == VERDICT_SUCCESS_UNCHALLENGED,
    )
    check(
        "a pow-link block, a still-verifying spinner and an unresolved button are three verdicts",
        classify_query_verdict(True, STATE_POW_LINK_BLOCK) == VERDICT_POW_LINK_BLOCKED
        and classify_query_verdict(True, STATE_BUTTON_VERIFYING) == VERDICT_STILL_VERIFYING
        and classify_query_verdict(True, STATE_BUTTON_PENDING) == VERDICT_BUTTON_UNRESOLVED,
    )
    check(
        "a genuine block after verifying is its own verdict",
        classify_query_verdict(True, STATE_BLOCKED) == VERDICT_BLOCKED,
    )
    check(
        "session-scoped cookie detection keys on expires",
        cookie_is_session_scoped({"expires": -1})
        and cookie_is_session_scoped({})
        and not cookie_is_session_scoped({"expires": 1789669939.0}),
    )


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
        [{"name": "a", "domain": ".brave.com", "path": "/", "value": "one", "expires": -1},
         {"name": "b", "domain": ".other.com", "path": "/", "value": "two", "expires": 100.0}],
        "brave",
    )
    after = fingerprint_cookies(
        [{"name": "a", "domain": ".brave.com", "path": "/", "value": "changed", "expires": -1},
         {"name": "c", "domain": ".brave.com", "path": "/", "value": "three", "expires": 100.0}],
        "brave",
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


def run_stats_checks() -> None:
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


def run_pow_link_rate_checks() -> None:
    check("pow-link rate on an empty population is None, not zero", pow_link_rate([]) is None)
    check(
        "pow-link rate counts POW_LINK_BLOCK states against the total",
        pow_link_rate([STATE_POW_LINK_BLOCK, STATE_RESULTS, STATE_POW_LINK_BLOCK, STATE_RESULTS]) == 0.5,
    )
