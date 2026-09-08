# Shortening search_web.py's search_web_workflow (2026-09-07)

`src/search/search_web.py`'s `search_web_workflow` was 52 LOC, over the 50-LOC function threshold.
Pure extraction inside the same file — no new module, zero behavior change: 378 passed before and
after.

## One extraction sufficed, chosen over the larger candidate

The task offered two candidates: the full timed post-processing tail (pool build, cap, format,
cache write — everything after the `try/finally` fan-out) or just the final timings-dict assembly.
The smaller cut was taken — `_build_search_result(formatted_text, with_timings, engine_fanout_ms,
engine_ms, engine_details, pool_build_ms, cache_write_ms, total_ms)`, wrapping the
`[TextContent]`-or-`(result, timings)` return-value construction — because it alone got the
function from 52 to 43 LOC, with a single, cleanly nameable responsibility ("build the workflow's
return value"), rather than reaching for the much larger tail extraction (which would have needed a
13-parameter helper) when it wasn't necessary. The `try/finally` around the fan-out (with
`kill_own_chrome()`) and the pool-build/cap/format/cache-write block stayed untouched in the
orchestrator, exactly as the task required.

## Incidental DOCS.md correction

`src/search/DOCS.md`'s `search_web.py` heading said "364 LOC" while the actual file was 361 LOC
before this edit — a pre-existing 3-line drift from an earlier untracked change. Since this task
already required updating that heading to the new post-extraction LOC, the corrected real value
(377) was used rather than perpetuating the old, already-wrong baseline.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count. Every monkeypatch in
`dev/tests/test_query_logger.py` was confirmed (by reading, before editing) to target
`search_web.ENGINES`/`_DEFAULT_ENGINES`/`cache_write` — none of the timed-tail internals this
extraction touched — so no patch-target change was needed or made.
