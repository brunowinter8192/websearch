# Shortening loop.py's run_loop and _execute_batch (2026-09-07)

`src/news/engine/proxy_pool/loop.py` had two functions over the 50-LOC threshold: `run_loop`
(62 LOC) and `_execute_batch` (57 LOC). Pure extraction inside the same module — no new file, zero
behavior change: 378 passed before and after.

## The real constraint: an order-sensitive `time.monotonic()` mock

Before touching anything, `dev/tests/test_proxy_pool.py` was read in full because its own comments
flagged the actual risk: `test_run_loop_refresh_swaps_pool_and_preserves_state` and
`test_run_loop_refresh_fresh_candidates_from_new_pool` patch
`src.news.engine.proxy_pool.loop.time` wholesale with a `MagicMock` whose `monotonic.side_effect`
is a fixed iterator of pre-counted values, and both tests document call-by-call, in their own
comments, exactly which line produces which value (startup `_last_refresh`/`_last_progress`,
per-iteration `now`, per-refresh-tick `_last_refresh`, and one `last_progress` update per
successful future inside the batch loop). Because the patch targets the whole `time` name at
module level, EVERY `time.monotonic()` call anywhere in `loop.py` consumes the next value from that
one shared sequence, in real program execution order — regardless of which function it's textually
inside. This made the extraction rule simple and mechanical: move each `time.monotonic()`-containing
block into its new function with no other statement added, removed, or reordered around it, and the
call still fires at the identical point in program order (Python resolves `time.monotonic` through
`loop.py`'s own patched module global, same object, whichever function calls it). Verified live, not
just by inspection — the full test suite was run after each function's extraction, and both
`test_run_loop_refresh_*` tests kept passing without any adjustment to their `side_effect` sequence.

## `_execute_batch`: 57 → 34 LOC

Extracted `_apply_future_outcome` — the per-future ok/dead/other branch, called once per future from
`_execute_batch`'s own `as_completed` loop. `wset`/`consec_fail`/`done`/`dead`/`batch_done`/
`batch_failed` are mutated in place (same objects, no rebinding needed). `buf` (rebound on
proxy-burn: `buf = [p for p in buf if p != key]`) and `last_progress` (reassigned on first-writer
ok/dead, the exact `time.monotonic()` call the test sequence depends on) are returned, and
`_execute_batch` rebinds its own locals: `buf, last_progress = _apply_future_outcome(...)`.

## `run_loop`: 62 → 45 LOC, in three extractions

`_maybe_refresh_and_refill` (refresh-if-due + refill-if-under-buffer_size, returns rebound
`pool`/`buf`/`last_refresh`) and `_run_batch_cycle` (consume the batch off `queue`, call
`_execute_batch`, requeue `batch_failed - batch_done`, returns rebound `buf`/`last_progress`) got
`run_loop` to exactly 50 LOC — not strictly "below 50". A third, smaller extraction closed the gap:
`_check_stall(now, last_progress, queue) -> bool` — the stall-log-and-signal block, which has a bare
`break` in the original inline code. Following the same pattern used for `rider.py`'s
`_next_url_for_slot` and `coindesk/discover.py`'s `_advance_cursor` two sessions ago in this same
`refactor_sweep` area, the helper returns an explicit boolean rather than trying to `break` from
inside itself (which would only exit the helper's own non-existent loop, not `run_loop`'s `while`);
the caller does `if _check_stall(...): break`.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count. No test needed a patch-target change:
`test_proxy_pool.py` patches `loop_module.fetch_url`/`loop_module.time`/`loop_module._sleep` — all
module-level attributes, untouched by moving code between functions within the same module.
