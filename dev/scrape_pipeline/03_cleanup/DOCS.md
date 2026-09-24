# dev/scrape_pipeline/03_cleanup/

## Role
Iterative-discovery artifact from the session that produced the `scrape-cleanup` skill — kept as reference for which cleanup patterns work on which content shapes. Not a maintained tool; do NOT copy to prod.

## Modules

### clean.py (269 LOC)

**Purpose:** URL-spanning cleanup of raw scraped markdown for RAG indexing. Reads files from `02_raw_data/<ts>/`, applies pattern set (pre-h1 chrome strip, skip-link strip, sphinx anchor strip, tail chrome strip, blank-line collapse) plus site-specific handlers (GitHub issue title anchor, HN top-nav strip).
**Reads:** `../02_raw_data/<ts>/` (scrape_pipeline root).
**Writes:** `cleaned_data/<ts>/<slug>_<hash>.md` per URL + `_summary.md` with byte deltas.
**Called by:** CLI only. `./venv/bin/python dev/scrape_pipeline/03_cleanup/clean.py`.

## Gotchas
Superseded by the `scrape-cleanup` skill for production use — this script is a historical reference for pattern discovery, not an actively maintained tool.
