# dev/logging/

## Role
Logging tooling: AST-based audit over `src/` logger call-sites (identify misclassified log levels) + test suite for the log_janitor retention algorithm (mirrors `src/log_janitor.py`). Backs `process-docs/logging/`.

## Modules

### 01_audit.py (119 LOC)

**Purpose:** AST walker over `src/`; emits one row per `logger.X()` / `logging.X()` call with file:line, logger object name, current level, and message template (truncated to 120 chars).
**Reads:** `src/**/*.py` source files.
**Writes:** MD report to `md/01_audit_<ts>.md`. Prints report path to stdout; scan progress to stderr.
**Called by:** CLI only. Run: `./venv/bin/python dev/logging/01_audit.py`.

---

### p1_log_janitor.py (82 LOC)

**Purpose:** Dev-isolated mirror of `src/log_janitor.py`. Stdlib-only. Provides `maybe_prune_jsonl`, `maybe_prune_sidecars`, `get_retention_days`.
**Reads:** JSONL log files, sidecar files, marker file mtimes (via caller).
**Writes:** Pruned JSONL files, deleted sidecar files, marker files (returned to caller, not written directly).
**Called by:** `01_prune_test.py`.

---

### 01_prune_test.py (104 LOC)

**Purpose:** Self-contained synthetic prune test. Creates a temp dir, writes 5 JSONL entries (2 × 20d-old, 3 × 2d-recent) + 3 sidecar files (2 × mtime 20d-ago, 1 recent), runs three scenarios (slow-path fires without marker; fast-path skip with recent marker; stale marker re-fires slow-path), asserts outcomes, exits 0 on all-pass / 1 on any failure.
**Reads:** Synthetic temp-dir fixtures it creates itself.
**Writes:** stdout PASS/FAIL lines, exit code.
**Called by:** CLI only. Run: `./venv/bin/python dev/logging/01_prune_test.py`.

## Gotchas
- Re-run `01_audit.py` after a call-site relevel pass to verify target categories moved off WARNING — compare successive `md/01_audit_<ts>.md` reports.
