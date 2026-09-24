# dev/search_pipeline/

## Role
Smoke tests, selector-drift probes, ranking-method eval harness and bee-investigation instrumentation for `src/search/`. Flat scripts here are per-engine smokes and standalone probes; multi-file units live in subfolders with their own DOCS.md. Touch when checking `src/search/` behaviour; never production code.

## Public Interface
No `__init__.py`. Scripts run as `./venv/bin/python dev/search_pipeline/<script>.py`; `_google_fixture.py` is imported by `dev/tests/test_google_engine.py`. Unit subfolders, each with own DOCS.md: `bee_probes/`, `browser_probes/`, `pdf_probes/`, `domain_probes/`, `ranking_eval/`, `report_analysis/`; `_lib/` and `inspections/` also keep their own.

## Flow
Scripts read `queries.txt` / `config.yml` or hardcoded query sets, drive `src/search/` engines or self-contained pydoll sessions, and write reports to the area-level output folders. Moved scripts resolve `SCRIPT_DIR` to this directory, so output paths are unchanged by the subfolder layout.

## Modules

### 01_google_smoke.py (121 LOC)

**Purpose:** Google production-mode smoke: `GoogleEngine().search()` per query, status OK/EMPTY.
**Reads:** `queries.txt`.
**Writes:** `md/google_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.google`, `src.search.browser`.

### 02_burst_smoke.py (270 LOC)

**Purpose:** Burst smoke against the production CLI: one `cli.py search_batch` subprocess per query batch.
**Reads:** `config.yml`, `queries.txt`.
**Writes:** `md/burst_<ts>.md`.
**Called by:** CLI only (`--queries-per-burst`, `--cooldown`, `--max-queries`).
**Calls out:** `cli.py` (subprocess), `yaml`.

### 04_ddg_smoke.py (121 LOC)

**Purpose:** DuckDuckGo production-mode smoke via `DuckDuckGoEngine`, same pattern as `01_google_smoke.py`.
**Reads:** `queries.txt`.
**Writes:** `md/ddg_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.duckduckgo`, `src.search.browser`.

### 05_search_smoke.py (223 LOC)

**Purpose:** Multi-engine comparison smoke: per-engine fanout, merge by URL keeping per-engine snippets, bypassing `_merge_and_rank`.
**Reads:** `queries.txt`.
**Writes:** `md/search_smoke_<ts>.md`.
**Called by:** CLI only (`--engines`, `--max-queries`).
**Calls out:** `src.search.browser`, `src.search.engines.{google,duckduckgo,scholar,openalex}`, `src.search.result`.

### 08_scholar_smoke.py (129 LOC)

**Purpose:** Google Scholar production-mode smoke with status taxonomy OK/EMPTY/SUSPECT/ERROR.
**Reads:** `queries.txt`.
**Writes:** `md/scholar_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.scholar`, `src.search.browser`.

### 09_openalex_smoke.py (117 LOC)

**Purpose:** OpenAlex smoke over pure HTTP with status taxonomy OK/EMPTY/RATE_LIMITED/ERROR.
**Reads:** `queries.txt`.
**Writes:** `md/openalex_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.openalex`.

### 11_pipeline_smoke.py (369 LOC)

**Purpose:** Full-pipeline smoke through `search_web_workflow`; produces the baseline report other analysis scripts consume.
**Reads:** `queries.txt`; cache via `cache_key`/`cache_read`.
**Writes:** `md/pipeline_smoke_<ts>.md`.
**Called by:** CLI only (`--max-queries`, `--language`, `--engine-timeout`, `--report-prefix`); output consumed by `report_analysis/`.
**Calls out:** `src.search.browser`, `src.search.cache`, `src.search.search_web`.

### 12_max_results_probe.py (168 LOC)

**Purpose:** Per-engine single-call ceiling probe: one high-`max_results` call per query, records count, latency, status.
**Reads:** hardcoded 3-query set.
**Writes:** `md/max_results_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,scholar,duckduckgo,openalex}`, `src.search.browser`.

### 13_free_word_probe.py (299 LOC)

