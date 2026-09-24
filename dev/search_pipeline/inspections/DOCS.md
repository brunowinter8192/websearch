# dev/search_pipeline/inspections/

## Role
DOM-inspection tooling for engine selector-drift recovery: runs seven heuristics against a live engine page and writes a timestamped report. Use when a browser engine returns persistent EMPTY or TIMEOUT; not for one-shot debugging.

## Public Interface
No `__init__.py`. Run as `./venv/bin/python dev/search_pipeline/inspections/inspect_engine_dom.py <engine_name> "<query>"`.

## Flow
Engine config from the module-level registry and a live page load in, seven DOM heuristics and a diagnosis, Markdown report to `md/` out.

## Modules

### inspect_engine_dom.py (344 LOC)

**Purpose:** Navigates to an engine search page via the production browser and writes a seven-heuristic DOM report with diagnosis.
**Reads:** Module-level engine registry; live DOM via pydoll.
**Writes:** `md/<engine>_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.browser`.

---

## State
none.
