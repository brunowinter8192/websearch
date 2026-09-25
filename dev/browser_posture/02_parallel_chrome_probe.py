#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    profile_dir, kill_by_profile, count_processes_for, spawn_plain_chrome,
    build_options, open_background_process_creator, get_frontmost_app,
)
from pydoll.browser import Chrome
from pydoll.browser.managers import BrowserProcessManager

SCRIPT_DIR = Path(__file__).parent
REPORT_DIR = SCRIPT_DIR / "md"

SESSION_DIR = str(Path.home() / ".websearch" / "browser-session")
SIMULATED_USER_PROFILE = profile_dir("simulated-user-chrome")


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    record = await _run_parallel_check()

    report_path = write_report(record)
    _print_report(report_path)


# FUNCTIONS

async def _run_parallel_check():
    record = {}
    try:
        record["baseline_chrome_running"] = any_chrome_running()
        record["frontmost_before_sim"] = get_frontmost_app()

        print("Spawning simulated already-running user Chrome (throwaway profile, backgrounded)...", file=sys.stderr)
        spawn_plain_chrome(SIMULATED_USER_PROFILE)
        await asyncio.sleep(2.0)
        record["sim_user_chrome_processes"] = count_processes_for(SIMULATED_USER_PROFILE)
        record["frontmost_after_sim"] = get_frontmost_app()

        print("Attempting production-shape backgrounded launch against the REAL SESSION_DIR...", file=sys.stderr)
        record.update(await attempt_backgrounded_launch())
        record["frontmost_after_attempt"] = get_frontmost_app()
    finally:
        print("Tearing down...", file=sys.stderr)
        kill_by_profile(SESSION_DIR)
        kill_by_profile(SIMULATED_USER_PROFILE)
        await asyncio.sleep(0.5)
        record["session_dir_processes_after_teardown"] = count_processes_for(SESSION_DIR)
        record["sim_user_processes_after_teardown"] = count_processes_for(SIMULATED_USER_PROFILE)
    return record


def write_report(record: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"02_parallel_chrome_probe_{ts}.md"

    focus_stolen, sim_focus_stolen, launch_focus_stolen = _compute_focus_steal(record)

    lines = [
        f"# Parallel-Chrome Collision Probe — {ts}",
        "",
        "Simulated already-running user Chrome (throwaway profile, `-g` backgrounded, never "
        "foregrounded) + a production-shape headed-backgrounded launch attempt against the REAL "
        "production SESSION_DIR (`~/.websearch/browser-session`), while the simulated user Chrome is "
        "running.",
        "",
    ]
    lines += _build_result_section(record, focus_stolen)
    lines += _build_teardown_section(record)
    lines += _build_reading_section(record, focus_stolen, sim_focus_stolen, launch_focus_stolen)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _print_report(report_path):
    print(f"\nReport: {report_path}", file=sys.stderr)


def any_chrome_running() -> bool:
    result = subprocess.run(
        ["pgrep", "-f", "Google Chrome.app/Contents/MacOS/Google Chrome"],
        capture_output=True, text=True,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()]) > 0


