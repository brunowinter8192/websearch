# dev/browser_posture/

## Role
Milestone probes backing headed-vs-headless browser posture decisions across BOTH browser lanes in
this project: the pydoll-driven DOM search engines (`src/search/browser.py`) and the patchright/
crawl4ai-driven ad-hoc chromium scrape lane (`src/scraper/chromium_scrape.py`'s `try_scrape`). `01`-`03`
+ `_lib.py` cover the pydoll lane: launch/navigation latency and the Playwright-default
backgrounding-flag effect, the everyday parallel-user-Chrome collision case, and whether
`src/search/browser.py`'s JS fingerprint patches (written for headless) still make sense under
headed. `04` covers the patchright lane: executable resolution (headless-shell vs full Chrome),
`LSUIElement` no-focus-steal viability, and backgrounding-flag presence, through the real
crawl4ai/patchright launch path — a DIFFERENT stack from `01`-`03` (no `_lib.py`/pydoll dependency).
`05` is the follow-up after `04` killed the `LSUIElement` lever: the `cdp_url` route (self-launch
Chrome via `open -g -n -a` + `--remote-debugging-port`, then crawl4ai/patchright CONNECTS instead
of launching) — focus behavior across the whole sequence, the working `BrowserConfig` shape, and
the cmdline delta vs. a patchright-direct launch (the anti-detection surface this route would make
us own). Does NOT measure block/CAPTCHA rates — see `process-docs/engine_expansion/` for why that axis was
rejected as a same-IP same-day confound. Backs `process-docs/browser_posture/`.

## Modules

### _lib.py (307 LOC)

**Purpose:** Shared launch/teardown/measurement primitives for THIS area's probe scripts (`01`-`03`) — profile isolation, the proven `open -g` process_creator, a throwaway local HTTP server, stats helpers, CDP injection, settle-poll. No focus-steal reclaim watchdog — see Gotchas.
**Reads:** nothing (pure infra + subprocess/CDP calls it makes itself).
**Writes:** nothing directly — returns data to callers; spawns/kills Chrome processes as a side effect.
**Called by:** `01_launch_latency_probe.py`, `02_parallel_chrome_probe.py`, `03_fingerprint_patch_probe.py`.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager, PageCommands).

---

### 01_launch_latency_probe.py (270 LOC)

**Purpose:** Measures 4 configs (headless-direct / headed-backgrounded-no-flags / headed-backgrounded
+3-flags / headless+3-flags control) x N=5 for start-to-drivable-tab + one-navigation latency, and
x N=3 for background-timer-throttling drift (setInterval(100ms) actual-vs-expected over a local page).
**Reads:** nothing (self-contained; serves its own local HTTP target).
**Writes:** MD report to `md/01_launch_latency_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/01_launch_latency_probe.py`.
**Calls out:** `pydoll` (via `_lib`).

---

### 02_parallel_chrome_probe.py (202 LOC)

