# dev/scrape_pipeline/ refactor sweep: 07_pipe_scrape_eval.py split and the dead-import case (2026-09-16)

Worker entry for the second hit-list batch of the `dev/` refactor sweep orchestrated from
`process-docs/refactor_sweep/2026-09-15_dev_sweep_orchestrator_and_phase4_scan.md`. This batch:
`07_pipe_scrape_eval.py` (482 LOC, module split) plus six functions across
`07_pipe_scrape_eval.py`, `04_overview_sweep/analyze.py`, `04_overview_sweep/sweep.py`,
`filter_eval/05_filter_debug.py`, `06_cloudflare_md_adoption.py`.

## The 07_pipe_scrape_eval.py split boundary

DOCS.md already described this file as three independent phases plus a smoke test, and `main()`'s
own dispatch (`argparse choices=['smoke','phase1','phase2','phase3']`) is the concern boundary the
code itself already drew. Split into `_pipe_scrape_eval_common.py` (shared `load_urls`/`stratify`/
`compute_metrics`, 47 LOC), `_pipe_scrape_eval_phase1.py` (95), `_pipe_scrape_eval_phase2.py` (99),
`_pipe_scrape_eval_phase3.py` (273 — the heaviest, since it alone carries the two function-level
hits). `07_pipe_scrape_eval.py` itself dropped to 64 LOC: imports, `main()` dispatch, `smoke_test`.

**Did not label `phase1_concurrency_sweep`/`phase2_delay_sweep`/`phase3_full_run` as
`# ORCHESTRATOR`** in their new homes, even though each is now the natural single entry point of
its own file. Each still contains a real for-loop with a conditional `break` (phase1) or genuine
step-sequencing logic beyond pure delegation (phase3, even post-split). The strict bar is "no
functional logic, may only call functions and decide via one condition which to call next" — a
for-loop building up a `sweep_rows` list fails that bar. Kept under `# FUNCTIONS`, matching how the
original single file already classified all three (only the true CLI dispatcher, `main()`, was
ever under `# ORCHESTRATOR`). **A successor tempted to promote one of these to ORCHESTRATOR should
first check whether it still has a real loop or conditional-branch-building-state in it — if yes,
it isn't one, regardless of how "central" the function feels for its file.**

## t0 threading across the phase3 split — the one place get-it-wrong-silently was possible

