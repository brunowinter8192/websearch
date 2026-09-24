# src/

## Role

Root of the source tree. `log_janitor.py` and `death_pipe.py` are the two `.py` modules directly at this level — shared, domain-agnostic utilities used by the sub-packages below. All functional packages (`search/`, `scraper/`, `crawler/`, `news/`) live one level down, each with its own `DOCS.md`.

## Modules

### log_janitor.py (80 LOC)

**Purpose:** 90-day log retention janitor. On-write trigger with 1h marker-throttled slow path. Three public functions: `get_retention_days()` (env override — as of 2026-09-09 raises on an unparsable value instead of swallowing it, see Gotchas), `maybe_prune_jsonl(log_path)` (timestamp-based JSONL filter + atomic rewrite), `maybe_prune_sidecars(sidecar_dir)` (mtime-based `.md` unlink). `maybe_prune_jsonl`/`maybe_prune_sidecars` still log every failure as WARNING and swallow it, including one raised by `get_retention_days()` reached through them — only `cli.py`'s own direct call site is a real, uncaught tripwire.
**Reads:** JSONL log files, sidecar `.md` directories, `WEBSEARCH_LOG_RETENTION_DAYS` env var.
**Writes:** rewrites pruned JSONL atomically, unlinks stale sidecar files.
**Called by:** `src/search/query_logger.py`, `src/scraper/scrape_logger.py`, `cli.py` (imports `get_retention_days` for `TimedRotatingFileHandler` backupCount).
**Calls out:** none (stdlib only).

### death_pipe.py (82 LOC)

**Purpose:** Process-hygiene "net 2" — a crash backstop for any browser lane. `spawn_watchdog(pids, cleanup_dir=None)` forks a detached, minimal helper (this same file, re-invoked as `__main__`) connected to the caller only via a pipe; the helper blocks reading it and only wakes on EOF, which the OS delivers the instant the caller ends for ANY reason (clean exit, uncaught exception, or `SIGKILL` — a hard kill closes every fd the process held, no cooperation required). On wake, the helper kills any of `pids` still alive and removes `cleanup_dir` if given, then exits — a no-op (and completely silent, no log line) if the caller's own normal teardown already did that first. Reused by `chromium_process.py`'s own `_kill_by_profile` and pre-launch orphan reap for the identical terminate/kill primitive (`_terminate_then_kill`), not just for net 2 itself.
**Reads:** nothing at import time; `WEBSEARCH_DEATH_PIPE_LOG_PATH` env (fallback `src/logs/cli.log`) only when it actually has to log an intervention.
**Writes:** one line to `src/logs/cli.log` ONLY when it actually kills a PID or removes a dir (silent otherwise); no other state.
**Called by:** `src/search/browser.py` (`get_tab`, after `_record_own_pids`); `src/scraper/chromium_scrape.py` (`_acquire_cdp_headed`, after the cdp port resolves, via `spawn_watchdog`); `src/scraper/chromium_process.py` (`_kill_by_profile`/`_reap_orphaned_scrapes`, via `_terminate_then_kill`).
**Calls out:** `psutil` (terminate/wait/kill); no project-internal imports (deliberately — this module must start and run correctly even if something else in the codebase is broken).

## Gotchas

- **REMOVED 2026-09-09: `get_retention_days`'s silent fallback to 14 on an unparsable `WEBSEARCH_LOG_RETENTION_DAYS` — user decision, Phase 4 control-flow review.** No supporting observation existed: the env var is set nowhere in the repo (`cli.py`, skills, configs). An invalid value now raises `ValueError` at first use. `cli.py`'s own call (`backupCount=get_retention_days()`, module-load time, outside any try/except) is the real, uncaught tripwire — a typo now fails CLI startup immediately. The two internal call sites (`_prune_jsonl`/`_prune_sidecars`) are UNCHANGED and stay out of scope: both are reached only through `maybe_prune_jsonl`/`maybe_prune_sidecars`, which wrap their own call in a pre-existing, deliberate `except Exception as e: logger.warning(...)` — a `ValueError` surfacing through that path is still caught and merely logged, not a crash. This is a separate, already-documented fail-soft design (see this module's own Purpose line above), not touched by this removal.
- 2026-09-24 Phase 5: `log_janitor._prune_jsonl` keeps an unparseable line (with a warning) instead of dropping it in the rewrite. `death_pipe._log_intervention` no longer swallows `OSError` (in the detached child, a failing log path ends the helper), and `removed_dir` in the intervention line is true only when the directory is actually gone. the unused tmux spawn shell helper was deleted (no caller anywhere) together with its `.drift-whitelist.txt` names.
