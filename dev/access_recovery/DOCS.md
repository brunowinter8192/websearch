# dev/access_recovery/

## Role
Two independent probes for the access-recovery investigation into why production Google search fails: a real headed-browser DOM path and a browserless WML-endpoint path. The DOM probe splits browser, page, and report concerns into helper modules; the WML probe is one self-contained file.

## Public Interface
No `__init__.py` — not a package. The two numbered probes are the entry points, run directly via `./venv/bin/python3`. The underscore modules are helpers imported only by the DOM probe via bare imports from its own directory.

## Flow
DOM path: `queries.json` -> browser helper opens a tab -> DOM helper navigates, handles consent, classifies the landed page -> report helper writes markdown; raw HTML and diagnostics land under `html/`.
WML path: `queries.json` -> curl_cffi fetch -> lxml parse -> markdown report; raw bodies under `wml/`. The browser helper uses the shared launcher in `dev/_lib/`.

## Modules

### _browser.py (48 LOC)

**Purpose:** Chrome tab lifecycle for the DOM probe: launch options, tab open and close, teardown.
**Reads:** nothing.
**Writes:** Returns a pydoll tab; spawns and kills the backgrounded Chrome process.
**Called by:** `01_google_dom_probe.py`.
**Calls out:** `pydoll`.

---

### _dom.py (180 LOC)

**Purpose:** Google results-page interaction: consent handling, result wait and parse, block check, structural diagnostic pass.
**Reads:** nothing; executes JS on the tab passed by the caller.
**Writes:** Returns parsed and diagnostic data to the caller.
**Called by:** `01_google_dom_probe.py`.
**Calls out:** `pydoll`.

---

### _report.py (171 LOC)

**Purpose:** Markdown report assembly for the DOM probe.
**Reads:** nothing; takes records and paths as arguments.
**Writes:** `md/google_dom_probe_<ts>.md`.
**Called by:** `01_google_dom_probe.py`.
**Calls out:** none.

---

### 01_google_dom_probe.py (170 LOC)

**Purpose:** Path A entry point: two navigations per query through a real browser, classified into a four-state outcome model.
**Reads:** `queries.json`.
**Writes:** `md/google_dom_probe_<ts>.md`; raw HTML and diagnostic JSON under `html/`.
**Called by:** CLI only.
**Calls out:** none.

---

### 02_google_wml_probe.py (300 LOC)

**Purpose:** Path B entry point: browserless WML-route fetch per query, classified with the same outcome model.
**Reads:** `queries.json`.
**Writes:** `md/google_wml_probe_<ts>.md`; raw bodies under `wml/`.
**Called by:** CLI only.
**Calls out:** `curl_cffi`, `lxml`.

---

## State
The browser helper owns one module-level handle for the whole probe run. It is not shared with the other modules. Background: process-docs area access_recovery.
