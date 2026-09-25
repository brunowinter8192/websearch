# dev/scrape_pipeline/garbage_eval/

## Role
Investigation and validation of garbage-content detection ideas for the scraper: discover which crawl-result metadata is reliable, then prototype fixes before touching production code.

## Public Interface
No `__init__.py` — not a package. Both scripts are CLI entry points run via `./venv/bin/python`.

## Flow
Probe URLs -> Crawl4AI scrape -> inspection or prototype validation -> markdown report in `md/`.

## Modules

### 07_result_inspect.py (117 LOC)

**Purpose:** Enumerates all metadata fields of a crawl result across normal, 404, and consent-heavy pages.
**Reads:** Hardcoded 3-URL probe set.
**Writes:** `md/07_result_inspect_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 09_garbage_fix_prototype.py (220 LOC)

**Purpose:** Prototypes status-code 404 detection and consent-prefix stripping and validates against edge-case and baseline URLs.
**Reads:** Hardcoded edge-case and baseline URL set.
**Writes:** `md/09_garbage_fix_prototype_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

## State
`md/` holds historical reports, including the output of a deleted edge-case script. Nothing reads them.
