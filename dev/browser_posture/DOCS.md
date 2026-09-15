# dev/browser_posture/

## Role
Milestone probes measuring headed-vs-headless browser posture for two lanes: pydoll-driven DOM search engines (`01`-`03`) and the patchright/crawl4ai ad-hoc chromium scrape lane (`04`-`05`). Touch this dir to add a new posture measurement; do not touch it for block/CAPTCHA-rate work — that lives in `process-docs/engine_expansion/`. Backs `process-docs/browser_posture/`.

## Public Interface
No `__init__.py` — not a package. `01_launch_latency_probe.py` through `05_cdp_headed_probe.py` are the five entry points, run directly via `./venv/bin/python`. `_lib.py` and the seven `_*.py` helper modules are area-local helpers, imported only via a bare `from _module import name` (relies on the script's own directory landing on `sys.path`).

## Flow
`01`-`03` (pydoll lane): `_lib.py` launches a headed/headless Chrome via CDP -> the probe measures latency/collision/fingerprint-patch behavior against a local page or a live detection-test site -> each script's own `write_report` emits `md/<script>_<ts>.md`.
`04`-`05` (crawl4ai/patchright lane): a real `BrowserConfig`/`AsyncWebCrawler` launch (`04`) or a macOS `open -g` self-launch + `cdp_url` connect (`05`) against a local throwaway page -> psutil/frontmost-app polling captures process identity and focus behavior -> each script's own `_*_report.write_report` emits `md/<script>_<ts>.md`.

## Modules

### _lib.py (307 LOC)

**Purpose:** Shared launch/teardown/measurement primitives for the pydoll-lane probes (`01`-`03`) — profile isolation, the `open -g` process creator, a throwaway local HTTP server, stats helpers, CDP injection, settle-poll.
**Reads:** nothing (pure infra; makes its own subprocess/CDP calls).
**Writes:** nothing directly — returns data to callers; spawns/kills Chrome processes as a side effect.
**Called by:** `01_launch_latency_probe.py`, `02_parallel_chrome_probe.py`, `03_fingerprint_patch_probe.py`.
**Calls out:** `pydoll` (`Chrome`, `ChromiumOptions`, `BrowserProcessManager`, `PageCommands`).

---

### 01_launch_latency_probe.py (300 LOC)

**Purpose:** Measures launch/navigation latency and background-timer-throttling drift across 4 headed/headless x backgrounding-flag configs.
**Reads:** nothing (self-contained; serves its own local HTTP target).
**Writes:** MD report to `md/01_launch_latency_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/01_launch_latency_probe.py`.
**Calls out:** `pydoll` (via `_lib`).

---

### 02_parallel_chrome_probe.py (221 LOC)

**Purpose:** Determines what happens when a headed-backgrounded launch targets the real production shared profile while a simulated already-running Chrome instance holds a separate profile.
**Reads:** nothing.
**Writes:** MD report to `md/02_parallel_chrome_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/02_parallel_chrome_probe.py`.
**Calls out:** `pydoll` (via `_lib`), `osascript`/`open`/`pgrep`/`pkill` (macOS process + focus control).

---

### 03_fingerprint_patch_probe.py (230 LOC)

**Purpose:** Per-block KEEP/DROP evidence for `src/search/browser.py`'s (since-removed) `JS_FINGERPRINT_PATCHES` under headed — 4 patch variants + 1 headless reference.
**Reads:** nothing (self-contained; serves its own local artifact page via `_lib`).
**Writes:** MD report via `_fingerprint_report.write_report` to `md/03_fingerprint_patch_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/03_fingerprint_patch_probe.py`.
**Calls out:** `pydoll` (via `_lib`); live HTTP to `bot.sannysoft.com` and `abrahamjuliot.github.io/creepjs`; `_fingerprint_report.py` (this directory).

---

### _fingerprint_report.py (257 LOC)

**Purpose:** Markdown report assembly for `03` — ActiveText verdict computation plus one section-builder helper per report section.
**Reads:** nothing — takes `03`'s result dicts as arguments.
**Writes:** `md/03_fingerprint_patch_probe_<ts>.md` (path built from the `report_dir` argument).
**Called by:** `03_fingerprint_patch_probe.py`.
**Calls out:** none.

---

### 04_headed_chromium_probe.py (172 LOC)

**Purpose:** Milestone 1 of the ad-hoc chromium lane's headed switch — binary identity, `LSUIElement` viability, and backgrounding-flag provenance through the real crawl4ai/patchright launch path.
**Reads:** nothing (self-contained; serves its own local throwaway HTTP page via `_lib`).
**Writes:** MD report via `_headed_chromium_report.write_report`. Progress to stderr. Mutates (and restores byte-exact) the chromium-1228 bundle's `Info.plist` during Run C only.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/04_headed_chromium_probe.py`.
**Calls out:** `crawl4ai`/`patchright` (real launch path, not `_lib`/pydoll), `psutil`; `_chromium_bundle.py`, `_chromium_teardown.py`, `_headed_chromium_report.py` (this directory).

---

### _chromium_bundle.py (60 LOC)

**Purpose:** Resolve `04`'s headed exe to its `.app` bundle and read/write/verify its `Info.plist` `LSUIElement` key and codesign status.
**Reads:** the chromium-1228 bundle's `Info.plist` and codesign metadata on disk.
**Writes:** `Info.plist`, when `set_lsuielement` is called by the caller.
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** none (stdlib `plistlib`, `subprocess`).

---

### _chromium_teardown.py (68 LOC)

**Purpose:** Multi-round Chrome-for-Testing process + launchd-supervision-job cleanup for `04`, against an observed launchd auto-relaunch race after a crash.
**Reads:** nothing — inspects live processes/launchd state itself.
**Writes:** nothing — kills processes and removes launchd jobs as a side effect.
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** `psutil`, `launchctl`/`pgrep` (macOS).

---

### _headed_chromium_report.py (211 LOC)

**Purpose:** Markdown report assembly for `04` — one section-builder helper per report section (executable resolution, backgrounding flags, `LSUIElement`, teardown).
**Reads:** nothing — takes `04`'s run dicts as arguments.
**Writes:** `md/04_headed_chromium_probe_<ts>.md` (path built from the `report_dir` argument).
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** `_lib.py` (`BACKGROUNDING_FLAGS`).

---

### 05_cdp_headed_probe.py (238 LOC)

**Purpose:** Milestone 1b — the `cdp_url` self-launch-then-connect route for the ad-hoc chromium lane after `04` killed `LSUIElement`, with a stage-labeled frontmost-app poll split route-under-test vs. `reference_launch`.
**Reads:** nothing (self-contained; serves its own local throwaway HTTP page via `_lib`).
**Writes:** MD report via `_cdp_report.write_report`. Progress to stderr. No plist edits.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/05_cdp_headed_probe.py`.
**Calls out:** `crawl4ai`/`patchright` (both the `connect_over_cdp` path and the direct-launch reference path), `psutil`; `_cdp_launch.py`, `_cdp_teardown.py`, `_cdp_report.py` (this directory).

---

### _cdp_launch.py (87 LOC)

**Purpose:** Bundle resolution, self-launch (`open -g -n -a`), `DevToolsActivePort` wait, and CDP-HTTP-readiness check for `05`'s self-launched Chrome.
**Reads:** the chromium-1228 bundle path on disk; the self-launched process's `DevToolsActivePort` file.
**Writes:** nothing directly — launches a Chrome process as a side effect.
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** none (stdlib `subprocess`, `urllib`).

---

### _cdp_teardown.py (51 LOC)

**Purpose:** Single-pass Chrome-by-profile kill plus a defensive ms-playwright/launchd sweep for `05`, on a route where no crash is expected.
**Reads:** nothing — inspects live processes/launchd state itself.
**Writes:** nothing — kills processes and removes launchd jobs as a side effect.
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** `psutil`, `pkill`/`launchctl`/`pgrep` (macOS).

---

### _cdp_report.py (183 LOC)

**Purpose:** Markdown report assembly for `05` — stage-focus breakdown, cmdline diff, and one section-builder helper per report section.
**Reads:** nothing — takes `05`'s run dicts and focus samples as arguments.
**Writes:** `md/05_cdp_headed_probe_<ts>.md` (path built from the `report_dir` argument).
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** none.

---

## State
No cross-call module state. Every probe script holds its own run state in local dicts/lists passed explicitly between its own functions; `_lib.py` and the seven split-out helper modules are pure functions over their arguments, with no shared mutable globals.
