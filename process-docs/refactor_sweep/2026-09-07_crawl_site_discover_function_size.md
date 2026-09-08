# Shortening crawl_site.py's discover_urls_playwright (2026-09-07)

`src/crawler/crawl_site.py`'s `discover_urls_playwright` was 54 LOC, over the 50-LOC function
threshold. Pure extraction inside the same file — no new module, zero behavior change: 378 passed
before and after.

## Correction to the task's caller assumption

The task prompt named `cli.py` as a caller to check. Grep found zero references to `crawl_site.py`
or `discover_urls_playwright` anywhere in `cli.py`. `src/crawler/DOCS.md`'s own Role section already
states why: `crawl_site.py` is one of "two standalone entry modules — neither is a `cli.py`
subcommand" (only `discovery.py` backs a real `cli.py` subcommand, `discover_urls`); `crawl_site.py`
runs standalone via its own `if __name__ == "__main__":` block. The only real caller of
`discover_urls_playwright` is `crawl_site_workflow`, in the same file. Worth recording since this is
the second time in this `refactor_sweep` area that a task prompt's caller list needed a grep-verified
correction rather than a blind trust (the `dev/scrape_pipeline/garbage_eval/08_garbage_edge_cases.py`
case, earlier in this same area, was the first).

## Two extractions (matching the task's two suggested candidates)

`_pop_batch(frontier, concurrency, max_depth)` — the inner "pop up to `concurrency` frontier entries
within `max_depth`" while-loop. The `if not batch: continue` check stays in the caller, since it
belongs to the OUTER loop and sits outside the extracted block — no loop-control hazard here at all
(unlike several other functions extracted earlier in this sweep).

`_build_discovery_stats(frontier, page_latencies, four_two_nine_count, stop_reason)` — the
stop_reason resolution + final stats-dict construction, at the end of the function.

Extracting only the batch-pop helper got the function to exactly 50 LOC — not strictly below the
threshold — so both extractions were done together, landing at 42 LOC. Same two-extraction pattern
this `refactor_sweep` area has now used repeatedly (`cursor_loop`, `run_loop`, `_run_slot`, and now
`discover_urls_playwright`) whenever the first "obvious" cut alone wasn't quite enough.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count — no test under `dev/tests/`
references `discover_urls_playwright` at all (confirmed by grep, matching the task's own
expectation).
