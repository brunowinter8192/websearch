# INFRASTRUCTURE
import json
from datetime import datetime, timezone
from pathlib import Path


# FUNCTIONS

def _build_header(ts: str, search_url: str, trigger_count: int, pause_s: float) -> list[str]:
    return [
        "# ALTCHA Trigger Probe",
        "",
        f"Run: {ts}",
        f"Target: {search_url}",
        f"Live requests made: {1 + trigger_count} passive-inspection-plus-trigger sessions, "
        f"2 navigations each (control URL + target), {pause_s:.0f}s pause between sessions",
        "",
    ]


def _build_summary_table(trigger_results: list) -> list[str]:
    lines = [
        "## Summary",
        "",
        "| Trigger | Widget found | Computation started | Final widget state | verified event | Page outcome | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in trigger_results:
        lines.append(
            f"| {r.trigger} | {r.element_found} | {r.computation_started} | {r.final_state} | "
            f"{r.verified_fired} | {r.page_outcome} | {r.verdict} |"
        )
    lines.append("")
    return lines


def _build_event_table(events: list[dict]) -> list[str]:
    if not events:
        return ["(no widget events observed)"]
    lines = ["| t_ms | event | detail |", "|---|---|---|"]
    t0 = events[0]["t_ms"]
    for e in events:
        detail = e.get("detail") or ""
        lines.append(f"| {e['t_ms'] - t0} | {e['event']} | {detail} |")
    return lines


def _build_inspection_section(inspection) -> list[str]:
    lines = ["## Step 1 — Passive Inspection", ""]
    if inspection.error:
        lines += [f"Error: {inspection.error}", ""]
        return lines
    lines += [
        f"Widget found: {inspection.widget_found}",
        f"Page title at capture: {inspection.page_title}",
        f"Widget state (getState()): {inspection.state}",
        f"Shadow root mode (via CDP DOM.describeNode, pierce=True — sees closed roots too): "
        f"{inspection.shadow_mode}",
        f"Interactive element located via: {inspection.interactive_element_selector} "
        f"(tag: {inspection.interactive_element_tag})",
        "",
        f"humanInteractionSignature (getConfiguration()): {inspection.his_enabled}",
        "",
        "### Attributes as served today",
        "",
        "```json",
        json.dumps(inspection.attributes, indent=2),
        "```",
        "",
        "### getConfiguration() output",
        "",
        "```json",
        json.dumps(inspection.configuration, indent=2),
        "```",
        "",
        "### Deviations from ALTCHA's documented defaults",
        "",
    ]
    if inspection.config_diffs:
        lines += [f"- {d}" for d in inspection.config_diffs]
    else:
        lines.append("- none observed against the documented default set")
    lines += [
        "",
        "### Surrounding form markup",
        "",
        "```html",
        inspection.form_outer_html or "(no enclosing form found)",
        "```",
        "",
        "### Widget markup",
        "",
        "```html",
        inspection.widget_outer_html or "(unavailable)",
        "```",
        "",
        "### Events observed during passive load (no trigger fired)",
        "",
    ]
    lines += _build_event_table(inspection.events)
    lines.append("")
    return lines


def _build_trigger_section(result) -> list[str]:
    lines = [f"## Trigger: {result.trigger}", ""]
    if result.error:
        lines += [f"Error: {result.error}", ""]
    lines += [
        f"Widget found: {result.element_found}",
        f"load event observed during readiness wait: {result.load_event_observed}",
        f"typeof verify === 'function' at readiness check: {result.verify_is_function}",
        f"Computation started (VERIFYING observed): {result.computation_started}",
        f"verified event fired: {result.verified_fired}",
        f"Final widget state: {result.final_state}",
        f"Page outcome: {result.page_outcome}",
        f"Verdict: {result.verdict}",
        "",
    ]
    if result.click_target is not None:
        lines += [
            "### Click target (real_click trigger only)",
            "",
            f"Click actually delivered to the DOM (mousedown/mouseup/click observed on the widget "
            f"host, bubbled from wherever it lands — composed events bubble out of shadow roots "
            f"regardless of open/closed mode): {result.click_delivered}",
            "",
            "```json",
            json.dumps(result.click_target, indent=2),
            "```",
            "",
        ]
    lines += [
        "### Page outcome detail",
        "",
        "```json",
        json.dumps(result.page_outcome_detail, indent=2),
        "```",
        "",
        "### Event sequence",
        "",
    ]
    lines += _build_event_table(result.events)
    lines.append("")
    return lines


def _build_methodology_section(
    result_link_selector: str, block_marker_text: str, in_flight_marker_text: str, settle_timeout_s: float,
) -> list[str]:
    return [
        "## Methodology",
        "",
        "Every session (1 inspection + 3 triggers) launches the same Chromium bundle production's "
        "`src/scraper/chromium_scrape.py`/`chromium_process.py` self-launches — resolved dynamically "
        "from patchright's own installed browser (`Google Chrome for Testing.app` on this machine, "
        "not the user's real Chrome), with the exact same `ManagedBrowser.build_browser_flags(enable_stealth=True)` "
        "CLI flags — against its own fresh `--user-data-dir`, backgrounded via `open -g -n -a`, with "
        "a PID-keyed focus-steal reclaim watchdog for the session's whole run. This script does not "
        "import from `src/` (a hard constraint enforced on new files in this repo's tooling), so the "
        "launch/resolve/flag-building/watchdog helpers are an inline copy of "
        "`src/scraper/chromium_process.py`'s current shape rather than a shared import — the same "
        "dev-isolation convention several sibling probes in this directory already use — but nothing "
        "about the actual browser build or its fingerprint differs from what production drives.",
        "",
        "Before navigating to Mojeek, every session first navigates to a neutral control URL in that "
        "same browser/profile. If that control navigation fails, the whole probe aborts immediately "
        "with the raw error instead of continuing to produce verdicts — a session that cannot reach "
        "the open internet at all cannot tell 'Mojeek refused' apart from 'this environment is blind "
        "right now', and reporting NEVER_STARTED in that case would be reporting nothing.",
        "",
        "Each session's page had a `Page.addScriptToEvaluateOnNewDocument`-equivalent init script "
        "registered (code guaranteed to run before any of Mojeek's own scripts) before the Mojeek "
        "navigation. That script installs a `MutationObserver` on `document` from the first instant "
        "of navigation, attaching listeners for every documented ALTCHA widget event the moment the "
        "widget node appears, and — for the `auto_onload` session only — setting `auto=\"onload\"` "
        "in that same synchronous callback, before the custom element upgrade can read a stale "
        "attribute. Widget events are bridged out to Python via an exposed binding call, a genuine "
        "push event, not a poll.",
        "",
        "The interactive element used for the `real_click` trigger is located via a raw CDP "
        "`DOM.describeNode(pierce=true)` call, which reports the widget's actual shadow-root mode "
        "and can resolve into the shadow tree regardless of whether that mode is `open` or `closed` "
        "— CDP inspection is not subject to the JS-level restriction that hides closed shadow "
        "content from `element.shadowRoot`. The click itself dispatches through CDP's real mouse "
        "input path (`Input.dispatchMouseEvent`), producing a trusted (`isTrusted=true`) synthetic "
        "click, distinct from a JS-level `.click()` call.",
        "",
        "The init script also attaches `mousedown`/`mouseup`/`click` listeners directly on the "
        "widget HOST element (not just the ALTCHA-specific events) — these are standard, composed "
        "UI events, so they bubble out to the host regardless of whether the actual target sits "
        "inside an open or closed shadow root, giving an independent, structural signal for whether "
        "the dispatched click was delivered to the page at all. This distinction matters: extensive "
        "ad-hoc testing during this milestone's build (documented in this session's process-docs "
        "entry, not repeated here — coordinates verified correct via `DOM.getNodeForLocation` "
        "hit-testing, `Target.activateTarget`/`Page.bringToFront`/`Emulation.setFocusEmulationEnabled` "
        "all tried, `document.hasFocus()`/`document.visibilityState` both already true/visible) found "
        "that `Input.dispatchMouseEvent` clicks (raw CDP, `page.mouse`, and `locator.click()` all "
        "three tried) land and fire correctly on light-DOM elements outside any shadow root in this "
        "self-launch-plus-`connect_over_cdp` session shape, but never reach ANY element located "
        "inside a shadow root (open or closed, button or checkbox alike) — zero "
        "`mousedown`/`mouseup`/`click` observed even at the dispatch target itself — while the exact "
        "same click on the exact same shadow-DOM control succeeds when Playwright launches and owns "
        "the browser process directly instead of attaching to a self-launched one. Since ALTCHA's "
        "`<altcha-widget>` is a Web Component and its own docs describe it as using the browser's "
        "native custom-element machinery, its interactive content is very likely shadow-DOM-scoped — "
        "the inspection pass below checks this directly rather than assuming it. If `click_delivered` "
        "is `False` below, the `real_click` trigger's NEVER_STARTED verdict reflects this gap in the "
        "click-delivery mechanism itself, not a refusal by Mojeek's widget, and must be read "
        "accordingly — a genuine limitation of the self-launch-plus-`connect_over_cdp` session shape "
        "production's own scrape lane also uses, not something specific to this probe.",
        "",
        "Readiness (element present, `load` event observed, `typeof verify === 'function'`) and "
        "trigger completion (`verified`/`error`/`expired` observed) are both awaited event- or "
        "poll-driven with a bounded timeout, never a single fixed sleep before one check.",
        "",
        "Page outcome is read from the live DOM as one of three states, checked in this order: "
        f"RESULTS (real result links matching `{result_link_selector}`, verified live on "
        "2026-05-03 — see `process-docs/engine_expansion/`); IN_FLIGHT (the literal, "
        f"locale-independent string `\"{in_flight_marker_text}\"` is present — the widget reached "
        "`verified` client-side and the server round trip is still open); BLOCKED (the literal "
        f"string `\"{block_marker_text}\"` is present and the IN_FLIGHT marker is gone). A first "
        "version of this probe treated BLOCKED as the default the instant the block-page's "
        "boilerplate text was present — which is true from the very first poll after any "
        "navigation, including while the widget is still mid-flight, since Mojeek's challenge page "
        "carries the same 'Verification required' boilerplate throughout the whole verification "
        "sequence, disappearing only once real results replace the page. That version silently "
        "misread 'still waiting on the server' as 'server rejected it' on its first live run — "
        "caught in review, not by this probe itself. The settle loop now keeps polling at 1s "
        f"intervals for up to {settle_timeout_s:.0f}s while the outcome is IN_FLIGHT, and only "
        "reports BLOCKED once that marker is gone and no results ever appeared. If IN_FLIGHT is "
        "still the outcome when the budget runs out, the verdict is INCONCLUSIVE_STILL_PENDING, "
        "never RAN_REJECTED — a stalled round trip is not evidence of a refusal, and this probe "
        "does not conflate the two.",
        "",
    ]


def build_report_md(
    inspection, trigger_results: list, search_url: str, pause_s: float,
    result_link_selector: str, block_marker_text: str, in_flight_marker_text: str, settle_timeout_s: float,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = _build_header(ts, search_url, len(trigger_results), pause_s)
    lines += _build_summary_table(trigger_results)
    lines += _build_inspection_section(inspection)
    for result in trigger_results:
        lines += _build_trigger_section(result)
    lines += _build_methodology_section(result_link_selector, block_marker_text, in_flight_marker_text, settle_timeout_s)
    return "\n".join(lines)


def write_report(report: str, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"altcha_trigger_probe_{ts}.md"
    report_path.write_text(report)
    print(f"Report written to {report_path}")
    return report_path
