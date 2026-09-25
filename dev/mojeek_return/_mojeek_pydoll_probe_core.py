# INFRASTRUCTURE
import base64
import hashlib
import json
import statistics

RESULT_LINK_SELECTOR = "ul.results-standard > li > a.ob"
BLOCK_MARKER_TEXT = "Verification required"
IN_FLIGHT_MARKER_TEXT = "Checking verification with server..."

STATE_RESULTS = "RESULTS"
STATE_IN_FLIGHT = "IN_FLIGHT"
STATE_CHALLENGE_PENDING = "CHALLENGE_PENDING"
STATE_BLOCKED = "BLOCKED"
STATE_UNKNOWN = "UNKNOWN"

TERMINAL_STATES = (STATE_RESULTS, STATE_BLOCKED)

VERDICT_SUCCESS_CHALLENGED = "SUCCESS_CHALLENGED"
VERDICT_SUCCESS_UNCHALLENGED = "SUCCESS_UNCHALLENGED"
VERDICT_BLOCKED = "BLOCKED"
VERDICT_STILL_PENDING = "INCONCLUSIVE_STILL_PENDING"
VERDICT_CHALLENGE_UNRESOLVED = "INCONCLUSIVE_CHALLENGE_UNRESOLVED"
VERDICT_UNKNOWN = "INCONCLUSIVE_UNKNOWN"

SESSION_EXPIRY_SENTINEL = -1

CARRY_OVER_INCONCLUSIVE = "INCONCLUSIVE_NOT_ENOUGH_QUERIES"
CARRY_OVER_NO_COLD_CHALLENGE = "UNMEASURABLE_COLD_PROFILE_WAS_NOT_CHALLENGED"
CARRY_OVER_CONFOUNDED = "CONFOUNDED_FRESH_PROFILE_ALSO_UNCHALLENGED"
CARRY_OVER_WITHIN_AND_ACROSS = "CARRIES_OVER_WITHIN_RUN_AND_ACROSS_RUNS"
CARRY_OVER_WITHIN_ONLY = "CARRIES_OVER_WITHIN_RUN_ONLY"
CARRY_OVER_NONE = "NO_CARRY_OVER"
CARRY_OVER_INCONSISTENT = "INCONSISTENT_WARM_WITHIN_RUN_CHALLENGED_BUT_ACROSS_RUNS_NOT"


# FUNCTIONS

def classify_page_state(facts: dict) -> str:
    if facts.get("result_link_count", 0) > 0:
        return STATE_RESULTS
    if facts.get("in_flight_marker_present"):
        return STATE_IN_FLIGHT
    if facts.get("widget_present"):
        return STATE_CHALLENGE_PENDING
    if facts.get("block_marker_present"):
        return STATE_BLOCKED
    return STATE_UNKNOWN


def is_terminal_state(state: str) -> bool:
    return state in TERMINAL_STATES


def classify_query_verdict(challenge_served: bool, final_state: str) -> str:
    if final_state == STATE_RESULTS:
        return VERDICT_SUCCESS_CHALLENGED if challenge_served else VERDICT_SUCCESS_UNCHALLENGED
    if final_state == STATE_BLOCKED:
        return VERDICT_BLOCKED
    if final_state == STATE_IN_FLIGHT:
        return VERDICT_STILL_PENDING
    if final_state == STATE_CHALLENGE_PENDING:
        return VERDICT_CHALLENGE_UNRESOLVED
    return VERDICT_UNKNOWN


def classify_carry_over(
    phase_cold_served: list[bool], phase_warm_served: list[bool], phase_fresh_served: list[bool]
) -> str:
    if len(phase_cold_served) < 2 or not phase_warm_served or not phase_fresh_served:
        return CARRY_OVER_INCONCLUSIVE
    if not phase_cold_served[0]:
        return CARRY_OVER_NO_COLD_CHALLENGE
    warm_within_run = not any(phase_cold_served[1:])
    warm_across_runs = not any(phase_warm_served)
    fresh_challenged = any(phase_fresh_served)
    if (warm_within_run or warm_across_runs) and not fresh_challenged:
        return CARRY_OVER_CONFOUNDED
    if warm_within_run and warm_across_runs:
        return CARRY_OVER_WITHIN_AND_ACROSS
    if warm_within_run:
        return CARRY_OVER_WITHIN_ONLY
    if warm_across_runs:
        return CARRY_OVER_INCONSISTENT
    return CARRY_OVER_NONE