**Purpose:** Free-word injection probe: appends `pdf`/`book` to queries and measures domain-distribution shift across engines.
**Reads:** hardcoded 3-query set.
**Writes:** `md/free_word_injection_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,scholar,duckduckgo,openalex}`, `src.search.browser`.

### 24_pydoll_teardown_verify.py (268 LOC)

**Purpose:** Integration test for `kill_tab` teardown: hung, normal and parallel-batch tab cases against real Chrome.
**Reads:** none (self-contained hang simulation).
**Writes:** `md/teardown_verify_<ts>.md`, stdout.
**Called by:** CLI only.
**Calls out:** `src.search.browser` (via importlib), pydoll CDP.

### _capture_sorry.py (223 LOC)

**Purpose:** Helper script capturing Google's `/sorry/` block page as HTML, screenshot and Markdown summary.
**Reads:** `config.yml`.
**Writes:** `md/sorry_<ts>.md`, `html/sorry_<ts>.html`, `png/sorry_<ts>.png`.
**Called by:** CLI only.
**Calls out:** `pydoll`, `yaml`.

### _google_fixture.py (217 LOC)

**Purpose:** Local HTTP fixture serving a Google-shaped results page and `/goto` redirect table for engine tests.
**Reads:** none (in-memory specs).
**Writes:** none (serves HTTP on loopback).
**Called by:** `dev/tests/test_google_engine.py`.
**Calls out:** stdlib only.

### empty_classify_se.py (207 LOC)

**Purpose:** Classification probe for Stack Exchange EMPTY queries via direct httpx against stackoverflow and cross-site fallback.
**Reads:** hardcoded query list.
**Writes:** `md/empty_classify_se_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

### google_selector_probe.py (251 LOC)

**Purpose:** Google DOM-selector diagnostic: compares `#rso h3` matches with alternative selectors at `num=100`.
**Reads:** live DOM fetch (hardcoded `QUERY`, `NUM`).
**Writes:** `md/google_selector_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.browser`, `src.search.engines.google`.

### no_google_burst_smoke.py (186 LOC)

**Purpose:** No-Google concurrent burst smoke: production `ScholarEngine` against two other engines to test burst survival.
**Reads:** hardcoded 12-query set.
**Writes:** `jsonl/no_google_burst_<ts>.jsonl`; summary table to stderr.
**Called by:** CLI only.
**Calls out:** `httpx`, `pydoll.exceptions`, `websockets.exceptions`, `src.search.{status,status_timeout,status_error,browser}`, `src.search.engines.{duckduckgo,openalex,scholar}`.

### pydoll_fingerprint_probe.py (192 LOC)

**Purpose:** Measures the production Chrome fingerprint against bot.sannysoft.com and prints pass/fail vectors.
**Reads:** live page load.
**Writes:** `/tmp/pydoll_probe_sannysoft.png`; JSON summary to stdout.
**Called by:** CLI only.
**Calls out:** `src.search.browser`.

### scholar_http_probe.py (119 LOC)

**Purpose:** Dev-only HTTP alternative to the browser Scholar engine: httpx plus lxml against scholar.google.com.
**Reads:** live HTTP fetch.
**Writes:** returns `SearchResult` list; no file output.
**Called by:** imported historically by `no_google_burst_smoke.py` (import now unused).
**Calls out:** `httpx`, `lxml.html`, `src.search.{rate_limiter,result,status}`.

### with_google_decoupling_smoke.py (172 LOC)

**Purpose:** Verifies Scholar is absent from the default engine set by inspecting the query log after five workflow runs.
**Reads:** `src/logs/query_log.jsonl` (tail).
**Writes:** `md/with_google_decoupling_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.search_web`, `src.search.browser`.

---

## State
`config.yml` holds run parameters (`queries_file`, `page_load_timeout`, `consent_settle`) and the report dir, read by `02_burst_smoke.py`, and `_capture_sorry.py`. `queries.txt` is the 30-query baseline shared by the per-engine smokes, `11_pipeline_smoke.py` and the bee probes. Reports go to `md/`; payload data to `jsonl/`, `txt/`, `png/`, `runs/` (per-run pool/methods/oracle JSON co-located with eval MDs). All are area-level, shared by every subfolder.
