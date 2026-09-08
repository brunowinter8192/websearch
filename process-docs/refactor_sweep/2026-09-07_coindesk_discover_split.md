# Splitting coindesk/discover.py by concern (2026-09-07)

`src/news/platforms/coindesk/discover.py` had grown to 402 LOC by mixing three concerns: discover
orchestration/cursor paging, timeline-API access + session re-warm, and per-year discover shard
storage. Pure relocation, zero behavior change: 378 passed before and after; smoke check
(`import src.news.platforms.coindesk as c; from src.news.registry import *`) passed after.

## Module boundary

`timeline.py` (85 LOC) took timeline-API access + re-warm: `parse_articles`, `build_cursor_url`,
`fetch_feedpage`, `try_rewarm` (the last one's browser-re-warm fallback still calls
`browser.py:browser_load_feed`, unchanged). `shards.py` (64 LOC) took per-year discover shard
storage: `_append_to_shard`, `load_discover`, `load_discover_filtered` — this last function has no
`proxy_riding`-style consumer inside `discover.py` at all, so `__init__.py` was re-pointed to import
it directly from `shards.py` rather than keeping a re-export shim through `discover.py` (the task's
preferred option, taken since nothing else needed the shim). `discover.py` (300 LOC) kept discover
orchestration and cursor paging: `discover`, `_parse_stop_date`, `_CursorLoopStats`, `cursor_loop`
and its helpers, `_build_entry`, `_extract_section`, `_is_live_blog`.

## `cursor_loop`: 74 → 42 LOC, two rounds

First round extracted the four candidates the task suggested: `_maybe_proactive_rewarm` (the
proactive-rewarm block), `_maybe_log_checkpoint` (the checkpoint log line, condition folded into
the helper so the call site is one line), `_close_year_files` (the `finally`-block shard close),
`_log_cursor_loop_summary` (the final summary log). That got `cursor_loop` to 51 LOC — one line over
the 50-LOC target. Rather than trim cosmetically (deleting a blank line, which is not a real
sub-concern cut), a second extraction was made: `_advance_cursor` — wraps `_fetch_next_page` +
`_handle_cursor_exhaustion` + the "cursor exhausted with no body" stop check into one coherent
"advance to the next page, handling exhaustion/re-warm" unit, returning
`(headers, body_or_None, last_date, should_stop)`. This dropped `cursor_loop` to 42 LOC. One
behavior-preservation detail worth recording: in the two stop paths, `_advance_cursor` returns
`body=None`, which `cursor_loop` assigns to its own `body` variable right before `break` — this
reassignment is inert because `cursor_loop` never reads `body` again after the loop (only
`stats`/`all_entries`/`t_start` are read in the post-loop summary and return), so it does not change
observable behavior.

## Why no external re-pointing was needed beyond `__init__.py`

Grep across `src/`, `dev/`, and `cli.py` before the move found every non-`discover.py` caller only
ever imports `discover` (the async orchestrator) or `load_discover_filtered` — both public,
`_`-free names. All the moved private symbols (`parse_articles`, `build_cursor_url`,
`fetch_feedpage`, `try_rewarm`, `_append_to_shard`, `load_discover`) were already
`discover.py`-internal. `dev/news_pipeline/01_coindesk_discover.py`,
`dev/news_pipeline/run_pipeline.py` (subprocess-only reference, no import), and every
`dev/news_pipeline/exploration/*.py` script have their own independent standalone copies with
zero `src.` imports — the same duplicated-dev-prototype precedent already established for
`p4_reporter.py` and the `dev/browser_posture/`/`dev/scrape_pipeline/garbage_eval/` scripts in
earlier sessions of this same `refactor_sweep` area. `dev/tests/` has no coindesk-discover test at
all — confirmed by grep, matching the task's own expectation.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count (no dedicated test file for this
module — the only regression risk was the import graph and the `cursor_loop` behavior preservation,
both checked above). Smoke check
(`import src.news.platforms.coindesk as c; from src.news.registry import *`) succeeded, confirming
`__init__.py`'s re-pointed `load_discover_filtered` import and the module's registration
side-effect both still resolve.
