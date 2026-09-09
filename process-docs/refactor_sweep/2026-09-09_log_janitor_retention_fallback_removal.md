# Removal of the silent default in log_janitor.py::get_retention_days (2026-09-09)

Seventh Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal, the proxy_riding abort stub removal, the engine `search()` wrapper removal, the
camoufox raw-HTML fallback removal, the engine `_parse_results` JSON-handler removal, and the bing
`_clean_url` decode-fallback removal for the six before it). `get_retention_days` parsed
`WEBSEARCH_LOG_RETENTION_DAYS` via `int(os.environ.get(..., 14))` and on `ValueError`/`TypeError`
silently returned 14 — a value produced by a second, degraded way whenever the env var was set but
malformed. The user ordered its removal: the env var is set nowhere in the repo (`cli.py`, skills,
configs), so the handler had zero real trigger.

## What changed

```python
def get_retention_days() -> int:
    return int(os.environ.get("WEBSEARCH_LOG_RETENTION_DAYS", 14))
```
The `try/except (ValueError, TypeError): return 14` is gone. An unparsable value now raises
`ValueError` at the first call.

## Callers and the asymmetric tripwire (a finding worth recording, not a defect)

Reading `cli.py` and `log_janitor.py` in full surfaced an asymmetry in how the new exception
actually surfaces:

- `cli.py` calls `get_retention_days()` directly at module-load time
  (`backupCount=get_retention_days()`), outside any try/except — this is the real, uncaught
  tripwire. A malformed env value now crashes CLI startup immediately.
- `log_janitor.py`'s own two internal call sites (`_prune_jsonl`, `_prune_sidecars`) are each
  reached only through `maybe_prune_jsonl`/`maybe_prune_sidecars`, which wrap their call in a
  pre-existing, deliberate `except Exception as e: logger.warning(...)` (already documented in
  `src/DOCS.md`'s Purpose line as this module's own fail-soft design). A `ValueError` from
  `get_retention_days()` reached through that path is still caught and merely logged as a warning,
  not a crash.

This was reported to Main during planning and left untouched — the task's own scope was
`get_retention_days` alone ("nothing else changes"), and the `maybe_prune_*` swallow is a separate,
already-intentional design, not itself examined for its own defensibility in this task.

## Tests

`src/log_janitor.py` had zero test coverage before this task (confirmed: no `dev/tests/
test_log_janitor.py` existed; `dev/logging/` holds an unrelated dev-script mirror with its own
independent copy of `get_retention_days`, explicitly out of scope). New file
`dev/tests/test_log_janitor.py` (17 LOC) adds the module's first coverage: one test confirms the
default (14) when the env var is unset, one confirms `pytest.raises(ValueError)` when it is set to
a non-integer string. Full suite: 365 (baseline) + 2 = 367, confirmed by
`./venv/bin/python -m pytest -q`.

## Docs

`src/DOCS.md` gained its first Gotchas section (none existed before), with one bullet documenting
the removal, the evidence, and the asymmetric-tripwire finding above; `log_janitor.py`'s Purpose
line was adjusted to note that `get_retention_days` no longer swallows while
`maybe_prune_jsonl`/`maybe_prune_sidecars` still do; LOC updated (82→79). `dev/tests/DOCS.md`
gained a `test_log_janitor.py` entry and added `src/log_janitor.py` to its Role paragraph's
coverage list.
