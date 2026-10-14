# dev/kvp/

## Role
Continuous-improvement report for the ad hoc lane and the deep dive lane: reads the production logs, derives every verdict (blocked, usable, silent failure) offline and writes one markdown report per run. The canary runner re-scrapes a fixed URL list before and after a fix. Touch it to change an indicator definition, a verdict rule or the case list; never write verdicts into the production logs.

## Public Interface
No `__init__.py`. Run from the repo root as `./venv/bin/python -m dev.kvp.kvp_report [--since ISO] [--until ISO]`. Optional path flags: `--log-dir`, `--rag-search-log`, `--collection-dir`. Prints the report path. Canary: `./venv/bin/python -m dev.kvp.kvp_canary [--baseline <json>]`, prints the report and JSON path.

## Flow
Logs, scrape sidecars, rag-cli search log and the `websearch-pages` collection are loaded, filtered to the window -> verdict rules classify scrapes, engine runs, pipe records and collection files -> indicators are computed for all records and per `code_version` -> markdown goes to `md/`. Canary: fixed cases are scraped one by one through the real chromium workflow into a throwaway log -> `kvp_classify` gives the verdict, `must_contain` checks the content -> report to `md/`, JSON to `json/`, optional comparison with an earlier JSON.

## Modules

### kvp_report.py (101 LOC)

**Purpose:** Entry point: parses the window, loads and classifies the sources, computes the indicators and writes the report.
**Reads:** `query_log.jsonl`, `scrape_log.jsonl` with sidecars, `pipe_scrape_log.jsonl`, rag-cli `search.jsonl`, the collection directory.
**Writes:** `md/kvp_report_<since>_<until>_<timestamp>.md`; the path on stdout.
**Called by:** invoked directly with `-m`.
**Calls out:** none.

---

### kvp_config.py (57 LOC)

**Purpose:** Paths, verdict labels and constants shared by two or more modules of this directory.
**Reads:** none.
**Writes:** none.
**Called by:** every other module here.
**Calls out:** none.

---

### kvp_load.py (84 LOC)

**Purpose:** Reads the JSONL logs, sidecar bodies and collection files and filters records to the time window.
**Reads:** the log directory, the sidecar directory, the collection directory.
**Writes:** none.
**Called by:** kvp_report.py, kvp_indicators.py.
**Calls out:** none.

---

### kvp_classify.py (244 LOC)

**Purpose:** The verdict rules as pure functions: scrape, pipe record, engine run, collapse search pattern, collection file, duplicate files.
**Reads:** none.
**Writes:** none.
**Called by:** kvp_indicators.py, dev/tests/test_kvp_classify.py.
**Calls out:** none.

---

### kvp_indicators.py (290 LOC)

**Purpose:** Applies the verdicts to the records and computes the indicators per lane and level, split by `code_version`, plus the rows of the collapse searches and the per-version table of the focus engine (google).
**Reads:** the loaded and classified records.
**Writes:** none.
**Called by:** kvp_report.py.
**Calls out:** none.

---

### kvp_render.py (263 LOC)

**Purpose:** Renders the indicator data, the focus-engine table, the collapse searches with their host facts and the lists of flagged records as markdown tables.
**Reads:** none.
**Writes:** none.
**Called by:** kvp_report.py.
**Calls out:** none.

---

### kvp_canary.py (105 LOC)

**Purpose:** Entry point of the canary run: loads the case list, scrapes each URL through the production workflow into an isolated log, evaluates and writes report and JSON.
**Reads:** `canary_cases.json`, an earlier canary JSON via `--baseline`, the throwaway scrape log it writes itself.
**Writes:** `md/kvp_canary_<timestamp>.md`, `json/kvp_canary_<timestamp>.json`; sets `WEBSEARCH_SCRAPE_LOG_PATH` for its own process.
**Called by:** invoked directly with `-m`.
**Calls out:** src/scraper/chromium_scrape.py, src/code_version.py.

---

### kvp_canary_logic.py (165 LOC)

**Purpose:** Pure canary functions: evaluates one case against its expected verdict and content marker, compares two runs, renders the report.
**Reads:** none.
**Writes:** none.
**Called by:** kvp_canary.py, dev/tests/test_kvp_canary.py.
**Calls out:** none.

---

### probe_google_load_events.py (216 LOC)

**Purpose:** One-off measurement of when Google's results DOM, `DOMContentLoaded` and the load event arrive in the production browser setup; run with `--mode poll` or `--mode events`.
**Reads:** nothing from the production logs; sends real Google searches through `search_web_workflow` with an isolated log and no cache write.
**Writes:** `md/probe_google_load_events_<mode>_<timestamp>.md`, `json/probe_google_load_events_<mode>_<timestamp>.json`.
**Called by:** invoked directly with `-m`; no stop at Google's CAPTCHA page, mind the Google volume (see process-docs area kvp).
**Calls out:** src/search/search_web.py, src/search/engines/google.py.

---

## State
None. Each run is stateless; reports in `md/` and `json/` are written once and never edited. `canary_cases.json` is the one hand-maintained data file. Verdict definitions and details: process-docs area kvp. Test fixtures: `dev/tests/fixtures/kvp/`.
