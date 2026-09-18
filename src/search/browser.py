# INFRASTRUCTURE
import asyncio
import functools
import logging
import subprocess
import time
from pathlib import Path

import psutil
from patchright.async_api import async_playwright
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.managers import BrowserProcessManager
from pydoll.commands import TargetCommands
from pydoll.connection import ConnectionHandler

from src.search import browser_lock
from src import death_pipe

logger = logging.getLogger(__name__)

SESSION_DIR = str(Path.home() / ".websearch" / "browser-session-selflaunch")
LOCK_PATH = Path(SESSION_DIR).parent / f"{Path(SESSION_DIR).name}.lock"

LOCK_HARD_BUDGET_S = 60.0 + 6.0 + 15.0

FOCUS_STEAL_POLL_INTERVAL_S = 0.25
CDP_PORT_WAIT_TIMEOUT_S = 10.0

BACKGROUNDING_FLAGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

_browser = None
_init_lock = asyncio.Lock()
_lock_handle: browser_lock.LockHandle | None = None
_owned_pids: list[int] = []
_focus_watchdog_task: asyncio.Task | None = None


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


def _open_background_process_creator(bundle_path: Path, command: list[str]) -> subprocess.Popen:
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", str(bundle_path), "--args", *args]
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.add_argument("--no-startup-window")
    options.block_popups = True
    options.block_notifications = True

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True

    for flag in BACKGROUNDING_FLAGS:
        options.add_argument(flag)

    options.browser_preferences = {
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

    return options


def _reap_session_profile() -> None:
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True, text=True
    )
    pids = [int(p) for p in result.stdout.split() if p.strip().isdigit()]
    if not pids:
        return
    logger.info("Reaping orphaned Chrome on session profile: pids=%s", pids)
    _terminate_then_kill(pids)


def _record_own_pids() -> None:
    global _owned_pids
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={SESSION_DIR}"], capture_output=True, text=True
    )
    _owned_pids = [int(p) for p in result.stdout.split() if p.strip().isdigit()]
    logger.info("Own Chrome pids: %s", _owned_pids)


def _clear_stale_devtools_port() -> None:
    Path(SESSION_DIR, "DevToolsActivePort").unlink(missing_ok=True)


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


def _terminate_then_kill(pids: list[int], timeout_s: float = 5.0) -> None:
    procs = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            procs.append(proc)
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=timeout_s)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass


async def get_tab():
    global _browser, _lock_handle
    async with _init_lock:
        if _browser is None:
            bundle_path = await _resolve_chromium_bundle_path()
            logger.info("Acquiring cross-process browser-session lock")
            _lock_handle = await asyncio.to_thread(
                browser_lock.acquire, LOCK_PATH, LOCK_HARD_BUDGET_S, _reap_session_profile
            )
            try:
                logger.info("Starting Chrome session")
                _reap_session_profile()
                _clear_stale_devtools_port()
                anchor_pid = _get_frontmost_pid()
                options = build_options()
                _browser = Chrome(options)
                _browser._browser_process_manager = BrowserProcessManager(
                    process_creator=functools.partial(_open_background_process_creator, bundle_path)
                )
                _browser._setup_user_dir()
                binary_location = _browser.options.binary_location or _browser._get_default_binary_location()
                _browser._browser_process_manager.start_browser_process(
                    binary_location, 0, _browser.options.arguments
                )
                port = await asyncio.to_thread(_wait_for_devtools_port, SESSION_DIR, CDP_PORT_WAIT_TIMEOUT_S)
                _browser._connection_port = port
                _browser._connection_handler = ConnectionHandler(port)
                _record_own_pids()
                death_pipe.spawn_watchdog(_owned_pids)
                _spawn_focus_watchdog(_owned_pids, anchor_pid)
            except Exception:
                _browser = None
                _lock_handle.release()
                _lock_handle = None
                raise


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


async def _focus_steal_watchdog_by_pid(owned_pids: set[int], last_other_pid: int | None) -> None:
    while True:
        current_pid = await asyncio.to_thread(_get_frontmost_pid)
        if current_pid in owned_pids:
            if last_other_pid is not None and last_other_pid not in owned_pids:
                await asyncio.to_thread(_activate_pid, last_other_pid)
        else:
            last_other_pid = current_pid
        await asyncio.sleep(FOCUS_STEAL_POLL_INTERVAL_S)


def _spawn_focus_watchdog(pids: list[int], anchor_pid: int | None) -> None:
    global _focus_watchdog_task
    _focus_watchdog_task = asyncio.create_task(_focus_steal_watchdog_by_pid(set(pids), anchor_pid))


async def _cancel_focus_watchdog() -> None:
    global _focus_watchdog_task
    if _focus_watchdog_task is not None:
        _focus_watchdog_task.cancel()
        try:
            await _focus_watchdog_task
        except asyncio.CancelledError:
            pass
        _focus_watchdog_task = None


async def new_tab():
    await get_tab()
    tab = await _browser.new_tab()
    return tab


async def kill_tab(tab) -> None:
    global _browser
    target_id = getattr(tab, '_target_id', None)
    if _browser is None or target_id is None:
        return
    try:
        await asyncio.wait_for(
            _browser._execute_command(TargetCommands.close_target(target_id)),
            timeout=5.0,
        )
    except Exception as e:
        logger.warning("kill_tab close_target failed (target_id=%s): %s", target_id, e)
    finally:
        if _browser is not None:
            _browser._tabs_opened.pop(target_id, None)


async def close_browser():
    global _browser
    await _cancel_focus_watchdog()
    if _browser is not None:
        await _browser.stop()
        _browser = None


async def kill_own_chrome() -> None:
    global _browser, _owned_pids, _lock_handle
    if _browser is not None:
        try:
            await close_browser()
        except Exception as e:
            logger.warning("close_browser failed (Chrome likely already dead): %s", e)
            _browser = None
    if _owned_pids:
        logger.info("Killing own Chrome (safety net): pids=%s", _owned_pids)
        _terminate_then_kill(_owned_pids, timeout_s=10.0)
        _owned_pids = []
    if _lock_handle is not None:
        _lock_handle.release()
        _lock_handle = None


def kill_own_chrome_atexit() -> None:
    asyncio.run(kill_own_chrome())
