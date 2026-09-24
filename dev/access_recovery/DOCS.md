# dev/access_recovery/

## Role
Two independent probes for the access-recovery investigation into why production Google search fails: a real headed-browser DOM path (`01`) and a browserless WML-endpoint path (`02`). `01`'s browser/page/report concerns are split across `_browser.py`/`_dom.py`/`_report.py`; `02` stays self-contained in one file.

## Public Interface
No `__init__.py` — not a package. `01_google_dom_probe.py` and `02_google_wml_probe.py` are the two entry points, run directly via `./venv/bin/python3`. `_browser.py`, `_dom.py`, `_report.py` are area-local helpers, imported only by `01` via a bare `from _module import name` (relies on the script's own directory being on `sys.path`).

## Flow
`01`: `queries.json` -> `_browser` opens a tab -> `_dom` navigates/handles consent/classifies the landed page -> `_report` writes the run's `.md`; raw HTML + diagnostic JSON land under `html/`.
`02`: `queries.json` -> `curl_cffi` WML fetch -> `lxml` parse against SearXNG's own selectors -> `write_report`'s `.md`; raw response bodies land under `wml/`.

## Modules

### _browser.py (48 LOC)

**Purpose:** Chrome tab lifecycle for the DOM probe — launch options, tab open/close, teardown, via `dev/_lib/browser_launch.py`.
**Reads:** nothing (pure subprocess/CDP calls it makes itself, through `dev._lib.browser_launch`).
**Writes:** nothing directly — returns a pydoll tab; spawns/kills the backgrounded Chrome process as a side effect.
**Called by:** `01_google_dom_probe.py`.
**Calls out:** `pydoll` (`ChromiumOptions`), `dev._lib.browser_launch` (`launch_backgrounded_chrome`, `close_tab`, `teardown`).

---

### _dom.py (178 LOC)

**Purpose:** Google results-page interaction — consent detection/handling, result wait/parse, the /sorry/ block check, and the structural diagnostic JS pass.
**Reads:** nothing — executes JS against the `tab` object passed by the caller.
**Writes:** nothing — returns parsed/diagnostic dicts and lists to the caller.
**Called by:** `01_google_dom_probe.py`.
**Calls out:** `pydoll` (`NetworkCommands`, `CookieSameSite`).

---

### _report.py (171 LOC)

**Purpose:** Markdown report assembly for the DOM probe — outcome counting plus one section-builder helper per report section.
**Reads:** nothing — takes the run's records and paths as arguments.
**Writes:** `md/google_dom_probe_<ts>.md` (path built from the `report_dir` argument).
**Called by:** `01_google_dom_probe.py`.
**Calls out:** none (stdlib `pathlib` only).

---

### 01_google_dom_probe.py (148 LOC)

**Purpose:** Path A probe entry point — two navigations per query (num=100, num=10) through a real browser, classified into OK/EMPTY_PARSED/NO_CONTAINERS/BLOCKED/ERROR.
**Reads:** `queries.json`.
**Writes:** `md/google_dom_probe_<ts>.md` (via `_report`), raw HTML + diagnostic JSON under `html/google_dom_probe_<ts>/`.
**Called by:** CLI only. `./venv/bin/python3 dev/access_recovery/01_google_dom_probe.py`.
**Calls out:** `_browser.py`, `_dom.py`, `_report.py` (this directory).

---

### 02_google_wml_probe.py (286 LOC)

**Purpose:** Path B probe entry point — browserless WML-route fetch (Nokia UA + curl_cffi `chrome99_android` impersonation) per query, classified into the same four-state outcome model.
**Reads:** `queries.json`.
**Writes:** `md/google_wml_probe_<ts>.md`, raw response bodies under `wml/google_wml_probe_<ts>/`.
**Called by:** CLI only. `./venv/bin/python3 dev/access_recovery/02_google_wml_probe.py`.
**Calls out:** `curl_cffi`, `lxml`.

---

## State
`_browser.py` owns a single module-level `_handle` (a `BackgroundedBrowser` from `dev._lib.browser_launch`) for the whole probe run — set by `new_tab()` on first call, read by `kill_tab()`, cleared by `close_browser()`. Not shared with `_dom.py`, `_report.py`, or `02_google_wml_probe.py`.

## Gotchas
- `_dom.py`'s parse JS is a frozen copy of `src/search/engines/google.py`'s selectors from 2026-09-15 (`a[href^="http"]`). Google's organic hrefs are same-origin `/goto?url=` redirectors, so `01` classifies pages with results as EMPTY_PARSED by construction; the diagnostic evidence, not the outcome label, is what the probe still yields. Background: `process-docs/access_recovery/`.
