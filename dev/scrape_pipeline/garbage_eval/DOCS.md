# dev/scrape_pipeline/garbage_eval/

## Role
Investigation and validation suite for `is_garbage_content()` garbage detection. Workflow: 07 discovers available `CrawlResult` metadata, 09 prototypes and validates fixes before production code changes. The former 08 (edge-case tests of `is_garbage_content()`) was deleted because that function was retired 2026-09-09.

## Modules

### 07_result_inspect.py (103 LOC)

**Purpose:** Inspects the full Crawl4AI `CrawlResult` object to discover available metadata fields. Scrapes 3 URLs (normal, 404, consent-heavy) and enumerates all result attributes with types and values. Key finding: `result.status_code` is available and reliable (404 for error pages, 200 for good pages); `result.success` is always True and unreliable.
**Reads:** hardcoded 3-URL probe set.
**Writes:** `md/07_result_inspect_<timestamp>.md`.
**Called by:** CLI only.

### 09_garbage_fix_prototype.py (202 LOC)

**Purpose:** Prototypes and validates garbage detection improvements — status_code based 404 detection, consent prefix stripping. Validates against edge case and baseline URLs to confirm no false positives.
**Reads:** hardcoded edge-case + baseline URL set.
**Writes:** `md/09_garbage_fix_prototype_<timestamp>.md`.
**Called by:** CLI only.

## Historical data
`md/08_garbage_edge_cases_20260331_193034.md` is the output of the deleted `08_garbage_edge_cases.py`; kept as a historical record, nothing reads it.
