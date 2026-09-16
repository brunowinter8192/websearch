# _fixture_site.py content/server split, and the re-export constraint that shaped it (2026-09-16)

Worker entry for the `dev/` refactor sweep orchestrated from `process-docs/refactor_sweep/`. This
area's hit list: `_fixture_site.py` at 415 LOC (module split) and `01_resume_state_probe.py
::write_report` at 59 LOC (function split, see below).

## Why this is a 2-way split, not 3 or 4

The obvious first cut (constants / content generators / ground-truth / HTTP server as four files)
was rejected in favor of two, because of a hard external constraint discovered by grep BEFORE
writing any code: `dev/tests/test_discovery.py` and `dev/tests/test_seed_feeders.py` import
directly from `dev.url_discovery._fixture_site` — not just `start_fixture_server`/
`stop_fixture_server`/`ground_truth`/`seed_url`, but also `DEFAULT_HOST`, `RSC_DEMO_ROOT`,
`RSC_DEMO_CHILDREN`, `ROBOTS_DISALLOW_PATHS`, `ROBOTS_ALLOW_PATHS`, `SITEMAP_BLOG_PAGES`,
`SITEMAP_LEGAL_PAGES`, `NAVTREE_CANONICAL_PAGES`, `NAVTREE_V1_ONLY_PAGES` — nine constants, most of
which the HTTP-serving code itself never touches (`RSC_DEMO_ROOT`/`RSC_DEMO_CHILDREN` etc. are only
used building routes). Splitting constants into their own file would have forced `_fixture_site.py`
to re-import every one of them anyway, purely for re-export — no LOC or clarity win, only more
files. So the actual concern boundary used is: **site definition** (constants + content generators
+ `_build_routes` + `ground_truth`/`_expected_seeds`/`seed_url`, all in the new
`_fixture_site_content.py`, 263 LOC) vs. **HTTP serving mechanics** (`_FixtureHandler`,
`start_fixture_server`, `stop_fixture_server`, the module-level request-count/rate-limit state, all
staying in `_fixture_site.py`, now 167 LOC). `_fixture_site.py` imports everything it needs from
the content module, including several constants it re-exports but never reads itself
(`RSC_DEMO_ROOT`/`RSC_DEMO_CHILDREN`/`NAVTREE_*`/`SITEMAP_*`) purely so
`from dev.url_discovery._fixture_site import RSC_DEMO_ROOT` keeps working unchanged for the tests.

**If a successor is tempted to "clean up" those apparently-unused re-exported imports in
`_fixture_site.py`: don't, without first re-grepping `dev/tests/` for every name imported from this
module.** They look dead by local reading; they are load-bearing for two test files.

## The module docstring: kept once, not duplicated, not deleted

The original 31-line module docstring describes both the site's content shape and its server
behavior (thin-body/429 failure modes) in one place. It was kept verbatim, once, in
`_fixture_site.py` (the file that remains the public import surface) and NOT copied into
`_fixture_site_content.py`, which gets no new docstring at all — adding one would have been
inventing new prose in a split that is supposed to be pure relocation. Verified with
`ast.get_docstring()` on both old and new: identical string, and confirmed absent from the content
module.

## The same sys.path import hazard as lane_choice/04_lane_metrics.py

`_fixture_site.py` importing its own new sibling needed the same fix already established by
`dev/url_discovery/02_fixture_site_server.py`: `sys.path.insert(0, str(Path(__file__).parent))`
then a plain `from _fixture_site_content import ... # noqa: E402`, not a `dev.url_discovery.`
absolute form — direct script invocation (and, for `_fixture_site.py`, being imported bare by
`02_fixture_site_server.py` via its own `sys.path.insert`) never has the project root on
`sys.path`. See `process-docs/lane_choice/2026-09-16_lane_metrics_concern_split.md` for the fuller
writeup of this same hazard hit independently in that area.

## Verification

Ran the real `ThreadingHTTPServer` — pre-refactor code (`git show`'d to `/tmp`) and post-split code
— sequentially on the SAME fixed port (`19345`, not an OS-assigned one, specifically so absolute
`<loc>` URLs embedded in the served sitemap/robots XML would be byte-identical rather than
differing only by port number), fetched 19 real routes plus `/_control/status` over real HTTP, and
diffed `(status, body)` per route: byte-identical for all 19. Separately exercised both switchable
failure modes (`thin_body`, sliding-window `rate_limit`) live over HTTP: byte-identical. `ground_truth()`
and `seed_url()` called directly: identical dicts/strings. Full `dev/tests/test_discovery.py` +
`test_seed_feeders.py` (77 tests, the ONLY test files in the repo depending on this fixture) and the
full suite (378 tests) pass. Comment multiset diff (old file vs. union of the two new files,
section markers and the one new `noqa: E402` excluded): empty. No `try`/`except`/`finally`/`with`
body was moved across the split boundary — `_FixtureHandler`'s three methods and
`start_fixture_server`/`stop_fixture_server` each stayed whole, entirely inside `_fixture_site.py`.

## 01_resume_state_probe.py::write_report

Split the same "one helper per `##` experiment section" pattern as every other `write_report` in
this sweep: `_format_experiment_1_section` through `_format_experiment_4_section`. 280 -> 295 LOC.
Verified byte-identical against a synthetic four-experiment fixture built from this file's own real
constants (`HOMEPAGE`/`TRAVEL_URL`/`MYSTERY_URL`/`PHILOSOPHY_URL`), including an empty-results edge
case for experiment 2's three dict-shape subtests.

## Numbers after this pass

`_fixture_site.py`: 415 -> 167 LOC (+1 new file at 263 LOC). No module in this area is over 400
LOC. No function is at or above 50 LOC (`_serve_content` at 32 is the largest survivor).
