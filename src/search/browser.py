# INFRASTRUCTURE
import asyncio
import functools
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from patchright.async_api import async_playwright
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.managers import BrowserProcessManager
from pydoll.commands import TargetCommands
from pydoll.connection import ConnectionHandler

from src.search import browser_lock
from src import death_pipe
from src.config import CDP_PORT_WAIT_TIMEOUT_S, FOCUS_STEAL_POLL_INTERVAL_S

logger = logging.getLogger(__name__)

SESSION_DIR_PREFIX = "websearch-browser-session-"
LOCK_PATH = Path.home() / ".websearch" / "browser-session.lock"

LOCK_HARD_BUDGET_S = 60.0 + 6.0 + 15.0

BACKGROUNDING_FLAGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

_browser = None
_init_lock = asyncio.Lock()
_lock_handle: browser_lock.LockHandle | None = None
_owned_pids: list[int] = []
_session_dir: str | None = None
_focus_watchdog_task: asyncio.Task | None = None
_osascript_warned: set[str] = set()


# FUNCTIONS

async def new_tab():
    await get_tab()
    tab = await _browser.new_tab()
    return tab


async def get_tab():
    global _browser, _lock_handle, _session_dir
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
                _session_dir = tempfile.mkdtemp(prefix=SESSION_DIR_PREFIX)
                anchor_pid = _get_frontmost_pid()
                options = build_options(_session_dir)
                _browser = Chrome(options)
                _browser._browser_process_manager = BrowserProcessManager(
                    process_creator=functools.partial(_open_background_process_creator, bundle_path)
                )
                _browser._setup_user_dir()
                binary_location = _browser.options.binary_location or _browser._get_default_binary_location()
                _browser._browser_process_manager.start_browser_process(
                    binary_location, 0, _browser.options.arguments
                )
                port = await asyncio.to_thread(_wait_for_devtools_port, _session_dir, CDP_PORT_WAIT_TIMEOUT_S)
                _browser._connection_port = port
                _browser._connection_handler = ConnectionHandler(port)
                _record_own_pids(_session_dir)
                death_pipe.spawn_watchdog(_owned_pids, cleanup_dir=_session_dir)
                _spawn_focus_watchdog(_owned_pids, anchor_pid)
            except Exception:
                _browser = None
                if _session_dir is not None:
                    shutil.rmtree(_session_dir, ignore_errors=True)
                    _session_dir = None
                _lock_handle.release()
                _lock_handle = None
                raise


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


def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


def _reap_session_profile() -> None:
    pids = _pids_matching_session_profiles()
    if pids:
        logger.info("Reaping orphaned Chrome on session profiles: pids=%s", pids)
        death_pipe.terminate_then_kill(pids)
    _remove_orphaned_session_dirs()


def _pids_matching_session_profiles() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir=.*{SESSION_DIR_PREFIX}"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


def _remove_orphaned_session_dirs() -> None:
    for entry in Path(tempfile.gettempdir()).glob(f"{SESSION_DIR_PREFIX}*"):
        shutil.rmtree(entry, ignore_errors=True)


def _get_frontmost_pid() -> int | None:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get unix id of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    pid = result.stdout.strip()
    if result.returncode != 0 or not pid.isdigit():
        _warn_osascript_once("get_frontmost", f"returncode={result.returncode} stdout={pid!r} stderr={result.stderr.strip()!r}")
    return int(pid) if pid.isdigit() else None


def _warn_osascript_once(what: str, detail: str) -> None:
    if what in _osascript_warned:
        return
    _osascript_warned.add(what)
    logger.warning("osascript %s failed (focus-steal reclaim ineffective): %s", what, detail)


def build_options(session_dir: str) -> ChromiumOptions:
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={session_dir}")
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


def _open_background_process_creator(bundle_path: Path, command: list[str]) -> subprocess.Popen:
    args = command[1:]
    open_cmd = ["open", "-g", "-n", "-a", str(bundle_path), "--args", *args]
    return subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def _record_own_pids(session_dir: str) -> None:
    global _owned_pids
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={session_dir}"], capture_output=True, text=True
    )
    _owned_pids = [int(p) for p in result.stdout.split() if p.strip().isdigit()]
    logger.info("Own Chrome pids: %s", _owned_pids)


def _spawn_focus_watchdog(pids: list[int], anchor_pid: int | None) -> None:
    global _focus_watchdog_task
    _focus_watchdog_task = asyncio.create_task(_focus_steal_watchdog_by_pid(set(pids), anchor_pid))


async def _focus_steal_watchdog_by_pid(owned_pids: set[int], last_other_pid: int | None) -> None:
    while True:
        current_pid = await asyncio.to_thread(_get_frontmost_pid)
        if current_pid in owned_pids:
            if last_other_pid is not None and last_other_pid not in owned_pids:
                await asyncio.to_thread(_activate_pid, last_other_pid)
        else:
            last_other_pid = current_pid
        await asyncio.sleep(FOCUS_STEAL_POLL_INTERVAL_S)


def _activate_pid(pid: int) -> None:
    result = subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of (first process whose unix id is {pid}) to true',
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _warn_osascript_once("activate", f"returncode={result.returncode} stderr={result.stderr.strip()!r}")


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


def kill_own_chrome_atexit() -> None:
    asyncio.run(kill_own_chrome())


async def kill_own_chrome() -> None:
    global _browser, _owned_pids, _lock_handle, _session_dir
    if _browser is not None:
        try:
            await close_browser()
        except Exception as e:
            logger.warning("close_browser failed (Chrome likely already dead): %s", e)
            _browser = None
    if _owned_pids:
        logger.info("Killing own Chrome (safety net): pids=%s", _owned_pids)
        death_pipe.terminate_then_kill(_owned_pids, timeout_s=10.0)
        _owned_pids = []
    if _session_dir is not None:
        shutil.rmtree(_session_dir, ignore_errors=True)
        _session_dir = None
    if _lock_handle is not None:
        _lock_handle.release()
        _lock_handle = None


async def close_browser():
    global _browser
    await _cancel_focus_watchdog()
    if _browser is not None:
        await _browser.stop()
        _browser = None


async def _cancel_focus_watchdog() -> None:
    global _focus_watchdog_task
    if _focus_watchdog_task is not None:
        _focus_watchdog_task.cancel()
        try:
            await _focus_watchdog_task
        except asyncio.CancelledError:
            pass
        _focus_watchdog_task = None
