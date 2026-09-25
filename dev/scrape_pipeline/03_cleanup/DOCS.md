# dev/scrape_pipeline/03_cleanup/

## Role
Reference artifact from the session that produced the scrape-cleanup skill, showing which cleanup patterns work on which content shapes. Not a maintained tool and not to be copied to production.

## Public Interface
No `__init__.py` — not a package. The script is a CLI entry point run via `./venv/bin/python`.

## Flow
Raw scraped markdown from `../02_raw_data/` -> pattern-based chrome removal -> cleaned markdown plus summary under `cleaned_data/`.

## Modules

### clean.py (277 LOC)

**Purpose:** URL-spanning cleanup of raw scraped markdown with generic and site-specific patterns.
**Reads:** `../02_raw_data/<ts>/`.
**Writes:** `cleaned_data/<ts>/` markdown and a byte-delta summary.
**Called by:** CLI only.
**Calls out:** none.

## State
`cleaned_data/` is the baseline consumed by `../04_overview_sweep/analyze.py`.
