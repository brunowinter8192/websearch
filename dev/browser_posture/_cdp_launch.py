# INFRASTRUCTURE
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

CHROMIUM_REVISION_TAG = "chromium-1228"  # the ONLY revision this probe is allowed to touch
CDP_HTTP_READY_TIMEOUT_S = 5.0

# Deliberately minimal — the point of the args-delta step is to reveal what patchright's driver
# adds "for free" that this route would need to backfill, not to pre-empt the diff by mirroring it.
# --no-startup-window: no pre-existing blank tab at connect time, forcing crawl4ai's get_page() to
# call context.new_page() — the exact page-creation-over-CDP event playwright#42343 flags as risky
# (confirmed by reading crawl4ai's own get_page(): it REUSES an existing page if one is already
# open, so a default startup window would silently dodge the very risk this probe exists to measure).
SELF_LAUNCH_ARGS = ["--no-startup-window", "--no-first-run", "--no-default-browser-check"]


# FUNCTIONS

# Locate the chromium-1228 Google Chrome for Testing.app bundle and hard-verify the revision tag —
# same guard as probe 04, refuses to proceed against any other resolved path (e.g. chromium-1223)
def resolve_chromium_1228_bundle() -> Path:
    matches = list(Path.home().glob(
        "Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/*.app"
    ))
    if not matches:
        raise RuntimeError("No chromium-1228 .app bundle found under ~/Library/Caches/ms-playwright/")
    bundle = matches[0]
    if CHROMIUM_REVISION_TAG not in str(bundle):
        raise RuntimeError(f"Resolved bundle {bundle} is NOT {CHROMIUM_REVISION_TAG}")
    return bundle


# Launch the chromium-1228 bundle headed-but-backgrounded via macOS `open -g -n -a`, targeting the
# resolved .app PATH directly (not a bare name) — deterministic, no Launch Services ambiguity
def self_launch_chrome(bundle_path: Path, user_data_dir: str) -> None:
    open_cmd = [
        "open", "-g", "-n", "-a", str(bundle_path), "--args",
        "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}",
        *SELF_LAUNCH_ARGS,
    ]
    subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Poll for Chromium's own DevToolsActivePort file (standard mechanism when --remote-debugging-port=0
# is used) and return the real assigned port — avoids a pre-probed-free-port TOCTOU race
def wait_for_devtools_port(user_data_dir: str, timeout_s: float) -> int:
    port_file = Path(user_data_dir) / "DevToolsActivePort"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if port_file.exists():
            lines = port_file.read_text().splitlines()
            if lines and lines[0].strip().isdigit():
                return int(lines[0].strip())
        time.sleep(0.1)
    raise TimeoutError(f"DevToolsActivePort did not appear under {user_data_dir} within {timeout_s}s")


# Independent confirmation the CDP HTTP endpoint is actually reachable, separate from crawl4ai's
# own internal _verify_cdp_ready retries — a direct GET on /json/version, parsed for the real
# reported browser string
def check_cdp_http_ready(port: int) -> dict:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + CDP_HTTP_READY_TIMEOUT_S
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                data = json.loads(resp.read())
                return {"ready": True, "detail": data.get("Browser"), "webSocketDebuggerUrl": data.get("webSocketDebuggerUrl")}
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_error = str(e)
            time.sleep(0.2)
    return {"ready": False, "detail": last_error}


# Real PID of the self-launched Chrome, found by --user-data-dir substring (NOT children-of-self:
# `open` forks and the actual Chrome process is not our descendant — same lesson as probe 04's
# launchd-driven-respawn finding; the only reliable handle is the profile-dir substring, matching
# src/search/browser.py's own kill_stale_chrome/kill_by_profile pattern)
def find_pid_by_profile(user_data_dir: str) -> int | None:
    result = subprocess.run(["pgrep", "-f", f"user-data-dir={user_data_dir}"], capture_output=True, text=True)
    pids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return int(pids[0]) if pids else None
