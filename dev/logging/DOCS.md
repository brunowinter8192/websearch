# dev/logging/

## Role
Logging tooling: AST-based audit over `src/` logger call-sites (identify misclassified log levels). Backs `process-docs/logging/`. The log_janitor retention tests live in `dev/tests/test_log_janitor.py`.

## Modules

### 01_audit.py (115 LOC)

**Purpose:** AST walker over `src/`; emits one row per `logger.X()` / `logging.X()` call with file:line, logger object name, current level, and message template (truncated to 120 chars).
**Reads:** `src/**/*.py` source files.
**Writes:** MD report to `md/01_audit_<ts>.md`. Prints report path to stdout; scan progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/logging/01_audit.py`.

## Gotchas
- Re-run `01_audit.py` after a call-site relevel pass to verify target categories moved off WARNING — compare successive `md/01_audit_<ts>.md` reports.
