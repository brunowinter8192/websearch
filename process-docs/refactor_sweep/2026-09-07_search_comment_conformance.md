# Comment-rule conformance for src/search/ (2026-09-07)

Phase 2 of the comment-rule conformance sweep (the first pass covered `src/scraper/`, see that
area's own entry in this same folder). Every comment line and docstring in `src/search/**/*.py`
(9 top-level modules, 9 `engines/` modules, 18 files total) was removed except the three allowed
section markers. Pure relocation-free deletion: no code line changed, no reformatting, zero
behavior change — 378 passed before and after.

## Verifying the all-DELETE triage before touching anything

Unlike the `src/scraper/` pass (which had DELETE/GOTCHA/ENTRY triage across multiple files), this
area's triage was "every hit is DELETE." Before implementing, every comment block in all 18 files
was read and cross-checked against `src/search/DOCS.md`, `src/search/engines/DOCS.md`, and the four
named process-docs areas (`browser_lifecycle`, `search_pipeline`, `engine_reduction`,
`engine_expansion`). Specific confirmations worth recording since they were the harder cases:

- `LOCK_HARD_BUDGET_S`'s `60+6+15` derivation and the `~7.25s`/`~7.1s` two-parallel-CLI-run
  measurement — found in `process-docs/browser_lifecycle/2026-08-25_milestone1_strict_serialization.md`,
  not just asserted in DOCS.md.
- `_record_own_pids`'s "trustworthy as ours only because the lock + pre-launch reap guarantee no
  foreign Chrome" claim — found in the same process-docs entry, lines 28-29, near-verbatim.
- Yandex's `_is_self_referential`'s "dot-separated hostname LABEL, not a raw substring" precision
  (guarding against a real `notyandex.com`-shaped false positive) — found in
  `process-docs/engine_expansion/yandex_wiring_2026-07-21.md`, which also names the specific bug
  (`yandex.com/video/preview/...` self-link) this filter exists to catch.
- `ENGINE_WATCHDOG_TIMEOUT`'s 6.0s-uniform rationale and the 138-workflow_summary-record
  measurement — found in `process-docs/search_pipeline/2026-08-25_uniform_engine_watchdog.md`.

This confirmed the triage was correct for 17 of 18 files' comments, with one exception surfaced and
handed back for a decision rather than resolved unilaterally (per the task's own instruction not to
decide gaps alone).

## The one gap: kill_own_chrome_atexit's asyncio-safety reasoning

`src/search/browser.py`'s `kill_own_chrome_atexit()` carried a 2-line comment: it is a sync wrapper
because `atexit` callbacks cannot be coroutines, and this is safe specifically because `atexit`
fires only after `asyncio.run()` in `cli.py`'s `main()` has already returned — i.e., no event loop
is running at that point. This exact reasoning was not found in `src/search/DOCS.md`,
`src/search/engines/DOCS.md`, or any of the four named process-docs areas, nor via a broader
repo-wide grep for "atexit". Flagged rather than deleted or preserved unilaterally. Resolution: add
one Gotcha bullet to `src/search/DOCS.md` capturing the reasoning plus its own future-maintenance
trigger ("if `cli.py` ever keeps a loop alive past `main()`, this wrapper must change"), then delete
the comment.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count. The AST-based scan script (module
docstrings, function/class docstrings, any comment line other than the three markers, and inline
trailing comments outside string literals) printed nothing for `src/search/`, confirmed twice — once
immediately after the comment deletions, once again as the final check after the DOCS.md LOC updates
touched nothing code-side. All 19 touched `.py` files' `wc -l` values were verified to match their
`src/search/DOCS.md`/`src/search/engines/DOCS.md` headings exactly, one file at a time, not by spot
check.