`phase3_full_run`'s original `total_wall_s = time.time() - t0` measures from `t0` set once, right
before the main pass begins, through to AFTER the retry pass — i.e. main pass + inter-batch pauses
+ retry cooldown + retry pass, cumulative from one shared origin, NOT `main_wall_s + retry_elapsed`
computed as two independently-clocked pieces (which would silently double-count nothing but could
drift if either step's own internal bookkeeping changed). The split threads `t0` as an explicit
parameter into `run_main_pass_step(urls, delay_s, concurrency, output_dir, t0)`, and
`phase3_full_run` itself still owns `total_wall_s = time.time() - t0` after both steps return. A
naive split (e.g. each step returning its own `time.time() - time.time()` local elapsed) would have
been silently wrong in a way no unit test comparing final report numbers would necessarily catch
without the exact multi-batch, multi-retry timing scenario — verified against this here by running
old vs. new through 4 synthetic scenarios (no 429s / retry-recovers-all / retry-partial / WAF-never-
clears) with `asyncio.sleep` patched to a no-op, confirming byte-identical stdout including every
`wall=` figure.

## The dead-import case: 05_filter_debug.py

Confirmed before touching anything: `filter_eval/05_filter_debug.py` cannot be imported at all.
`from src.scraper.routing import resolve_profile, load_config, match_url_to_profile` and three more
`src.scraper.*` imports plus `chromium_scrape.{init_browser,fetch_url_content,cleanup_browser}` are
all dead — `src/scraper/` currently holds only `camoufox_scrape.py`, `chromium_process.py`,
`chromium_scrape.py`, `scrape_logger.py`. The user independently reproduced the same
`ModuleNotFoundError` before authorizing the split, and specified exactly what the Gotcha note must
say: which imports are dead, that the module cannot execute at all, and that verification was by
text diff, not execution — worded so nobody mistakes the structural proof for a behavior proof. That
exact wording now lives in `filter_eval/DOCS.md`'s `05_filter_debug.py` entry.

**One constraint worth restating for a successor:** commit logs are not an evidence source (see the
worker-rules "Code-Untersuchung" section). I could not cite "since when" these imports went dead
from `git log`, even though `git log --diff-filter=D` on the four `src/scraper/*.py` files returns
exactly one commit. The Gotcha instead says "no process-docs record of when this happened was
found; treat 'since when' as undocumented" — that is the correct move whenever you find a real fact
in git history that has no process-docs or DOCS.md corroboration: state "not documented", don't
launder the git-log date into prose as if it were a documented fact.

**How `run_pipeline_debug` (62 LOC) was verified without running it:** pulled both the pre-split
and post-split function bodies via `ast.parse` + line-slicing (not `git show` to a temp file this
time, since the import itself is what's broken, not the git history), and diffed every non-glue
statement line-for-line. All matched, in the same order; only the extraction glue (two
call-and-unpack assignments, two `return` tuples) is new. This is a real, useful proof for "did the
relocation introduce a logic change" — it is not a proof that `run_pipeline_debug` ever worked, or
that it still would if its imports were fixed. Recorded as a distinct failure mode from a normal
output-identity proof, not a lesser version of the same thing.

## Two invented comments caught before commit, corrected the same way as last batch

Wrote a one-line leading comment above `run_one_combo` in `sweep.py` and above each of the two new
`05_filter_debug.py` helpers, describing what they do. All three were new prose that did not exist
anywhere in the original file — caught by running the same comment-multiset diff
(`grep '^\s*#'` old vs. union of new, sorted, `diff`) used throughout this whole sweep, and removed
before commit rather than left in. Consistent with the discipline established in the first batch
(`process-docs/lane_choice/2026-09-16_lane_metrics_concern_split.md` and
`process-docs/url_discovery/2026-09-16_fixture_site_content_split.md`), and with the standing
project-wide finding recorded in `process-docs/refactor_sweep/2026-09-15_dev_sweep_orchestrator_and_phase4_scan.md`
that this exact mistake ("Two earlier workers silently changed comment lines while splitting") is a
repeat-offender class of error across this whole multi-session sweep, not a one-off.

**A concrete tell worth naming:** the temptation to add a comment came specifically at the two
points where a function was extracted with NO original comment above the code it took — `run_one_
combo`'s body had none, and neither did the code that became `run_node_level_filter_steps`/
`run_markdown_cleanup_steps`. The instinct to "help the reader" by summarizing a brand-new helper
is exactly the invention this sweep's hazard rule forbids. The rule that held: only relocate a
comment that already existed; a helper born from a split with no original comment gets none, full
stop, even if every sibling function in the same file happens to have one.

## Sequencing note on gcommit, reused correctly this time

Made every file change for this batch (all 12 touched/new files, including both DOCS.md fixes for
the two LOC numbers that drifted after removing the invented comments) before the single
`gcommit` call, having learned from the first batch's mistake
(`process-docs/refactor_sweep/2026-09-16_dev_sweep_batch1_explore_lane_url_cli.md`) that `gcommit`
stages the full current diff regardless of what was `git add`ed beforehand. One commit, one
accurate message this time: `9cc40fc refactor: split dev/scrape_pipeline oversized module and
functions`.

## One test-harness mistake caught before commit, not after

An early output-identity test for `analyze.py::write_report` used `PROJECT_ROOT = Path(WORKTREE)`
(the real worktree, not a `/tmp` sandbox) as the base for a fixture `sweep_dir`, which caused the
test itself to create `dev/scrape_pipeline/04_overview_sweep/sweep_data/FAKE_TS/` inside the real
tree. Caught by `git status --short` showing an unexpected `??` entry before the recap commit, not
during the test run itself — the test's own assertions all passed regardless, since correctness and
"where did the test write" are independent failures. Deleted the directory before committing;
confirmed `git status` clean of anything except the intended file set afterward. **Every
output-identity test that touches the filesystem in this kind of session should build its `PROJECT_
ROOT`/output-dir fixtures from a `/tmp` path from the first line, not from the module's own real
`Path(__file__).parent`-derived constants, even when only reading input relative to those — reusing
a "real" `PROJECT_ROOT` for convenience is how a test's write path silently lands in the tree being
refactored.**

## Numbers after this pass

`07_pipe_scrape_eval.py`: 482 → 64 LOC (+4 new files, largest 273, largest function 37).
`04_overview_sweep/analyze.py`: 355 → 367. `04_overview_sweep/sweep.py`: 271 → 279.
`filter_eval/05_filter_debug.py`: 382 → 393. `06_cloudflare_md_adoption.py`: 282 → 301. No module
in this area is over 400 LOC. No function is at or above 50 LOC. Full suite: 378 passed both before
and after (this area has no dedicated `dev/tests/` file of its own — the count is unchanged because
nothing here was ever covered by it, not because it was verified not to regress by the suite).
