# dev/ module layout sweep (worker wsdev, 2026-09-25)

Area: refactor_sweep. Base: `integration` at 7bb68ff. Scope: every tracked `.py` under `dev/` including `dev/tests/`, except `dev/news_pipeline/theblock/jhao104/upstream/` (vendored, gitignored) and one exempt overlay (below). The earlier main-session record left module layout for a separate task; this is that task. Zero behaviour change.

## Result

Measured with `dev/refactor_sweep/01_layout_scan.py` (AST scan, all 316 tracked dev files at the start).

| | start | end |
|---|---|---|
| files with findings | 272 of 316 | 0 of 326 (316 plus 10 refactor_sweep tools) |
| findings | 2408 | 0 |

Start counts by code: NO_MARKER_FOR_DEF 881, STEPDOWN 805, STATEMENT_OUTSIDE_INFRASTRUCTURE 510, ORCHESTRATOR_LOGIC 97, FUNC_IN_INFRASTRUCTURE 48, GUARD_LOGIC 35, ENTRY_NOT_ORCHESTRATOR 24, ORCHESTRATOR_COUNT 4, MARKER_ORDER 3, MARKER_DUPLICATE 1. The four-eyes review (P2-02 to P2-05) had named about 70 files; the real number is 272 because stepdown order, orchestrator logic and guard logic were not part of that list. Kinds among the 316 files: 75 test files, 117 scripts (have a `__main__` guard), 123 libraries.

## Classification rule (from Main, applied)

- A module that is run as a script or has an entry workflow executing several steps has exactly one ORCHESTRATOR function that only calls functions.
- A pure library whose functions are separate entry points called from other modules gets only INFRASTRUCTURE and FUNCTIONS.
- Test modules (pytest) are libraries of independent entry points: no ORCHESTRATOR.
- The `if __name__ == "__main__":` guard stays at file end as the entry line.
- Entry function of a script = the function called in the guard (`main()`, `asyncio.run(main())`, `sys.exit(main())`, `raise SystemExit(asyncio.run(main()))`). A library that already had exactly one function under `# ORCHESTRATOR` keeps it.
- "Only calls functions" as checked by the scan: statements are calls, assignments of calls or names, `return` of a call, `if` (any condition built from comparisons, `and`/`or`/`not`) with such bodies, `raise SystemExit(call)`. Anything else (for, while, try, with, arithmetic, f-strings, comprehensions, conditional expressions, lambdas) counts as logic and is extracted.

## Decisions

- **sys.path.insert and bare sibling imports (P2-12 dev part).** Path-run scripts (`python dev/x/y.py`) cannot import siblings absolutely without path setup, and sibling modules have digit-leading names (`01_...`, `_06_capture`) that are not valid in `from dev.x import name`. So the rule "absolute imports `from src.x.y import name`" applies to `src` imports; the `sys.path.insert` stays and sits in INFRASTRUCTURE before the sibling imports; bare sibling imports stay. Re-measured 2026-09-25: 76 dev files with `sys.path.insert` (79 module-level statements), 207 bare sibling import statements in 88 files (ws6 estimated 65 files). Converting to package imports would need `__init__.py` files and a changed way to run the scripts; that is a separate task with a runner change.
- **Shebang stays** (main-session decision, unchanged).
- **jhao104 `patches/helper/validator.py` is exempt.** It is a verbatim overlay: `jhao104/setup.sh` copies it over the vendored upstream `helper/validator.py`, it imports upstream-only modules, and it must remain diffable against upstream. Its decorators register at definition time (`@ProxyValidator.addPreValidator`), which pins the definition order. The exemption is visible in `EXEMPT_FILES` (`dev/refactor_sweep/_layout_lib.py`, printed in the scan report) and in the directory's DOCS.md.
- **Classes.** A class goes to FUNCTIONS in stepdown order. If a module-level statement uses a class at import time (`x = Foo()`), the class is hoisted into INFRASTRUCTURE in front of that statement (with its own definition-time dependencies). The repo already mixed both placements (dev: 19 classes in INFRASTRUCTURE, 6 in FUNCTIONS at the start); the tool now decides by use.
- **Definition-dependent module statements.** A module-level statement that calls or references a function defined in the same module at import time (`GOOD_HASH = _hash(GOOD_URL)`, `_ROOT = _repo_root()`, `RateLimiter.acquire = _patched_acquire`, `NAV_FUNCS = {"google": nav_google, ...}`) cannot sit above the function. It is emitted after FUNCTIONS, before the guard, in original order, together with every statement that reads a name it assigns. This is the same shape as the guard: an entry line, not a constant. Files: `coindesk_proxy_riding/analyze_write_times.py`, `p3_url_sampler.py`, `bee_probes/_acquire_probe_instrument.py`, `_branch_probe_instrument.py`, `_cdp_starvation_probe_instrument.py`, `browser_probes/_date_availability_probe_nav.py`, `tests/test_theblock_clean_pass.py`, `tests/test_theblock_discover.py`. The scan accepts a statement outside INFRASTRUCTURE only if it belongs to this set. The alternative (inlining the expression, deleting the helper) was rejected: it edits code bodies for no layout gain.
- **Local stdlib imports inside an orchestrator** (`import argparse` in `main`) were hoisted to module level (4 statements in 3 files). Stdlib only; a non-stdlib local import stays in place and becomes an extracted helper (`_import_pool_loader`).
- **Guard with logic** (35 files): the guard body becomes a function `main` (`run_main` if `main` exists) and the guard calls it. A file whose guard assigns names that module functions read as globals is not liftable; none was left after the liveness refinement (first pass reported 12: the scan of loaded names counted function-local names).
- **One case moved a statement out of a guard by hand:** `selector_js_equivalence_check.py` had `sys.path.insert(...)` in the guard; it moved to INFRASTRUCTURE (nobody imports that script), the guard keeps `raise SystemExit(asyncio.run(main()))`.
- **Test files:** INFRASTRUCTURE (imports, constants), FUNCTIONS (tests, fixtures, helpers, fakes). Tests, fixtures and conftest hooks are the level-0 nodes of the stepdown order and keep their original relative order; helpers and fake classes move below their first user. Collection is by name, decorator and file name, none of which changed.

