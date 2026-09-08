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

# From death_pipe.py: net-2 crash backstop (per-call watchdog) — net-3 orphan reap reuses its
# terminate/kill primitive
from src import death_pipe

logger = logging.getLogger(__name__)

# Our own bounded DevToolsActivePort wait (R6: self-owned, deterministic — a real deadline-checked
# loop, not an unbounded event wait). Value proven in dev/browser_posture/05_cdp_headed_probe.py.
CDP_PORT_WAIT_TIMEOUT_S = 10.0
# Focus-steal watchdog poll interval — tight enough that any steal (self-launched Chrome is a
# regular, non-accessory app; LSUIElement crashes this bundle per dev/browser_posture/DOCS.md, so
# Camoufox's own accessory-app lever is unavailable here) is a sub-second flicker rather than a
# sustained foreground grab. Same 0.25s granularity this project's own focus-poll probes already use
# (dev/browser_posture/_lib.py's get_frontmost_app).
FOCUS_STEAL_POLL_INTERVAL_S = 0.25

# Outer wall-clock guard for the single cdp-headed acquisition path: 1.0 (bundle-path resolution via
# patchright's own BrowserType.executable_path property — measured ~0.15-0.25s x3 this session,
# margin added, not independently wait_for'd, same treatment as the project's original cold-start
# summand) + 10.0 (DevToolsActivePort wait, CDP_PORT_WAIT_TIMEOUT_S) + 15.5 (crawl4ai's own
# _verify_cdp_ready: 5x2s aiohttp.ClientTimeout + backoff sum
# 0.5*(1.4**0+1.4**1+1.4**2+1.4**3+1.4**4)=5.4728, source: crawl4ai/browser_manager.py) + 180.0
# (connect_over_cdp's own DEFAULT_PLAYWRIGHT_LAUNCH_TIMEOUT_IN_MILLISECONDS fallback — the SAME
# mechanism/constant that governed the old launch()-based path's cold start, still applies here:
# crawl4ai passes no explicit timeout to connect_over_cdp either, confirmed via patchright's
# _impl/_browser_type.py: "connectOverCDP", TimeoutSettings.launch_timeout, params) + 30.0 (nav,
# page_timeout) + 5.0 (render wait, delay_before_return_html) + 1.3 (consent handling) = 242.8. The
# DevToolsActivePort wait does NOT replace the 180s cold-start ceiling as first assumed — it's an
# addition in front of it, not a substitute. (Lowered from 245.8: the former +3.0 htmldate-extraction
# summand, HTMLDATE_TIMEOUT_S, was removed along with htmldate itself — see this module's own
# Gotchas/DOCS.md — since the declared-date fact now comes from crawl4ai's own already-parsed
# result.metadata, at zero extra acquisition time.)
TOTAL_SCRAPE_BUDGET_S = 242.8


# FUNCTIONS

# Walk up from a bundle-internal executable path to the .app root — same shape as
# camoufox_scrape.py's _find_app_bundle, duplicated per this project's own precedent of not sharing
# small acquisition-lane-specific mechanisms across independent, parallel lanes
def _find_app_bundle(executable_path: str) -> Path | None:
    for parent in Path(executable_path).parents:
        if parent.suffix == ".app":
            return parent
    return None


# Resolve patchright's OWN currently-installed chromium bundle path dynamically — NOT hardcoded to
# a revision number (e.g. "chromium-1228"), which would silently go stale on a patchright upgrade.
# crawl4ai's own get_chromium_path() is NOT usable here: it unconditionally resolves via plain
# playwright, not patchright (confirmed by reading crawl4ai/utils.py) — that would return
# Playwright's OWN separate chromium revision, the wrong bundle entirely (probe 04's finding).
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


# Self-launch flag surface: crawl4ai's OWN flag-construction for an externally-managed/CDP-connected
# browser (ManagedBrowser.build_browser_flags — a live call to the installed package, never pinned,
# so it can never drift out of sync with whatever crawl4ai version is running), plus --window-size
# to match ManagedBrowser's own assembly (_get_browser_args adds it separately, same source).
#
# Deliberately does NOT reach "full" parity with patchright's own RPC-launched headed cmdline
# (probe 05's 34-flag delta): those flags are constructed by patchright's internal Node driver
# specifically for a browserType.launch()/connectOverCDP RPC call — confirmed by reading
# ManagedBrowser.start() itself, which launches via a raw subprocess.Popen, the exact same class of
# mechanism our own `open -g` self-launch uses. No raw-subprocess launcher (crawl4ai's own
# ManagedBrowser included) can ever produce those flags; "full parity" with the RPC cmdline is not
# achievable by construction, not a maintenance gap to guard against.
#
# One deliberate 3-flag deviation from that same delta: build_browser_flags() gates
# --disable-gpu/--disable-gpu-compositing/--disable-software-rasterizer behind `if not
# config.enable_stealth` (its own comment: "Keep WebGL working via SwiftShader when stealth mode is
# active"); the OLDER direct-launch path's sibling function includes them unconditionally, ignoring
# enable_stealth (an existing inconsistency in installed crawl4ai 0.9.2). Kept as build_browser_flags
# produces it, i.e. GPU/WebGL stays ON — more consistent with enable_stealth=True's own intent than
# literal cmdline parity would be.
def _build_self_launch_flags(browser_config: BrowserConfig) -> list[str]:
    flags = list(ManagedBrowser.build_browser_flags(browser_config))
    if browser_config.viewport_width and browser_config.viewport_height:
        flags.append(f"--window-size={browser_config.viewport_width},{browser_config.viewport_height}")
    return flags


