# dev/

## Role
Development scripts — probes, smokes, and evals — organized one subdirectory per area, each with its own `DOCS.md` (`access_recovery/`, `agentic_discovery/`, `browser_posture/`, `camoufox_lane/`, `engine_reduction/`, `explore_pipeline/`, `lane_choice/`, `logging/`, `mojeek_return/`, `news_pipeline/`, `pipe_scraper_hardening/`, `scrape_pipeline/`, `search_pipeline/`, `tests/`, `url_discovery/`). This directory holds no scripts of its own; `_lib/` is the one exception — the only package shared across every area.

## Shared code
`_lib/` (own DOCS.md) — dev-wide shared primitives, importable from any area (see `_lib/DOCS.md` for the import pattern). Currently holds `browser_launch.py`: backgrounded Chrome launch + focus-steal reclaim watchdog + teardown. Before writing a new area-local `_lib.py`/`_lib/`, or reimplementing an OS-level launch/process-control primitive inline in a probe, check here first — a dev-wide need belongs in `dev/_lib/`, not duplicated per area.
