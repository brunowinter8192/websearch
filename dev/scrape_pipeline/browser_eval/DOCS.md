# dev/scrape_pipeline/browser_eval/

## Role
Regression baseline and browser-config tuning for the production scraper. Snapshot with the baseline script, diff with the regression script; the browser script is a standalone config comparison for JS-heavy sites.

## Public Interface
No `__init__.py` — not a package. All three scripts are CLI entry points run via `./venv/bin/python`.

## Flow
Test domains -> production scrape saved as numbered iterations -> regression diff of the last two iterations. Browser script: URL -> several browser configs -> content yield comparison. The production scrape under evaluation is `src/scraper/chromium_scrape.py`.

## Modules

### 01_baseline.py (141 LOC)

**Purpose:** Scrapes all test domains with the production scraper and saves numbered iterations with metadata.
**Reads:** `domains.txt` in the parent directory.
**Writes:** `01_baselines/<domain>/` markdown and metadata.
**Called by:** CLI only.
**Calls out:** none.

### 02_regression.py (196 LOC)

**Purpose:** Diffs the last two iterations per domain and classifies changes by magnitude.
**Reads:** `01_baselines/`.
**Writes:** `md/02_diff_report_<ts>.txt`.
**Called by:** CLI only.
**Calls out:** none.

### 03_browser.py (136 LOC)

**Purpose:** Compares content yield across browser wait-strategy configurations for JS-heavy sites.
**Reads:** Hardcoded domain set or a CLI URL.
**Writes:** `md/03_<domain>_<slug>_<config>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

## State
`01_baselines/` is gitignored raw eval data; `md/` reports are tracked.