**Purpose:** Determines what happens when a headed-backgrounded launch (`open -g -n -a "Google
Chrome"`) targets the REAL production shared profile (`src/search/browser.py` SESSION_DIR) while a
Chrome instance is already running — the everyday "user already has Chrome open" case. Simulates
the already-running Chrome via a throwaway profile (never touches the user's real default profile).
**Reads:** nothing.
**Writes:** MD report to `md/02_parallel_chrome_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/02_parallel_chrome_probe.py`.
**Calls out:** `pydoll` (via `_lib`), `osascript`/`open`/`pgrep`/`pkill` (macOS process + focus control).

---

### 03_fingerprint_patch_probe.py (439 LOC)

**Purpose:** Per-block KEEP/DROP evidence for `src/search/browser.py`'s (since-removed) `JS_FINGERPRINT_PATCHES` under headed — 4 patch variants + 1 headless reference against the local artifact page, real screen properties, sannysoft, and CreepJS.
**Reads:** nothing (self-contained; serves its own local artifact page via `_lib`).
**Writes:** MD report to `md/03_fingerprint_patch_probe_<ts>.md`. Progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/03_fingerprint_patch_probe.py`.
**Calls out:** `pydoll` (via `_lib`); live HTTP to `bot.sannysoft.com` and
`abrahamjuliot.github.io/creepjs` — these are detection test pages, the intended target of this probe,
not production engines.

---

### 04_headed_chromium_probe.py (449 LOC)

**Purpose:** Milestone 1 of the ad-hoc chromium lane's headed switch — binary identity under headless True/False (psutil on the real process), `LSUIElement` viability on the chromium-1228 bundle, and backgrounding-flag provenance on the real cmdline.
**Reads:** nothing (self-contained; serves its own local throwaway HTTP page via `_lib`).
**Writes:** MD report to `md/04_headed_chromium_probe_<ts>.md`. Progress to stderr. Mutates (and
restores byte-exact) the chromium-1228 bundle's `Info.plist` during Run C only.
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/04_headed_chromium_probe.py`.
**Calls out:** `crawl4ai`/`patchright` (real launch path, not `_lib`/pydoll), `psutil` (process
introspection), `codesign`/`launchctl`/`pgrep` (macOS signature + process/launchd supervision checks).

---

### 05_cdp_headed_probe.py (497 LOC)

**Purpose:** Milestone 1b — the `cdp_url` route for the ad-hoc chromium lane after `04` killed `LSUIElement`: self-launch the chromium-1228 bundle backgrounded, connect crawl4ai over CDP, run a real `arun()`, with a stage-labeled frontmost-app poll split route-under-test vs. reference_launch.
**Reads:** nothing (self-contained; serves its own local throwaway HTTP page via `_lib`).
**Writes:** MD report to `md/05_cdp_headed_probe_<ts>.md`. Progress to stderr. No plist edits
anywhere (unlike `04`).
**Called by:** CLI only. Run: `./venv/bin/python dev/browser_posture/05_cdp_headed_probe.py`.
**Calls out:** `crawl4ai`/`patchright` (both the `connect_over_cdp` path and, for the reference
launch, the direct launch path), `psutil`, `open`/`pgrep`/`pkill`/`launchctl` (macOS process +
launchd checks).

---

## Gotchas

- None of `_lib.py`'s `open -g`-based launches (`open_background_process_creator`,
  `spawn_plain_chrome`) run a focus-steal reclaim watchdog — `open -g` only suppresses activation at
  the launch moment (playwright#42343), so a window from any of these can still steal focus later in
  the probe run. This went unnoticed here because these probes are short/self-contained; it caused a
  real, repeated focus-steal in `dev/access_recovery/01_google_dom_probe.py` (a longer-running,
  multi-navigation probe using the same pattern), which is why `dev/_lib/browser_launch.py` (own
  DOCS.md, dev-wide, not area-scoped) exists. Any NEW dev script that needs a headed-backgrounded
  Chrome for more than a one-shot launch should use that helper, not `_lib.py`'s launch functions —
  see `process-docs/browser_posture/` for the failure this addressed.
- Both scripts open real, visible Chrome windows on macOS (headed configs) — not safe to run on a
  headless CI runner; developed and verified interactively on the target Mac.
- `01`'s timer-drift measurement could NOT confirm real window occlusion in this environment
  (`document.visibilityState` stayed `visible` even with a same-geometry, `-g`-backgrounded coverer
  window on top) — the machine runs multiple concurrent real login sessions, so window-stacking
  assumptions don't hold. The drift numbers in the report are labeled "occlusion unconfirmed"; do not read a "no
  drift" result as proof the three flags make no difference under genuine occlusion.
- Full-screen `screencapture` was used once during development to debug the occlusion gap above and
  incidentally captured live, unrelated session content on this shared machine — deleted immediately,
  not part of either script. Do not add screenshot-based verification to these scripts without a
  window-specific (not full-screen) capture target.
- All probe profile dirs live under `~/.websearch/browser-posture-probe/` — isolated from
  `src/search/browser.py`'s shared `SESSION_DIR`, EXCEPT `02_parallel_chrome_probe.py`, which
  deliberately targets the real `SESSION_DIR` (that's the scenario under test).
- `03`'s CreepJS extraction does NOT look for "Trust Score"/"N lies" text — the live build (checked
  directly, not assumed from memory of another version) renders no such summary at all; every
  "trust"/"lie" substring in the page is a false positive (e.g. "CLIENT" contains "lie"). The real
  signal extracted is the "Headless" section's three percentages plus "confidence: &lt;level&gt;"
  notes. Re-verify this against the live page before reusing the extraction if CreepJS's UI changes.
- `03`'s getComputedStyle artifact test is `color: ActiveText` on a dedicated element, NOT a resting
  `<a>` — a plain link computes to the ordinary link color in every mode and never exercises what the
  patch targets (CSS ActiveText, the link's ACTIVE-state system color).
- `04` writes to the REAL, machine-shared chromium-1228 install under `~/Library/Caches/ms-playwright/`
  (not an isolated probe profile dir like `01`-`03`) — the `Info.plist` mutation is real, on the
  actual bundle patchright resolves in production. Hard-verifies the resolved bundle path contains
  `chromium-1228` before writing (refuses otherwise) — chromium-1223 (Playwright's own, separate
  revision) must never be touched.
- `04`'s plist revert is a byte-exact restore from a raw-bytes backup, NOT a `plistlib` round-trip —
  `plistlib.dump()` defaults to XML and silently converts a binary (`bplist00`) plist to XML even on
  a content-correct revert (caught during this probe's own development).
- `04` found that `LSUIElement=true` reliably CRASHES this bundle's launch (`icudtl.dat not found in
  bundle`, SIGTRAP) — differs from the Camoufox precedent (`process-docs/camoufox_lane/`), where the
  same mechanism worked. Isolated from plist format (XML-format-no-key launches fine); the crash
  tracks the `LSUIElement` key specifically.
- Deliberately triggering that crash makes macOS itself register a launchd per-app supervision job
  (`application.com.google.chrome.for.testing.<ids>`, visible via `launchctl list`) that auto-relaunches
  the full browser 10-20s later — independent of this script's own process-tree teardown, and NOT
  reliably bounded by any in-script sleep. `kill_survivors()` removes the launchd job every sweep
  round in addition to killing processes, but is not proven sufficient alone — verify manually
  (`pgrep -fl "ms-playwright/chromium"` + `launchctl list | grep chrome.for.testing`) ~20s after this
  script exits before trusting its own "0 orphans" line. One-shot-per-crash, not a repeating loop.
- `05`'s first draft called `wait_for_devtools_port`/`kill_by_profile`/`kill_survivors`/
  `self_launch_chrome` as plain synchronous functions from the async orchestrator instead of via
  `asyncio.to_thread` — their blocking `time.sleep`/`subprocess.run` calls starved the concurrently-
  running focus-poll task's event loop turns, silently producing 0 samples for the `cdp_port_wait`
  and `teardown` stages (looked like "these stages are just fast," was actually an instrumentation
  bug). Fixed by wrapping all of them in `asyncio.to_thread`; re-run confirmed real samples appear.
- `05`'s focus-poll headline number MUST exclude the `reference_launch` stage (an internal, direct,
  un-backgrounded patchright launch used only to capture a cmdline baseline for the args-delta, not
  part of the `cdp_url` route under test) — a first draft aggregated all stages into one percentage,
  which read as "the route steals focus ~50% of the time" when the actual route was 0% and the
  reference step (expected to steal focus, not a defect) was the entire cause. Report splits "route"
  vs. "reference" explicitly; do not re-merge them.