## Tools (dev/refactor_sweep/)

| script | job |
|---|---|
| `_layout_lib.py` | shared AST analysis: markers, definition-time dependencies, orchestrator purity check, reference graph, fingerprints |
| `01_layout_scan.py` | scan, report `md/01_layout_scan.md` |
| `02_relayout.py` | rewrites a file by reordering its top-level nodes (source text of each node is copied unchanged); aborts on duplicate definitions, stray comments, overlapping statements, statements after the guard; verifies the sorted multiset of top-level `ast.dump` values before and after |
| `06_extract_orchestrator.py` + `_extract_plan.py` | extracts impure orchestrator statements into named helpers, lifts guard logic into `main`, hoists stdlib imports; names come from an auto rule plus an override JSON |
| `03_ast_equivalence.py` | per changed file: top-level node multiset against the merge base (119 files differ: exactly the ones with extraction helpers; 172 identical) |
| `07_inline_equivalence.py` | puts every extraction helper back into its call site and compares the resulting function (and guard) with the merge-base function via `ast.dump`; also checks that call arguments equal helper parameters, returned names equal assigned names, and that no parameter is unused |
| `04_import_snapshot.py` | imports each module in a fresh interpreter in an isolated tree copy and dumps module-level names as JSON |
| `08_run_compare.py` | runs sandbox-safe scripts (plain and `--help`) in a base tree and a current tree, compares exit code, normalised output, written files |
| `05_fix_doc_loc.py` | rewrites LOC numbers in dev DOCS.md headings from line counts |

## Proof of zero behaviour change

1. **Collection.** `pytest --collect-only -q` node id lists are byte identical before and after (`-m "not browser"` default 664, `-m browser` 12, `-m "browser or not browser"` 676); compared with the summary line removed (only the elapsed time differs). Compared again after each commit.
2. **Suite.** `dev/tests/run_strands.sh`: `strands=66 skipped=1 failed=0` before and after; the summed pass counts of the per-file logs are 645 in both.
3. **Mechanical relayout.** `ast.dump` multiset of top-level nodes identical for all 172 files that only got reordered; the relayout tool checks this on every write.
4. **Extraction.** 336 helpers in 119 files were inlined back by `07_inline_equivalence.py`: 0 problems. Hand-edited files (8) are listed in that report with the reason.
5. **Names.** `pyflakes` over `dev/`: no finding added or removed against the merge base (164 lines before, same after; undefined names would appear here).
6. **Import time.** `04_import_snapshot.py`: 312 modules import in both trees, 3 exit at import in both. Module-level names and values equal; the only added names are callables (the helpers).
7. **Run.** 24 sandbox-safe scripts (no network, browser or `src.search/scraper/crawler/news` import, direct or via siblings) ran plain and with `--help` in two tree copies: 47 of 48 runs identical (exit code, normalised output, files written). The one difference is `03_coindesk_cleanup.py --help`: the default path shown in the help text contains the tree directory name and wraps at a different column. Without fixture data those runs mostly reach the early-exit branches (missing input directory); the orchestration bodies are covered by proof 4.
8. **Not run:** the scripts that drive a browser or the network (`search_pipeline/*_smoke`, probes, `explore_pipeline`, most of `news_pipeline`). They are proven by proofs 3 to 6 only. Nothing touched live infrastructure.

