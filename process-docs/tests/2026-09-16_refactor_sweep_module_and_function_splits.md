# dev/tests/ refactor sweep: six module splits, one function-only split, and the hook that reshaped every helper module (2026-09-16)

Worker entry for the third and final hit-list batch of the `dev/` refactor sweep orchestrated from
`process-docs/refactor_sweep/2026-09-15_dev_sweep_orchestrator_and_phase4_scan.md`. This batch:
`test_chromium_scrape.py` (1257 LOC), `test_pipe_scraper.py` (906), `test_seed_feeders.py` (788),
`test_camoufox_scrape.py` (747), `test_proxy_pool.py` (573), `test_browser.py` (446) — all module
splits — plus three function-level hits (two in `test_proxy_pool.py`, one in
`test_query_logger.py`).

## The area-specific rulings that shaped everything, restated for a successor

The orchestrator gave three rulings specific to this area before work started, all still binding
for anyone touching `dev/tests/` again: no `# INFRASTRUCTURE`/`# ORCHESTRATOR`/`# FUNCTIONS`
markers (a pytest module has no orchestrator, the marker would be a fiction); every docstring and
comment stays, moved verbatim with the code it belongs to (a separate pass owns deleting them, not
this one); a file holding only fixtures/helpers may take any name, but a file holding `test_*`
functions MUST be named `test_*.py` or `pytest.ini`'s `testpaths = dev/tests` silently stops
collecting it. All three held throughout — see the verification section below for how each was
checked, not just asserted.

## The hook nobody warned about, found empirically before it wasted more than one file

`Write`ing a plain-named helper module (`_chromium_scrape_fakes.py`) with
`from src.scraper import chromium_process, chromium_scrape` at the top failed outright: *"dev/
scripts may not import from src/ — copy the logic into the dev/ module or import from another pN_
module."* A same-content file named `test_zzz_hook_probe.py` (matching `test_*.py`) went through
fine with the identical import. **The rule is filename-pattern-based, not directory-based: any
`dev/` file whose name does NOT match `test_*.py` is treated as a "dev script" that must be
self-contained, `test_*.py` files are exempt.** This is not documented anywhere I could find before
hitting it — confirmed by two throwaway probe files (one matching `test_*.py`, one not), both
diffed against each other, not by reading anything.

**The fix applied everywhere in this batch:** every new `_*_fakes.py` helper module takes the
already-imported `src` module or callable as a parameter instead of importing it itself. Concretely:
`_patch_cdp_launch_mechanics(monkeypatch, chromium_scrape, chromium_process)` (was
`_patch_cdp_launch_mechanics(monkeypatch)`, with the two modules imported inside the helper file
itself), `_reset_state(monkeypatch, browser)` (was `_reset_state(monkeypatch)`), and
`_write_and_read_md(compute_stats, write_md, tmp_path, events, target, done)` (was
`_write_and_read_md(tmp_path, events, target, done)`, with `_compute_stats`/`_write_md` imported
directly from `janitor.py` inside the original single file). None of these are logic changes — the
call sites in every test just grew the extra leading arguments, and every one of them was updated
consistently. **A successor building another shared dev/tests helper module should assume this
constraint applies and design the parameter list for it from the start**, rather than discovering it
the same way this session did.

Three of the six new helper modules needed NO such treatment at all, because none of their fakes
ever reference a `src` name directly: `_camoufox_scrape_fakes.py`, `_seed_feeders_fakes.py`,
`_pipe_scraper_fakes.py` are pure synthetic classes/functions (`_FakeResponse`, `_FakeAsyncClient`,
`_xml`, etc.) with zero `src` imports — they were the easy cases. `_chromium_scrape_fakes.py`,
`_browser_fakes.py`, `_proxy_pool_fakes.py` needed the parameter-injection treatment because their
one shared helper each (`_patch_cdp_launch_mechanics`, `_reset_state`, `_write_and_read_md`) does
real monkeypatching against a real module object.

## The proof method this task actually asked for, and why it differs from the last two batches

Byte-identical output was explicitly ruled out for this area — a test suite's own pass/fail state
*is* its output, and the real failure mode (a test silently stops being collected) is invisible to
a green run. The method used instead, and the one to reuse for any future `dev/tests/` split:

