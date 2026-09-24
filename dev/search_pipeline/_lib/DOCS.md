# dev/search_pipeline/_lib/

## Role
Shared parser and text utilities for the `report_analysis/` scripts: single source of truth for the known-engine list, smoke-report parsing and snippet-text cleanup and scoring. Touch when the smoke report format or snippet heuristics change.

## Public Interface
`__init__.py` is empty. Callers import the two modules by package-relative name after putting `dev/search_pipeline/` on `sys.path`.

## Flow
A caller passes a smoke-report `Path` or raw snippet text in; the modules return parsed records, cleaned strings or scores. No I/O.

## Modules

### parse.py (116 LOC)

**Purpose:** Parses the pipeline-smoke report format into per-URL records with query, class, engines, previews, and per-engine snippets.
**Reads:** report `Path` passed by the caller.
**Writes:** Returns parsed records; no I/O.
**Called by:** `report_analysis/engine_distribution_analysis.py`, `report_analysis/snippet_quality_analysis.py`, `report_analysis/snippet_selection_simulator.py`.
**Calls out:** none beyond stdlib.

### text.py (85 LOC)

**Purpose:** EN+DE stopwords, bloat detection and stripping, and lexical-density scoring for snippet-quality comparisons.
**Reads:** raw snippet text passed by the caller.
**Writes:** returns strings, sets or floats; no I/O.
**Called by:** `report_analysis/snippet_quality_analysis.py`, `report_analysis/snippet_selection_simulator.py`.
**Calls out:** none beyond stdlib.

## State
none.
