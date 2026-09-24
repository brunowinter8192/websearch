# dev/_lib/

## Role
Dev-wide shared primitives usable from any area under `dev/` — unlike `dev/search_pipeline/_lib/` or `dev/browser_posture/_lib.py`, which are area-scoped and only importable by scripts in their own directory. Reachable from any script regardless of its own directory via `sys.path.insert(0, str(REPO_ROOT))` + `from dev._lib.<module> import ...` (see `browser_launch.py`'s own callers for the exact pattern). Touch this when a dev-wide, not one-area, OS-interaction primitive is needed; area-specific helpers stay in that area's own `_lib`.

## Public Interface
`__init__.py` is empty, package marker only.

## Flow
Caller builds a `ChromiumOptions` (its own stealth/flag choices) -> `launch_backgrounded_chrome()` resolves patchright's Chromium bundle, launches it backgrounded via `open -g`, captures a pre-launch focus anchor, and spawns a PID-keyed focus-steal reclaim watchdog -> caller opens/closes tabs on the returned handle's browser -> `teardown()` cancels the watchdog, stops the browser via CDP, and `pkill`s the profile as a safety net.

## Modules

### browser_launch.py (144 LOC)

**Purpose:** Backgrounded launch of patchright's resolved Chromium bundle, PID-keyed focus-steal reclaim watchdog, and teardown, shared by any dev script — `open -g` alone only suppresses activation at the launch moment (playwright#42343); any window created afterward can still steal focus.
**Reads:** nothing (pure subprocess/CDP calls it makes itself).
**Writes:** nothing directly — returns a `BackgroundedBrowser` handle; spawns/kills Chrome processes and an asyncio watchdog task as a side effect.
**Called by:** `dev/access_recovery/_browser.py`.
**Calls out:** `patchright` (executable path resolution), `pydoll` (Chrome, BrowserProcessManager, TargetCommands), `osascript`/`open`/`pgrep`/`pkill` (macOS process + focus control).

---

## State
`BackgroundedBrowser` is a plain dataclass returned to the caller — no module-level state. Each `launch_backgrounded_chrome()` call owns its own handle; multiple concurrent handles in one process are possible but untested (no dev script does this today).
