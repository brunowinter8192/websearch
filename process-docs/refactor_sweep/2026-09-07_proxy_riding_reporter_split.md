# Splitting proxy_riding/reporter.py by concern (2026-09-07)

`src/news/engine/proxy_riding/reporter.py` had grown to 424 LOC by mixing three concerns: metric
derivation from `RiderState`, matplotlib plot-file writing, and markdown rendering of `job.md`.
Pure relocation, zero behavior change: 378 passed before and after.

## Module boundary

`metrics.py` (160 LOC) took metric derivation: `_compute_stats` (the entry point
`write_riding_report` calls), `_compute_retry_outcome`, `_compute_pool_windows`,
`_compute_load_percentiles`, `_compute_connect_fail_stats`, `_distribution_stats`, and
`_BACKFILL_TOTAL`. `plots.py` (77 LOC) took the three matplotlib writers
(`_write_cumulative_plot`, `_write_load_hist`, `_write_cf_hist`) — these turned out to have zero
`proxy_riding`-internal dependency at all (pure functions of `job_dir: Path` + the `stats` dict),
so `plots.py` imports nothing from `state.py`. `reporter.py` (213 LOC) kept the orchestrator
(`write_riding_report`) plus the markdown-rendering concern (`_write_md` and its `_md_*` helpers,
`_fmt`) — the task allowed splitting markdown out too, but at 213 LOC post-extraction there was no
size reason to, and the `_md_*` functions are one coherent unit (format `stats` into `job.md`
lines) that reads naturally alongside the orchestrator that calls it.

## `_compute_stats`: 61 → 39 LOC

Extracted `_compute_fetch_counts(jobs, state, t_job_start) -> dict` — the per-fetch-record block:
`n_total_fetches`/`n_ok`/`n_regwall_fetches`/`n_failed`/`n_connect_fail`, elapsed-time
`mean_s`/`median_s`, `wall_s`/`urls_per_min`, `ok_completion_s`. This is everything derivable from
`jobs`/`t_job_start` alone (plus one `state.n_connect_fail` read), computed before any
ride/proxy/pool/load/connect-fail-specific work begins in the original function body — a real,
nameable sub-concern, not an arbitrary line cut. `_compute_stats` now does
`fetch_counts = _compute_fetch_counts(...)`, reads `fetch_counts["n_ok"]`/
`fetch_counts["n_regwall_fetches"]`/`fetch_counts["n_total_fetches"]` where it used to read local
variables of the same name, and spreads `**fetch_counts` into the returned dict — same keys, same
values, dict-equal to the pre-extraction return shape (dict key order is not part of the contract
here; every caller reads by key).

## Why no external re-pointing was needed

Every private symbol moved (`_compute_*`, `_write_cumulative_plot`, `_write_load_hist`,
`_write_cf_hist`, `_distribution_stats`, `_BACKFILL_TOTAL`) was already `reporter.py`-internal —
grep across `src/` and `dev/` before the move confirmed every external caller (`pipeline.py`,
`abort.py`'s late import, `dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py`,
`test_tail_race.py`) only ever touches `write_riding_report`, which stayed in `reporter.py`. Zero
files needed an import-path change as a result of this split.
`dev/news_pipeline/coindesk_proxy_riding/p4_reporter.py` has its own independent, already-diverged
local prototype copy (different fields, sibling-file import, no `src.` import at all) — same
duplicated-dev-prototype precedent already established elsewhere in this project, left untouched.

## Cycle check

`abort.py` late-imports `reporter.write_riding_report` specifically to avoid a cycle that would
otherwise exist through `rider.py` (which imports both `state.py` and `abort.py`) — this rationale,
recorded in `src/news/engine/proxy_riding/DOCS.md`'s own Gotchas before this split, does not change:
`reporter.py` now depends on `state.py` (directly, for the `RiderState` type hint) and on
`metrics.py`/`plots.py` (the former also depending on `state.py`, the latter depending on nothing
`proxy_riding`-internal). None of the three modules import `abort.py` or `rider.py`, so no new edge
was added back toward the cycle, and the late import remains necessary and sufficient. Verified
live: `smoke_stage1.py`'s Section-1 structural checks (import resolution for `rider`/`abort`/
`reporter`/`scrape`/`state`, `RidingScrapeConfig` defaults, `BROWSER_ELIGIBLE_PROTOS`, no
`sys.path.insert` in any of the three production modules, `"src.news.engine.proxy_riding.reporter"`
present in `abort.py`'s own source) all passed when run directly against this worktree — that
script's Sections 2/3 assume a different worktree's path layout and a live network scrape, and were
not run, being unrelated to this split.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count (no test added/removed — this module
has no dedicated `dev/tests/` coverage; the only regression risk was the import graph, checked
above). `./venv/bin/python -c "from src.news.pipeline import *; from
src.news.engine.proxy_riding.abort import *"` succeeded.
