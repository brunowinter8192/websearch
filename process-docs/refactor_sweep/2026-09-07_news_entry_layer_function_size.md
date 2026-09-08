# Shortening the news entry layer's oversized functions (2026-09-07)

Three functions over the 50-LOC threshold in `src/news/pipeline.py` and `src/news/__main__.py`:
`run_scrape_only` (55 LOC), `_run_pipeline_proxy_pool` (66 LOC), `_add_core_args` (56 LOC). Pure
extraction inside the same two files — no new module, zero behavior change: 378 passed before and
after, plus a byte-identical `--help` diff (below).

## `_run_pipeline_proxy_pool`: the early-return-inside-try/finally hazard

This function's STAGE blocks (discover, dedup, scrape) sit inside a `try/finally` where `finally`
reads `len(new_entries)`/`n_ok` regardless of which `return False` fired. The task's own review
caught a real design choice here worth recording: the first draft had BOTH `_stage_discover_proxy_pool`
and `_stage_dedup_proxy_pool` return `None` as an abort sentinel, with the caller resetting
`new_entries = []` before returning in the dedup-abort case (since `finally` would otherwise call
`len(None)` and crash). Main's review replaced that with a simpler, more faithful design for the
dedup stage specifically: `_stage_dedup_proxy_pool` returns the REAL (possibly empty) `new_entries`
list unconditionally, and the caller keeps the original inline `if not new_entries: log + marker +
return False` check verbatim — no sentinel, no reset line, because `filter_new_entries` never
returns `None` in the first place, so introducing a `None` convention on top of it was an invented
indirection, not a fidelity requirement. The discover stage keeps its `None`-sentinel design
(`_stage_discover_proxy_pool`) because `platform.discover()`'s natural "found nothing" result
(`entries` falsy) genuinely has no better representation to hand back than a sentinel distinguishing
"aborted" from "the real, further-usable value" — but even there, `entries` is never read in
`finally`, so no reset was ever needed for that path either. The general lesson: prefer returning
the caller's own already-meaningful falsy/empty value over inventing a parallel sentinel, and only
reach for a sentinel when the real return type can't itself distinguish "nothing" from "stop".

Three helpers: `_stage_discover_proxy_pool`, `_stage_dedup_proxy_pool`, `_stage_scrape_proxy_pool`.
66 → 39 LOC.

## `run_scrape_only`: no control-flow hazard at all

Single extraction, `_scrape_only_preamble` (logging setup, `job_id`/`filter_desc`, both precondition
checks). Unlike the `_run_pipeline_proxy_pool` case, this block's two failure exits are
`sys.exit(1)`, not `return` — `SystemExit` propagates transparently through a function call
boundary, so no signal-back plumbing was needed at all. 55 → 41 LOC.

## `_add_core_args`: argument order preserved by construction

Split into `_add_run_mode_args` (`--source`/`--skip-index`/`--timeframe`/`--discover-only`/
`--scrape-only`) and `_add_date_filter_args` (`--year`/`--from`/`--to`/`--limit`), called from
`_add_core_args` in that exact order — `add_argument` call order, and therefore `--help` output
order, is unchanged by construction (not just by inspection). 56 → 4 LOC (`_add_core_args` is now a
pure 2-call dispatcher).

## Verification

`./venv/bin/python -m pytest -q`: 378 passed. `--help` diff: captured
`./venv/bin/python -m src.news --help` to a file BEFORE editing, re-captured the identical command
AFTER editing, `diff`'d the two — zero differences, confirming the argparse surface (flag order,
wrapping, help text) is byte-identical to what `integration` currently serves. Grep confirmed no
`dev/tests/` file imports `src.news.pipeline` or `src.news.__main__` (the one broad-pattern hit
during the initial grep was a false positive from an overly loose regex matching unrelated
`src.news.engine.proxy_pool.*` imports); `dev/news_pipeline/run_pipeline.py` is a fully independent
standalone script with its own `pipeline_workflow()`, no `src.` import — unrelated to this module
despite the shared name.
