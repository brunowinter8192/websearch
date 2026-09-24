# dev/scrape_pipeline/browser_eval/

## Role
Regression baseline + browser-config tuning for the production scraper (`scrape_url_chromium_workflow`). Baseline/regression workflow: run 01 to snapshot, run 02 to diff against the previous iteration. 03 is a standalone browser-config comparison for JS-heavy sites failing under default settings.

## Modules

### 01_baseline.py (129 LOC)

**Purpose:** Scrapes all test domains using the production `scrape_url_chromium_workflow` and saves results as numbered iterations with metadata (char count, word count, timestamp).
**Reads:** `domains.txt` (pipeline root).
**Writes:** `01_baselines/<domain>/iteration_<N>.md` + `metadata_<N>.json`.
**Called by:** CLI only.

### 02_regression.py (169 LOC)

**Purpose:** Compares the last two iterations per domain to detect regressions. Generates unified diffs and classifies changes by magnitude (IDENTICAL, MINOR_CHANGE, MODERATE_CHANGE, MAJOR_CHANGE).
**Reads:** `01_baselines/`.
**Writes:** `md/02_diff_report_<timestamp>.txt`.
**Called by:** CLI only. Run after `01_baseline.py` has produced ≥2 iterations.

### 03_browser.py (121 LOC)

**Purpose:** Tests multiple Crawl4AI browser configurations for JS-heavy sites that fail with default settings. Compares content yield (char count, word count) across configs with different wait strategies: domcontentloaded baseline, networkidle, extended delay, CSS selector wait, full page scan.
**Reads:** hardcoded domain set or a URL CLI arg.
**Writes:** `md/03_<domain>_<slug>_<config>.md`.
**Called by:** CLI only.

## Gotchas
`01_baselines/` is gitignored raw eval data — present on disk locally, never tracked. `md/` reports are tracked (mirrors `garbage_eval/md/`).
