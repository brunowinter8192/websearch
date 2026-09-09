# Retirement of crawl_site.py and garbage_filter.py (2026-09-09)

A Phase 4 control-flow item, but a dead-code retirement rather than a fallback removal (see this
same folder's other 2026-09-09 entries for the fallback removals proper). `crawl_site.py`
(356 LOC) was `src/crawler/`'s original discovery-plus-batch-crawl module; it had already been
superseded piecewise — `discovery.py` took over the discovery step, `pipe_scraper.py` took over
the batch-scrape step — and `src/crawler/DOCS.md` already flagged it "scheduled for retirement" at
the start of this task. Verified before touching anything: zero callers anywhere in `src/`,
`cli.py`, `skills/`, or `dev/tests/` — its only entry point was its own `if __name__ ==
"__main__":` block. `garbage_filter.py` (50 LOC, `is_garbage_content`) had exactly one caller,
`crawl_site.py`'s `save_markdown`, so it had no independent reason to survive the removal. User
decision in the Phase 4 control-flow review.

## What changed

Both files deleted outright. No behavior moved anywhere — `discovery.py` and `pipe_scraper.py`
already carried the discovery and batch-scrape functions this pair used to provide; nothing that
called either deleted module needed a replacement.

In `dev/tests/test_chromium_scrape.py`: the `from src.crawler import garbage_filter` import and
the two tests that existed solely to guard `garbage_filter.is_garbage_content`
(`test_is_garbage_content_still_importable_and_functioning`,
`test_try_scrape_does_not_call_is_garbage_content`, plus their section-comment header) were
removed — both tests existed only because `crawl_site.py` depended on the function staying
importable and unreachable-from-`try_scrape` at the same time; with the dependency gone, so is the
reason for either assertion. File dropped from 1295 to 1252 LOC. `pytest` count: 371 (session
baseline) − 2 = 369, confirmed by `./venv/bin/python -m pytest -q`.

`dev/scrape_pipeline/garbage_eval/08_garbage_edge_cases.py` (a one-shot dev script, not part of any
maintained test suite) still imports `is_garbage_content` from the now-deleted
`src.crawler.garbage_filter` and will fail on import from here on. Left untouched by explicit
instruction — it is a one-shot dev script, and dev/ scripts are not part of the doc-drift/test
surface this task's contract covers. Its entry in `dev/scrape_pipeline/garbage_eval/DOCS.md` grew
a Gotcha stating the broken import and why.

## Docs

`src/crawler/DOCS.md`: removed both modules' entries under Modules, their three Public Interface
bullets, and the crawl_site sentence in Flow. The Role paragraph's old "`crawl_site.py` is now
superseded by `discovery.py`..." sentence became a "REMOVED 2026-09-09" note naming both files, the
zero-caller finding, and the Phase 4 control-flow review as the decision source. Two Gotchas were
retired with the files they were about: the `--concurrency`/429 note (crawl_site-only, no
surviving code to guide) was dropped outright; the `seed_feeders_scope.normalize_url` vs.
`crawl_site.normalize_url` comparison bullet was rewritten to drop the now-nonexistent
`crawl_site.normalize_url` side while keeping the merge-boundary reasoning that still guides
`seed_feeders_scope.normalize_url` itself (the worst-case-inversion argument for why query strings
stay distinct). One residual mention of `crawl_site.normalize_url` inside the `seed_feeders_scope.py`
Module entry's own Purpose line was found and fixed during the sweep — not caught by the initial
grep since it wasn't in a Gotcha, found only by a second full-text grep pass after the first round
of edits.

`src/scraper/DOCS.md`: the Role paragraph's opening sentence dropped "and the shared garbage
classifier for batch crawling" / "or garbage classification" (both stale — no classifier lives
anywhere in this project anymore). The Contract paragraph and the matching Gotcha were both
rewritten from "`is_garbage_content` still exists, lives in `garbage_filter.py`" to "no longer
exists anywhere" — framed with two dates: content judgment left this module 2026-08-05 (unchanged,
already documented), and the function's last home was retired 2026-09-09 (new). The sentence
forbidding a content-judgment call from `try_scrape`/`scrape_url_chromium_workflow` was kept
verbatim in the Contract paragraph, per the task's own instruction not to lose it.

`dev/tests/DOCS.md`: `test_chromium_scrape.py`'s heading LOC updated (1295→1252) and the sentence
in its Purpose describing the `garbage_filter.py` coverage removed.

## docs-drift-check interaction

The first pass of both rewrites left `` `src/crawler/garbage_filter.py` ``/`` `src/crawler/
crawl_site.py` `` as full slash-paths inside backticks in `src/scraper/DOCS.md`'s Contract
paragraph and Gotcha — `docs-drift-check`'s path-existence check flags any backtick-wrapped,
slash-containing token whether the surrounding prose is past-tense or not, since it has no
"historical mention" exemption outside `decisions/OldThemes/`. Fixed by rephrasing both mentions to
`` `garbage_filter.py` in `src/crawler/` `` (bare filename, no slash — the tool's `PATH_PATTERN`
requires at least one `/` to fire) plus a separate `` `src/crawler/` `` directory reference (which
still exists on disk, so it resolves cleanly). Re-run confirmed zero path-drift findings naming
either retired file; the six remaining path-drift findings post-fix are pre-existing and unrelated
(verified by diffing the finding list before and after this task's edits).
