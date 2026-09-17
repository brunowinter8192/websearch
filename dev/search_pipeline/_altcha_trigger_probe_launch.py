# INFRASTRUCTURE
import asyncio
import subprocess
import time
from pathlib import Path

from crawl4ai import BrowserConfig
from crawl4ai.browser_manager import ManagedBrowser
from patchright.async_api import async_playwright

FOCUS_STEAL_POLL_INTERVAL_S = 0.25


# FUNCTIONS

def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


async def resolve_chromium_bundle_path() -> Path:
    pw = await async_playwright().start()
    try:
        executable_path = pw.chromium.executable_path
    finally:
        await pw.stop()
    bundle = _find_app_bundle(executable_path)
    if bundle is None:
        raise RuntimeError(f"No .app bundle found above patchright's resolved executable: {executable_path}")
    return bundle


def build_launch_flags() -> list[str]:
    return list(ManagedBrowser.build_browser_flags(BrowserConfig(enable_stealth=True)))


def self_launch_chrome(bundle_path: Path, user_data_dir: str, flags: list[str]) -> None:
    open_cmd = [
        "open", "-g", "-n", "-a", str(bundle_path), "--args",
        "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}",
        "--no-startup-window", "--no-first-run", "--no-default-browser-check",
        *flags,
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


def _get_frontmost_app() -> str:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _activate_app(app_name: str) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of process "{app_name}" to true',
        ],
        capture_output=True, text=True,
    )


async def focus_steal_watchdog(app_name: str) -> None:
    last_other_app = await asyncio.to_thread(_get_frontmost_app)
    while True:
        current = await asyncio.to_thread(_get_frontmost_app)
        if current == app_name:
            if last_other_app and last_other_app != app_name:
                await asyncio.to_thread(_activate_app, last_other_app)
        else:
            last_other_app = current
        await asyncio.sleep(FOCUS_STEAL_POLL_INTERVAL_S)


def kill_by_profile(user_data_dir: str) -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={user_data_dir}"], capture_output=True)
