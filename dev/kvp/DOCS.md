# dev/kvp/

## Role
Continuous-improvement report for the ad hoc lane and the deep dive lane: reads the production logs, derives every verdict (blocked, usable, silent failure) offline and writes one markdown report per run. Touch it to change an indicator definition or a verdict rule; never write verdicts into the production logs.

## Public Interface
No `__init__.py`. Run from the repo root as `./venv/bin/python -m dev.kvp.kvp_report [--since ISO] [--until ISO]`. Optional path flags: `--log-dir`, `--rag-search-log`, `--collection-dir`. Prints the report path.

## Flow
Logs, scrape sidecars, rag-cli search log and the `websearch-pages` collection are loaded, filtered to the window -> verdict rules classify scrapes, engine runs, pipe records and collection files -> indicators are computed for all records and per `code_version` -> markdown goes to `md/`.

## Modules

### kvp_report.py (101 LOC)

**Purpose:** Entry point: parses the window, loads and classifies the sources, computes the indicators and writes the report.
**Reads:** `query_log.jsonl`, `scrape_log.jsonl` with sidecars, `pipe_scrape_log.jsonl`, rag-cli `search.jsonl`, the collection directory.
**Writes:** `md/kvp_report_<since>_<until>_<timestamp>.md`; the path on stdout.
**Called by:** invoked directly with `-m`.
**Calls out:** none.

---

### kvp_config.py (45 LOC)

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

### kvp_classify.py (193 LOC)

**Purpose:** The verdict rules as pure functions: scrape, pipe record, engine run, collection file, duplicate files.
**Reads:** none.
**Writes:** none.
**Called by:** kvp_indicators.py, dev/tests/test_kvp_classify.py.
**Calls out:** none.

---

### kvp_indicators.py (226 LOC)

**Purpose:** Applies the verdicts to the records and computes the indicators per lane and level, split by `code_version`.
**Reads:** the loaded and classified records.
**Writes:** none.
**Called by:** kvp_report.py.
**Calls out:** none.

---

### kvp_render.py (212 LOC)

**Purpose:** Renders the indicator data and the lists of flagged records as markdown tables.
**Reads:** none.
**Writes:** none.
**Called by:** kvp_report.py.
**Calls out:** none.

---

## State
None. Each run is stateless; reports in `md/` are written once and never edited. Verdict definitions and details: process-docs area kvp. Test fixtures: `dev/tests/fixtures/kvp/`.
