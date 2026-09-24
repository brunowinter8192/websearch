# Google goto-resolution drops are now counted and logged (2026-09-21)

## Problem
`_resolve_urls` in `src/search/engines/google.py` dropped results silently (debug log only) and the
engine status stayed `OK`. Over 173 logged engine_run records google was EMPTY in 65% of runs and OK in 29%,
with OK runs clustering at 7-9 results and 6 runs at exactly 1. A thinned page looked identical to a
genuine one.

## What was built
- `_resolve_one` returns `(result | None, reason | None)`; `_resolve_urls` returns `(results, stats)`.
- Reason keys (flat): `timeout` (curl_cffi `Timeout`), `request_error` (any other `RequestException`),
  `non_302_<status>`, `no_location`, `relative_location`, `duplicate_destination`.
- Stats: `{"found", "resolved", "dropped", "reasons": {key: count}}`, stored as
  `diagnosis.goto_resolution` on the success return and on the zero-results-after-resolution return.
  It flows into both `engine_run` and `workflow_summary` records with no change to `search_web.py`.
  When the page parsed zero results, it reads `found: 0`.
- `_log_drops` writes one WARNING per run when `dropped > 0`. `cli.py` configures the root logger at
  DEBUG to `src/logs/cli.log`, so it lands there.
- Not changed, by owner rule: `GOTO_RESOLVE_TIMEOUT_S`, the rate limiter, any concurrency or timing value.
- Not counted: containers the JS skips for no anchor/title (`_JS_PARSE` untouched).

## Tests
`dev/tests/test_google_goto_drops.py` (9 tests). Loopback via `dev/search_pipeline/_google_fixture.py`
for non_302, no_location, relative_location, duplicate, mixed arithmetic. `timeout` and
`request_error` use a stub session raising the curl_cffi exception immediately (no wait, no constant
patched). One test stubs the tab and browser functions and asserts the diagnosis key. Existing
`test_google_engine.py` was adapted to the tuple return. Suite: 475 passed + 1 failed
(`test_brave_engine.py::test_light_dom_challenge_button_is_solved_and_returns_real_results`) before;
485 passed after. The brave failure did not recur on the full run afterwards; it was not investigated.

## Verification (2026-09-21, one run)
`cli.py search_web "faltenbalg antriebswelle wechseln kosten werkstatt"`: google OK, 9 results,
`goto_resolution: {found: 9, resolved: 9, dropped: 0, reasons: {}}`. This run had no drops, so the
WARNING path was exercised only by the unit test, not live.

## Open observation (no action taken)
Whether drops are timeouts at 1.5 s cannot be judged until `reasons` accumulates in the log.
If `timeout` dominates, that is a timing question for the owner. No timing change was made.
