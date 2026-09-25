# INFRASTRUCTURE
from datetime import datetime
from pathlib import Path


# FUNCTIONS

def write_report(results: dict, orphans: list[str], report_dir: Path, variants: list, hardcoded_props: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"03_fingerprint_patch_probe_{ts}.md"

    none = results["none"]
    href = results["headless_reference"]
    verdict = _compute_activetext_verdict(none, href)

    lines = [
        f"# Fingerprint-Patch Consistency Probe — {ts}",
        "",
        "Dev-only probe (macOS, headed-backgrounded only): does `src/search/browser.py`'s "
        "`JS_FINGERPRINT_PATCHES` (written for headless) still make sense under headed? 4 variants "
        "+ 1 headless reference (artifact test only). Targets: local artifact page (system colors + "
        "screen/window props), bot.sannysoft.com, CreepJS.",
        "",
    ]
    lines += _build_activetext_section(results, variants, href, verdict)
    lines += _build_screen_props_section(results, variants, href)
    lines += _build_sannysoft_section(results, variants)
    lines += _build_creepjs_section(results, variants)
    lines += _build_per_block_verdict_section(results, hardcoded_props, verdict)
    lines += _build_teardown_section(orphans)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _compute_activetext_verdict(none: dict, href: dict) -> dict:
    red_headed_nopatch = none["colors"].get("activeText") == "rgb(255, 0, 0)"
    red_headless_nopatch = href["colors"].get("activeText") == "rgb(255, 0, 0)"
    if red_headless_nopatch and not red_headed_nopatch:
        reading = "**Red is headless-only.**"
        plain = (
            "red is headless-only — the patch's own premise holds: headless reports rgb(255, 0, 0) "
            "for ActiveText, headed does not"
        )
    elif red_headless_nopatch and red_headed_nopatch:
        reading = "**Red occurs in BOTH modes.**"
        plain = (
            "red occurs in BOTH modes — ActiveText resolves to rgb(255, 0, 0) under headed too, which "
            "is what real Chrome reports, not a headless artifact; the patch's premise does not hold"
        )
    elif not red_headless_nopatch and not red_headed_nopatch:
        reading = "**Red occurs in NEITHER mode observed here.**"
        plain = (
            "red occurs in neither mode observed here — the patch corrects a condition not observed "
            "in this Chrome version on this machine, headed or headless"
        )
    else:
        reading = "**Red occurs under headed but NOT headless.**"
        plain = "red occurs under headed but not headless — the inverse of the patch's premise"
    return {
        "red_headed_nopatch": red_headed_nopatch,
        "red_headless_nopatch": red_headless_nopatch,
        "reading": reading,
        "plain": plain,
    }


def _build_activetext_section(results: dict, variants: list, href: dict, verdict: dict) -> list[str]:
    none = results["none"]
    lines = [
        "## getComputedStyle artifact: does the rgb(255,0,0) ActiveText artifact occur under headed?",
        "",
        "Tested on `color: ActiveText` directly (not a resting `<a>`, which computes to the ordinary "
        "link color in every mode and never touches what the patch targets).",
        "",
        "| Variant | plainLink | activeText | linkText | visitedText |",
        "|---|---|---|---|---|",
    ]
    for v in variants:
        c = results[v["slug"]]["colors"]
        lines.append(f"| {v['label']} | {c.get('plainLink')} | {c.get('activeText')} | {c.get('linkText')} | {c.get('visitedText')} |")
    lines.append(f"| {href['label']} | {href['colors'].get('plainLink')} | {href['colors'].get('activeText')} | {href['colors'].get('linkText')} | {href['colors'].get('visitedText')} |")

    lines += [
        "",
        f"**ActiveText under headed, no patches: `{none['colors'].get('activeText')}`** "
        f"({'IS' if verdict['red_headed_nopatch'] else 'is NOT'} `rgb(255, 0, 0)`).",
        f"**ActiveText under headless, no patches: `{href['colors'].get('activeText')}`** "
        f"({'IS' if verdict['red_headless_nopatch'] else 'is NOT'} `rgb(255, 0, 0)`).",
        "",
        f"{verdict['reading']} The patch's own comment claims headless-only "
        f"(`rgb(255, 0, 0)` for ActiveText); the data above shows {verdict['plain']}.",
    ]
    return lines


def _build_screen_props_section(results: dict, variants: list, href: dict) -> list[str]:
    lines = [
        "",
        "## Real vs. hardcoded screen/window properties (all 4 variants + headless reference)",
        "",
        "| Variant | screenW | screenH | availW | availH | colorDepth | pixelDepth | dPR | innerW | innerH | outerW | outerH |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v in variants:
        p = results[v["slug"]]["props"]
        lines.append(
            f"| {v['label']} | {p.get('screenWidth')} | {p.get('screenHeight')} | {p.get('availWidth')} | "
            f"{p.get('availHeight')} | {p.get('colorDepth')} | {p.get('pixelDepth')} | {p.get('devicePixelRatio')} | "
            f"{p.get('innerWidth')} | {p.get('innerHeight')} | {p.get('outerWidth')} | {p.get('outerHeight')} |"
        )
    p_href = href["props"]
    lines.append(
        f"| {href['label']} | {p_href.get('screenWidth')} | {p_href.get('screenHeight')} | {p_href.get('availWidth')} | "
        f"{p_href.get('availHeight')} | {p_href.get('colorDepth')} | {p_href.get('pixelDepth')} | {p_href.get('devicePixelRatio')} | "
        f"{p_href.get('innerWidth')} | {p_href.get('innerHeight')} | {p_href.get('outerWidth')} | {p_href.get('outerHeight')} |"
    )
    lines += [
        "",
        f"**Hardcoded by the patch:** screenW/H=1920x1080, availW/H=1920x1057, colorDepth/pixelDepth=30, "
        f"devicePixelRatio=2, outerW=innerW, outerH=innerH+85.",
        f"**Real values under headed, no patches** (variant 4 above): screenW/H="
        f"{results['none']['props'].get('screenWidth')}x{results['none']['props'].get('screenHeight')}, "
        f"availW/H={results['none']['props'].get('availWidth')}x{results['none']['props'].get('availHeight')}, "
        f"colorDepth/pixelDepth={results['none']['props'].get('colorDepth')}/{results['none']['props'].get('pixelDepth')}, "
        f"devicePixelRatio={results['none']['props'].get('devicePixelRatio')} — "
        "this machine has a real 3456x2234 Retina display; the window geometry is whatever "
        "`--window-size`/position the launch used, not the hardcoded external-monitor values.",
    ]
    return lines


def _build_sannysoft_section(results: dict, variants: list) -> list[str]:
    lines = [
        "",
        "## bot.sannysoft.com",
        "",
        "| Variant | total rows | failed rows |",
        "|---|---|---|",
    ]
    for v in variants:
        s = results[v["slug"]]["sannysoft"]
        lines.append(f"| {v['label']} | {s['total_rows']} | {len(s['failed_rows'])} |")
    if all(len(results[v["slug"]]["sannysoft"]["failed_rows"]) == 0 for v in variants):
        lines.append(
            "\nAll 4 variants: 0 failed rows. sannysoft does not discriminate between any of these "
            "patch combinations — neither block's presence or absence is visible to this particular check."
        )
    for v in variants:
        s = results[v["slug"]]["sannysoft"]
        if s["failed_rows"]:
            lines.append(f"\n**{v['label']} — failed rows:**")
            for r in s["failed_rows"]:
                lines.append(f"- {r['label']}: {r['result']}")
    return lines


def _build_creepjs_section(results: dict, variants: list) -> list[str]:
    lines = [
        "",
        "## CreepJS",
        "",
        "No literal \"Trust Score\"/\"N lies\" summary exists in this live build (checked directly — "
        "every \"trust\"/\"lie\" substring hit in the full page HTML is a false positive, e.g. "
        "\"CLIENT\" containing \"lie\", or \"TrustedTypePolicy\"). The actual inconsistency-scoring "
        "surface here is the \"Headless\" section's three percentages plus scattered "
        "\"confidence: &lt;level&gt;\" notes.",
        "",
        "| Variant | settled | headless signals (%, label) | confidence notes | literal lie/trust wording? |",
        "|---|---|---|---|---|",
    ]
    for v in variants:
        c = results[v["slug"]]["creepjs"]
        lines.append(
            f"| {v['label']} | {c['settled']} | {c['headless_signals']} | {c['confidence_signals']} | "
            f"{c['literal_lie_or_trust_wording_found']} |"
        )
    signal_sets = {tuple(results[v["slug"]]["creepjs"]["headless_signals"]) for v in variants}
    if len(signal_sets) == 1:
        lines.append(
            "\nAll 4 variants produced the IDENTICAL headless-signal reading. CreepJS's headless-"
            "detection module does not discriminate between any of these patch combinations either."
        )
    return lines


def _build_per_block_verdict_section(results: dict, hardcoded_props: dict, verdict: dict) -> list[str]:
    lines = ["", "## Per-Block Verdict", ""]
    lines.append(_build_block_b_verdict(verdict))
    lines.append("")
    lines.append(_build_block_a_verdict(results, hardcoded_props))
    return lines


def _build_teardown_section(orphans: list[str]) -> list[str]:
    lines = [
        "",
        "## Teardown",
        "",
        f"Orphan Chrome processes pinned to any `browser-posture-probe` profile after the run: {len(orphans)}",
    ]
    if orphans:
        lines.append("")
        lines.extend(f"    {o}" for o in orphans)
    return lines


def _build_block_b_verdict(verdict: dict) -> str:
    if verdict["red_headless_nopatch"] and not verdict["red_headed_nopatch"]:
        return (
            "**Block B (getComputedStyle Proxy): KEEP.** Evidence: the ActiveText artifact table above "
            "— `rgb(255, 0, 0)` occurs under headless-no-patches and does NOT occur under headed-no-"
            "patches. The patch's own premise is correct; dropping it under headed would leave headless "
            "runs (if any remain, e.g. via `WEBSEARCH_HEADED` unset) uncorrected, but under headed itself "
            "the Proxy is presently a no-op (nothing to rewrite) rather than a harmful wrapper, since the "
            "trigger condition never fires."
        )
    return (
        "**Block B (getComputedStyle Proxy): DROP under headed.** Evidence: the ActiveText artifact "
        "table above shows the rgb(255,0,0) condition does not discriminate headless-only as the "
        f"patch's comment assumes — {verdict['plain']}. Keeping an always-on Proxy wrapper around "
        "`window.getComputedStyle` under headed adds a detectable deviation (a native function "
        "replaced by a Proxy) for a condition that, per the data above, is not what it was written "
        "to fix in this mode."
    )


def _build_block_a_verdict(results: dict, hardcoded_props: dict) -> str:
    real_props = results["none"]["props"]
    diverging = [k for k, v in hardcoded_props.items() if real_props.get(k) != v]
    matching = [k for k, v in hardcoded_props.items() if real_props.get(k) == v]
    real_outer_h = real_props.get("outerHeight")
    real_inner_h = real_props.get("innerHeight")
    outer_h_offset = (real_outer_h - real_inner_h) if isinstance(real_outer_h, int) and isinstance(real_inner_h, int) else None

    if not diverging:
        return (
            "**Block A (screen/window overrides): the real and hardcoded values happen to match this "
            "run — re-check before relying on this on a different display/window configuration.**"
        )
    return (
        f"**Block A (screen/window overrides): DROP under headed.** Evidence, precisely: "
        f"`{', '.join(diverging)}` diverge from their hardcoded values on this machine's real headed "
        f"window (real vs. hardcoded — see property table above); "
        + (f"`{', '.join(matching)}` happen to coincide with the hardcoded values on this specific "
           f"machine (this Mac is itself 30-bit-color, devicePixelRatio 2) " if matching else "")
        + f"— that coincidence does not generalize to a different machine. The outerHeight formula "
        f"(innerHeight+85) is also off by itself: real outerHeight-innerHeight = {outer_h_offset} here, "
        f"not 85. Under headless there was no real display to contradict; under headed there is a real "
        "window with real, observable dimensions, and reporting values that don't match what a "
        "fingerprinter can cross-check against other signals (the actual rendered viewport, "
        "devicePixelRatio-dependent canvas/font rendering) is exactly the kind of contradiction "
        "detectors score. If a headed default ever needs a DIFFERENT consistent screen profile (not "
        "this machine's real one), values must be internally consistent with each other and with what "
        "the renderer actually does — Milestone 3's concern."
    )
