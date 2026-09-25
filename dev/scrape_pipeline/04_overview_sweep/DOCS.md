# dev/scrape_pipeline/04_overview_sweep/

## Role
Empirical sweep of Crawl4AI filter dimensions against the Q24 URL set, scored against a clean-raw baseline. Touch it to re-rank filter configurations; the matrix itself lives in `sweep_config.yml`.

## Public Interface
No `__init__.py` — not a package. Both scripts are CLI entry points; run the sweep first, then the analysis.

## Flow
`sweep_config.yml` plus Q24 URL set -> sweep scrapes every config -> analysis diffs each config against the cleaned baseline -> ranked analysis report.

## Modules

### sweep.py (268 LOC)

**Purpose:** Runs every configuration of the sweep matrix against the Q24 URL set.
**Reads:** `sweep_config.yml`, Q24 URL set.
**Writes:** `sweep_data/<ts>/` per-config markdown and run metadata.
**Called by:** CLI only.
**Calls out:** `crawl4ai`, `yaml`.

### analyze.py (344 LOC)

**Purpose:** Scores each sweep candidate against the clean-raw baseline and ranks configurations with drill-down diffs.
**Reads:** `sweep_data/<ts>/`, baseline from `../03_cleanup/cleaned_data/`.
**Writes:** `sweep_data/<ts>/_analysis.md`.
**Called by:** CLI only.
**Calls out:** none.

## State
None beyond `sweep_data/`. Scoring caveat: process-docs area scrape_pipeline.
