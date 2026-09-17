# dev/ refactor sweep — resume scan after an aborted run, and the dev-to-area mapping audit (2026-09-17)

The `iterative-dev-refactor` run recorded in this folder's 2026-09-15 and 2026-09-16 entries was cut
off mid-flight when its session ended. This entry holds the closing of that run and a fresh scan of
all three autonomous Phases, so the next agent can pick up without re-measuring anything.

## What the aborted run left behind, and how it was closed

The abort was clean in the working tree and dirty in the documentation.

- Working tree clean, nothing uncommitted, `integration` 80 commits ahead of `main`.
- The worktree `.claude/worktrees/refactor` still existed on a branch `refactor` whose commits were
  already fully contained in `integration`. Nothing was lost by removing it.
- The last two commits, `5f87ec3` and `0c1ab9b` on `dev/news_pipeline/theblock/`, had merged but
  carried no process-docs recap. The worker died before writing it. The recap was written by the
  orchestrator from the merged diff and lives in `process-docs/news_pipeline/`.

Closing sequence that worked: write the missing recap, merge `integration` into `main`, sync docs to
RAG, push. This repo carries `.claude-plugin/plugin.json`, so the push runs through `plugin-publish`,
not `git push`. A successor who reaches for `git push` here will be blocked.

`worker-cli kill <name>` is the only way to remove a stale worktree. The raw
`git worktree remove .claude/worktrees/<name>` is blocked by a hook, even when the worker is long
dead and absent from the registry. `kill` handled the dead-registry case without complaint.

## Phase 1 — size thresholds, measured 2026-09-17

AST walk over every `.py` file, excluding the vendored
`dev/news_pipeline/theblock/jhao104/upstream/` tree. Thresholds are module over 400 LOC, function
at or above 50 LOC.

| Scope | Modules over 400 | Functions at or above 50 |
|---|---|---|
| `src/` | 0 | 0 |
| `cli.py` | 0 | 0 |
| `dev/news_pipeline/` | 1 | 11 |
| `dev/search_pipeline/` | 11 | 53 |
| every other `dev/` area | 0 | 0 |

Twelve areas went to zero and stayed there. Against the starting numbers in this folder's 2026-09-15
entry — 35 modules and 133 functions across 15 areas — what remains is two areas.

The `cli.py::main` hit at 80 LOC named in the 2026-09-15 entry was closed by commit `ba31ba3`, which
split it into `build_parser` plus a dispatch helper.

The remaining `dev/news_pipeline/` hits, for whoever picks this up:

- `theblock/probe_liveness.py` at 410 LOC, the only module left over threshold in the area.
- `theblock/acquire_pipe/p4_loop.py::run_loop` at 111 and
  `theblock/probe_curl_cffi_discriminator.py::build_report` at 106 are the two hard targets.
- Eight more functions between 50 and 82, spread over `acquire_pipe/p4_race.py`,
  `acquire_pipe/acquire_pipe.py`, `pipe_theblock.py`, `probe_curated_theblock_cf.py`,
  `probe_liveness.py`, `source_tracker.py` and `acquire_pipe/p4_loop.py::_build_batch`.

`dev/search_pipeline/` is untouched by the whole sweep. Its eleven oversized modules run from
`branch_probe.py` at 704 LOC down to `bm25_sweep_smoke.py` at 420. Its largest functions are
`13_timing_ablation.py::write_report` at 166, `branch_probe.py::_write_findings` at 161 and
`branch_probe.py::_write_report` at 145.

The shape of the `search_pipeline` debt is worth naming, because it decides how to slice the work.
The overwhelming majority of its oversized functions are markdown report assembly: names matching
`write_report`, `_write_report`, `_write_findings`, `_write_summary_md`, `_write_query_md`,
`_build_query_section` and `_section_*` account for well over half the hit list. That is the same
concern the `news_pipeline` and `lane_choice` splits already dealt with, and the same technique —
one renderer per report section, the caller reduced to concatenation — applies directly.

## Phase 2 — comments and docstrings, measured 2026-09-17

`ast.get_docstring` on the module node and on every `FunctionDef`, `AsyncFunctionDef` and
`ClassDef`, plus every `tokenize.COMMENT` token minus the shebang and the three section markers.

`src/` is at zero on both counts. That is the residue of the 2026-08-20 and 2026-09-07 conformance
passes recorded in this folder.

`dev/` has never had a Phase 2 pass. 252 files carry 412 docstrings and 3082 comments. `cli.py`
carries 20 comments and no docstrings.

Per area, so the work can be sliced:

| Area | Files | Docstrings | Comments |
|---|---|---|---|
| `search_pipeline` | 59 | 74 | 799 |
| `news_pipeline` | 76 | 96 | 736 |
| `tests` | 46 | 179 | 599 |
| `scrape_pipeline` | 22 | 15 | 218 |
| `browser_posture` | 13 | 6 | 193 |
| `agentic_discovery` | 7 | 25 | 181 |
| `lane_choice` | 10 | 4 | 138 |
| `url_discovery` | 4 | 3 | 82 |
| `explore_pipeline` | 6 | 3 | 68 |
| `logging` | 3 | 2 | 22 |
| `pipe_scraper_hardening` | 1 | 0 | 17 |
| `access_recovery` | 3 | 3 | 13 |
| `camoufox_lane` | 1 | 1 | 8 |
| `engine_reduction` | 1 | 1 | 8 |

