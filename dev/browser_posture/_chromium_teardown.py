# INFRASTRUCTURE
import subprocess
import time

import psutil


# FUNCTIONS

# Remove any macOS launchd per-app supervision job for Chrome for Testing — root cause of the
# gotcha below: when the app CRASHES (e.g. Run C's SIGTRAP from the ICU failure), launchd registers
# `application.com.google.chrome.for.testing.<ids>` and auto-restarts it on a throttled backoff,
# entirely independent of this script's own process tree — a plain psutil/pgrep process kill can
# never stop this, only removing the launchd job does. Returns the labels it found (for reporting).
def remove_stray_launchd_jobs() -> list[str]:
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    labels = [line.split()[-1] for line in result.stdout.splitlines() if "chrome.for.testing" in line.lower()]
    for label in labels:
        subprocess.run(["launchctl", "remove", label], capture_output=True, text=True)
    return labels


# Kill any live process still running under ms-playwright's chromium cache — system-wide by exe
# path, NOT restricted to our own psutil children: Chrome's GPU/renderer/utility helper processes
# get reparented to launchd the instant the main browser process dies, so once that happens they
# are no longer our descendants even though they never received a kill signal themselves. Scoped
# safely because ms-playwright/chromium* is this project's own browser cache, not shared with
# anything else on the machine (same scope as check_orphans()'s pgrep pattern).
#
# Multi-round + launchd-job removal each round: a single terminate-and-wait pass left a fresh
# "Google Chrome for Testing" main process alive ~15s later (new PID, not a slow-dying old one) —
# traced to the launchd supervision job above, NOT a psutil-visible respawn mechanism. Removing
# the job every round (before it can fire again) is what actually stops it.
def kill_survivors(rounds: int = 3, settle_s: float = 1.5) -> None:
    for _ in range(rounds):
        remove_stray_launchd_jobs()
        victims = []
        for proc in psutil.process_iter(["pid"]):
            try:
                if "ms-playwright/chromium" in proc.exe():
                    proc.terminate()
                    victims.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if not victims:
            continue
        gone, alive = psutil.wait_procs(victims, timeout=3)
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(settle_s)


# pgrep for any leftover process under ms-playwright's chromium cache dirs (covers both
# chromium-*/Chrome-for-Testing and chromium_headless_shell-* by substring), plus any residual
# launchd supervision job (see remove_stray_launchd_jobs — the actual respawn source)
def check_orphans() -> list[str]:
    result = subprocess.run(["pgrep", "-fl", "ms-playwright/chromium"], capture_output=True, text=True)
    orphans = [line for line in result.stdout.splitlines() if line.strip()]
    launchd_result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    orphans += [
        f"launchd job: {line}"
        for line in launchd_result.stdout.splitlines()
        if "chrome.for.testing" in line.lower()
    ]
    return orphans
