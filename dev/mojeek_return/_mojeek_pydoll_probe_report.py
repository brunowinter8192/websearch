# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path

from _mojeek_pydoll_probe_core import (
    classify_carry_over, count_over_budget, diff_cookie_fingerprints, summarize_durations,
)

ENGINE_WATCHDOG_BUDGET_MS = 6000.0


# FUNCTIONS

def _fmt_ms(value) -> str:
    return "-" if value is None else f"{value:.0f}"


def _phase_query_rows(phase) -> list[str]:
    rows = []
    for m in phase.measurements:
        rows.append(
            f"| {phase.name} | {m.label} | {m.challenge_served} | {m.verdict} | "
            f"{m.result_link_count} | {_fmt_ms(m.nav_ms)} | {_fmt_ms(m.widget_seen_ms)} | "
            f"{_fmt_ms(m.verify_fired_ms)} | {_fmt_ms(m.verified_ms)} | {_fmt_ms(m.results_ms)} | "
            f"{_fmt_ms(m.total_ms)} | {_fmt_ms(m.pow_time_ms)} |"
        )
    return rows


def _build_header(ts: str, live_requests: int, gap_s: float, prior_spend_note: str) -> list[str]:
    return [
        "# Mojeek ALTCHA under the search lane's pydoll browser",
        "",
        f"Run: {ts}",
        "Browser: the same build, flags and launch shape `src/search/browser.py` produces "
        "(pydoll `Chrome` + `BrowserProcessManager(process_creator=...)` re-launching the user's "
        "real Google Chrome via `open -g -n -a`, `--user-data-dir` profile, "
        "`--disable-blink-features=AutomationControlled`, backgrounding flags, same "
        "`browser_preferences`), inlined rather than imported.",
        f"Live requests against mojeek.com this run: {live_requests}. "
        f"Minimum gap between consecutive Mojeek navigations: {gap_s:.0f}s "
        "(production's limiter is 4 requests per minute). Control navigations go to a neutral "
        "URL, not to Mojeek, and are not counted here.",
        "",
        prior_spend_note,
        "",
    ]


