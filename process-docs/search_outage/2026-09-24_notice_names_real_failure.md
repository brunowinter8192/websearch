# Degraded-run notice names the real failure (2026-09-24)

## Change

`src/search/search_web.py::_format_degraded_notice` now prints, per failing engine,
`name  STATUS  <shortened drop_reason>`, and the `Repair:` line is gated on the failure signature
instead of on "any ERROR_BROWSER". The earlier gate (`process-docs/search_pipeline/`, 2026-09-21)
is superseded. That gate was built from the 2026-09-21 incident alone.

## The two observed shapes (both from `src/logs/query_log.jsonl`, `engine_run`)

| shape | status | drop_reason (raw) | notice shows | repair line |
|---|---|---|---|---|
| 2026-09-21 08:41:49, Chromium bundle deleted | ERROR_BROWSER x4 | `Failed to get browser ws address: Cannot connect to host localhost:9256 ssl:default [Multiple exceptions: ...]` | `Failed to get browser ws address: Cannot connect to host localhost:9256` | yes |
| same record | TIMEOUT_WATCHDOG x3 | `asyncio.TimeoutError after 6.0s watchdog` | unchanged | (does not trigger it) |
| 2026-09-24 17:13Z, network refused | ERROR_BROWSER x7 | `Navigation to <url> failed: net::ERR_CONNECTION_REFUSED` | `Navigation failed: net::ERR_CONNECTION_REFUSED` | no |
| same records | ERROR_HTTP (openalex) | `502 Bad Gateway` | unchanged | no |

## Rules implemented

- Repair line only if some failing engine has status ERROR_BROWSER AND drop_reason starting with
  `BROWSER_NEVER_STARTED_PREFIX` ("Failed to get browser ws address"). Anything else, including
  ERROR_BROWSER with `None` or an unrecognised reason, gets no repair line (no guessing).
- Shortening: the ws-address reason is cut at ` ssl:default` (drops the multi-exception tail, keeps
  the port); `Navigation to <url> failed:` becomes `Navigation failed:` (the URL repeats the query);
  everything else passes through, capped at 120 chars. `None` gives a bare status.
- `drop_reason` is read with `.get`, so stats dicts without it still work.

## Tests

`dev/tests/test_search_web_degraded_notice.py`: fixtures rebuilt from the real records (both
2026-09-24 queries, the 2026-09-21 records). Exact-string assertions for both shapes. Run with
`-s` to see the formatted 2026-09-24 notice. One labelled hypothesis case: ERROR_BROWSER without a
recognised reason gets no repair line. Suite: 476 passed before, 479 after.

## Verification

Healthy live run (`search_web "python asyncio tutorial"`) printed no notice. The 2026-09-24 shape
cannot be reproduced on demand; its notice is shown by the test output.

## Gotcha for the next agent

Tool hooks in this environment reject piping a CLI into another command and reading back a redirected
CLI output with `cat` in the same call. Redirect in one call, read with Read in the next.

## Process notes (recap)

- Old tests failed to express the new gate: fixtures with ERROR_BROWSER and no drop_reason no longer
  produce a repair line by design. The three tests that asserted the repair line (techniker, bramfelder,
  prepend) had to be rebuilt on real drop_reasons. The `_stats` helper takes an optional third
  element (drop_reason) so the old status-only fixtures still work.
- The 2026-09-21 fixture uses port 9256 (record 08:41:49) for the exact-string test and 9296
  (record 08:40:45) for the techniker test. Ports differ per record; the notice keeps the port.
- Files touched: `src/search/search_web.py`, `dev/tests/test_search_web_degraded_notice.py`,
  `src/search/DOCS.md`, this file. DOCS.md LOC (409) matches `wc -l`.
- Not done: no live reproduction of the 2026-09-24 shape (cannot be forced); a live 09-21 repro
  (moving the chromium revision aside) was not repeated, the fixture comes from the real record.
