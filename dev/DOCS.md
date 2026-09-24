# dev/

## Role
Development scripts (probes, smokes, evals) organized one subdirectory per area, each with its own DOCS.md. This directory holds no scripts of its own, except the shared package `_lib/`. Touch it to find the right area; do not add area-specific code here.

## Public Interface
No `__init__.py` — not a package. Each area's scripts are run directly via `./venv/bin/python`.

## Flow
Area scripts import from `src/` or run standalone -> write reports into their own area subdirectories (`md/`, `csv/`, `01_reports/` and similar) -> findings go to `process-docs/<area>/`.

## Modules
None at this level. Area subdirectories: access_recovery, agentic_discovery, browser_posture, brave_return, camoufox_lane, engine_reduction, explore_pipeline, lane_choice, logging, mojeek_return, news_pipeline, pipe_scraper_hardening, scrape_pipeline, search_pipeline, tests, url_discovery. `_lib/` is the dev-wide shared package; check it before writing an OS-level launch or process-control primitive inline in a probe.

## State
None.