# Frontmost macOS application (process) name — same primitive as dev/browser_posture/_lib.py's
# get_frontmost_app, duplicated per this project's own precedent (chromium_scrape.py's own
# _find_app_bundle comment) of not sharing small lane-specific mechanisms across independent lanes
def _get_frontmost_app() -> str:
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


# Re-activate a named process via System Events — the same process-name namespace _get_frontmost_app reads from
def _activate_app(app_name: str) -> None:
    subprocess.run(
        [
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of process "{app_name}" to true',
        ],
        capture_output=True, text=True,
    )


# Background task for the whole acquisition span: the self-launched scrape Chrome is a regular,
# non-accessory app (LSUIElement crashes this bundle, dev/browser_posture/DOCS.md), so any window it
# creates can auto-activate it (playwright#42343, process-docs/browser_posture/) regardless of
# `open -g`, which only covers the initial launch moment. Whenever THIS app_name specifically (never
# the user's own separate "Google Chrome", never any other app) is frontmost, immediately re-activates
# whichever app was frontmost the moment before — tracked dynamically as the loop runs, never
# hardcoded — bounding any steal to one FOCUS_STEAL_POLL_INTERVAL_S flicker. Cancelled in
# _acquire_cdp_headed's `finally` (net 1); an in-process asyncio task dies with its own process, so
# unlike a separate watchdog subprocess it cannot outlive a crashed CLI and leave a poll loop behind.
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


# Launch the resolved chromium bundle headed-but-backgrounded via macOS `open -g -n -a` — the
# proven no-focus-steal mechanism (src/search/browser.py, dev/browser_posture/05_cdp_headed_probe.py)
# — targeting the .app PATH directly, never a bare name (deterministic, no Launch Services ambiguity)
def _self_launch_chrome(bundle_path: Path, user_data_dir: str, flags: list[str]) -> None:
    open_cmd = [
        "open", "-g", "-n", "-a", str(bundle_path), "--args",
        "--remote-debugging-port=0", f"--user-data-dir={user_data_dir}",
        "--no-startup-window", "--no-first-run", "--no-default-browser-check",
        *flags,
    ]
    subprocess.Popen(open_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Poll for Chromium's own DevToolsActivePort file (standard mechanism when --remote-debugging-port=0
# is used) and return the real assigned port — avoids a pre-probed-free-port TOCTOU race. Bounded by
# CDP_PORT_WAIT_TIMEOUT_S; the raised message matches a _BROWSER_LAUNCH_SIGNATURES entry so a
# missing/never-launching bundle is classified as browser_missing, same actionable fix as before.
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


# PIDs of processes whose cmdline names this exact profile dir — the shared identification
# primitive behind _kill_by_profile, the death_pipe watchdog spawn, and _reap_orphaned_scrapes
def _pids_on_profile(user_data_dir: str) -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", f"user-data-dir={user_data_dir}"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


# Kill the self-launched Chrome by profile-dir substring — the mandatory teardown path since
# `open -g`'s own Popen is a short-lived wrapper, never Chrome itself (src/search/browser.py's
# original kill_stale_chrome pattern; death_pipe._terminate_then_kill WAITS for actual process
# death via psutil rather than a fire-and-forget pkill: a plain pkill returns as soon as the signal
# is sent, not once Chrome actually exits, which raced against the caller's immediately-following
# shutil.rmtree and left a real, non-empty profile directory behind — confirmed live via a real
# cli.py scrape_url_chromium run.
def _kill_by_profile(user_data_dir: str) -> None:
    pids = _pids_on_profile(user_data_dir)
    if pids:
        death_pipe._terminate_then_kill(pids, timeout_s=3.0)


# Net 3 — pre-launch reap for the scrape lane, called at the start of every try_scrape. Parallel
# scrapes are legitimate (every call gets its own unique throwaway profile dir), so a live process
# is NEVER killed just for existing — only once its age exceeds TOTAL_SCRAPE_BUDGET_S, the SAME
# bound any legitimate scrape is itself bounded by (asyncio.wait_for in try_scrape); a still-running
# process past that age cannot be a legitimate in-flight scrape, only an orphan (net 1 and net 2 both
# failed for it — e.g. a pre-death_pipe-milestone leak). Directories are swept on a separate,
# stricter criterion: any scrape-url-cdp-* dir with NO live process at all, any age, is unambiguously
# orphaned regardless of the process-age threshold above.
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


# All PIDs currently on ANY scrape-url-cdp-* profile (broad prefix match, not one literal dir)
def _pids_matching_scrape_profiles() -> list[int]:
    result = subprocess.run(
        ["pgrep", "-f", "user-data-dir=.*scrape-url-cdp-"], capture_output=True, text=True
    )
    return [int(p) for p in result.stdout.split() if p.strip().isdigit()]


# The set of scrape-url-cdp-* profile dir paths that currently have at least one live process —
# read fresh (after any kill above) so a just-orphaned dir is correctly seen as sweepable this pass
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
