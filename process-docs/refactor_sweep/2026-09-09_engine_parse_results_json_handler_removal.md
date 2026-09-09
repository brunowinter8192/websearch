# Removal of _parse_results's JSONDecodeError handler in the six browser engines (2026-09-09)

Fifth Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal, the proxy_riding abort stub removal, the engine `search()` wrapper removal, and
the camoufox raw-HTML fallback removal for the four before it). Every one of the six pydoll-driven
search engines (`bing`, `brave`, `duckduckgo`, `google`, `startpage`, `yandex`) wrapped
`_parse_results`'s `json.loads(value)` call in `try: ... except (json.JSONDecodeError, TypeError):
return []`, converting a genuine parse failure into a silent empty-results page. The user ordered
its removal: the handler dated from each engine's first commit (2026-04-07) with no supporting
observation behind it — 0 `ERROR_PARSE` occurrences across 4566 logged engine records, and the
value being parsed is always this project's own `JSON.stringify` output from `_JS_PARSE`, never
third-party data that could plausibly be malformed.

## What changed, and what stayed

`_parse_results`'s `if not value: return []` guard was kept untouched — an empty/`None` value
(`_wait_for_results` failing, or the page's own JS returning nothing) is a real "no containers"
outcome, unrelated to parsing. The try/except immediately after it was removed in all six engines,
reducing to a bare `items = json.loads(value)`. A parse failure now propagates through
`search_with_reason` into `search_web.py::_engine_with_timing`, which was read in full and
confirmed to already classify `json.JSONDecodeError` (a `ValueError` subclass) into `ERROR_PARSE`
via `_classify_engine_exception`. A bare `TypeError` is NOT in that classifier's tuple and would
fall through to the generic `ERROR_OTHER` branch — per the task, this was left as-is and reported
rather than extending the tuple, since no observed `TypeError` trigger exists to justify adding a
new isinstance branch for one either.

`import json` was kept in every one of the six modules, unconditionally: each engine's separate
`_diagnose(tab)` function has its OWN `json.loads(val)` call, wrapped in its own, different
try/except that was explicitly left untouched (a different function, out of scope for this
removal, not re-examined for its own defensibility here).

## Tests

One new test, `dev/tests/test_bing_engine.py::test_parse_results_raises_on_invalid_json`, covers
all six engines' identical removed code path. `bing.py` was chosen among the four candidate test
files with existing coverage (`test_bing_engine.py`/`test_brave_engine.py`/
`test_startpage_engine.py`/`test_yandex_engine.py` — none of the four had a tab-driving fixture
already, all four only tested pure helpers like `_build_results`) because bing's own
`_parse_results` has the plainest call shape (`return _build_results(items, max_results)`, no
inline per-item loop like duckduckgo/google, no extra self-referential filtering like yandex) — the
least incidental surface for a fixture whose only job is to reach the removed handler. A minimal
`_FakeTab.execute_script` returns `{"result": {"result": {"value": "not valid json{"}}}`, matching
`_extract_value`'s expected unwrap shape, and the test asserts `_parse_results` now raises
`json.JSONDecodeError` instead of returning `[]`. Full suite: 364 (baseline) + 1 = 365, confirmed
by `./venv/bin/python -m pytest -q`.

## Caller check

`grep -rn "_parse_results" dev/`: `openalex.py`'s own `_parse_results(works: list[dict])` is an
unrelated, differently-shaped function (no JSON parsing at all, iterates dicts) tested in
`dev/tests/test_openalex_engine.py` — not one of the six engines, untouched. The five
`dev/search_pipeline/{25,26,27,28,29}_*_probe.py` scripts each define their OWN standalone
`_parse_results(tab, max_results)` — independent duplicated exploratory code, not imported from
`src/search/engines/` — untouched.

## Docs

`src/search/engines/DOCS.md` gained a new Gotcha bullet at the end of the Gotchas section
documenting the removal (evidence, the `_classify_engine_exception` `TypeError` gap left
un-extended, and the explicit note that `_diagnose`'s own separate handler was not touched); LOC
for all six engine modules was updated (verified programmatically against `wc -l`, zero
mismatches). `dev/tests/DOCS.md`'s `test_bing_engine.py` entry and LOC were updated to describe the
new test and why the other five engines share its coverage rather than each getting their own.
