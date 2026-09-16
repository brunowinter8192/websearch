# dev/ sweep batch 1: explore_pipeline, lane_choice, url_discovery, cli.py (2026-09-16)

Worker entry for the first hit-list batch handed out from
`process-docs/refactor_sweep/2026-09-15_dev_sweep_orchestrator_and_phase4_scan.md`. That entry's
own table listed this batch as: `dev/lane_choice/04_lane_metrics.py` (520 LOC),
`dev/url_discovery/_fixture_site.py` (415 LOC), plus seven functions at/over 50 LOC across
`explore_pipeline`, `lane_choice`, `url_discovery`, and `cli.py::main`. Per-area detail lives in
`process-docs/explore_pipeline/2026-09-16_refactor_sweep_function_splits.md`,
`process-docs/lane_choice/2026-09-16_lane_metrics_concern_split.md`, and
`process-docs/url_discovery/2026-09-16_fixture_site_content_split.md`. This entry holds only what's
specific to `cli.py` (not a `dev/` area, so it gets no area folder of its own) plus one operational
note the per-area entries don't cover.

## cli.py::main split

`main` (80 LOC) contained two genuinely different concerns: building the argparse surface (four
subcommands, ~39 LOC of `add_parser`/`add_argument` calls) and dispatching to the right workflow
once parsed. Split into `build_parser() -> argparse.ArgumentParser` (moved verbatim, including its
five `# ── <name> ──` divider comments) and a new `_dispatch_search_engine_drilldown(args)` helper
that took the `search_engine_drilldown` branch's whole body (its three early-return paths preserved
exactly as returns from the helper, `main` still returns right after calling it — same observable
control flow). The `scrape_url_chromium` branch's PDF pre-check was deliberately left inline in
`main` rather than extracted: an early version tried returning `None` from a helper as a "skip"
sentinel, which is unsafe — if `scrape_url_chromium_workflow` itself ever legitimately returned
`None`, the sentinel-based helper would silently `return` instead of crashing at `result[0].text`
the way the original does, a real behavior change. The PDF check is 5 lines and doesn't need
extracting; `main` is 23 LOC after the two real extractions, well under 50 either way.

Verification for `cli.py` specifically was structural rather than execution-based:
`build_parser().parse_args(argv)` was not re-diffed against argparse's own Namespace output because
the argument definitions were moved character-for-character (confirmed by diffing the extracted
block against the original inline block, not by re-typing it). `_dispatch_search_engine_drilldown`
was traced by hand against the original three-early-return shape rather than executed, since it
calls `search_web_workflow` (real network) with no fixture seam already in the file to intercept it
without also touching scope outside this task (adding a monkeypatch seam to `cli.py` itself would
be a behavior-adjacent change beyond "split a function"). `dev/tests/test_query_logger.py` imports
`cli` and calls `cli._log_drilldown` directly via subprocess — `_log_drilldown` itself was not
touched, and the full suite (378 tests, includes that file) passes.

## Operational note: `gcommit` stages ALL changes, not just what you `git add`

Tried `git add cli.py` then `gcommit "..."` expecting a cli.py-only commit. `gcommit` staged every
modified/untracked file in the worktree regardless (staged: all 18 changed/new files; skipped: the
pre-existing `venv` symlink via its own skip-list) and committed them together under the message
meant for just `cli.py`. `git commit --amend` is blocked by a hook in this environment
("Never amend existing commits — create a new commit instead"), so the message could not be
corrected after the fact. **A successor planning multiple small commits within one session should
make ALL the file changes for commit N, run `gcommit` for commit N, and only then start touching
files for commit N+1** — there is no way to stage a subset ahead of a `gcommit` call; the tool
always commits the full current diff.

## Numbers after this pass (whole batch)

| File | Before | After |
|---|---|---|
| `cli.py` | 193 LOC, `main` 80 | 200 LOC, `main` 23, largest function `build_parser` 39 |
| `dev/lane_choice/04_lane_metrics.py` | 520 LOC | 62 LOC + 6 new sibling files, largest 136 |
| `dev/url_discovery/_fixture_site.py` | 415 LOC | 167 LOC + 1 new sibling file (263 LOC) |

Full AST scan across all 21 touched files (`cli.py` + every `.py` in the three areas) after the
pass: 0 modules over 400 LOC, 0 functions at or above 50 LOC. Full `dev/tests/` suite: 378 passed.
