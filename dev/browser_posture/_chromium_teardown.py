# INFRASTRUCTURE
import subprocess
import time

import psutil


# FUNCTIONS

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


def remove_stray_launchd_jobs() -> list[str]:
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    labels = [line.split()[-1] for line in result.stdout.splitlines() if "chrome.for.testing" in line.lower()]
    for label in labels:
        subprocess.run(["launchctl", "remove", label], capture_output=True, text=True)
    return labels
