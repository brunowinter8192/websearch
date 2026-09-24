# dev/logging/

## Role
Logging tooling: an AST-based audit over `src/` logger call-sites to identify misclassified log levels. Backs the logging area of process-docs. Log-janitor retention tests live in `dev/tests/`, not here.

## Public Interface
No `__init__.py` — not a package. The audit script is the entry point, run directly via `./venv/bin/python`.

## Flow
`src/` Python sources -> AST walk over logger call-sites -> markdown report under `md/`; path to stdout, progress to stderr.

## Modules

### 01_audit.py (115 LOC)

**Purpose:** Walks `src/` and emits one report row per logger call with location, level, and message template.
**Reads:** `src/**/*.py`.
**Writes:** `md/01_audit_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

---

## State
None. Successive reports in `md/` are compared by hand after a re-level pass.