## Mistakes and pitfalls seen (for a successor)

- **A parameter that is not one.** First extraction version passed `r` into a helper for `alive = sum(1 for r in results if r["alive"])`: the comprehension variable had been counted as a read of the enclosing `for r in results` variable. Observed in `theblock/proxy_status_log.py` (`_compute_alive(r, results, data)`), which would have raised NameError on an empty result list. `pyflakes` did not see it (the name exists in the caller). Fix: the load scan is scope-aware (comprehensions, lambdas, `for` bodies shadow their targets); `07_inline_equivalence.py` now fails on unused parameters. Apply "used after" logic the same way: a loop variable reused by a later loop must not be returned (`p0_pool.py`, 12 loops with `proto`).
- **Group per statement, not per run.** The first version grouped consecutive impure statements; names like `_compute_ok_count` then hid a compute plus two prints. Now one statement per helper, except consecutive statements of the same kind (several `parser.add_argument`, several `lines.append`, several `print`) which form one helper.
- **Conditionally bound names.** A helper `return x` for a name bound only inside a loop, `except` branch or `if` changes the moment an unbound name fails. The planner refuses such groups (`definitely_binds` accepts assign, with-as, import, def, try without handlers, if with both branches); 7 blocks with `return` inside `try`/`with` were rewritten by hand with an explicit `None`/`False` result and an early `return` in the caller (`05b_coindesk_warmth_probe.py`, `06_coindesk_full_discovery.py`, `google_selector_probe.py`, `p1_fetch.py`, `p1_pipe_scraper.py`, `monosans_loader.py`, `probe_repo_cf_survey.py`). Example: in `06_coindesk_full_discovery.py` the final `print(f"Log -> {log_path}")` is skipped when warmup fails (early `return` inside the `with`); the helper returns `False` and the caller prints only on `True`.
- **The sandbox hook** rejects a call that pipes a script into another command (`script.py | tail`) and aborts the whole command; the parts of the call before the pipe do not run. Redirect to a file, then read it. `git add` with a `venv` path in the same command line is also rejected: the isolated trees for the import snapshots use `git init` only (enough for `git rev-parse` inside the scripts). zsh expands `====` in `echo`.
- **Isolated trees need a repository.** Some scripts call `git rev-parse --git-common-dir` at import (`analyze_write_times.py`, `p3_url_sampler.py`, `run_coindesk_riding.py`); in a bare archive copy they raise, which looked like a behaviour difference until the copy got a `git init`.
- **Naming quality is the weak point of the extraction.** Helper names come from the statement (`_compute_<target>`, `_print_<first words>`, `_add_arguments`, `_run_<loop variable>`) and a hand-made override list for loops and `try` blocks (about 70 names). Some derived names are cryptic (`_compute_n_s`, renamed in `snippet_quality_analysis.py`; `_compute_gap`, `_compute_only` remain). Rename freely; the inline check does not care about names.

## Observations outside the scope (not changed)

- `dev/news_pipeline/coindesk_proxy_riding/p3_url_sampler.py` assigns `SAMPLE_YEARS` twice with the same value (ws6 P2-05 mentioned it); left as is.
- 3 scripts exit at import time in both trees (`acquire_pipe.py`, `p3_target.py`, `probe_48h_article_fetch.py`): unchanged behaviour, not investigated.
- ws6 P4-09 (emoji in about 13 dev files) and P5-06 (silent handlers in dev) were not part of this task.

## Coordination

Worker wssrc changes `src/` and `cli.py` and will fix dev callers of the engine classes (`dev/search_pipeline` smoke scripts, `selector_js_equivalence_check.py`, `bee_probes` branch probe loader, `dev/tests` files using engine classes) after merging integration; conflicts in those dev files are expected at merge time and go to the merge. Integration had not moved (7bb68ff) when this work was committed.

## Files touched

`git diff integration --name-only -- dev process-docs`: 340 files under `dev/` at the second commit. Among them 291 existing `.py` files (172 only reordered, 119 with extraction helpers), the new `dev/refactor_sweep/` scripts and `md/` reports, dev DOCS.md files (LOC headings, `dev/DOCS.md` area list, an exemption sentence in `jhao104/patches/helper/DOCS.md`), and this file.
