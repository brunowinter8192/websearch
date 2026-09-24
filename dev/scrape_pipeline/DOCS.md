# dev/scrape_pipeline/

## Role
Quality monitoring and configuration testing for the URL scraper (`src/scraper/`). Own-level scripts cover the pipe-scraper eval, a raw-scrape baseline, and Cloudflare markdown-adoption probing. Sub-suites (`filter_eval/`, `browser_eval/`, `garbage_eval/`, `03_cleanup/`, `04_overview_sweep/`, `05_paper_mode/`) each have their own DOCS.md.

## Public Interface
No `__init__.py` — not a package. The numbered scripts are CLI entry points run via `./venv/bin/python`; the underscore-prefixed and `p1_` modules are helpers of the pipe-scrape eval.

## Flow
URL list (from explore_pipeline's discovered set, a search smoke report, or a hardcoded set) -> scrape via the probe scraper or direct HTTP -> metrics and sweeps per phase -> markdown reports in `md/` and raw corpora in `*_data/` folders.

## Modules

### p1_pipe_scraper.py (94 LOC)

**Purpose:** Core probe scraper returning per-URL metrics under a locked raw-markdown configuration, optionally saving the markdown.
**Reads:** nothing directly.
**Writes:** Optional markdown files when an output dir is given.
**Called by:** `07_pipe_scrape_eval.py`, `_pipe_scrape_eval_phase1.py`, `_pipe_scrape_eval_phase2.py`, `_pipe_scrape_eval_phase3.py`.
**Calls out:** `crawl4ai`.

---

### 07_pipe_scrape_eval.py (61 LOC)

**Purpose:** CLI entry point routing smoke and the three eval phases to their sibling modules; owns the smoke test.
**Reads:** URL list via the common module.
**Writes:** nothing directly.
**Called by:** CLI only.
**Calls out:** `p1_pipe_scraper.py`, the common and three phase modules.

---

### _pipe_scrape_eval_common.py (44 LOC)

**Purpose:** Utilities shared by all eval phases: URL list loading, stratified sampling, aggregate latency and outcome metrics.
**Reads:** The discovered-URL list file.
**Writes:** nothing.
**Called by:** `07_pipe_scrape_eval.py`, `_pipe_scrape_eval_phase1.py`, `_pipe_scrape_eval_phase2.py`, `_pipe_scrape_eval_phase3.py`.
**Calls out:** none.

---

### _pipe_scrape_eval_phase1.py (92 LOC)

**Purpose:** Phase 1 concurrency and WAF sweep that recommends the highest WAF-safe level.
**Reads:** nothing directly; takes a loaded URL list.
**Writes:** `md/07_concurrency_sweep_<ts>.md`.
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.py`, the common module.

---

### _pipe_scrape_eval_phase2.py (96 LOC)

**Purpose:** Phase 2 delay sweep at fixed concurrency that picks the plateau delay by content-size gain.
**Reads:** nothing directly; takes a loaded URL list.
**Writes:** `md/07_delay_sweep_<ts>.md`.
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.py`, the common module.

---

### _pipe_scrape_eval_phase3.py (266 LOC)

**Purpose:** Phase 3 full-corpus run with WAF probe, batched pacing, position-tracked 429s, and one retry pass.
**Reads:** nothing directly; takes a loaded URL list.
**Writes:** `md/07_full_run_<ts>.md`; raw markdown corpus under `07_pipe_scrape_eval_data/`.
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.py`, the common module.

---

### 02_raw_smoke.py (199 LOC)

**Purpose:** Dev-only raw scrape of URLs parsed from a search smoke report, with no fallback chain or garbage detection, as a cleanup baseline.
**Reads:** A search smoke markdown report given by `--input`.
**Writes:** `02_raw_data/<ts>/` markdown files plus a triage report.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

---

### 06_cloudflare_md_adoption.py (289 LOC)

**Purpose:** Probes a curated URL set for server-side markdown adoption via the markdown Accept header and measures byte reduction.
**Reads:** Hardcoded URL set.
**Writes:** `md/06_cf_md_adoption_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

---

## State
`domains.txt` is the shared test URL list for `browser_eval/` and `filter_eval/`. `failures.jsonl` (gitignored) is the failure log written by the production scraper. `01_dual_mode_data/` is a historical record of a deleted script; nothing reads it. Details and inspection recipes: process-docs area scrape_pipeline.
