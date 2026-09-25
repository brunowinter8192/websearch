# dev/search_pipeline/

## Role
Smoke tests, selector-drift probes, ranking-method eval harness and bee-investigation instrumentation for `src/search/`. Flat scripts here are per-engine smokes and standalone probes; multi-file units live in subfolders with their own DOCS.md. Touch when checking `src/search/` behaviour; never production code.

## Public Interface
No `__init__.py`. Scripts run as `./venv/bin/python dev/search_pipeline/<script>.py`; `_google_fixture.py` is imported by `dev/tests/test_google_engine.py`. Unit subfolders, each with own DOCS.md: `bee_probes/`, `browser_probes/`, `pdf_probes/`, `domain_probes/`, `ranking_eval/`, `report_analysis/`; `_lib/` and `inspections/` also keep their own.

## Flow
Scripts read `queries.txt` / `config.yml` or hardcoded query sets, drive `src/search/` engines or self-contained pydoll sessions, and write reports to the area-level output folders. Scripts moved into subfolders still write to this directory's output folders.

## Modules

### 01_google_smoke.py (120 LOC)

**Purpose:** Google production-mode smoke: one engine search per query, status OK or EMPTY.
**Reads:** `queries.txt`.
**Writes:** `md/google_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### selector_js_equivalence_check.py (113 LOC)

**Purpose:** Runs old and current parse JS of four engines in headless Chrome on synthetic HTML, verifying identical items apart from the new selector key.
**Reads:** Engine sources at a pinned git revision, current engine modules.
**Writes:** `md/selector_js_equivalence_check_<timestamp>.md`; prints a pass or fail verdict.
**Called by:** manual run.
**Calls out:** `pydoll`.

### 02_burst_smoke.py (269 LOC)

**Purpose:** Burst smoke against the production CLI: one batch-search subprocess per query batch.
**Reads:** `config.yml`, `queries.txt`.
**Writes:** `md/burst_<ts>.md`.
**Called by:** CLI only (`--queries-per-burst`, `--cooldown`, `--max-queries`).
**Calls out:** `yaml`.

### 04_ddg_smoke.py (120 LOC)

**Purpose:** DuckDuckGo production-mode smoke, same pattern as `01_google_smoke.py`.
**Reads:** `queries.txt`.
**Writes:** `md/ddg_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 05_search_smoke.py (222 LOC)

**Purpose:** Multi-engine smoke: per-engine fanout, URL merge keeping per-engine snippets, bypassing production ranking.
**Reads:** `queries.txt`.
**Writes:** `md/search_smoke_<ts>.md`.
**Called by:** CLI only (`--engines`, `--max-queries`).
**Calls out:** none.

### 08_scholar_smoke.py (128 LOC)

**Purpose:** Google Scholar production-mode smoke with status taxonomy OK/EMPTY/SUSPECT/ERROR.
**Reads:** `queries.txt`.
**Writes:** `md/scholar_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 09_openalex_smoke.py (116 LOC)

**Purpose:** OpenAlex smoke over pure HTTP with status taxonomy OK/EMPTY/RATE_LIMITED/ERROR.
**Reads:** `queries.txt`.
**Writes:** `md/openalex_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 11_pipeline_smoke.py (367 LOC)

**Purpose:** Full-pipeline smoke through the production search workflow; produces the baseline report other analysis scripts consume.
**Reads:** `queries.txt`; the search cache.
**Writes:** `md/pipeline_smoke_<ts>.md`.
**Called by:** CLI only (`--max-queries`, `--language`, `--engine-timeout`, `--report-prefix`); output consumed by `report_analysis/`.
**Calls out:** none.

### 12_max_results_probe.py (167 LOC)

**Purpose:** Per-engine single-call ceiling probe: one high-limit call per query, records count, latency, status.
**Reads:** hardcoded 3-query set.
**Writes:** `md/max_results_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 13_free_word_probe.py (298 LOC)

**Purpose:** Free-word injection probe: appends a word to queries and measures domain-distribution shift across engines.
**Reads:** hardcoded 3-query set.
**Writes:** `md/free_word_injection_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 24_pydoll_teardown_verify.py (268 LOC)

**Purpose:** Integration test for tab teardown: hung, normal, and parallel-batch tab cases against real Chrome.
**Reads:** none (self-contained hang simulation).
**Writes:** `md/teardown_verify_<ts>.md`, stdout.
**Called by:** CLI only.
**Calls out:** pydoll CDP.

### _capture_sorry.py (222 LOC)

**Purpose:** Helper script capturing Google's block page as HTML, screenshot, and markdown summary.
**Reads:** `config.yml`.
**Writes:** `md/sorry_<ts>.md`, `html/sorry_<ts>.html`, `png/sorry_<ts>.png`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `yaml`.

### _google_fixture.py (216 LOC)

**Purpose:** Local HTTP fixture serving a Google-shaped results page and redirect table for engine tests.
**Reads:** none (in-memory specs).
**Writes:** none (serves HTTP on loopback).
**Called by:** `dev/tests/test_google_engine.py`.
**Calls out:** stdlib only.

### empty_classify_se.py (206 LOC)

**Purpose:** Classification probe for Stack Exchange EMPTY queries via direct httpx against stackoverflow and cross-site fallback.
**Reads:** hardcoded query list.
**Writes:** `md/empty_classify_se_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

### google_selector_probe.py (250 LOC)

**Purpose:** Google DOM-selector diagnostic comparing the main heading selector with alternatives on a 100-result page.
**Reads:** Live DOM fetch with a hardcoded query.
**Writes:** `md/google_selector_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### no_google_burst_smoke.py (185 LOC)

**Purpose:** No-Google concurrent burst smoke: the production Scholar engine against two other engines to test burst survival.
**Reads:** hardcoded 12-query set.
**Writes:** `jsonl/no_google_burst_<ts>.jsonl`; summary table to stderr.
**Called by:** CLI only.
**Calls out:** `httpx`, `pydoll.exceptions`, `websockets.exceptions`.

### pydoll_fingerprint_probe.py (193 LOC)

**Purpose:** Measures the production Chrome fingerprint against bot.sannysoft.com and prints pass/fail vectors.
**Reads:** live page load.
**Writes:** `/tmp/pydoll_probe_sannysoft.png`; JSON summary to stdout.
**Called by:** CLI only.
**Calls out:** none.

### scholar_http_probe.py (116 LOC)

**Purpose:** Dev-only HTTP alternative to the browser Scholar engine, using httpx and lxml.
**Reads:** live HTTP fetch.
**Writes:** Returns a result list; no file output.
**Called by:** none in use; `no_google_burst_smoke.py` imports it but the import is unused. Effectively DEAD CODE.
**Calls out:** `httpx`, `lxml.html`.

### with_google_decoupling_smoke.py (171 LOC)

**Purpose:** Verifies Scholar is absent from the default engine set by inspecting the query log after five workflow runs.
**Reads:** `src/logs/query_log.jsonl` (tail).
**Writes:** `md/with_google_decoupling_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

---

## State
`config.yml` holds run parameters and the report dir, read by `02_burst_smoke.py`, and `_capture_sorry.py`. `queries.txt` is the 30-query baseline shared by the per-engine smokes, `11_pipeline_smoke.py` and the bee probes. Reports go to `md/`; payload data to `jsonl/`, `txt/`, `png/`, `runs/` (per-run pool/methods/oracle JSON co-located with eval MDs). All are area-level, shared by every subfolder.
