# dev/browser_posture/

## Role
Milestone probes measuring headed-versus-headless browser posture for two lanes: pydoll-driven DOM search engines (probes 01 to 03) and the patchright/crawl4ai chromium scrape lane (probes 04 and 05). Touch it to add a posture measurement, not for block or CAPTCHA-rate work.

## Public Interface
No `__init__.py` — not a package. The five numbered probes are the entry points, run directly via `./venv/bin/python`. `_lib.py` and the underscore helpers are imported via bare imports from the script's own directory.

## Flow
Pydoll lane (01 to 03): shared launch helper starts Chrome -> probe measures latency, collision, or fingerprint-patch behaviour on a local page or live detection site -> report helper writes `md/`.
Crawl4ai lane (04, 05): real crawl4ai launch or self-launch plus CDP connect on a local throwaway page -> process and focus polling -> report helper writes `md/`.

## Modules

### _lib.py (252 LOC)

**Purpose:** Shared launch, teardown, and measurement primitives for the pydoll-lane probes.
**Reads:** nothing.
**Writes:** nothing directly; spawns and kills Chrome processes.
**Called by:** `01_launch_latency_probe.py`, `02_parallel_chrome_probe.py`, `03_fingerprint_patch_probe.py`, `04_headed_chromium_probe.py`, `05_cdp_headed_probe.py`, `_headed_chromium_report.py`.
**Calls out:** `pydoll`.

---

### 01_launch_latency_probe.py (257 LOC)

**Purpose:** Measures launch and navigation latency and timer-throttling drift across headed and headless flag configurations.
**Reads:** nothing; serves its own local target.
**Writes:** `md/01_launch_latency_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`.

---

### 02_parallel_chrome_probe.py (194 LOC)

**Purpose:** Determines what a backgrounded headed launch on the production shared profile does while another Chrome instance is running.
**Reads:** nothing.
**Writes:** `md/02_parallel_chrome_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, macOS process tools.

---

### 03_fingerprint_patch_probe.py (180 LOC)

**Purpose:** Per-block keep or drop evidence for the since-removed fingerprint patches under headed mode.
**Reads:** nothing; serves its own local page.
**Writes:** `md/03_fingerprint_patch_probe_<ts>.md` via the report helper.
**Called by:** CLI only.
**Calls out:** `pydoll`, live detection-test sites.

---

### _fingerprint_report.py (256 LOC)

**Purpose:** Markdown report assembly for probe 03, including its verdict computation.
**Reads:** nothing; takes result dicts.
**Writes:** `md/03_fingerprint_patch_probe_<ts>.md`.
**Called by:** `03_fingerprint_patch_probe.py`.
**Calls out:** none.

---

### 04_headed_chromium_probe.py (146 LOC)

**Purpose:** Measures binary identity, LSUIElement viability, and backgrounding-flag provenance through the real crawl4ai/patchright launch path.
**Reads:** nothing; serves its own local page.
**Writes:** Markdown report via the report helper; edits and restores the chromium bundle's plist during one run.
**Called by:** CLI only.
**Calls out:** `crawl4ai`, `patchright`, `psutil`.

---

### _chromium_bundle.py (49 LOC)

**Purpose:** Resolves the headed executable to its app bundle and reads, writes, and verifies plist and codesign state.
**Reads:** The chromium bundle's plist and codesign metadata.
**Writes:** The plist, when the caller sets the key.
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** none.

---

### _chromium_teardown.py (49 LOC)

**Purpose:** Multi-round Chrome process and launchd-job cleanup for probe 04 against an observed auto-relaunch race.
**Reads:** nothing; inspects live processes.
**Writes:** nothing; kills processes and removes launchd jobs.
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** `psutil`, macOS process tools.

---

### _headed_chromium_report.py (201 LOC)

**Purpose:** Markdown report assembly for probe 04, one section per finding area.
**Reads:** nothing; takes run dicts.
**Writes:** `md/04_headed_chromium_probe_<ts>.md`.
**Called by:** `04_headed_chromium_probe.py`.
**Calls out:** none.

---

### 05_cdp_headed_probe.py (201 LOC)

**Purpose:** Measures the self-launch-then-connect route for the chromium lane with a stage-labelled frontmost-app poll.
**Reads:** nothing; serves its own local page.
**Writes:** Markdown report via the report helper; no plist edits.
**Called by:** CLI only.
**Calls out:** `crawl4ai`, `patchright`, `psutil`.

---

### _cdp_launch.py (68 LOC)

**Purpose:** Bundle resolution, self-launch, DevTools port wait, and CDP readiness check for probe 05.
**Reads:** The chromium bundle path and the launched process's DevTools port file.
**Writes:** nothing directly; launches a Chrome process.
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** none.

---

### _cdp_teardown.py (44 LOC)

**Purpose:** Single-pass Chrome kill by profile plus a defensive launchd sweep for probe 05.
**Reads:** nothing; inspects live processes.
**Writes:** nothing; kills processes and removes launchd jobs.
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** `psutil`, macOS process tools.

---

### _cdp_report.py (172 LOC)

**Purpose:** Markdown report assembly for probe 05: stage-focus breakdown, command-line diff, and section builders.
**Reads:** nothing; takes run dicts and focus samples.
**Writes:** `md/05_cdp_headed_probe_<ts>.md`.
**Called by:** `05_cdp_headed_probe.py`.
**Calls out:** none.

---

## State
No cross-call module state. Each probe keeps its own run state in local structures; the helpers are pure over their arguments.