def fingerprint_cookies(cookies: list[dict], domain_filter: str | None = None) -> list[dict]:
    selected = []
    for cookie in cookies:
        domain = cookie.get("domain") or ""
        if domain_filter and domain_filter not in domain:
            continue
        selected.append(fingerprint_cookie(cookie))
    return sorted(selected, key=lambda c: (c["name"] or "", c["domain"] or ""))


def diff_cookie_fingerprints(before: list[dict], after: list[dict]) -> dict:
    before_map = {_cookie_key(c): c for c in before}
    after_map = {_cookie_key(c): c for c in after}
    added = [after_map[k] for k in after_map if k not in before_map]
    removed = [before_map[k] for k in before_map if k not in after_map]
    changed = [
        {"name": k[0], "domain": k[1], "path": k[2],
         "before_value_sha256_12": before_map[k]["value_sha256_12"],
         "after_value_sha256_12": after_map[k]["value_sha256_12"]}
        for k in after_map
        if k in before_map and before_map[k]["value_sha256_12"] != after_map[k]["value_sha256_12"]
    ]
    unchanged = [
        after_map[k] for k in after_map
        if k in before_map and before_map[k]["value_sha256_12"] == after_map[k]["value_sha256_12"]
    ]
    return {
        "added": sorted(added, key=lambda c: c["name"] or ""),
        "removed": sorted(removed, key=lambda c: c["name"] or ""),
        "changed": sorted(changed, key=lambda c: c["name"] or ""),
        "unchanged": sorted(unchanged, key=lambda c: c["name"] or ""),
    }


def extract_pow_time_ms(events: list[dict]) -> float | None:
    for record in events:
        if record.get("event") != "verified":
            continue
        detail = record.get("detail")
        if not detail:
            continue
        payload = json.loads(detail).get("payload")
        if not isinstance(payload, str):
            continue
        decoded = _decode_altcha_payload(payload)
        if decoded and isinstance(decoded.get("solution"), dict):
            return decoded["solution"].get("time")
    return None


def extract_widget_states(events: list[dict]) -> list[str]:
    states = []
    for record in events:
        if record.get("event") != "statechange":
            continue
        detail = record.get("detail")
        if not detail:
            continue
        state = json.loads(detail).get("state")
        if state:
            states.append(state)
    return states


def summarize_durations(values: list[float]) -> dict:
    present = [v for v in values if v is not None]
    if not present:
        return {"n": 0, "min_ms": None, "median_ms": None, "max_ms": None}
    return {
        "n": len(present),
        "min_ms": round(min(present)),
        "median_ms": round(statistics.median(present)),
        "max_ms": round(max(present)),
    }


def count_over_budget(values: list[float], budget_ms: float) -> int:
    return sum(1 for v in values if v is not None and v > budget_ms)


def fingerprint_cookie(cookie: dict) -> dict:
    value = cookie.get("value") or ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return {
        "name": cookie.get("name"),
        "domain": cookie.get("domain"),
        "path": cookie.get("path"),
        "expires": cookie.get("expires"),
        "session_scoped": cookie_is_session_scoped(cookie),
        "http_only": cookie.get("httpOnly"),
        "secure": cookie.get("secure"),
        "same_site": cookie.get("sameSite"),
        "value_length": len(value),
        "value_sha256_12": digest,
    }


def _cookie_key(fingerprint: dict) -> tuple:
    return (fingerprint["name"], fingerprint["domain"], fingerprint["path"])


def _decode_altcha_payload(payload: str) -> dict | None:
    padded = payload + "=" * (-len(payload) % 4)
    try:
        raw = base64.b64decode(padded)
        return json.loads(raw)
    except Exception:
        return None


def cookie_is_session_scoped(cookie: dict) -> bool:
    expires = cookie.get("expires")
    if expires is None:
        return True
    return expires <= SESSION_EXPIRY_SENTINEL
