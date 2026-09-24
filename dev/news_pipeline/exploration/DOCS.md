# dev/news_pipeline/exploration/

## Role
Manual UI and API exploration probes for CoinDesk, run to learn page structure, load-more mechanics, and the timeline API before building production discovery. Not a production pipeline; each numbered probe has helper siblings for DOM scripting, capture, and reports.

## Public Interface
No `__init__.py` — not a package. The numbered probe scripts (01 to 06) are CLI entry points run via `./venv/bin/python`; underscore modules are helpers imported by flat name.

## Flow
Numbered probe drives a live CoinDesk session (pydoll or Playwright) or replays the captured timeline API request -> helper siblings extract, capture, and log -> report sibling writes markdown to the probe's `NN_output/` folder.

## Modules

### 01_coindesk_ui_probe.py (222 LOC)

**Purpose:** Pydoll playthrough of the latest-news page to learn the load-more button, click mechanics, and article URL pattern.
**Reads:** Live CoinDesk site.
**Writes:** `01_output/` JSON and a debug screenshot.
**Called by:** CLI only.
**Calls out:** none.

### _01_dom.py (215 LOC)

**Purpose:** Pydoll and CDP DOM-scripting layer for probe 01: launch options plus inspect, extract, count, find, and click helpers.
**Reads:** nothing; takes a tab handle.
**Writes:** nothing.
**Called by:** `01_coindesk_ui_probe.py`.
**Calls out:** `pydoll`.

### 02_coindesk_pagination_probe.py (24 LOC)

**Purpose:** CLI entry that dispatches to quick mode or depth mode.
**Reads:** nothing.
**Writes:** nothing directly.
**Called by:** CLI only.
**Calls out:** none.

### _02_dom.py (131 LOC)

**Purpose:** Shared Playwright page-scripting layer for both modes: article extraction, feed-count polling, oldest-date computation.
**Reads:** nothing; takes a page handle.
**Writes:** nothing.
**Called by:** `_02_quick.py`, `_02_depth.py`.
**Calls out:** none.

### _02_quick.py (205 LOC)

**Purpose:** Quick-mode probe: a few clicks with full HAR capture and live network logging keyed by click number.
**Reads:** Live CoinDesk site.
**Writes:** `02_output/` HAR and report.
**Called by:** `02_coindesk_pagination_probe.py`.
**Calls out:** `playwright`.

### _02_depth.py (164 LOC)

**Purpose:** Depth-mode probe: clicks until disabled, plateau, or cap, with a lightweight network log and no HAR.
**Reads:** Live CoinDesk site.
**Writes:** `02_output/` depth report.
**Called by:** `02_coindesk_pagination_probe.py`.
**Calls out:** `playwright`.

### _02_report.py (185 LOC)

**Purpose:** Markdown report assembly for quick and depth modes.
**Reads:** nothing; takes result data.
**Writes:** Report files at caller-given paths.
**Called by:** `_02_quick.py`, `_02_depth.py`.
**Calls out:** none.

### 03_coindesk_backfill_traversal.py (336 LOC)

**Purpose:** Uncapped browser-driven backfill of the latest-news page reusing production discovery Chrome machinery, with stop rules for button gone, disabled, or plateau.
**Reads:** Live CoinDesk site.
**Writes:** `03_output/` final URL list, crash-safe checkpoint, progress log, stage report.
**Called by:** CLI only.
**Calls out:** none.

### _03_capture.py (216 LOC)

**Purpose:** Pydoll and CDP browser launch plus click, extract, and button-state helpers with disabled-button retry.
**Reads:** nothing; takes a tab handle.
**Writes:** nothing.
**Called by:** `03_coindesk_backfill_traversal.py`.
**Calls out:** `pydoll`.

### _03_log.py (23 LOC)

**Purpose:** Live-tailable progress log writer for probe 03.
**Reads:** nothing.
**Writes:** `03_output/progress_<ts>.log`.
**Called by:** `03_coindesk_backfill_traversal.py`.
**Calls out:** none.

### _03_report.py (140 LOC)

**Purpose:** Stage A sanity report: timing, DOM growth trend, and projection to the founding date.
**Reads:** nothing; takes result values.
**Writes:** `03_output/` stage report.
**Called by:** `03_coindesk_backfill_traversal.py`.
**Calls out:** none.

### 04_coindesk_timeline_replay_probe.py (148 LOC)

