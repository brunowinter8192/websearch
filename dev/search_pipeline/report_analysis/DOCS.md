# dev/search_pipeline/report_analysis/

## Role
Offline analysis of existing artifacts: pipeline-smoke reports (engine slot distribution, snippet quality and selection) and the query log (engine health, summary). No live engine calls. Touch to interpret past smoke baselines; not for production logging.

## Public Interface
No `__init__.py`. Entry scripts run as `./venv/bin/python dev/search_pipeline/report_analysis/<script>.py`; three import the shared parser and text helpers from `../_lib/` via a `sys.path` insert.

## Flow
Scripts read the newest `../md/pipeline_smoke_*.md` (or `src/logs/query_log.jsonl`), compute aggregates, and write Markdown to `../md/` or stdout. Shared parsing and text helpers come from `../_lib/`.

## Modules

### engine_distribution_analysis.py (287 LOC)

**Purpose:** Per-engine slot-count and slot-share analysis over the newest pipeline-smoke baseline.
**Reads:** newest `../md/pipeline_smoke_*.md`.
**Writes:** `../md/engine_distribution_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### snippet_quality_analysis.py (371 LOC)

**Purpose:** Per-source bloat and lexical-density analysis of snippets from the newest pipeline-smoke baseline.
**Reads:** newest `../md/pipeline_smoke_*.md`.
**Writes:** `../md/snippet_quality_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### snippet_selection_simulator.py (189 LOC)

**Purpose:** Dry-run of snippet selection over the smoke baseline: scores each source, picks the best, reports floor cases.
**Reads:** newest `../md/pipeline_smoke_*.md`.
**Writes:** `../md/snippet_selection_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### engine_health_audit.py (178 LOC)

**Purpose:** Aggregates per-engine status counts from the query log and classifies each engine BROKEN, DEGRADED, SLOW, RATE_LIMITED or OK.
**Reads:** `src/logs/query_log.jsonl`.
**Writes:** `../md/<report>.md`.
**Called by:** CLI only (`--last`, `--since`, `--engine`).
**Calls out:** stdlib only.

### inspect_query_log.py (94 LOC)

**Purpose:** Quick summary of the query log: record counts, wall-time stats, bottleneck engines, latest query breakdown.
**Reads:** `src/logs/query_log.jsonl` (path via `--log-path`, env or default).
**Writes:** stdout only.
**Called by:** CLI only (`--tail`, `--log-path`, `--all-types`).
**Calls out:** stdlib only.

---

## State
none.
