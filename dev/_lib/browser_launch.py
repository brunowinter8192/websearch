# INFRASTRUCTURE
import asyncio
import functools
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from patchright.async_api import async_playwright
from pydoll.browser import Chrome
from pydoll.browser.managers import BrowserProcessManager
from pydoll.commands import TargetCommands

logger = logging.getLogger(__name__)

FOCUS_STEAL_POLL_INTERVAL_S = 0.25


@dataclass
class BackgroundedBrowser:
    browser: Chrome
    profile: str
    owned_pids: list[int]
    watchdog_task: asyncio.Task | None
    executable_path: str


# FUNCTIONS

def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


async def resolve_chromium_executable_path() -> str:
    pw = await async_playwright().start()
    try:
        return pw.chromium.executable_path
    finally:
        await pw.stop()


def resolve_chromium_bundle(executable_path: str) -> Path:
    bundle = _find_app_bundle(executable_path)
    if bundle is None:
        raise RuntimeError(f"No .app bundle found above patchright's resolved executable: {executable_path}")
    return bundle


def _open_background_process_creator(bundle_path: Path, command: list[str]) -> subprocess.Popen:
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", str(bundle_path), "--args", *args]
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def kill_by_profile(profile: str) -> None:
    subprocess.run(["pkill", "-f", f"user-data-dir={profile}"], capture_output=True)


def _pids_for_profile(profile: str) -> list[int]:
    result = subprocess.run(["pgrep", "-f", f"user-data-dir={profile}"], capture_output=True, text=True)
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


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


def _activate_pid(pid: int) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true',
        ],
        capture_output=True, text=True,
    )


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


async def launch_backgrounded_chrome(profile: str, options) -> BackgroundedBrowser:
    kill_by_profile(profile)
    await asyncio.sleep(0.5)
    anchor_pid = await asyncio.to_thread(_get_frontmost_pid)
    executable_path = await resolve_chromium_executable_path()
    bundle_path = resolve_chromium_bundle(executable_path)
    options.binary_location = executable_path
    browser = Chrome(options)
    browser._browser_process_manager = BrowserProcessManager(
        process_creator=functools.partial(_open_background_process_creator, bundle_path)
    )
    await browser.start()
    owned_pids = _pids_for_profile(profile)
    watchdog_task = asyncio.create_task(_focus_steal_watchdog_by_pid(set(owned_pids), anchor_pid))
    return BackgroundedBrowser(
        browser=browser, profile=profile, owned_pids=owned_pids,
        watchdog_task=watchdog_task, executable_path=executable_path,
    )


async def close_tab(browser: Chrome, tab) -> None:
    target_id = getattr(tab, "_target_id", None)
    if target_id is None:
        return
    try:
        await asyncio.wait_for(browser._execute_command(TargetCommands.close_target(target_id)), timeout=5.0)
    except Exception as e:
        logger.warning("close_tab failed (target_id=%s): %s", target_id, e)
    finally:
        browser._tabs_opened.pop(target_id, None)


async def teardown(handle: BackgroundedBrowser) -> None:
    if handle.watchdog_task is not None:
        handle.watchdog_task.cancel()
        try:
            await handle.watchdog_task
        except asyncio.CancelledError:
            pass
    try:
        await handle.browser.stop()
    except Exception as e:
        logger.warning("browser.stop() failed (expected to fall through to pkill): %s", e)
    kill_by_profile(handle.profile)
