# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path

from _brave_probe_core import (
    STATE_BUTTON_PENDING, STATE_BUTTON_VERIFYING, STATE_POW_LINK_BLOCK, STATE_RESULTS,
    classify_carry_over, count_over_budget, diff_cookie_fingerprints, pow_link_rate,
    summarize_durations,
)

ENGINE_WATCHDOG_BUDGET_MS = 6000.0
QUERY_BUDGET_NOTE = "30s"


# FUNCTIONS

def _fmt_ms(value) -> str:
    return "-" if value is None else f"{value:.0f}"


def _phase_query_rows(phase) -> list[str]:
    rows = []
    for m in phase.measurements:
        rows.append(
            f"| {phase.name} | {m.label} | {m.challenge_served} | {m.final_state} | {m.verdict} | "
            f"{m.result_link_count} | {m.trigger_mechanism or '-'} | {_fmt_ms(m.nav_ms)} | "
            f"{_fmt_ms(m.button_seen_ms)} | {_fmt_ms(m.trigger_fired_ms)} | {_fmt_ms(m.results_ms)} | "
            f"{_fmt_ms(m.total_ms)} |"
        )
    return rows


def _build_header(ts: str, live_requests: int, gap_s: float, budget_note: str) -> list[str]:
    return [
        "# Brave PoW challenge under the search lane's pydoll browser",
        "",
        f"Run: {ts}",
        "Browser: the SAME resolved Chromium bundle `src/search/browser.py` launches in "
        "production (`patchright.async_api`'s own `chromium.executable_path`, walked up to its "
        "enclosing `.app`), NOT the literal `Google Chrome` app — inlined into this probe's own "
        "launch wrapper rather than reused from `dev/_lib/browser_launch.py`, which still hardcodes "
        "the literal app and was deliberately left unfixed this milestone. Same profile-directory, "
        "backgrounding-flag and `browser_preferences` shape as `src/search/browser.py` otherwise.",
        f"Live requests against search.brave.com this run: {live_requests}. "
        f"Minimum gap between consecutive Brave navigations: {gap_s:.0f}s "
        "(production's limiter is 4 requests per minute). Control navigations go to a neutral "
        "URL, not to Brave, and are not counted here.",
        "",
        budget_note,
        "",
    ]


