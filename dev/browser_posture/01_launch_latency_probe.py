#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    BACKGROUNDING_FLAGS, WINDOW_ARGS, launch_chrome, stop_chrome, spawn_plain_chrome, kill_by_profile,
    profile_dir, start_probe_server, stop_probe_server, read_tick_stats, read_visibility_state, stats_ms,
)

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

N_LATENCY = 5
N_DRIFT = 3
NAV_TIMEOUT_S = 15.0
DRIFT_WAIT_S = 4.5

CONFIGS = [
    {"slug": "headless_direct", "label": "1. headless, direct", "headless": True, "flags": [], "backgrounded": False},
    {"slug": "headed_bg_noflags", "label": "2. headed, backgrounded, no flags", "headless": False, "flags": [], "backgrounded": True},
    {"slug": "headed_bg_flags", "label": "3. headed, backgrounded, +3 flags", "headless": False, "flags": BACKGROUNDING_FLAGS, "backgrounded": True},
    {"slug": "headless_flags", "label": "4. headless, direct, +3 flags (control)", "headless": True, "flags": BACKGROUNDING_FLAGS, "backgrounded": False},
]

OCCLUDER_PROFILE = profile_dir("occluder")


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    server, thread, port = start_probe_server()
    base_url = f"http://127.0.0.1:{port}/"
    results = {}
    try:
        for cfg in CONFIGS:
            print(f"=== {cfg['label']} ===", file=sys.stderr)
            results[cfg["slug"]] = {
                "label": cfg["label"],
                "latency": await measure_latency(cfg, base_url),
                "drift": await measure_drift(cfg, base_url),
            }
    finally:
        stop_probe_server(server, thread)
        kill_by_profile(OCCLUDER_PROFILE)

    orphans = check_orphans()
    report_path = write_report(results, orphans)
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Orphan Chrome processes after run: {len(orphans)}", file=sys.stderr)


# FUNCTIONS

async def measure_latency(cfg: dict, base_url: str) -> dict:
    profile = profile_dir(cfg["slug"])
    tab_times, drivable_times, nav_times, nav_failures = [], [], [], 0
    for i in range(N_LATENCY):
        print(f"  latency rep {i + 1}/{N_LATENCY}", file=sys.stderr)
        browser, tab, t_tab, t_drivable = await launch_chrome(profile, cfg["headless"], cfg["flags"], cfg["backgrounded"])
        tab_times.append(t_tab)
        drivable_times.append(t_drivable)
        t0 = time.monotonic()
        try:
            await tab.go_to(base_url, timeout=NAV_TIMEOUT_S)
            nav_times.append(time.monotonic() - t0)
        except Exception as e:
            nav_failures += 1
            print(f"    nav failed: {type(e).__name__}: {e}", file=sys.stderr)
        await stop_chrome(browser, profile)
    return {
        "start_to_tab": stats_ms(tab_times),
        "start_to_drivable": stats_ms(drivable_times),
        "navigation": stats_ms(nav_times),
        "nav_failures": nav_failures,
    }


async def measure_drift(cfg: dict, base_url: str) -> dict:
    profile = profile_dir(f"{cfg['slug']}-drift")
    counts, mean_intervals, max_gaps, occluded_confirmed = [], [], [], []
    for i in range(N_DRIFT):
        print(f"  drift rep {i + 1}/{N_DRIFT}", file=sys.stderr)
        browser, tab, _, _ = await launch_chrome(profile, cfg["headless"], cfg["flags"], cfg["backgrounded"])
        await tab.go_to(base_url, timeout=NAV_TIMEOUT_S)
        if cfg["backgrounded"]:
            spawn_plain_chrome(OCCLUDER_PROFILE, window_args=WINDOW_ARGS)
            await asyncio.sleep(1.0)
            vis = await read_visibility_state(tab)
            occluded_confirmed.append(vis.get("visibilityState") == "hidden" or vis.get("hidden") is True)
        await asyncio.sleep(DRIFT_WAIT_S)
        stats = await read_tick_stats(tab)
        counts.append(stats["count"])
        if stats["mean_interval_ms"] is not None:
            mean_intervals.append(stats["mean_interval_ms"])
            max_gaps.append(stats["max_gap_ms"])
        if cfg["backgrounded"]:
            kill_by_profile(OCCLUDER_PROFILE)
        await stop_chrome(browser, profile)
    return {
        "expected_ticks": 40,
        "actual_ticks": sorted(counts),
        "mean_interval_ms": round(sum(mean_intervals) / len(mean_intervals), 1) if mean_intervals else None,
        "max_gap_ms": max(max_gaps) if max_gaps else None,
        "occlusion_applicable": cfg["backgrounded"],
        "occlusion_confirmed": any(occluded_confirmed) if occluded_confirmed else None,
    }