def _build_summary_table(phases: list) -> list[str]:
    lines = [
        "## Per-query result",
        "",
        "All times in milliseconds from navigation start. `pow_ms` is ALTCHA's own self-reported "
        "client-side proof-of-work time out of the solution payload, not a probe measurement.",
        "",
        "| Phase | Query | Challenge served | Verdict | Links | nav | widget | verify() | verified | results | total | pow_ms |",
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
    challenged = [m for m in all_measurements if m.challenge_served]
    solved = [m for m in challenged if m.final_state == "RESULTS"]
    fired = [m for m in challenged if m.verify_fired]
    return [
        "## Q1 — does the ALTCHA flow complete under this project's pydoll build?",
        "",
        f"Challenged queries: {len(challenged)}. `verify()` dispatched successfully on "
        f"{len(fired)} of them. Reached real result links: {len(solved)}.",
        "",
        "The trigger is a single main-world `el.verify()` call through pydoll's "
        "`Tab.execute_script`, which is `Runtime.evaluate` with no isolated world. The "
        "patchright-specific failure mode recorded in the `engine_reduction` area (page-defined "
        "custom element methods being invisible in an isolated context) does not exist on this "
        "path; it was verified against a local fixture widget before any live request.",
        "",
    ]


def _build_q2_section(phases: list) -> list[str]:
    all_measurements = [m for p in phases for m in p.measurements]
    challenged = [m for m in all_measurements if m.challenge_served and m.total_ms is not None]
    unchallenged = [m for m in all_measurements if not m.challenge_served and m.total_ms is not None]
    challenged_totals = [m.total_ms for m in challenged]
    unchallenged_totals = [m.total_ms for m in unchallenged]
    lines = _q2_intro_lines()
    lines += _q2_population_rows(challenged_totals, unchallenged_totals)
    lines += _q2_split_lines(challenged)
    lines += _q2_tab_lines(all_measurements)
    return lines


def _q2_intro_lines() -> list[str]:
    return [
        "## Q2 — what does a challenged query cost in wall-clock time?",
        "",
        "Clock starts at the instruction before `tab.go_to(...)` and stops at the first poll at "
        "which the production selector `ul.results-standard > li > a.ob` matches. Poll interval "
        "is 200ms, which is this measurement's granularity. `new_tab()` and `kill_tab()` are "
        "measured separately below because production's per-engine watchdog covers them too.",
        "",
        "| Population | n | min | median | max | over 6.0s |",
        "|---|---|---|---|---|---|",
    ]


def _q2_population_rows(challenged_totals: list, unchallenged_totals: list) -> list[str]:
    lines = []
    for label, totals in (("challenged", challenged_totals), ("unchallenged", unchallenged_totals)):
        stats = summarize_durations(totals)
        over = count_over_budget(totals, ENGINE_WATCHDOG_BUDGET_MS)
        lines.append(
            f"| {label} | {stats['n']} | {_fmt_ms(stats['min_ms'])} | {_fmt_ms(stats['median_ms'])} | "
            f"{_fmt_ms(stats['max_ms'])} | {over} |"
        )
    return lines


def _q2_split_lines(challenged: list) -> list[str]:
    lines = ["", "### Splits inside the challenged span", ""]
    for name, values in (
        ("navigation", [m.nav_ms for m in challenged]),
        ("widget in DOM", [m.widget_seen_ms for m in challenged]),
        ("verify() dispatched", [m.verify_fired_ms for m in challenged]),
        ("client-side verified", [m.verified_ms for m in challenged]),
        ("results present", [m.results_ms for m in challenged]),
        ("ALTCHA self-reported PoW", [m.pow_time_ms for m in challenged]),
    ):
        stats = summarize_durations(values)
        lines.append(
            f"- {name}: n={stats['n']}, min={_fmt_ms(stats['min_ms'])}ms, "
            f"median={_fmt_ms(stats['median_ms'])}ms, max={_fmt_ms(stats['max_ms'])}ms"
        )
    return lines


def _q2_tab_lines(all_measurements: list) -> list[str]:
    tab_stats = summarize_durations([m.new_tab_ms for m in all_measurements])
    kill_stats = summarize_durations([m.kill_tab_ms for m in all_measurements])
    return [
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


def _build_q3_section(phases: list, cookie_notes: list[str]) -> list[str]:
    cold, warm, fresh = phases[0], phases[1], phases[2]
    cold_served = [m.challenge_served for m in cold.measurements]
    warm_served = [m.challenge_served for m in warm.measurements]
    fresh_served = [m.challenge_served for m in fresh.measurements]
    verdict = classify_carry_over(cold_served, warm_served, fresh_served)
    lines = [
        "## Q3 — does a solved challenge carry over to later queries?",
        "",
        f"Machine-classified verdict: **{verdict}**",
        "",
        f"- Phase A (cold profile, one browser process): challenged per query {cold_served}",
        f"- Phase C (same profile directory, browser killed and relaunched in between): {warm_served}",
        f"- Phase D (second, fresh profile, run last on the same machine and network): {fresh_served}",
        "",
        "Phase D is the discriminator. Without it, a quiet Phase C is equally well explained by "
        "Mojeek having stopped challenging this address during the run. The verdict above only "
        "reports a carry-over when a fresh profile at the end of the run was challenged again.",
        "",
        "Within-run and across-run carry-over are reported separately on purpose. They are two "
        "different production verdicts: `search_web_workflow` calls `kill_own_chrome()` in a "
        "`finally` on every run, so production never keeps a browser process between runs, only "
        "the profile directory on disk.",
        "",
    ]
    lines += cookie_notes
    return lines


def _cookie_lines(phases: list) -> list[str]:
    lines = ["### Cookies Mojeek set, and what survived", ""]
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
        "`session_scoped` is read straight off the CDP cookie record: an `expires` of -1 (or "
        "absent) is a session cookie, which Chrome does not normally persist across a restart. "
        "This single attribute is what a successor needs in order to reason about production "
        "without re-running this probe.",
        "",
    ]


def _build_widget_section(phases: list) -> list[str]:
    for phase in phases:
        for m in phase.measurements:
            if m.widget_detail:
                return [
                    "## Widget as served this run",
                    "",
                    f"First captured on {phase.name} / {m.label}.",
                    "",
                    "```json",
                    json.dumps(m.widget_detail, indent=2),
                    "```",
                    "",
                ]
    return ["## Widget as served this run", "", "No widget was captured on any query this run.", ""]


def _build_limits_section() -> list[str]:
    return [
        "## What this run does not measure",
        "",
        "- **The concurrent case.** Production fans out seven engines at once inside one browser. "
        "Every query here is sequential with a gap. Nothing in this report extends to a Mojeek "
        "query sharing a browser with six concurrent engine tabs.",
        "- **Production's own profile.** This probe uses dedicated temporary profile directories "
        "with identical flags, never `~/.websearch/browser-session`, so it cannot contaminate "
        "production state or be contaminated by it.",
        "- **Anything beyond this machine and network.** The 2026-09-05 removal recorded the "
        "block as tied to this project's network. A single run cannot separate a Mojeek policy "
        "from a local reputation effect beyond what Phase D tests.",
        "",
    ]


def _build_methodology_section(queries_per_phase: dict, gap_s: float, budget_s: float) -> list[str]:
    return [
        "## Methodology",
        "",
        "Every phase launches Chrome through an inline copy of `src/search/browser.py`'s launch "
        "shape (no `from src.` import, which this repo's tooling blocks for new dev files) and, "
        "before the first Mojeek navigation of that phase, navigates a neutral control URL. If "
        "that control navigation fails the whole probe aborts with the raw error. One tripwire, "
        "no branch per failure mode: a session that cannot reach the open internet cannot tell "
        "'Mojeek refused' from 'this machine is blind right now'. A local network outage hit this "
        "probe's predecessor mid-run on 2026-09-17, which is why the tripwire exists.",
        "",
        "Per query the page is polled every 200ms and classified into one of five states: RESULTS "
        "(production result links present), IN_FLIGHT (the literal string 'Checking verification "
        "with server...'), CHALLENGE_PENDING (an `altcha-widget` is in the DOM), BLOCKED (the "
        "string 'Verification required' with no widget and no in-flight marker), UNKNOWN. Only "
        "RESULTS and BLOCKED are terminal. Mojeek's block-page boilerplate is present from the "
        "first poll and stays on screen through the whole verification sequence, so a verdict "
        "keyed on it would fire on iteration zero every time - the defect that produced two wrong "
        "live runs on 2026-09-17. A fixture that keeps that boilerplate visible along the entire "
        "success path is part of the offline test module and asserts that the first poll is never "
        "terminal.",
        "",
        "The trigger is `document.querySelector('altcha-widget').verify()`, dispatched once, as "
        "soon as the widget is in the DOM and reports `typeof verify === 'function'`. Widget "
        "events are buffered in the page (`window.__mojeekEvents`) and drained on each poll; "
        "event timestamps are mapped onto the probe's own clock through an offset captured at "
        "attach time.",
        "",
        f"Cookies are read via CDP at three points per query - before the navigation, right after "
        "it, and after the page settles. Values are never written to this report: each cookie is "
        "recorded as name, domain, path, expiry, flags, value length and a 12-character SHA-256 "
        "prefix of the value, which is enough to prove that the same value carried across queries "
        "and across a process restart without putting a live session token into version control.",
        "",
        f"Queries per phase: {json.dumps(queries_per_phase)}. Per-query budget {budget_s:.0f}s, "
        f"gap between consecutive Mojeek navigations {gap_s:.0f}s.",
        "",
    ]


def build_report_md(
    phases: list, persistence: dict, live_requests: int, gap_s: float, budget_s: float,
    prior_spend_note: str = "",
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queries_per_phase = {p.name: [m.label for m in p.measurements] for p in phases}
    lines = _build_header(ts, live_requests, gap_s, prior_spend_note)
    lines += _build_phase_descriptions(phases)
    lines += _build_summary_table(phases)
    lines += _build_q1_section(phases)
    lines += _build_q2_section(phases)
    lines += _build_q3_section(phases, _build_profile_persistence_section(persistence) + _cookie_lines(phases))
    lines += _build_widget_section(phases)
    lines += _build_limits_section()
    lines += _build_methodology_section(queries_per_phase, gap_s, budget_s)
    return "\n".join(lines)


def write_report(report: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"mojeek_pydoll_probe_{ts}.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")
    return report_path