1. `pytest -q` before, record the passed count (378).
2. `pytest --collect-only -q` before, captured to a file (`/tmp/proof3/before_collect.txt`).
3. Same two after.
4. A `Counter` multiset diff of collected node IDs with the `<module>::` prefix stripped, compared
   in both directions (`before - after` for anything that vanished, `after - before` for anything
   duplicated). Both empty is the only passing result — checking only one direction would miss a
   test that got copied into two files instead of moved.

This caught nothing wrong in this run (378/378 both times, multiset diff empty both directions),
which is the expected, correct outcome for a pure relocation — but the check is real, not
ceremonial: a copy-instead-of-move mistake earlier in the session (see below) would have shown up
here as a `+1` in the `after` direction for exactly the duplicated function name, and this is the
only mechanism in the whole sweep that would have caught it.

## Every comment-banner near-miss caught before commit, and the general pattern behind them

Two comment-preservation mistakes were caught by the standard `grep '^\s*#'` old-vs-union-of-new
multiset diff, both worth naming as a reusable category:

1. **A section divider comment dropped, not reworded.** `_camoufox_scrape_fakes.py`'s "Fakes"
   section originally sat under a `# ---\n# Fakes\n# ---` banner in the source file; the first
   draft of the extraction carried the class bodies but not the banner above them. Caught by the
   multiset diff showing 2 missing `# ---` lines from the total count, not by eyeballing the file.
2. **One shared banner split into two differently-worded banners.** `test_seed_feeders.py`
   originally had ONE banner — `# robots_feeder_workflow / sitemap_feeder_workflow — end-to-end,
   fake client injected via monkeypatching...` — covering tests that got split across
   `test_seed_feeders_robots.py` and `test_seed_feeders_sitemap.py`. First instinct was to write a
   shorter, file-specific banner in each ("# robots_feeder_workflow — end-to-end..." /
   "# sitemap_feeder_workflow — end-to-end...") — this is exactly the invented-comment hazard even
   though each half read as "more accurate" for its own file. Fixed by keeping the original
   4-line banner verbatim in ONE of the two files (robots, since it's named first in the original
   text) and adding nothing to the other.

**The generalizable rule, worth restating precisely:** when a single original comment covers code
that ends up split across two or more new files, either (a) the comment moves whole into exactly
one of them, or (b) parts of the code get no comment at all. Writing a "better," differently-worded
comment for each new home is not an option, no matter how each rewrite reads in isolation — the
multiset must reproduce the *exact original text*, once, not an equivalent-meaning paraphrase per
site.

## The two `test_proxy_pool.py` integration tests: two-layer extraction, not one

