# Shortening rider.py's _run_slot and _apply_fetch_result (2026-09-07)

`src/news/engine/proxy_riding/rider.py` had two functions over the 50-LOC threshold: `_run_slot`
(78 LOC) and `_apply_fetch_result` (57 LOC). Pure extraction inside the same module — no new file,
zero behavior change: 378 passed before and after, plus two offline dev test scripts re-run
directly (see Verification below).

## `_run_slot`: 78 → 48 LOC, in two extraction rounds

First extraction: `_next_url_for_slot(slot_id, state)` for the "take the next URL" block (queue
dequeue, dup-skip, empty-queue tail-race pick). The real hazard here — the one this session's task
prompt warned about explicitly — is that the original inline block has ONE bare `continue` (a stale
dequeued dup) and TWO bare `break`s (`all_resolved`; no open URL left to race), all meaningful only
in the caller's own `while` loop. Collapsing these into a single sentinel return (e.g. `None` for
"skip") would have silently turned the `continue` case into a `break`, since a `continue`/`break`
executed inside a helper function does not propagate to the caller's loop at all. The fix: return
an explicit 3-way `("continue"|"break"|"proceed", url, dequeued)` tuple, mirroring the sibling
`_apply_fetch_result`'s existing `"continue"/"append"/"break"` string-action convention already
used elsewhere in this file — the caller does `if action == "continue": continue` /
`if action == "break": break` explicitly, a mechanical 1:1 translation with no room for the
collapse-into-one-sentinel mistake.

Second extraction (needed because the first round only got `_run_slot` to 55 LOC, still over the
50-LOC target): `_fetch_and_build_job` (in-flight bookkeeping + the `_fetch_one_url` call +
`JobRecord` construction) plus a further composing helper, `_fetch_and_apply` (computes `ride_pos`,
calls `_fetch_and_build_job` then `_apply_fetch_result`, returns `(action, job)`). This is the same
pattern the `coindesk_discover_split` session used for `cursor_loop` two entries ago in this same
`refactor_sweep` area: extracting the four "obvious" candidates got close but not under the line
target, and a second, still-coherent extraction ("fetch this URL and dispatch its outcome" as one
named unit) closed the gap rather than trimming cosmetically.

## `_apply_fetch_result`: 57 → 21 LOC, split by status branch + dedup

The function's four branches (`ok`, `regwall`, `connect_fail`, and the `failed`/`empty` fallback)
became four separate one-status-each helpers (`_apply_ok_result`, `_apply_regwall_result`,
`_apply_connect_fail_result`, `_apply_generic_failure_result`), with `_apply_fetch_result` reduced
to a pure 4-branch dispatcher. On top of the per-branch split, the identical
`if dequeued and url not in state.done_urls: state.url_queue.put_nowait(url)` line — present
verbatim in 3 of the 4 original branches — was pulled into `_maybe_requeue(state, url, dequeued)`,
since once the branches were separate functions this was real, visible duplication rather than
four lines that happened to look similar.

## Verification: byte-identical log output, not just passing assertions

This module has no `dev/tests/` coverage (confirmed by grep), so the real regression risk was
silent behavior drift in a 300+-line async slot loop with no test asserting every log line. Two
independent checks: (1) `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py` — fully
offline/deterministic (`_fetch_one_url`/`_next_proxy` mocked, no network/browser) — run directly,
7/7 passed, and its own printed log lines (`"[slot 0] ok  r=1 https://cd.com/a"`,
`"[slot 0] failed fail=1/2 r=1 → requeue"`, etc.) were inspected against the original inline
branches' f-strings and matched verbatim. `test_3_no_spurious_requeue`'s sub-case A specifically
exercises the stale-dequeued-dup `continue` path this session's `_next_url_for_slot` extraction was
built around, and passed unchanged. (2) `dev/news_pipeline/coindesk_proxy_riding/test_sigint_report.py`
— also offline, exercises `_abort_interrupted` (untouched by this session) — run as a collateral
regression check, 2/2 passed. Neither script needed a patch-target change: both patch
`_fetch_one_url`/`_next_proxy`/`os._exit`/`POOL_REFRESH_INTERVAL_S` and call `_run_slot`/`_watchdog`
as black boxes; every new helper stays inside `rider.py` (no new module), so the defining-module-
globals constraint this package's own DOCS.md Gotchas already documented for `_run_slot`/`_watchdog`
continues to hold for the new helpers too.