Note the ordering trap this table exposes. `browser_posture`, `lane_choice`, `url_discovery`,
`explore_pipeline`, `access_recovery`, `agentic_discovery` and `engine_reduction` are all at zero on
Phase 1 and still carry comments. Several of those comments were *created* by the Phase 1 splits, not
merely survived them. See the next section.

### Phase 1 splits manufacture Phase 2 violations

Commit `5f87ec3` on `theblock/probe_pool_size.py` is the clearest observed case. The original
`build_report_md` carried in-body section labels: `# Headline`, `# Per-bucket summary`,
`# Per-source detail — one table per bucket`, `# Failed sources`, `# Baseline comparison`. The split
turned each labelled block into its own renderer and left every label sitting directly above the new
`def` line.

A comment that was a violation inside a function body is still a violation above a function. The
heading-over-a-`def` form is named explicitly in the code standard.

The consequence for sequencing: running Phase 1 on an area does not leave its comment count where it
was, it can raise it. Any Phase 2 scan must be re-run after Phase 1 merges, never reused from before.
The per-area table above was measured after all Phase 1 merges to date, so it is usable as-is for the
twelve closed areas, and will need re-measuring for `news_pipeline` and `search_pipeline` once their
Phase 1 work lands.

The prompt instruction that would have prevented it: when a function is split, the block comment is
answered by the new helper's name and is deleted. If the name cannot carry the meaning, the
explanation goes into process-docs, never above the `def`.

## Phase 3 — DOCS.md line count, measured 2026-09-17

Threshold is 400 lines, at or above which the directory splits into unit subfolders.

Two files are over, both in the two areas that still carry Phase 1 debt:

- `dev/tests/DOCS.md` at 493 lines
- `dev/search_pipeline/DOCS.md` at 454 lines

Every other `DOCS.md` in `dev/` and `src/` is under. The next largest are
`dev/lane_choice/DOCS.md` at 266 and `src/news/engine/proxy_riding/DOCS.md` at 238.

`dev/tests/` is interesting because it is already at zero on Phase 1, so its 493-line `DOCS.md` is
not going to shrink on its own. It needs the Step 2 unit plan: entry script plus its exclusive import
closure moves into a subfolder, shared modules stay flat. The `_*_fakes.py` helper modules created by
the 2026-09-16 tests split are the obvious shared-versus-exclusive question there, and several of
them are imported by exactly one test module, which makes them exclusive.

## The dev-to-area mapping audit

Checked both directions against the rule that every `dev/` subfolder has a matching
`process-docs/<area>/`, while an area needs no `dev/` folder.

Fourteen `dev/` subfolders map one-to-one onto an identically named area: `access_recovery`,
`agentic_discovery`, `browser_posture`, `camoufox_lane`, `engine_reduction`, `explore_pipeline`,
`lane_choice`, `logging`, `news_pipeline`, `pipe_scraper_hardening`, `scrape_pipeline`,
`search_pipeline`, `tests`, `url_discovery`. No drift, no near-misses, no renames left half-done.

`dev/_lib/` is the fifteenth and has no area, deliberately. It is the dev-wide shared bus, named as
the one exception in `dev/DOCS.md`, and holds a single module, `browser_launch.py` at 110 LOC. It has
no subject matter of its own, so an area for it would hold nothing.

Seven areas have no `dev/` folder, all legitimately:

- Work that happened only in `src/`: `browser_lifecycle`, `engine_expansion`, `pdf_pipeline`,
  `pipe_scraper`, `project_rename`.
- Meta-areas with no code of their own: `refactor_sweep` (this folder, 40 entries of orchestrator
  records).
- `pooling`, which is the one worth knowing about. It holds 11 entries, and the dev scripts the
  entries describe live under `dev/news_pipeline/theblock/`, for example `probe_pool_size.py`. Not a
  rule violation, but a successor looking for proxy-pool history will find the prose under `pooling`
  and the code under `news_pipeline`.

### One documentation inaccuracy found and left standing

`dev/_lib/DOCS.md` lists `browser_launch.py`'s **Called by** as
`dev/access_recovery/01_google_dom_probe.py`. The actual importing module is
`dev/access_recovery/_browser.py`, which holds the
`from dev._lib.browser_launch import launch_backgrounded_chrome, close_tab, teardown` line. The entry
script itself mentions `dev/_lib/browser_launch.py` only in a comment and imports nothing from it.

It was left unfixed on purpose rather than patched in passing, so the fix travels with the rest of
the outstanding sweep work instead of arriving as an orphan edit.

## Sequencing recommendation for whoever resumes

Phase 1 first and only on the two remaining areas, because it is bounded and because its splits
change the Phase 2 numbers. Then re-measure Phase 2 for those two areas and only then decide the
Phase 2 slice, since 3082 comments across 252 files is not one worker's job and the per-area table
above is the natural cut. Phase 3 last, because `dev/search_pipeline/DOCS.md` will be rewritten by
the Phase 1 splits anyway and re-measuring it before those land is wasted work. `dev/tests/DOCS.md`
is the exception and could be planned at any point, since its area is Phase 1 complete.
