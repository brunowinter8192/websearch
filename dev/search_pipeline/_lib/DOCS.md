# dev/search_pipeline/_lib/

## Role
Shared parser and text utilities for the `report_analysis/` scripts: single source of truth for `KNOWN_ENGINES`, smoke-report parsing and snippet-text cleanup and scoring. Touch when the smoke report format or snippet heuristics change.

## Public Interface
`__init__.py` is empty. Callers import `from _lib.parse import ...` and `from _lib.text import ...` after putting `dev/search_pipeline/` on `sys.path`.

## Flow
A caller passes a smoke-report `Path` or raw snippet text in; the modules return parsed records, cleaned strings or scores. No I/O.

## Modules

### parse.py (121 LOC)

**Purpose:** Parses the `pipeline_smoke_<ts>.md` report format into per-URL records with query, class, engines, previews and per-engine snippets.
**Reads:** report `Path` passed by the caller.
**Writes:** returns `list[dict]`; no I/O.
**Called by:** `report_analysis/engine_distribution_analysis.py`, `report_analysis/snippet_quality_analysis.py`, `report_analysis/snippet_selection_simulator.py`.
**Calls out:** none beyond stdlib.

### text.py (85 LOC)

**Purpose:** EN+DE stopwords, bloat detection and stripping, and lexical-density scoring for snippet-quality comparisons.
**Reads:** raw snippet text passed by the caller.
**Writes:** returns strings, sets or floats; no I/O.
**Called by:** `report_analysis/snippet_quality_analysis.py`, `report_analysis/snippet_selection_simulator.py`.
**Calls out:** none beyond stdlib.

### test_text.py (27 LOC)

**Purpose:** Standalone assertion script for `strip_bloat` with six regression cases.
**Reads:** none.
**Writes:** stdout or `AssertionError`.
**Called by:** CLI only (`./venv/bin/python dev/search_pipeline/_lib/test_text.py`).
**Calls out:** `_lib.text`.

---

## State
none.
