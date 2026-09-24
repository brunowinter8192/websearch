# dev/_lib/

## Role
Dev-wide shared primitives usable from any area under `dev/`, unlike the area-scoped helpers in `dev/search_pipeline/_lib/` or `dev/browser_posture/`. Touch it when a dev-wide OS-interaction primitive is needed; area-specific helpers stay in that area.

## Public Interface
`__init__.py` is empty, package marker only. Importable from any script by putting the repo root on `sys.path` and importing from `dev._lib`.

## Flow
Caller builds its own Chromium options -> browser_launch starts the browser backgrounded and guards against focus steal -> caller works on tabs -> teardown stops the browser and removes the profile process.

## Modules

### browser_launch.py (144 LOC)

**Purpose:** Backgrounded launch of the resolved Chromium bundle, focus-steal reclaim watchdog, and teardown for any dev script.
**Reads:** nothing.
**Writes:** Returns a browser handle; spawns and kills Chrome processes and a watchdog task as side effects.
**Called by:** `dev/access_recovery/_browser.py`.
**Calls out:** `patchright`, `pydoll`, macOS process and focus tools.

---

## State
No module-level state. Each launch owns its own handle.
