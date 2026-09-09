# Removal of the stub job.md fallback in proxy_riding's abort.py (2026-09-09)

Second Phase 4 control-flow removal, following the pipe_scraper curl_cffi fallback removal (see
that same area's own entry in this folder). `_abort_write_report_and_exit`
(`src/news/engine/proxy_riding/abort.py`) wrote a minimal hand-built `job.md` from `state` in its
`except Exception` branch whenever the real `write_riding_report` call raised — a second way to
produce the same artifact. The user classified this as a fallback and ordered its removal, keeping
only the tripwire: the WARN line naming the reporter exception on stderr, `sys.stderr.flush()`,
and `os._exit(exit_code)`. A missing `job.md` after an abort is now the honest signal that the
reporter itself failed.

## What changed

`_abort_write_report_and_exit`'s inner `try`/`except` that built the stub (title from a per-caller
`fallback_title`, termination, the four counters, the reporter error, wrapped in its own
`except Exception as write_exc` in case even the stub write failed) was deleted outright. The
`fallback_title`/`extra_fields` parameters existed only to feed that stub, so both were removed
from the function's signature and from all three callers (`_abort_done`, `_abort_interrupted`,
`_abort_stall`). `_abort_stall`'s `idle_s` value used to also land in `extra_fields`; nothing was
lost by dropping that, since `_abort_stall`'s own `print(...)` already puts `idle_s` on stderr
independently.

## Baseline check on the two offline dev scripts

Per the task's own instruction, both `dev/news_pipeline/coindesk_proxy_riding/test_sigint_report.py`
and `smoke_stage1.py` were run before and after the change, since neither lives under `dev/tests/`
and both exercise `abort.py` indirectly.

- `test_sigint_report.py`: 2/2 passed both before and after — both its tests build a valid
  `RiderState` with real job/ride data, so `write_riding_report` succeeds for real and the
  reporter-failure branch (the one this task touched) is never exercised.
- `smoke_stage1.py`: 1/3 passed both before and after, identically — section 2
  (`test_watchdog_deterministic`) fails with `TypeError: RiderState.__init__() missing 2 required
  positional arguments: 'job_dir' and 'target_urls'`, a stale `RiderState(...)` construction that
  predates those two fields becoming required (unrelated to this task, not touched by it); section
  3 (`test_live_run`) fails on a missing local `data/news/coindesk/inventory` directory, a
  real-data/live-network section this sandboxed environment cannot satisfy regardless of any code
  change. Both failures are pre-existing and out of scope for this task, confirmed identical
  before and after the edit — not fixed here.

## Tests

No existing `dev/tests/` file covered `src/news/engine/proxy_riding/` at all before this task —
its only prior coverage lived in the offline dev scripts above. A new file,
`dev/tests/test_proxy_riding_abort.py` (43 LOC), adds the package's first pytest coverage: one
test, `test_abort_stall_writes_no_job_md_on_reporter_failure`, monkeypatches
`reporter.write_riding_report` to raise and `abort.os._exit` to a no-op recorder (the same
"patch the shared `os` module object" convention the existing dev scripts already use), builds a
minimal `RiderState` from the module's own required fields (`url_queue`, `proxy_pool`,
`cooldown_mgr`, `output_dir`, `job_dir`, `burn_threshold`, `page_timeout_ms`, `total_urls`,
`target_urls`), and asserts no `job.md` was written, the WARN line landed on stderr, and
`os._exit(1)` was still called. Full suite: 365 (baseline) + 1 = 366, confirmed by
`./venv/bin/python -m pytest -q`.

## Docs

`src/news/engine/proxy_riding/DOCS.md`'s `abort.py` entry (Purpose/Reads/Writes, LOC 90→54) was
rewritten to describe the tripwire instead of the stub, and a new Gotcha bullet documents the
removal in full — what existed, why it was removed (the same "output by a second method is a
fallback" framing as the pipe_scraper removal), and what replaced it — per this project's rule
against deleting history silently. `dev/tests/DOCS.md` gained the new test file's entry and added
`src/news/engine/proxy_riding/` (abort.py only, as of 2026-09-09) to its Role paragraph's coverage
list.