async def attempt_backgrounded_launch() -> dict:
    kill_by_profile(SESSION_DIR)
    time.sleep(0.3)
    options = build_options(SESSION_DIR, headless=False, extra_flags=[], window_args=True)
    browser = Chrome(options)
    browser._browser_process_manager = BrowserProcessManager(process_creator=open_background_process_creator)
    t0 = time.monotonic()
    result = {"launch_success": False}
    try:
        tab = await browser.start()
        result["connect_ms"] = round((time.monotonic() - t0) * 1000)
        value = await tab.execute_script("1+1")
        result["drivable"] = value is not None
        result["drivable_ms"] = round((time.monotonic() - t0) * 1000)
        result["launch_success"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    result["session_dir_processes_during_run"] = count_processes_for(SESSION_DIR)
    try:
        if result["launch_success"]:
            await browser.stop()
    except Exception as e:
        result["stop_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    return result


def _compute_focus_steal(record: dict) -> tuple[bool, bool, bool]:
    baseline = record.get("frontmost_before_sim")
    sim_focus_stolen = baseline != "Google Chrome" and record.get("frontmost_after_sim") == "Google Chrome"
    launch_focus_stolen = baseline != "Google Chrome" and record.get("frontmost_after_attempt") == "Google Chrome"
    focus_stolen = sim_focus_stolen or launch_focus_stolen
    return focus_stolen, sim_focus_stolen, launch_focus_stolen


def _build_result_section(record: dict, focus_stolen: bool) -> list[str]:
    return [
        "## Result",
        "",
        f"- **Frontmost app before either spawn (baseline):** {record.get('frontmost_before_sim')}",
        f"- **Baseline Chrome running before probe:** {record.get('baseline_chrome_running')} "
        "(any profile, any purpose — this machine may run unrelated headless automation under its "
        "own profile; that alone is not evidence of the user's own foreground browsing session)",
        f"- **Simulated user Chrome processes (its own profile) after spawn:** {record.get('sim_user_chrome_processes')}",
        f"- **Frontmost app after simulated user Chrome spawn:** {record.get('frontmost_after_sim')}",
        f"- **Our backgrounded launch succeeded (CDP connected + tab drivable):** {record.get('launch_success')}",
        f"- **Connect latency (ms):** {record.get('connect_ms')}",
        f"- **Drivable latency (ms):** {record.get('drivable_ms')}",
        f"- **Chrome processes pinned to SESSION_DIR during the run:** {record.get('session_dir_processes_during_run')} "
        "(counts the main process plus its GPU/renderer/network-service children, which all inherit "
        "`--user-data-dir` — not a count of distinct browser instances)",
        f"- **Frontmost app immediately after our launch attempt:** {record.get('frontmost_after_attempt')}",
        f"- **Focus stolen by our launch (frontmost became Google Chrome because of it):** {focus_stolen}",
    ]


def _build_teardown_section(record: dict) -> list[str]:
    clean_teardown = (
        record.get("session_dir_processes_after_teardown", 1) == 0
        and record.get("sim_user_processes_after_teardown", 1) == 0
    )
    return [
        "",
        "## Teardown",
        "",
        f"- SESSION_DIR processes after teardown: {record.get('session_dir_processes_after_teardown')}",
        f"- Simulated-user-profile processes after teardown: {record.get('sim_user_processes_after_teardown')}",
        f"- **Clean teardown:** {clean_teardown}",
    ]


def _build_reading_section(record: dict, focus_stolen: bool, sim_focus_stolen: bool, launch_focus_stolen: bool) -> list[str]:
    lines = ["", "## Reading", ""]
    if record.get("launch_success"):
        lines.append(
            "- `open -g -n -a \"Google Chrome\" --args ... --user-data-dir=<SESSION_DIR>` DID reach a "
            "genuinely separate, distinctly-profiled Chrome process even with another Chrome instance "
            "already running under a different profile — `-n` + a distinct `--user-data-dir` forced a "
            "new instance rather than macOS `open` addressing the already-running one and dropping "
            "`--args`. CDP connected and the tab was drivable."
        )
    else:
        lines.append(
            f"- Launch FAILED with the user's Chrome already running: `{record.get('error')}`. This is "
            "the exact failure mode the milestone flagged as a risk — `open -a` addressing the existing "
            "instance and ignoring `--args` (no `--remote-debugging-port`, no isolated profile), leaving "
            "CDP unreachable."
        )
    if not focus_stolen:
        lines.append(
            "- No focus steal observed from either spawn: frontmost app never became Google Chrome, "
            "neither from the simulated-user-Chrome spawn nor from our own launch attempt, both `-g` "
            "backgrounded. Caveat: this session runs in an agent-driven execution context, not a fully "
            "interactive login session — the OS-level frontmost-app signal is the level of proof reached "
            "here; a human visual spot-check remains the stronger confirmation for the visual/"
            "attention-stealing claim specifically (Verification Levels: rendered/visual correctness is "
            "the one thing self-checks cannot fully replace)."
        )
    else:
        lines.append(
            f"- Focus WAS stolen: frontmost app became Google Chrome "
            f"(sim-spawn steal={sim_focus_stolen}, our-launch steal={launch_focus_stolen})."
        )
    return lines


if __name__ == "__main__":
    asyncio.run(run_probe())
