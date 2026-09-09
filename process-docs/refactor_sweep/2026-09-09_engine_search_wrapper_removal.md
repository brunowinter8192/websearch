# Removal of the exception-swallowing search() wrappers in src/search/engines/ (2026-09-09)

Third Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal and the proxy_riding abort stub removal for the two before it). Every engine in
`src/search/engines/` (`bing`, `brave`, `duckduckgo`, `google`, `openalex`, `scholar`, `startpage`,
`yandex`) defined its own `search()` as `try: results, _, _ = await self.search_with_reason(...);
return results; except Exception as e: logger.error(...); return []`. Production
(`search_web.py::_engine_with_timing`, both its timed and untimed branches) calls only
`search_with_reason` directly — `search()` was never on the production path at all. The user
classified the wrapper as silent exception swallowing, a code-standards violation (no try/except
may hide an error affecting business logic), and ordered its removal across all eight engines.

## The openalex.py finding

Before touching anything, `openalex.py`'s own `search()` was read in full to check whether it
might be the PRIMARY implementation rather than a wrapper (all the fetch/parse logic for other
engines lives in `search_with_reason`, and `openalex.py`'s `search_with_reason` already held all
of its own real logic too). It turned out to be neither the primary implementation nor the
swallowing wrapper — it was already the bare delegation (`results, _, _ = await
self.search_with_reason(...); return results`) with **no** try/except, identical in shape to what
the new base-class method now provides. Deleting it was a pure no-op for behavior: the inherited
method does exactly what this override already did, character for character. No other change was
needed in `openalex.py` to satisfy the inverted `BaseEngine` contract, since it already implemented
`search_with_reason`.

## What changed

`BaseEngine` (`base.py`) inverted its composition: `search_with_reason` is now the abstract method
(every engine's real logic already lived there), and `search()` is the one concrete base method — a
plain delegation with no try/except. An exception from any engine's `search_with_reason` now
propagates through `search()` unchanged. The seven wrapper bodies (`bing`, `brave`, `duckduckgo`,
`google`, `scholar`, `startpage`, `yandex`) and openalex's redundant bare delegation were all
deleted; nothing else in any of the eight engine modules changed.

## Caller check

`grep -rn "\.search(\|def search(" src cli.py` found every `def search(` hit was one of the 9
definitions being touched (8 engines + `base.py`) and every other `.search(` hit was an unrelated
regex `.search(...)` call in `crawler`/`news` modules (e.g. `DATE_RE.search(...)`) — zero
production callers of `engine.search(...)` anywhere in `src/` or `cli.py`. `search_web.py`
confirmed calling only `engine.search_with_reason(...)` in both `_engine_with_timing` branches.
The offline dev scripts under `dev/search_pipeline/` (`01_google_smoke`, `04_ddg_smoke`,
`05_search_smoke`, `08_scholar_smoke`, `09_openalex_smoke`, `12_max_results_probe`,
`13_free_word_probe`, `13_timing_ablation`, `19_books_probe`, `20_docs_probe`) all call
`engine.search(...)` directly and were left untouched, per the task's own instruction — an engine
exception now propagates into them instead of silently becoming an empty list, which is the
intended tripwire, not a regression to paper over.

## Tests

`dev/tests/test_openalex_engine.py` is the only test file in the suite that exercises `search()`
at all (confirmed by reading it in full). Its existing success-path test was renamed from
`test_search_legacy_wrapper_still_returns_plain_list` to
`test_search_base_method_returns_plain_list` — `search()` is no longer an engine-specific legacy
wrapper, it's `BaseEngine`'s own method now, and the old name no longer describes what it tests.
One new test, `test_search_base_method_propagates_exception`, installs a minimal
`_RaisingAsyncClient` whose `get` raises `RuntimeError`, then asserts `await engine.search(...)`
raises that same exception via `pytest.raises` — proving the replacement contract. Full suite:
366 (baseline) + 1 = 367, confirmed by `./venv/bin/python -m pytest -q`.

## Docs

`src/search/engines/DOCS.md`'s `base.py` entry was rewritten for the inverted contract; each of
the eight engine modules' LOC was updated (verified programmatically against `wc -l`, zero
mismatches). A new Gotcha bullet documents the removal in full — what existed, that production
never called it, who the real callers were (dev scripts + one test), and what replaced it — ending
with an explicit instruction that `search()` must never grow a try/except again, since an engine
exception reaching a dev script through it is the intended tripwire. `dev/tests/DOCS.md`'s
`test_openalex_engine.py` entry and LOC were updated to describe both the renamed test and the new
exception-propagation test.
