# dev/scrape_pipeline/04_overview_sweep/

## Role
Empirical sweep of Crawl4AI filter dimensions (PruningContentFilter at thresholds 0.30/0.48/0.60/0.75 + BM25ContentFilter, `content_source` ∈ {cleaned_html, fit_html, raw_html}, `excluded_selector` ∈ {cookies, cookies+sphinx}) against the Q24 URL set — 36 configs × 20 URLs = 720 outputs, scored against a clean-raw baseline.

## Modules

### sweep.py (264 LOC)

**Purpose:** Runs all 36 filter-dimension configs against the Q24 URL set.
**Reads:** `sweep_config.yml`, Q24 URL set.
**Writes:** `sweep_data/<ts>/<config_name>/<slug>_<hash>.md` per URL + `_run_metadata.json` with timing/sizes.
**Called by:** CLI only.

### analyze.py (340 LOC)

**Purpose:** Diffs each sweep candidate against the clean-raw baseline (latest `../03_cleanup/cleaned_data/`), computes line-set recall/precision/F1 per (config, URL), aggregates per config (median + per-shape), generates cross-config ranking + per-shape breakdown + unified_diff drill-down for top-3 configs. F1 is symmetric — chrome retention and content loss reduce it equally; for asymmetric preferences (e.g. "strip more chrome at cost of detail"), read `precision` separately and inspect the drill-down diffs.
**Reads:** `sweep_data/<ts>/`, `../03_cleanup/cleaned_data/` baseline.
**Writes:** `sweep_data/<ts>/_analysis.md`.
**Called by:** CLI only.

## Gotchas
`sweep_config.yml` defines the 36-config matrix — module-specific config, not shared. F1 symmetry caveat above applies to all rankings produced by `analyze.py`.
