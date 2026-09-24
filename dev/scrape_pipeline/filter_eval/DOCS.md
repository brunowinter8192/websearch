# dev/scrape_pipeline/filter_eval/

## Role
Crawl4AI content-filter configuration exploration: compares filter strategies and content-source variants to find the best markdown extraction for cleanup and RAG indexing.

## Public Interface
No `__init__.py` — not a package. Both scripts are CLI entry points run via `./venv/bin/python`.

## Flow
Test URLs (`domains.txt` or explore_pipeline discovery reports) -> scrape under several filter configurations -> raw markdown per config for manual inspection.

## Modules

### 04_filtering.py (146 LOC)

**Purpose:** Compares several content-filter configurations per URL and saves raw and fit markdown for each.
**Reads:** `domains.txt` in the parent directory, or a CLI URL.
**Writes:** `03_filter_comparison/` markdown files.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 06_content_source.py (181 LOC)

**Purpose:** Compares content-source and filter combinations across many URLs per domain.
**Reads:** Discovery JSON reports from `dev/explore_pipeline/md/`.
**Writes:** `05_content_source/<domain>/<config>/` markdown files.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

## State
None. Script 06 requires the explore_pipeline discovery run with all domains to have produced its reports first.