def _build_summary_table(phases: list) -> list[str]:
    lines = [
        "## Per-query result",
        "",
        "All times in milliseconds from navigation start.",
        "",
        "| Phase | Query | Challenge served | Final state | Verdict | Links | Trigger | nav | "
        "button | fired | results | total |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for phase in phases:
        lines += _phase_query_rows(phase)
    lines.append("")
    return lines


def _build_phase_descriptions(phases: list) -> list[str]:
    lines = ["## Phases", ""]
    for phase in phases:
        lines += [
            f"**{phase.name}** — {phase.description}",
            f"Profile: `{phase.profile_dir}`",
            f"Queries challenged: {sum(1 for m in phase.measurements if m.challenge_served)} "
            f"of {len(phase.measurements)}",
            "",
        ]
    return lines


def _build_q1_section(phases: list) -> list[str]:
    all_measurements = [m for p in phases for m in p.measurements]
    button_shape = [m for m in all_measurements if m.final_state in (STATE_BUTTON_PENDING, STATE_BUTTON_VERIFYING, STATE_RESULTS) and m.trigger_found_button]
    pow_link_shape = [m for m in all_measurements if m.final_state == STATE_POW_LINK_BLOCK]
    triggered = [m for m in button_shape if m.trigger_attempted]
    fired = [m for m in triggered if m.trigger_mechanism in ("js_click", "cdp_dispatch")]
    solved = [m for m in fired if m.final_state == STATE_RESULTS]
    return [
        "## Q1 — does the flow complete under the search lane's own pydoll browser, driven from code?",
        "",
        f"Queries that presented the button-challenge shape and offered a clickable candidate: "
        f"{len(button_shape)}. Trigger attempted on {len(triggered)}, actually fired "
        f"(`js_click` or `cdp_dispatch`) on {len(fired)}. Reached real result links: {len(solved)}.",
        f"Queries that landed on the 429/pow-link shape instead (no known clickable element, not "
        f"attempted): {len(pow_link_shape)}.",
        "",
        "Trigger mechanism used per query is in the summary table above (`js_click` = a deep-queried "
        "`.click()` call, matching a light-DOM or shadow-hosted button uniformly but producing an "
        "`isTrusted: false` event; `cdp_dispatch` = a real `Input.dispatchMouseEvent` at the same "
        "element's bounding-rect center, tried only when `js_click` produced no observable "
        "progress).",
        "",
    ]


def _build_q2_section(phases: list) -> list[str]:
    all_measurements = [m for p in phases for m in p.measurements]
    challenged = [m for m in all_measurements if m.challenge_served and m.total_ms is not None]
    unchallenged = [m for m in all_measurements if not m.challenge_served and m.total_ms is not None]
    challenged_totals = [m.total_ms for m in challenged]
    unchallenged_totals = [m.total_ms for m in unchallenged]
    lines = [
        "## Q2 — what does a challenged query cost, end to end, against the 6.0 second watchdog?",
        "",
        "Clock starts at the instruction before `tab.go_to(...)` and stops when the state machine "
        "reaches a terminal state (`RESULTS`, `POW_LINK_BLOCK` or `BLOCKED`) or the per-query "
        f"budget ({QUERY_BUDGET_NOTE}) runs out. Poll interval is 200ms.",
        "",
        "| Population | n | min | median | max | over 6.0s |",
        "|---|---|---|---|---|---|",
    ]
    for label, totals in (("challenged", challenged_totals), ("unchallenged", unchallenged_totals)):
        stats = summarize_durations(totals)
        over = count_over_budget(totals, ENGINE_WATCHDOG_BUDGET_MS)
        lines.append(
            f"| {label} | {stats['n']} | {_fmt_ms(stats['min_ms'])} | {_fmt_ms(stats['median_ms'])} | "
            f"{_fmt_ms(stats['max_ms'])} | {over} |"
        )
    lines += ["", "### Splits inside the challenged span", ""]
    for name, values in (
        ("navigation", [m.nav_ms for m in challenged]),
        ("button in DOM", [m.button_seen_ms for m in challenged]),
        ("trigger fired", [m.trigger_fired_ms for m in challenged]),
        ("results present", [m.results_ms for m in challenged]),
    ):
        stats = summarize_durations(values)
        lines.append(
            f"- {name}: n={stats['n']}, min={_fmt_ms(stats['min_ms'])}ms, "
            f"median={_fmt_ms(stats['median_ms'])}ms, max={_fmt_ms(stats['max_ms'])}ms"
        )
    tab_stats = summarize_durations([m.new_tab_ms for m in all_measurements])
    kill_stats = summarize_durations([m.kill_tab_ms for m in all_measurements])
    lines += [
        "",
        f"- `new_tab()` around the span: n={tab_stats['n']}, median={_fmt_ms(tab_stats['median_ms'])}ms, "
        f"max={_fmt_ms(tab_stats['max_ms'])}ms",
        f"- `kill_tab()` after the span: n={kill_stats['n']}, median={_fmt_ms(kill_stats['median_ms'])}ms, "
        f"max={_fmt_ms(kill_stats['max_ms'])}ms",
        "",
        f"`ENGINE_WATCHDOG_TIMEOUT` in `src/search/search_web.py` is 6.0s and this milestone does "
        "not change it. The 'over 6.0s' column counts individual queries, not an average.",
        "",
    ]
    return lines


def _build_q3_section(phases: list, cookie_notes: list[str]) -> list[str]:
    cold, warm, fresh = phases[0], phases[1], phases[-1]
    cold_served = [m.challenge_served for m in cold.measurements]
    warm_served = [m.challenge_served for m in warm.measurements]
    fresh_served = [m.challenge_served for m in fresh.measurements]
    verdict = classify_carry_over(cold_served, warm_served, fresh_served)
    lines = [
        "## Q3 — does a solved challenge carry over, within a run and across runs?",
        "",
        f"Machine-classified verdict: **{verdict}**",
        "",
        f"- Phase A (cold profile, one browser process): challenged per query {cold_served}",
        f"- Phase C (same profile directory, browser killed and relaunched in between): {warm_served}",
        f"- Phase D (fresh profile, run last on the same machine and network): {fresh_served}",
        "",
        "Phase D is the discriminator. Without it, a quiet Phase C is equally well explained by "
        "Brave having stopped challenging this address during the run. The verdict above only "
        "reports a carry-over when a fresh profile at the end of the run was challenged again.",
        "",
    ]
    lines += cookie_notes
    return lines


def _build_q4_section(phases: list) -> list[str]:
    all_measurements = [m for p in phases for m in p.measurements]
    states = [m.final_state for m in all_measurements]
    pre_cookie = []
    post_cookie = []
    saw_cookie = False
    for m in all_measurements:
        target = post_cookie if saw_cookie else pre_cookie
        target.append(m.final_state)
        if m.final_state == STATE_RESULTS and m.challenge_served:
            saw_cookie = True
    return [
        "## Q4 — does passing the button challenge have any effect on the 429/pow-link shape?",
        "",
        f"Observational only, n={len(all_measurements)} across the whole run. NOT provoked — "
        "deliberately triggering a 429 would require bursting past the 20s pacing this milestone's "
        "budget requires, so this section reports what was seen at ordinary pacing, not what a "
        "burst would show.",
        "",
        f"429/pow-link rate before any button-challenge in this run was solved: "
        f"{pow_link_rate(pre_cookie)}",
        f"429/pow-link rate after a button-challenge was solved: {pow_link_rate(post_cookie)}",
        f"All final states this run, in order: {states}",
        "",
        "A direction, not a cause, at this sample size. Do not read a single run's before/after "
        "split as proof either way.",
        "",
    ]


def _cookie_lines(phases: list) -> list[str]:
    lines = ["### Cookies Brave set, and what survived", ""]
    for phase in phases:
        for m in phase.measurements:
            nav_diff = diff_cookie_fingerprints(m.cookies_before, m.cookies_after_nav)
            settle_diff = diff_cookie_fingerprints(m.cookies_after_nav, m.cookies_after_settle)
            lines += [
                f"**{phase.name} / {m.label}**",
                "",
                f"- present before navigation: {[c['name'] for c in m.cookies_before]}",
                f"- added by the navigation: {[c['name'] for c in nav_diff['added']]}",
                f"- added or changed during verification: "
                f"{[c['name'] for c in settle_diff['added']] + [c['name'] for c in settle_diff['changed']]}",
                f"- present at the end: {[c['name'] for c in m.cookies_after_settle]}",
                "",
                "```json",
                json.dumps(m.cookies_after_settle, indent=2),
                "```",
                "",
            ]
    return lines


def _build_profile_persistence_section(persistence: dict) -> list[str]:
    return [
        "### What survived the browser process being killed",
        "",
        "```json",
        json.dumps(persistence, indent=2),
        "```",
        "",
    ]


def _build_limits_section(extension_used: bool) -> list[str]:
    lines = [
        "## What this run does not measure",
        "",
        "- **The concurrent case.** Production fans out eight engines at once inside one browser. "
        "Every query here is sequential with a gap. Nothing in this report extends to a Brave "
        "query sharing a browser with seven concurrent engine tabs.",
        "- **Production's own profile.** This probe uses dedicated temporary profile directories, "
        "never `~/.websearch/browser-session`, so it cannot contaminate production state or be "
        "contaminated by it.",
        "- **Whether the trigger mechanisms used here generalize.** Both `js_click` and "
        "`cdp_dispatch` were tried against whatever this run's own live pages actually presented; "
        "this report does not claim either mechanism is reliable beyond what it observed.",
        f"- **Q4 is a single run's observation, n small by construction, not a controlled "
        "experiment.**",
    ]
    if extension_used:
        lines.append(
            "- **The bounded extension was used** (phases A and C together produced zero button "
            "challenges, so a third fresh profile ran before phase D). See the phase list above "
            "for what it added."
        )
    lines.append("")
    return lines


def _build_methodology_section(queries_per_phase: dict, gap_s: float, budget_s: float) -> list[str]:
    return [
        "## Methodology",
        "",
        "Every phase launches Chrome through an inline copy of `src/search/browser.py`'s launch "
        "shape (no `from src.` import, which this repo's tooling blocks for new dev files), "
        "resolving the SAME dedicated Chromium bundle production launches via "
        "`patchright.async_api`'s `chromium.executable_path`, and, before the first Brave "
        "navigation of that phase, navigates a neutral control URL. If that control navigation "
        "fails the whole probe aborts with the raw error.",
        "",
        "Per query the page is polled every 200ms and classified into one of six states: RESULTS "
        "(`div[data-type=\"web\"]` present), BUTTON_VERIFYING (an in-flight marker such as "
        "'Letting you in...' is present), BUTTON_PENDING (a deep-queried button/role=button "
        "element whose text matches a trigger-word list is present, searched through shadow roots "
        "too), POW_LINK_BLOCK (a `pow-captcha` link is present with no clickable candidate found), "
        "BLOCKED (a block marker with neither a button nor a pow-link), UNKNOWN. Only RESULTS, "
        "POW_LINK_BLOCK and BLOCKED are terminal. There is deliberately no branch that treats a "
        "marker or pow-link's mere presence as terminal on the first poll - that is brave.py's own "
        "current defect, and repeating it in this probe's polling would make Q1 unanswerable by "
        "construction.",
        "",
        "The trigger, once a BUTTON_PENDING state is seen, is a deep-queried `.click()` call "
        "(searches through shadow roots for a `button`/`[role=button]` element whose text matches "
        "a trigger-word list, then clicks it directly - this finds the element correctly regardless "
        "of shadow DOM, but produces an `isTrusted: false` event). If that produces no observable "
        "state change, `Input.dispatchMouseEvent` is tried at the same element's bounding-rect "
        "center on the next poll - a real, trusted input event, though the same limitation the "
        "`engine_reduction` area recorded against shadow-DOM-scoped elements may apply.",
        "",
        f"Cookies are read via CDP `Storage.getCookies` (browser-wide, not `Tab.get_cookies()`, "
        "which the `mojeek_return` area's own investigation found is scoped to whatever page the "
        "tab currently shows and reads empty on a blank tab by construction) at three points per "
        "query - before the navigation, right after it, and after the page settles.",
        "",
        f"Queries per phase: {json.dumps(queries_per_phase)}. Per-query budget {budget_s:.0f}s, "
        f"gap between consecutive Brave navigations {gap_s:.0f}s.",
        "",
    ]


def build_report_md(
    phases: list, persistence: dict, live_requests: int, gap_s: float, budget_s: float,
    budget_note: str, extension_used: bool,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queries_per_phase = {p.name: [m.label for m in p.measurements] for p in phases}
    lines = _build_header(ts, live_requests, gap_s, budget_note)
    lines += _build_phase_descriptions(phases)
    lines += _build_summary_table(phases)
    lines += _build_q1_section(phases)
    lines += _build_q2_section(phases)
    lines += _build_q3_section(phases, _build_profile_persistence_section(persistence) + _cookie_lines(phases))
    lines += _build_q4_section(phases)
    lines += _build_limits_section(extension_used)
    lines += _build_methodology_section(queries_per_phase, gap_s, budget_s)
    return "\n".join(lines)


def write_report(report: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"brave_pydoll_probe_{ts}.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")
    return report_path
