# dev/search_pipeline/browser_probes/

## Role
Go/no-go scrapeability and measurement probes for candidate search engines and anti-bot mechanisms, each self-contained (inline copy of the pydoll session shape, no `src/` import) except the altcha probe. Touch to reproduce engine-candidate decisions; not production engine code.

## Public Interface
No `__init__.py`. Entry scripts `25_startpage_probe.py`, `26_brave_probe.py`, `27_brave_headed_lane_probe.py`, `28_bing_probe.py`, `29_yandex_probe.py`, `31_date_availability_probe.py`, `altcha_trigger_probe.py` run as `./venv/bin/python dev/search_pipeline/browser_probes/<script>.py`.

## Flow
Each entry drives a live browser session against one engine (or the ALTCHA widget), runs a fixed query set, and hands records to its `_<probe>_report.py` sibling, which writes a Markdown report to `../md/`.

## Modules

### 25_startpage_probe.py (259 LOC)

**Purpose:** Go/no-go probe for startpage.com scrapeability via the real homepage search form; ten queries, counts and block markers.
**Reads:** none (live run).
**Writes:** `../md/startpage_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `_startpage_probe_report.py`.

### _startpage_probe_report.py (129 LOC)

**Purpose:** Markdown report assembly for the Startpage probe: headline, selector findings, per-query table, samples, non-OK details.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/startpage_probe_<ts>.md`.
**Called by:** `25_startpage_probe.py`.
**Calls out:** stdlib only.

### 26_brave_probe.py (234 LOC)

**Purpose:** Three-condition gate probe for Brave Search (real rows, no PoW/CAPTCHA, latency at most five seconds); result DROP.
**Reads:** none (live run).
**Writes:** `../md/brave_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `_brave_probe_report.py`.

### _brave_probe_report.py (142 LOC)

**Purpose:** Markdown report assembly for the Brave probe: verdict, headline, stack notes, per-query table.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/brave_probe_<ts>.md`.
**Called by:** `26_brave_probe.py`.
**Calls out:** stdlib only.

### 27_brave_headed_lane_probe.py (216 LOC)

**Purpose:** Headed-background Chrome lane probe (macOS `open -g`) against Brave PoW; result DROP, launch mechanism validated.
**Reads:** none (live run).
**Writes:** `../md/brave_headed_lane_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (`BrowserProcessManager` override), macOS `open`, `_brave_headed_lane_probe_report.py`.

### _brave_headed_lane_probe_report.py (152 LOC)

**Purpose:** Markdown report assembly for the headed-lane probe: verdict, launch mechanism, headline, per-query table.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/brave_headed_lane_probe_<ts>.md`.
**Called by:** `27_brave_headed_lane_probe.py`.
**Calls out:** stdlib only.

### 28_bing_probe.py (250 LOC)

**Purpose:** Go/no-go probe for bing.com as a second Bing-index path, including unwrapping of `ck/a` tracking redirects; result CANDIDATE.
**Reads:** none (live run).
**Writes:** `../md/bing_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `_bing_probe_report.py`.

### _bing_probe_report.py (143 LOC)

**Purpose:** Markdown report assembly for the Bing probe: verdict, headline, selector findings, per-query table.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/bing_probe_<ts>.md`.
**Called by:** `28_bing_probe.py`.
**Calls out:** stdlib only.

### 29_yandex_probe.py (230 LOC)

**Purpose:** Go/no-go probe for yandex.com as an independent-index candidate under a relaxed criterion; result CANDIDATE.
**Reads:** none (live run).
**Writes:** `../md/yandex_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `_yandex_probe_report.py`.

### _yandex_probe_report.py (174 LOC)

**Purpose:** Markdown report assembly for the Yandex probe: verdict, quality note, headline, findings, per-query table.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/yandex_probe_<ts>.md`.
**Called by:** `29_yandex_probe.py`.
**Calls out:** stdlib only.

### 31_date_availability_probe.py (137 LOC)

**Purpose:** Measurement probe: whether eight DOM-scraped engines expose result dates as elements, snippet text, nowhere or unmeasurable.
**Reads:** none (live run).
**Writes:** `../md/date_availability_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll`, browser, nav and report siblings.

### _date_availability_probe_browser.py (148 LOC)

**Purpose:** Inline pydoll session shape for the date probe: options, fingerprint patches, tab lifecycle, generic block diagnosis.
**Reads:** none.
**Writes:** own `_browser` state; kills stale Chrome via `pkill`.
**Called by:** `31_date_availability_probe.py`, nav sibling.
**Calls out:** `pydoll`.

### _date_availability_probe_nav.py (149 LOC)

**Purpose:** Per-engine navigation, wait and diagnose flows for the eight engines plus container selectors.
**Reads:** none.
**Writes:** none (drives the live tab).
**Called by:** `31_date_availability_probe.py`.
**Calls out:** `pydoll`, browser sibling.

### _date_availability_probe_report.py (88 LOC)

**Purpose:** Raw-evidence Markdown report for the date probe, grouped per engine and record.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/date_availability_probe_<ts>.md`.
**Called by:** `31_date_availability_probe.py`.
**Calls out:** stdlib only.

### altcha_trigger_probe.py (396 LOC)

**Purpose:** Go/no-go probe: can Mojeek's ALTCHA challenge be started and completed by automation via three isolated trigger attempts.
**Reads:** none (live run).
**Writes:** `../md/altcha_trigger_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `patchright`, `crawl4ai.browser_manager` (flags only), cdp, js, launch and report siblings.

### _altcha_trigger_probe_cdp.py (72 LOC)

**Purpose:** Raw-CDP shadow-DOM helpers: widget node lookup, shadow-root mode, coordinate click.
**Reads:** none (CDP session passed in).
**Writes:** one live click on the page.
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** stdlib types only.

### _altcha_trigger_probe_js.py (96 LOC)

**Purpose:** JS snippet constants and builders: widget-event init script, inspection, verify, outcome detection.
**Reads:** none.
**Writes:** none (string builders).
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** stdlib (`json`).

### _altcha_trigger_probe_launch.py (95 LOC)

**Purpose:** Backgrounded-Chrome launch helpers: inline copy of the chromium self-launch and focus-watchdog shape.
**Reads:** none.
**Writes:** spawns and kills Chrome processes and a watchdog task.
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** `patchright`, `crawl4ai.browser_manager`, macOS `open`/`osascript`/`pkill`.

### _altcha_trigger_probe_report.py (287 LOC)

**Purpose:** Markdown report assembly for the ALTCHA probe: summary, inspection, per-trigger sections, methodology.
**Reads:** none (dataclass instances passed in).
**Writes:** `../md/altcha_trigger_probe_<ts>.md` via `write_report`.
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** stdlib only.

---

## State
`31_date_availability_probe` state (`_browser`) lives in `_date_availability_probe_browser.py`; every other probe keeps its session state inside its entry script.
