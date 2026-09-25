# INFRASTRUCTURE
import asyncio
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from crawl4ai import BrowserConfig
from crawl4ai.browser_manager import ManagedBrowser
import psutil
from patchright.async_api import async_playwright

from src import death_pipe
from src.config import CDP_PORT_WAIT_TIMEOUT_S, FOCUS_STEAL_POLL_INTERVAL_S

logger = logging.getLogger(__name__)

TOTAL_SCRAPE_BUDGET_S = 242.8

_osascript_warned: set[str] = set()


# FUNCTIONS

def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


async def _resolve_chromium_bundle_path() -> Path:
    pw = await async_playwright().start()
    try:
        executable_path = pw.chromium.executable_path
    finally:
        await pw.stop()
    bundle = _find_app_bundle(executable_path)
    if bundle is None:
        raise RuntimeError(f"No .app bundle found above patchright's resolved executable: {executable_path}")
    return bundle


def _build_self_launch_flags(browser_config: BrowserConfig) -> list[str]:
    flags = list(ManagedBrowser.build_browser_flags(browser_config))
    if browser_config.viewport_width and browser_config.viewport_height:
        flags.append(f"--window-size={browser_config.viewport_width},{browser_config.viewport_height}")
    return flags


def _warn_osascript_once(what: str, detail: str) -> None:
    if what in _osascript_warned:
        return
    _osascript_warned.add(what)
    logger.warning("osascript %s failed (focus-steal reclaim ineffective): %s", what, detail)


def _get_frontmost_app() -> str:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    name = result.stdout.strip()
    if result.returncode != 0 or not name:
        _warn_osascript_once("get_frontmost", f"returncode={result.returncode} stderr={result.stderr.strip()!r}")
    return name


def _activate_app(app_name: str) -> None:
    result = subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of process "{app_name}" to true',
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _warn_osascript_once("activate", f"returncode={result.returncode} stderr={result.stderr.strip()!r}")


async def _focus_steal_watchdog(app_name: str) -> None:
    last_other_app = await asyncio.to_thread(_get_frontmost_app)
    while True:
        current = await asyncio.to_thread(_get_frontmost_app)
        if current == app_name:
            if last_other_app and last_other_app != app_name:
                await asyncio.to_thread(_activate_app, last_other_app)
        else:
            last_other_app = current
        await asyncio.sleep(FOCUS_STEAL_POLL_INTERVAL_S)


def _self_launch_chrome(bundle_path: Path, user_data_dir: str, flags: list[str]) -> None:
    open_cmd = [
        "open", "-g", "-n", "-a", str(bundle_path), "--args",
        "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}",
        "--no-startup-window", "--no-first-run", "--no-default-browser-check",
        *flags,
    ]
    subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_for_devtools_port(user_data_dir: str, timeout_s: float) -> int:
    port_file = Path(user_data_dir) / "DevToolsActivePort"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if port_file.exists():
            lines = port_file.read_text().splitlines()
            if lines and lines[0].strip().isdigit():
                return int(lines[0].strip())
        time.sleep(0.1)
    raise TimeoutError(f"DevToolsActivePort did not appear under {user_data_dir} within {timeout_s}s")


def _pids_on_profile(user_data_dir: str) -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={user_data_dir}"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


def _kill_by_profile(user_data_dir: str) -> None:
    pids = _pids_on_profile(user_data_dir)
    if pids:
        death_pipe._terminate_then_kill(pids, timeout_s=3.0)


def _reap_orphaned_scrapes() -> None:
    candidate_pids = _pids_matching_scrape_profiles()
    now = time.time()
    orphaned_pids = []
    for pid in candidate_pids:
        try:
            age_s = now - psutil.Process(pid).create_time()
        except psutil.NoSuchProcess:
            continue
        if age_s > TOTAL_SCRAPE_BUDGET_S:
            orphaned_pids.append(pid)
    if orphaned_pids:
        logger.warning(
            "Reaping orphaned scrape-cdp Chrome (age > %.1fs): pids=%s", TOTAL_SCRAPE_BUDGET_S, orphaned_pids
        )
        death_pipe._terminate_then_kill(orphaned_pids)

    live_dirs = _live_scrape_profile_dirs()
    for entry in Path(tempfile.gettempdir()).glob("scrape-url-cdp-*"):
        if str(entry) not in live_dirs:
            shutil.rmtree(entry, ignore_errors=True)


def _pids_matching_scrape_profiles() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", "user-data-dir=.*scrape-url-cdp-"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


def _live_scrape_profile_dirs() -> set[str]:
    dirs = set()
    for pid in _pids_matching_scrape_profiles():
        try:
            cmdline = psutil.Process(pid).cmdline()
        except psutil.NoSuchProcess:
            continue
        for arg in cmdline:
            if arg.startswith("--user-data-dir=") and "scrape-url-cdp-" in arg:
                dirs.add(arg.removeprefix("--user-data-dir="))
    return dirs
