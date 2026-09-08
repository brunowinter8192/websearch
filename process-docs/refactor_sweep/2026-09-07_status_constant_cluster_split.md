# Splitting status.py's TIMEOUT_/ERROR_ constant clusters (2026-09-07)

`src/search/status.py` (14 LOC) held two prefix clusters (`TIMEOUT_*`, 3 constants; `ERROR_*`, 4
constants) alongside three ungrouped constants (`OK`, `EMPTY`, `RATE_SKIP`) — this sweep's rule
(two-or-more prefix clusters in one file split into one module per cluster) applied. Pure
relocation, zero behavior change: 378 passed before and after.

## Module split and the alias-collision reason

`status_timeout.py` (`TIMEOUT_WATCHDOG`/`TIMEOUT_NONCOOP`/`TIMEOUT_HTTPX`) and `status_error.py`
(`ERROR_BROWSER`/`ERROR_HTTP`/`ERROR_PARSE`/`ERROR_OTHER`) took the two clusters; `status.py` kept
`OK`/`EMPTY`/`RATE_SKIP`. `search_web.py`'s existing `from src.search import status as S` import
was kept as-is for the three constants that stayed, and two more short aliases were added
(`status_timeout as ST`, `status_error as SE`) rather than switching to bare-name imports —
`search_web.py` uses `status` as a local variable name extensively (`_run_engine_fanout`,
`_query_engines_concurrent`, `_engine_with_timing` all unpack a `status` value from their fanout
tuples), which is exactly why the original import was aliased to `S` rather than imported bare in
the first place; the two new modules follow the same precedent for the same reason.

## One real consumer beyond search_web.py, found by grepping dev/

`dev/search_pipeline/no_google_burst_smoke.py` also does `from src.search import status as S` (a
pre-existing dev script that already imports several `src.search.*` modules directly — not a new
dev/src-import violation introduced by this task) and uses `S.TIMEOUT_WATCHDOG`/`S.TIMEOUT_HTTPX`/
`S.ERROR_BROWSER`/`S.ERROR_HTTP` — all four moved. Fixed with the identical two-alias pattern. Every
other `dev/search_pipeline/*.py` hit on these constant names (`stage1_pool_fetch.py`,
`11_pipeline_smoke.py`, `branch_probe.py`, `acquire_probe.py`, `pooling_probe.py`,
`engine_health_audit.py`, `inspect_query_log.py`, `cdp_starvation_probe.py`,
`24_pydoll_teardown_verify.py`) uses them as plain string literals (dict keys, comparisons,
comments) — never imported from `status.py` — confirmed by grep before touching anything, no
change needed. `dev/tests/test_query_logger.py` and `cli.py` have zero references to `status.py`.

## Incidental DOCS.md corrections

Two pre-existing drifts were fixed while updating the lines this task already required touching:
`status.py`'s "Called by" line named `src/search/engines/` as a caller, but grep found zero imports
of `status.py` anywhere under `engines/` — dropped and replaced with the two real callers.
`search_web.py`'s own heading LOC was updated to its real post-edit count (379, not 377) rather than
the pre-edit value, since the two new import lines this task added change that count too.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count. Live import check confirmed every
constant resolves from its new module (`from src.search.status import OK, EMPTY, RATE_SKIP`, etc.)
and `search_web_workflow` itself still imports cleanly. A repo-wide grep for the old `S.TIMEOUT_*`/
`S.ERROR_*` access path after the edit returned zero hits.
