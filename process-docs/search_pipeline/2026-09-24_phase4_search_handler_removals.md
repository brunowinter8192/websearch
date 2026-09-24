# Phase 4: unobserved swallow handlers removed from src/search/ (2026-09-24)

Issue #47 control-flow review of `src/search/`, owner decisions applied. This entry records what a
successor needs to understand why these handlers are gone and what to do if their conditions appear.

## Rule applied

A fallback is only allowed when the triggering condition was actually observed and every path is
traceable. Anything unobserved goes to the tripwire: let the exception propagate. In this package the
propagated exception is already turned into a visible status by `_engine_with_timing` via
`_classify_engine_exception` (`KeyError`/`ValueError`/`JSONDecodeError` -> `ERROR_PARSE`, pydoll and
websocket errors -> `ERROR_BROWSER`, anything else -> `ERROR_OTHER`).

## Removed (no replacement handler)

- Every browser engine's `_extract_value`: `(KeyError, TypeError) -> None`. A CDP result without
  `value` (script threw, execution context destroyed during navigation) is now `KeyError`, a non-dict
  result `TypeError`. Before, both looked like "0 containers" and ended as a genuine-looking `EMPTY`.
- Every browser engine's `_diagnose`: `(JSONDecodeError, TypeError) -> keep blank defaults`. The JSON
  is this project's own `JSON.stringify` output.
- brave `_poll_state` and `_click_challenge_button`: same JSON handler, defaults were "zero state" and
  `False`.
- `cache.cache_read`: `Exception -> None`. A corrupt cache file used to read as a cache miss and the
  drilldown then told the user to rerun `search_web`.
- `document_status.start_document_status_capture`: `Exception -> warning, empty chain`.

Why they went: 0 `ERROR_PARSE` in 209 `engine_run` records; 0 log lines `Cache read error` and
`document-status capture setup failed` in the retained `cli.log` files (2026-08-31 .. 2026-09-24, root
logger at DEBUG). The logs never record CDP `Runtime.evaluate` responses, so "a script returned no
value" could not be observed either way.

## Kept, with reasons

- `query_logger.log_query` (`Exception -> WARNING`): reclassified as best-effort telemetry. Losing a
  log record does not change search results; deliberate posture. 0 hits in the logs.
- `search_web._prewarm_browser`: the fallback condition WAS observed, 6 times on 2026-09-21 (10:40,
  10:41, 10:45, 10:47, 11:56, 12:03): `DevToolsActivePort did not appear under <tmpdir> within
  10.0s`. Each run then showed `Engine browser error: Failed to get browser ws address: Cannot connect
  to host localhost:<port>` for the browser engines (status `ERROR_BROWSER`), followed by
  `close_browser failed (Chrome likely already dead): The browser is not running`, and only openalex
  returned results in the runs that had any. The old WARNING said "engines will retry individually";
  in 6 of 6 cases that retry did not recover. New wording: "Browser prewarm failed, browser engines
  are expected to fail individually, non-browser engines still run: <error>". Removing the handler
  instead would abort the whole run and lose the non-browser results.
- Other handlers classified A (status/report), D (cleanup/teardown) and E (`browser_lock` two-step
  sidecar protocol) stay; the full 34-row table is in the `refactor_sweep` entry of the same date.

## Expected behaviour change and how to read it

- A transient no-value or bad-JSON result inside an engine poll loop now ends that engine with
  `ERROR_PARSE` (or `ERROR_OTHER` for a bare `TypeError`) and a `drop_reason` in `query_log.jsonl`
  instead of silently polling on. Startpage is the most exposed, it polls across its form-submit
  navigation. Two real runs after the change (8 engines each) showed no such status. If one appears,
  read its `drop_reason` first and do not add a handler back without an observed trigger.
- `start_document_status_capture` failing (seen once in a real headless Chrome test as
  `websockets InvalidStatus: HTTP 500 "No such target id"` from `enable_network_events()`) now fails
  the engine call. In production logs this has never appeared.

## Guards

`dev/tests/test_search_control_flow_removals.py` (parametrized over the seven engines) and
`dev/tests/test_document_status.py::test_setup_failure_propagates_instead_of_degrading_to_an_empty_chain`.
