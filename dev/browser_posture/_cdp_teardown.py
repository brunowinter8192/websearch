# INFRASTRUCTURE
import subprocess

import psutil


# FUNCTIONS

# Kill the self-launched Chrome by profile dir — the mandatory teardown path since `open -g`'s own
# Popen is a short-lived wrapper, not Chrome itself (same pattern as _lib.py's kill_by_profile /
# src/search/browser.py's kill_stale_chrome)
def kill_by_profile(user_data_dir: str) -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={user_data_dir}"], capture_output=True)


# Defensive sweep for any leftover ms-playwright/chromium process + launchd supervision job —
# duplicated from probe 04 (self-contained convention); no crash is expected on this route so this
# should always be a no-op, kept as a safety net and a live regression check on that expectation
def kill_survivors() -> None:
    launchd_result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    for line in launchd_result.stdout.splitlines():
        if "chrome.for.testing" in line.lower():
            label = line.split()[-1]
            subprocess.run(["launchctl", "remove", label], capture_output=True)
    victims = []
    for proc in psutil.process_iter(["pid"]):
        try:
            if "ms-playwright/chromium" in proc.exe():
                proc.terminate()
                victims.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if victims:
        gone, alive = psutil.wait_procs(victims, timeout=3)
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass


# pgrep for any leftover process pinned to this run's throwaway profile + any residual launchd job
def check_orphans(user_data_dir: str) -> list[str]:
    result = subprocess.run(["pgrep", "-fl", f"user-data-dir={user_data_dir}"], capture_output=True, text=True)
    orphans = [line for line in result.stdout.splitlines() if line.strip()]
    launchd_result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    orphans += [
        f"launchd job: {line}" for line in launchd_result.stdout.splitlines()
        if "chrome.for.testing" in line.lower()
    ]
    return orphans
