# Comment-rule conformance for src/crawler/ (2026-09-07)

Third pass of the comment-rule conformance sweep (`src/scraper/` and `src/search/` covered
earlier, see those areas' own entries in this same folder). Every comment line and docstring in
`src/crawler/*.py` (17 files) was removed except the three allowed section markers. Pure
deletion: no code line changed, no reformatting, zero behavior change — 378 passed before and
after.

## Verifying the all-DELETE triage before touching anything

Same shape as the `src/search/` pass: this area's triage was "every hit is DELETE," no
GOTCHA/ENTRY split. All 17 files were read end-to-end and cross-checked against
`src/crawler/DOCS.md` and the three named process-docs areas (`url_discovery`, `pipe_scraper`,
`pipe_scraper_hardening`). Every comment's substance traced to something already stated in
DOCS.md's Modules or Gotchas sections — DOCS.md itself already restates the process-docs
findings at length (the 3571-URL/12-minute traversal-removal measurement, the 50-of-54
`returnTo=` onward-link finding, the navtree payload-shape/version-union rationale, the
`outcome`-field removal, the `seed_feeders_scope.normalize_url` vs `crawl_site.normalize_url`
boundary), so no process-docs file needed a full re-read to confirm a claim — a targeted grep
would have sufficed for any single claim, and none was actually needed since DOCS.md's own text
already carried the same wording near-verbatim in most cases.

**No gap was found.** Unlike the `src/search/` pass (one `atexit`-safety comment had no DOCS.md
home and required a Gotcha addition before deletion), every comment line across all 17
`src/crawler/` files matched something already on record. `crawl_site.py`'s comments were the
simplest case: plain function-purpose headers with no unique rationale, consistent with DOCS.md
marking that whole module superseded by `discovery.py`. `pipe_scraper_constants.py` and
`seed_feeders_constants.py` had zero comment lines beyond the `# INFRASTRUCTURE` marker already,
confirmed both before and after the edit pass.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count (matches the pre-sweep baseline
recorded for this phase). The AST-based scan script (module docstrings, function/class
docstrings, any comment line other than the three markers, and inline trailing comments outside
string literals) printed nothing for `src/crawler` after the edit pass. All 15 touched `.py`
files' `wc -l` values (`pipe_scraper_constants.py` and `seed_feeders_constants.py` excluded,
having no hits and no LOC change) were updated in `src/crawler/DOCS.md`'s per-module headings to
match exactly, one file at a time.