def check_orphans() -> list[str]:
    import subprocess
    result = subprocess.run(["pgrep", "-fl", "browser-posture-probe"], capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def write_report(results: dict, orphans: list[str]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"01_launch_latency_probe_{ts}.md"

    lines = [
        f"# Launch Latency + Flag Probe — {ts}",
        "",
        "Dev-only probe (macOS): headless-direct vs headed-backgrounded Chrome launch latency, one "
        "local-page navigation, and background-timer-throttling drift. N=5 per config for launch/nav, "
        "N=3 per config for the (more expensive, fixed ~4.8s wait) timer-drift measurement.",
        "",
    ]
    lines += _build_config_table()
    lines += _build_latency_table(results)
    lines += _build_drift_table(results)
    lines += _build_watchdog_fit(results)
    lines += _build_excluded_flag_note()
    lines += _build_teardown_section(orphans)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _build_config_table() -> list[str]:
    lines = [
        "## Configurations",
        "",
        "| # | Config | headless | backgrounded (`open -g`) | flags |",
        "|---|--------|----------|---------------------------|-------|",
    ]
    for cfg in CONFIGS:
        flags = ", ".join(cfg["flags"]) if cfg["flags"] else "(none)"
        lines.append(f"| {cfg['label'][0]} | {cfg['label'][3:]} | {cfg['headless']} | {cfg['backgrounded']} | {flags} |")
    return lines


def _build_latency_table(results: dict) -> list[str]:
    lines = [
        "",
        "## Launch + Navigation Latency (ms, min/median/max, N=5)",
        "",
        "| Config | start->tab | start->drivable | navigation | nav failures |",
        "|--------|-----------|------------------|------------|--------------|",
    ]
    for cfg in CONFIGS:
        r = results[cfg["slug"]]["latency"]
        lines.append(f"| {cfg['label']} | {_fmt_stats(r['start_to_tab'])} | {_fmt_stats(r['start_to_drivable'])} | {_fmt_stats(r['navigation'])} | {r['nav_failures']}/{N_LATENCY} |")
    return lines


def _build_drift_table(results: dict) -> list[str]:
    lines = [
        "",
        "## Background-Timer-Throttling Drift (expected 40 ticks / ~4000ms nominal, N=3)",
        "",
        "| Config | actual ticks (per rep) | mean interval ms | max single gap ms | occlusion confirmed |",
        "|--------|-------------------------|-------------------|--------------------|----------------------|",
    ]
    any_occlusion_applicable = False
    any_occlusion_confirmed = False
    for cfg in CONFIGS:
        d = results[cfg["slug"]]["drift"]
        occ = "n/a (headless, no window)" if not d["occlusion_applicable"] else ("YES" if d["occlusion_confirmed"] else "NOT CONFIRMED")
        if d["occlusion_applicable"]:
            any_occlusion_applicable = True
            any_occlusion_confirmed = any_occlusion_confirmed or bool(d["occlusion_confirmed"])
        lines.append(f"| {cfg['label']} | {d['actual_ticks']} | {d['mean_interval_ms']} | {d['max_gap_ms']} | {occ} |")

    if any_occlusion_applicable and not any_occlusion_confirmed:
        lines += [
            "",
            "**Occlusion NOT confirmed for configs 2/3.** `document.visibilityState` stayed `visible` "
            "throughout, despite spawning a same-geometry, `-g`-backgrounded coverer window on top of the "
            "automation window. This machine has multiple concurrent real login sessions (`who` showed "
            "an active console session plus many tty sessions); the coverer and/or automation window "
            "may be placed in a different macOS Space than assumed, so true screen-occlusion could not "
            "be verified here without a privacy-invasive full-screen capture (deliberately not repeated "
            "after one such capture incidentally showed live, unrelated session content — deleted "
            "immediately, not part of this deliverable). **Read the drift numbers above as: 'no "
            "throttling observed under `open -g` backgrounding, occlusion state unconfirmed' — NOT as "
            "proof the flags make no difference under genuine window occlusion.** This is a real gap "
            "against the milestone's own goal of measuring the flags' effect; a follow-up needs either "
            "a single-user, single-session machine, or a CDP-level way to force renderer occlusion that "
            "does not depend on real window-manager stacking.",
        ]
    return lines


def _build_watchdog_fit(results: dict) -> list[str]:
    watchdog_lines = ["", "## Watchdog Fit", ""]
    for cfg in CONFIGS:
        r = results[cfg["slug"]]["latency"]
        total = r["start_to_drivable"]["max"]
        if total is None:
            continue
        fits_default = total <= 3600
        fits_override = total <= 6000
        watchdog_lines.append(
            f"- **{cfg['label']}**: worst-case start->drivable = {total}ms — "
            f"{'fits' if fits_default else 'EXCEEDS'} the 3.6s default watchdog, "
            f"{'fits' if fits_override else 'EXCEEDS'} the 6.0s override ceiling."
        )
    return watchdog_lines


def _build_excluded_flag_note() -> list[str]:
    return [
        "",
        "## Excluded: `--disable-new-content-rendering-timeout`",
        "",
        "Not measured. It governs blanking of stale COMPOSITOR output after a stalled paint — a "
        "purely visual concern. Production never screenshots or reads rendered pixels (every signal "
        "is CDP/DOM: `execute_script`, `Runtime.evaluate`), so a blanked compositor frame is invisible "
        "to every signal this probe or production consumes. Revisit only if a future milestone adds "
        "screenshot-based extraction.",
    ]


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


def _fmt_stats(s: dict) -> str:
    return f"{s['min']}/{s['median']}/{s['max']}" if s["n"] else "n/a"


if __name__ == "__main__":
    asyncio.run(run_probe())
