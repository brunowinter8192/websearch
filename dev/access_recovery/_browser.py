# INFRASTRUCTURE
import sys
from pathlib import Path

from pydoll.browser.options import ChromiumOptions

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dev._lib.browser_launch import launch_backgrounded_chrome, close_tab, teardown

SESSION_DIR = str(Path.home() / ".access_recovery" / "google-dom-probe-session")

_handle = None


# FUNCTIONS

def _build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.add_argument(f"--user-data-dir={SESSION_DIR}")
    options.block_popups = True
    options.block_notifications = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.webrtc_leak_protection = True
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    return options


async def new_tab():
    global _handle
    if _handle is None:
        _handle = await launch_backgrounded_chrome(SESSION_DIR, _build_options())
    return await _handle.browser.new_tab()


async def kill_tab(tab) -> None:
    if _handle is not None:
        await close_tab(_handle.browser, tab)


async def close_browser() -> None:
    global _handle
    if _handle is not None:
        await teardown(_handle)
        _handle = None
