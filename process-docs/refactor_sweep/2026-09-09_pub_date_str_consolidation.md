# pub_date_str consolidated into dedup.py (2026-09-09)

Phase 4 (control-flow integrity) of the refactor sweep, cross-module pass. Two byte-identical
`pub_date_str(entry)` functions existed in `src/news/clean_pass.py` and `src/news/engine/dedup.py`,
differing only in the no-date fallback value: `"unknown"` in clean_pass, `""` in dedup. This was the
one duplicate in the cross-module list with an observed divergence, so it was handled first.

## Why the divergence mattered

clean_pass writes the collection file as `theblock__{pubdate}__{hash}.md`; dedup's `mode="pubdate"`
branch looks up `{source}__{pubdate}__{hash}.md` to decide whether an entry is already present. For an
entry with no publication date and no date in its URL path, clean_pass wrote `theblock__unknown__h.md`
while dedup looked for `theblock____h.md`, so the lookup could never hit. Whether the case ever
occurred in production is unknown: as of 2026-09-09 every production caller of `filter_new_entries`
in `pipeline.py` passed `mode="raw"`, so the pubdate branch was reached only by tests, and no test
exercised it either.

## Change

- `dedup.py::pub_date_str` keeps the single definition and now returns `"unknown"` when no date is
  found; the user picked `"unknown"` because it stays readable inside a filename.
- `clean_pass.py` imports `pub_date_str` from `src.news.engine.dedup` and dropped its own copy, its
  `DATE_RE`, and the now-unused `import re`. Import direction is entry layer to engine layer, the same
  direction `pipeline.py` already uses; no cycle.
- Two tests added to `dev/tests/test_dedup_exclude.py`: the `"unknown"` fallback itself, and a
  `mode="pubdate"` lookup that treats a pre-existing `theblock__unknown__{hash}.md` as already present.

## Verification

`./venv/bin/python -m pytest -q`: 371 passed (369 before, plus the two new tests).
`dev/tests/test_theblock_clean_pass.py` unchanged and passing, since its fixture carries a real date and
never reached the fallback.

## Note on the worker

The worker that implemented this task hit its context limit after committing the task and before the
recap step; this entry was written by the orchestrator from the worker's plan and the merged diff.