`test_run_loop_refresh_swaps_pool_and_preserves_state` (86 LOC) and
`test_run_loop_refresh_fresh_candidates_from_new_pool` (83 LOC) needed MORE than the obvious single
extraction. First pass pulled only the mock-setup-and-`run_loop()`-call block into a shared
`_run_loop_with_mocked_time(...)` helper — this left both tests at 62 and 59 LOC, still over the
line, because the bulk of each function is its own docstring (~13 lines), its own huge
`time.monotonic` sequence explanatory comment (~11-14 lines, and the two are NOT identical text —
each explains that specific test's own batch composition), and its own distinctive assertions
(~25 lines with their own numbered sub-comments). A second extraction was needed: a per-test
scenario builder (`_swap_preserves_state_scenario()` / `_fresh_candidates_scenario()`) that owns the
pool/URL construction AND the `mono_seq` comment block together (they are tightly coupled — the
comment exists specifically to justify that literal list of numbers), returning a tuple the test
unpacks. This dropped both functions to 41 and 38 LOC. **The lesson for a successor facing a
still-over-50 function after one obvious extraction: check whether the remaining bulk is docstring
+ explanatory-comment + assertions (all things that must stay in the test, not move to a shared
helper) before concluding the split is done — a second, test-specific extraction of the SETUP DATA
(not the mechanism) may still be needed even after the mechanism itself is shared.**

Not merged: the two tests' own assertion blocks, even though assertions 1-2 in each are
structurally similar (`pool_provider.call_count == 2`, `set(done) == set(target_urls)` /
`dead == []` / `gap == []`). Their comments and assertion messages differ word-for-word between the
two tests ("Pool swap happened exactly once" with an f-string message vs. "Swap happened exactly
once" with none) — merging would have required inventing parameterized text to cover both, which is
the same hazard as the banner-comment case above, just inside an assertion instead of a `#` line.
Left as two separate, slightly-duplicated blocks rather than force a shared wording neither test
originally had.

## Module-boundary choices that mirror already-established production splits

`test_chromium_scrape.py`'s 5-way split (`test_chromium_scrape.py`,
`test_chromium_scrape_facts.py`, `test_chromium_scrape_output.py`,
`test_chromium_scrape_document_status.py`, `test_chromium_process.py`) deliberately tracks the
`chromium_scrape.py`/`chromium_process.py` production split documented in
`process-docs/refactor_sweep/2026-09-07_chromium_scrape_concern_split.md` — tests calling
`chromium_scrape.try_scrape`/monkeypatching names AS IMPORTED INTO `chromium_scrape`'s own
namespace stayed in the four `test_chromium_scrape*.py` files; tests calling `chromium_process.X`
directly or monkeypatching `chromium_process`'s OWN globals (subprocess/psutil/tempfile) went to
`test_chromium_process.py` alone. This is the exact "which module's globals actually matter"
distinction that process-docs entry already worked out for the production code; reusing it for the
test split was mechanical once recognized, not a fresh design decision.

`test_pipe_scraper.py`'s 4-way split tracks the production module names directly:
`pipe_scraper_config.py` tests -> `test_pipe_scraper_config.py`; the camoufox-vs-chromium engine
switch -> `test_pipe_scraper_camoufox_engine.py`; `pipe_scraper_acquisition.py`/
`pipe_scraper_report.py`'s onward-link functions -> `test_pipe_scraper_onward_links.py`; the
remaining `_scrape_all`/`log_pipe_scrape` core stayed in `test_pipe_scraper.py`. One cross-file
dependency caught mid-split: `_camoufox_meta()` was originally defined once, used by BOTH the
camoufox-engine-switch tests AND one wiring test in the "onward links" section
(`test_scrape_one_camoufox_never_produces_a_links_key`) — moved to the shared `_pipe_scraper_fakes.py`
rather than duplicated or left as a cross-`test_*.py`-file import, once the second usage site was
found by grepping `_camoufox_meta(` across the whole original file before finalizing file
boundaries (not after).

`test_seed_feeders.py`'s 6-way split tracks `seed_feeders_scope.py`/`seed_feeders_robots.py`/
`seed_feeders_sitemap.py`/`seed_feeders_navtree.py` directly, with the original file's own
`fixture_server` module-scoped fixture and its four fixture-backed integration tests staying
together as the sole remaining content of `test_seed_feeders.py` itself — the fixture was never at
risk of being separated from its users since all four of its users are the tests that stayed put.

## What was declined and why

Did not refactor `test_search_web_workflow_propagates_diagnosis_into_both_records` or
`test_search_web_workflow_writes_search_key_matching_cache_key` (both in `test_query_logger.py`) to
reuse the new `_run_search_web_workflow_and_get_log_lines` helper, even though both share the exact
mock-engines-patch-and-await-workflow-and-read-log-lines shape the helper now covers. Neither is in
the hit list (both already under 50 LOC) — touching them would have been "tidying," explicitly
out of scope per this sweep's own standing rule.

## Numbers after this pass

Full AST scan over every `.py` in `dev/tests/` after the pass: 0 modules over 400 LOC, 0 functions
at or above 50 LOC. Collection/pass counts: 378 before, 378 after, both directions of the node-name
multiset diff empty. This closes out the three-batch `dev/` sweep for this session — see
`process-docs/refactor_sweep/` for the two earlier batches' own entries
(`2026-09-16_dev_sweep_batch1_explore_lane_url_cli.md` and the `scrape_pipeline` entry under
`process-docs/scrape_pipeline/`).
