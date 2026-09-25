# INFRASTRUCTURE
import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import psutil
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.managers import BrowserProcessManager
from pydoll.commands import TargetCommands
from pydoll.connection import ConnectionHandler

logger = logging.getLogger(__name__)

FOCUS_STEAL_POLL_INTERVAL_S = 0.25
CDP_PORT_WAIT_TIMEOUT_S = 10.0

BACKGROUNDING_FLAGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

BROWSER_PREFERENCES = {
    "profile": {
        "exit_type": "Normal",
        "exited_cleanly": True,
    },
    "safebrowsing": {"enabled": True},
    "autofill": {"enabled": True},
    "search": {"suggest_enabled": True},
    "enable_do_not_track": False,
    "credentials_enable_service": True,
    "credentials_enable_autosignin": True,
}


# FUNCTIONS

@dataclass
class LaunchedBrowser:
    browser: Chrome
    profile_dir: str
    owned_pids: list[int]
    watchdog_task: asyncio.Task | None


async def launch_browser(profile_dir: str) -> LaunchedBrowser:
    reap_profile(profile_dir)
    _clear_stale_devtools_port(profile_dir)
    anchor_pid = await asyncio.to_thread(_get_frontmost_pid)
    options = build_options(profile_dir)
    browser = Chrome(options)
    browser._browser_process_manager = BrowserProcessManager(
        process_creator=_open_background_process_creator
    )
    browser._setup_user_dir()
    binary_location = browser.options.binary_location or browser._get_default_binary_location()
    browser._browser_process_manager.start_browser_process(
        binary_location, 0, browser.options.arguments
    )
    port = await asyncio.to_thread(_wait_for_devtools_port, profile_dir, CDP_PORT_WAIT_TIMEOUT_S)
    browser._connection_port = port
    browser._connection_handler = ConnectionHandler(port)
    owned_pids = pids_for_profile(profile_dir)
    watchdog_task = asyncio.create_task(_focus_steal_watchdog_by_pid(set(owned_pids), anchor_pid))
    logger.info("Launched Chrome on %s (port=%s, pids=%s)", profile_dir, port, owned_pids)
    return LaunchedBrowser(
        browser=browser, profile_dir=profile_dir, owned_pids=owned_pids, watchdog_task=watchdog_task
    )


async def new_tab(handle: LaunchedBrowser):
    return await handle.browser.new_tab()


async def kill_tab(handle: LaunchedBrowser, tab) -> None:
    target_id = getattr(tab, "_target_id", None)
    if target_id is None:
        return
    try:
        await asyncio.wait_for(
            handle.browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0
        )
    except Exception as e:
        logger.warning("kill_tab close_target failed (target_id=%s): %s", target_id, e)
    finally:
        handle.browser._tabs_opened.pop(target_id, None)


async def teardown(handle: LaunchedBrowser) -> None:
    if handle.watchdog_task is not None:
        handle.watchdog_task.cancel()
        try:
            await handle.watchdog_task
        except asyncio.CancelledError:
            pass
    try:
        await handle.browser.stop()
    except Exception as e:
        logger.warning("browser.stop() failed (falling through to pid kill): %s", e)
    if handle.owned_pids:
        _terminate_then_kill(handle.owned_pids, timeout_s=10.0)
    reap_profile(handle.profile_dir)


def reap_profile(profile_dir: str) -> None:
    pids = pids_for_profile(profile_dir)
    if not pids:
        return
    logger.info("Reaping Chrome on profile %s: pids=%s", profile_dir, pids)
    _terminate_then_kill(pids)


def _clear_stale_devtools_port(profile_dir: str) -> None:
    Path(profile_dir, "DevToolsActivePort").unlink(missing_ok=True)


def build_options(profile_dir: str) -> ChromiumOptions:
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-startup-window")
    options.block_popups = True
    options.block_notifications = True

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True

    for flag in BACKGROUNDING_FLAGS:
        options.add_argument(flag)

    options.browser_preferences = dict(BROWSER_PREFERENCES)

    return options


def _open_background_process_creator(command: list[str]) -> subprocess.Popen:
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", "Google Chrome", "--args", *args]
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_for_devtools_port(profile_dir: str, timeout_s: float) -> int:
    port_file = Path(profile_dir) / "DevToolsActivePort"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if port_file.exists():
            lines = port_file.read_text().splitlines()
            if lines and lines[0].strip().isdigit():
                return int(lines[0].strip())
        time.sleep(0.1)
    raise TimeoutError(f"DevToolsActivePort did not appear under {profile_dir} within {timeout_s}s")


async def _focus_steal_watchdog_by_pid(owned_pids: set[int], anchor_pid: int | None) -> None:
    last_other_pid = anchor_pid
    while True:
        current_pid = await asyncio.to_thread(_get_frontmost_pid)
        if current_pid in owned_pids:
            if last_other_pid is not None and last_other_pid not in owned_pids:
                await asyncio.to_thread(_activate_pid, last_other_pid)
        else:
            last_other_pid = current_pid
        await asyncio.sleep(FOCUS_STEAL_POLL_INTERVAL_S)


def _get_frontmost_pid() -> int | None:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get unix id of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    pid = result.stdout.strip()
    return int(pid) if pid.isdigit() else None


def pids_for_profile(profile_dir: str) -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={profile_dir}"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


def _terminate_then_kill(pids: list[int], timeout_s: float = 5.0) -> None:
    procs = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            procs.append(proc)
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout_s)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass


def _activate_pid(pid: int) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true',
        ],
        capture_output=True, text=True,
    )
