# INFRASTRUCTURE
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

CHROMIUM_REVISION_TAG = "chromium-1228"
CDP_HTTP_READY_TIMEOUT_S = 5.0

SELF_LAUNCH_ARGS = ["--no-startup-window", "--no-first-run", "--no-default-browser-check"]


# FUNCTIONS

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


def self_launch_chrome(bundle_path: Path, user_data_dir: str) -> None:
    open_cmd = [
        "open", "-g", "-n", "-a", str(bundle_path), "--args",
        "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}",
        *SELF_LAUNCH_ARGS,
    ]
    subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def find_pid_by_profile(user_data_dir: str) -> int | None:
    result = subprocess.run(["pgrep", "-f", f"user-data-dir={user_data_dir}"], capture_output=True, text=True)
    pids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return int(pids[0]) if pids else None
