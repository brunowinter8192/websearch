# dev/scrape_pipeline/garbage_eval/

## Role
Investigation and validation suite for `is_garbage_content()` garbage detection. Workflow: 07 discovers available `CrawlResult` metadata, 08 reproduces known failure edge cases, 09 prototypes and validates fixes before production code changes.

## Modules

### 07_result_inspect.py (103 LOC)

**Purpose:** Inspects the full Crawl4AI `CrawlResult` object to discover available metadata fields. Scrapes 3 URLs (normal, 404, consent-heavy) and enumerates all result attributes with types and values. Key finding: `result.status_code` is available and reliable (404 for error pages, 200 for good pages); `result.success` is always True and unreliable.
**Reads:** hardcoded 3-URL probe set.
**Writes:** `md/07_result_inspect_<timestamp>.md`.
**Called by:** CLI only.

### 08_garbage_edge_cases.py (122 LOC)

**Purpose:** Tests `is_garbage_content()` against known edge case URLs (consent-prefix sites, padded 404 pages) and baseline URLs. Scrapes raw and filtered content, runs garbage detection on both, tests header-zone (first 500 chars) detection for padded 404s.
**Reads:** hardcoded edge-case + baseline URL set.
**Writes:** `md/08_garbage_edge_cases_<timestamp>.md`.
**Called by:** CLI only.
**Gotcha:** its `from src.crawler.garbage_filter import is_garbage_content` fails on import since 2026-09-09 — `garbage_filter.py` was retired along with its only caller, `crawl_site.py` (zero callers, user decision in the Phase 4 control-flow review). This script itself was left untouched; it is a one-shot dev script, not maintained.

### 09_garbage_fix_prototype.py (202 LOC)

**Purpose:** Prototypes and validates garbage detection improvements — status_code based 404 detection, consent prefix stripping. Validates against edge case and baseline URLs to confirm no false positives.
**Reads:** hardcoded edge-case + baseline URL set.
**Writes:** `md/09_garbage_fix_prototype_<timestamp>.md`.
**Called by:** CLI only.