**Purpose:** Orchestrates capture, replay, cursor loop, and report for the timeline API probe.
**Reads:** Live CoinDesk site and timeline API.
**Writes:** `04_output/report_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### _04_capture.py (118 LOC)

**Purpose:** Captures timeline API requests through background Chrome and a HAR recorder to establish the minimum replay header set.
**Reads:** Live CoinDesk site.
**Writes:** nothing; returns the captured entry.
**Called by:** `04_coindesk_timeline_replay_probe.py`.
**Calls out:** `pydoll`.

### _04_replay.py (325 LOC)

**Purpose:** Dual-client HTTP replay of the captured timeline URL with cursor-chained pagination and 403 diagnostics.
**Reads:** Live timeline API.
**Writes:** nothing.
**Called by:** `04_coindesk_timeline_replay_probe.py`.
**Calls out:** `httpx`, `curl_cffi`.

### _04_report.py (172 LOC)

**Purpose:** Markdown report assembly: captured headers, replay results, cursor loop, rate-test comparison.
**Reads:** nothing; takes result data.
**Writes:** Report file at the caller-given path.
**Called by:** `04_coindesk_timeline_replay_probe.py`.
**Calls out:** none.

### 05_coindesk_cursor_probe.py (241 LOC)

**Purpose:** Investigates cursor validity and story-type distribution across paginated timeline calls in walk and fixed modes.
**Reads:** Live timeline API.
**Writes:** `05_data/` walk, fixed, and deep reports.
**Called by:** CLI only.
**Calls out:** none.

### _05_capture.py (122 LOC)

**Purpose:** Pydoll and CDP browser launch plus timeline-request capture for probe 05.
**Reads:** nothing; takes a tab handle.
**Writes:** nothing.
**Called by:** `05_coindesk_cursor_probe.py`.
**Calls out:** `pydoll`.

### _05_parse.py (43 LOC)

**Purpose:** Shared article-body parsing and cursor and URL building for both modes; a non-JSON body raises.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `05_coindesk_cursor_probe.py`, `_05_fixed.py`.
**Calls out:** none.

### _05_fixed.py (123 LOC)

**Purpose:** Fixed-cursor mode algorithm: skips invalid-type anchors, chains cursor calls, builds result rows.
**Reads:** nothing; takes headers and body.
**Writes:** nothing.
**Called by:** `05_coindesk_cursor_probe.py`.
**Calls out:** `httpx`.

### _05_report.py (156 LOC)

**Purpose:** Markdown report assembly for walk and fixed modes.
**Reads:** nothing; takes result data.
**Writes:** Report files at caller-given paths.
**Called by:** `05_coindesk_cursor_probe.py`.
**Calls out:** none.

### 05b_coindesk_warmth_probe.py (332 LOC)

**Purpose:** Measures IP warmth duration after a browser session closes by replaying the captured URL at growing intervals.
**Reads:** Live CoinDesk site and timeline API.
**Writes:** `05b_output/` warmth report and state file.
**Called by:** CLI only.
**Calls out:** none.

### _05b_report.py (106 LOC)

**Purpose:** Markdown report assembly for the warmth probe.
**Reads:** nothing; takes result values.
**Writes:** Report file at the caller-given path.
**Called by:** `05b_coindesk_warmth_probe.py`.
**Calls out:** none.

### 06_coindesk_full_discovery.py (348 LOC)

**Purpose:** Full discovery run combining browser capture and cursor loop, writing articles per year with checkpoint resume and rewarm fallback.
**Reads:** Live CoinDesk site and timeline API.
**Writes:** `06_output/` per-year URL files, progress log, summary report.
**Called by:** CLI only.
**Calls out:** none.

### _06_capture.py (167 LOC)

**Purpose:** Pydoll and CDP browser launch plus timeline-request capture for probe 06, reused for warmup and rewarm cycles.
**Reads:** nothing.
**Writes:** nothing; returns captured data.
**Called by:** `06_coindesk_full_discovery.py`.
**Calls out:** `pydoll`, `httpx`.

### _06_progress.py (42 LOC)

**Purpose:** Progress logging and crash-safe checkpoint persistence for the cursor loop.
**Reads:** nothing.
**Writes:** `06_output/` checkpoint and progress log.
**Called by:** `06_coindesk_full_discovery.py`.
**Calls out:** none.

### _06_report.py (35 LOC)

**Purpose:** Markdown report assembly for the final discovery summary.
**Reads:** nothing; takes the result dict.
**Writes:** Report file at the caller-given path.
**Called by:** `06_coindesk_full_discovery.py`.
**Calls out:** none.

---

## State
`01_output/` through `06_output/` and `05b_output/` are gitignored probe outputs. The checkpoint file in `06_output/` is the crash-safe resume state of the full discovery probe. Findings per probe: process-docs area news_pipeline.
