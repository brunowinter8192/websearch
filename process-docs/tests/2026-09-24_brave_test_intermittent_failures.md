# Intermittent brave test failures in full-suite runs (2026-09-24)

Orchestrator record. No code changed for this. The owner decided on 2026-09-24: record it, no
issue.

## What was observed

`dev/tests/test_brave_engine.py` drives a real headless browser against local fixture pages. In
full-suite runs on 2026-09-24, one test in it failed intermittently. Different tests failed on
different runs, always a single failure, and every failing test passed when rerun alone or in the
next full run.

| When (2026-09-24) | Who ran it | Failing test | Suite result |
|---|---|---|---|
| baseline, before any change | worker wsweep2 | `test_unrelated_button_before_containers_never_leaks_into_success_diagnosis` | 475 passed, 1 failed |
| baseline, before any change | worker wgoogle | `test_light_dom_challenge_button_is_solved_and_returns_real_results` | 475 passed, 1 failed |
| mid Phase 2 comment sweep | worker wcli | one brave test (name not recorded) | 487 passed, 1 failed |
| after Phase 4 handler removal | worker wgoogle | one real-headless brave test | failed once, then passed |
| mid Phase 4 dev removals | worker wcli | one brave test | 491 passed, 1 failed |

Every other full run that day, more than 20 of them across five workers and the orchestrator,
passed completely. Rough rate from these numbers: a few percent of full runs.

`test_brave_engine.py` alone (13 tests at the time) passed every time it was run alone.

## The one concrete trace

After Phase 4 removed the `except Exception` in
`src/search/document_status.py::start_document_status_capture` (it logged a warning and degraded to
an empty status chain), the next failure carried a real exception for the first time:

```
websockets InvalidStatus: HTTP 500 "No such target id"
```

raised from `tab.enable_network_events()` inside `start_document_status_capture`.

Hypothesis, not proven: the tab the test is about to observe is already gone, or not yet
registered, when network events are enabled. Chrome answers with "No such target id". Several
brave tests share one browser process across the module, so the timing of a previous test's tab
teardown is the most likely variable. The earlier failures, before the handler was removed, fit
the same cause: the swallowed error left `document_status_chain` empty, and a test asserting on
the diagnosis then failed on the wrong field instead of showing the real exception.

## Production

`src/logs/cli.log*` (2026-08-31 to 2026-09-24) contain zero
`document-status capture setup failed` warnings. The old handler would have logged exactly that
line. The race has never been observed in real `search_web` runs. The removed handler therefore
stays removed: the standard does not allow a fallback for a condition only seen in the test
harness.

## If this is picked up

- Start by reproducing with only this file, many times in parallel:
  `pytest dev/tests/test_brave_engine.py -q` with a repeat count fixed before the run. Do not
  raise the count step by step.
- Check how the test module creates and closes tabs between tests. A fixture that gives each test
  its own tab and waits for the previous close would fit the hypothesis.
- Do not fix it by catching the exception in `src/`. The fix belongs in the test fixture.
