# dev/search_pipeline Phase 1 size splits and unit-subfolder move (2026-09-24)

Worker record for the Phase 1 hit list of the dev sweep in this area. Two stages, four kinds of
commits: Stage A split every oversized function and module in place (files flat), Stage B moved
multi-file units into subfolders and split `DOCS.md`. Behaviour was to stay byte-identical; the
proof method is the reusable part of this entry.

## Numbers

Measured with an AST walk (function length = `end_lineno - lineno + 1`, signature included).

| Scope | Before | After |
|---|---|---|
| Modules over 400 LOC, whole area | 7 (`rerank_probe_smoke` 576, `31_date_availability_probe` 527, `16_search_to_pdf_probe` 495, `stage3_method_run_v3` 489, `20_docs_probe` 455, `15_citation_pdf_followup` 446, `bm25_sweep_smoke` 420) | 0 (largest 396, `altcha_trigger_probe`) |
| Functions at or above 50 LOC, flat files | 46 | 0 |
| Functions at or above 50 LOC, subfolders `_lib/`, `inspections/` | 2 (`_lib/parse.py::parse_smoke_report` 90, `inspections/inspect_engine_dom.py::build_report` 92) | 0 |
| Longest function | 166 (`13_timing_ablation.py::write_report`) | 49 |
| `DOCS.md` | 1 file, 640 lines | root 241 plus six unit files (153, 169, 97, 49, 177, 57) plus `_lib` 30 and `inspections` 23 |
| `./venv/bin/python -m pytest dev/tests/ -q` | 476 passed | 476 passed |

The 46 in the hit list the orchestrator gave was a flat-directory count. The two subfolder hits
only showed up on a recursive scan. Scan recursively.

The flaky `test_brave_engine::test_unrelated_button_before_containers_never_leaks_into_success_diagnosis`
named in the task did not fail in any of the three pytest runs of this session (start, mid, end).

## Stage A: method

Same technique as the earlier `dev/search_pipeline` splits recorded in the `refactor_sweep` area:
report builders become one renderer per section with the caller reduced to concatenation, long
bodies are cut along their real stages, and a module over 400 LOC gets siblings named
`_<entry name without numeric prefix>_<concern>.py`.

Rules applied on top, from the task:

- No heading comment above any new `def`. The helper name carries the meaning. A comment multiset
  diff (tokenize `COMMENT` tokens, old tree versus new tree) confirms it: zero added comments other
  than the section markers `# INFRASTRUCTURE` and `# FUNCTIONS` of the new modules.
- Existing comments and docstrings move unchanged with their code. Phase 2 owns removal.
- No `from src.` in any new file. Every new sibling either needs no `src` symbol or receives the
  callable or value as a parameter. Example: `bm25_sweep_smoke._classify` needs
  `src.search.merge.ACADEMIC/QA`, so `_build_query_section` in the report sibling takes it as the
  `classify` argument. Note on the hook: every file edit of this session went through scripted Python
  in Bash (line-range replacement, text slicing), not through the Write or Edit tools, so the
  `src/` import hook was never exercised and never refused anything. Whether it would have refused a
  Write of a moved entry file that re-states its existing `from src.` lines is untested.

### Where each large split landed

- `rerank_probe_smoke.py` (576 to 259): siblings `_config` (shared constants and query categories),
  `_gpu` (service helpers), `_rank` (per-config ranking stages), `_report`. The 130-line
  `_run_one_query` became `_fetch_and_filter` plus `_run_configs` returning two dicts (`fs`, `cf`);
  `_build_query_section` now takes `(query, fs, cf)` instead of 21 keyword arguments, because a
  21-parameter signature alone is 24 lines of the 50-line budget. The module still re-exports every
  name other scripts import (`QUERIES`, `QUERY_CATEGORIES`, `EMBEDDING_URL`, `RERANKER_URL`,
  `embed_batch`, `cross_encoder_rerank`, `cosine_sim`, `_bm25_score`, `_verify_services`,
  `close_browser`, `_query_engines_concurrent`, `_select_engines`). A tool that lists unused imports
  flags those as unused in the entry; they are the export surface, do not delete them.
- `bm25_sweep_smoke.py` (420 to 242): sibling `_report` holds `_build_query_section` (139 lines,
  now six section renderers), `_write_report`, `_overlap`. `VANILLA_KEY` moved with its trailing
  comment.
- `31_date_availability_probe.py` (527 to 174): siblings `_browser` (session, owns the `_browser`
  global together with every function that assigns it), `_nav` (eight per-engine flows plus
  `CONTAINER_SELECTOR`), `_report`.
- `stage3_method_run_v3.py` (489 to 249): siblings `_cheap` (M1-M5), `_gpu` (M6-M12), `_config`
  (`TOP_N`). The module-level `RERANKER_URL`/`SPLADE_URL`/`GENERATOR_URL` mutated through `global`
  became explicit parameters. `_run_one_pair` (64) is now `_run_methods` composed of
  `_run_cheap_methods` and `_run_gpu_methods`; the methods JSON key order is preserved on purpose
  (`{**cheap, **gpu}`), the file is compared byte-for-byte by anything diffing runs.
- `16_search_to_pdf_probe.py`, `15_citation_pdf_followup.py`, `20_docs_probe.py`: report sibling plus,
  where two modules share constants, a `_config` sibling (shared constants belong in a config
  module per the code standard; the earlier splits in this area passed them as parameters instead, both work).
- `25`-`29_*_probe.py`: one `_<name>_probe_report.py` each, with `write_report(records, report_dir
  [, latency_gate_s])`. The five report bodies stay separate on purpose, see the earlier `refactor_sweep`
  decision not to merge the `write_report` functions. The five sibling files were generated by slicing the
  original function text at its `"## ..."` list items, so the prose is verbatim.
- Report builders in `13_timing_ablation`, `02_burst_smoke`, `05_search_smoke`, `11_pipeline_smoke`,
  `pool_diff_v2_v3`, `stage4_aggregate*`, `value_eval_aggregate`, `stage1_pool_fetch`,
  `google_selector_probe`, `with_google_decoupling_smoke`, `altcha` report, `pooling_probe`,
  `bm25_idf_engine_smoke`: section renderers in place.
- Non-report bodies: `00_single_query.main`, `24_pydoll_teardown_verify` (two tests),
  `pydoll_fingerprint_probe.run_probe`, `altcha_trigger_probe.run_trigger_attempt`,
  `empty_classify_se.probe_query`, `inspect_query_log.main`, `single_query_pool_dump.run_probe`,
  `snippet_quality_analysis.compute_source_stats`, `value_eval_probe._run_one_pair`,
  `_lib/parse.py::parse_smoke_report`. The `try/finally` teardown stays at the call site in every
  case (the `refactor_sweep` area records the regression a dropped `finally` caused); `run_trigger_attempt` was checked with a raising
  callee to confirm the session close still runs.

### Deviations from "moved verbatim"

- Removed comment: `# Module-level; set once in run_method_run_v3 before first GPU call`. It described
  the three URL globals that no longer exist (now parameters). The only comment removed in the
  whole session.
- `31_date_availability_probe.py` used to import `re`, `parse_qs`, `urlparse` and never used them.
  The rebuilt entry does not import them. Not a behaviour change.
- `_build_category_summary` had `from collections import defaultdict` inside the function; the
  report sibling imports it at module top.
- `rerank_probe_smoke`: `_build_query_section`'s signature changed (above). `_write_report`
  (`bm25_sweep_smoke`) gained `top_n`. Report functions gained `report_dir` where the module-level
  `REPORT_DIR` would otherwise have been read from a sibling. All callers are inside this area.

## Stage A: proof of equivalence (no live probe)

Reusable harness, kept under `/tmp` (not persistent). Shape:

1. Snapshot the old tree with `git archive integration dev/search_pipeline dev/_lib` into
   `/tmp/eq/old`, rsync the working tree to `/tmp/eq/new`, symlink `src` into both.
2. One scenario script per target, run once per side in its own subprocess, stdout diffed.
   Inside a scenario: `datetime` in every module of the tree replaced by a frozen subclass,
   `time.perf_counter`/`time.monotonic` replaced by a counter (so the number and order of timing
   calls is part of the comparison), `httpx.post`/`httpx.AsyncClient` replaced by fakes,
   engine fan-out replaced by fixtures, `close_browser` replaced by a printing stub, output
   directories patched to per-side scratch directories.
3. Signature-adaptive calls (`inspect.signature`) where a report function gained `report_dir`.
4. Error paths covered the same way: API errors with retry, rate-skip cascade stop, `SystemExit`
   on missing service or `google_count == 0`, exception inside a guarded body.

Every target ended IDENTICAL: 00, 02, 05, 11, 13, 24, 25-29 (five modules times six record sets),
31 (report, nav functions, session lifecycle, `run_engine_query`), bm25, rerank, 20, 15, 16, stage3
v3 (three generator modes, two service failure modes, JSON output), altcha (report and
`run_trigger_attempt`), inspect_query_log, google_selector, empty_classify_se, pool_diff, pooling
(plain, cascade, API error), pydoll_fingerprint, single_query_pool_dump, stage1, snippet_quality,
stage4, stage4 v3, value_eval_aggregate, value_eval_probe, with_google, `_lib/parse` (all four real
`md/pipeline_smoke_*.md` files, 405 KB of JSON, plus a synthetic file), `inspect_engine_dom`.
CLI `--help` output was diffed for eight argparse scripts: identical.

### Findings the harness surfaced

- `asyncio.as_completed` order is not deterministic across process layouts. In
  `16_search_to_pdf_probe` the stderr order of two `[skip]` lines flipped between old and new until
  the scenario replaced `as_completed` with an ordered list; padding the OLD side with unrelated
  imports flipped it too, so the cause is memory layout, not the split. Do not chase such diffs.
- 14 modules do not import at baseline (2026-09-24, before any edit here). The cause is outside this
  area:
  - `src.search.merge` no longer exports `ACADEMIC`, `GENERAL`, `QA`, `_merge_and_rank`: breaks
    `bm25_sweep_smoke`, `rerank_probe_smoke`, `bm25_capped_smoke`, `bm25_compare_smoke`,
    `bm25_idf_engine_smoke`, `pooling_probe`, `single_query_pool_dump`, `stage1_pool_fetch`,
    `stage3_method_run`, `stage3_method_run_v3`, `value_eval_probe` (the whole ranking family).
  - `src.scraper.pdf_chain` does not exist: `16_search_to_pdf_probe`.
  - `src.search.engines.scholar` has no `MAX_WAIT_CYCLES`: `13_timing_ablation`.
  - `01_google_smoke.py` has no `load_config`/`start_browser`/`stop_browser`/`_build_js_patches`/
    `_inject_consent_cookie`/`_extract_scalar`: `00_single_query`.
  Nothing was fixed (out of scope). The scenarios injected stub attributes into `src.*` before
  import. The six new sibling modules that import `bm25_sweep_smoke` fail import for the same
  transitive reason: 63 modules imported cleanly before, 82 after, same 14 root causes.

### Baseline import failures, exact (14 modules, measured 2026-09-24 before any edit)

Measured by importing each module standalone from a `git archive integration` snapshot with the
project venv. Python stops at the first failing import, so "first error" is what the import reports
and "missing" is the full set checked afterwards against the live `src/` modules.

| Module | First error | Missing symbols |
|---|---|---|
| `bm25_sweep_smoke` | `ImportError: cannot import name 'ACADEMIC' from 'src.search.merge'` | `src.search.merge.ACADEMIC`, `GENERAL`, `QA`, `_merge_and_rank` (module exports only `build_engine_pools`) |
| `rerank_probe_smoke` | same, on `from src.search.merge import _merge_and_rank` after the `bm25_sweep_smoke` import chain fails | `src.search.merge._merge_and_rank` (plus the four above via `bm25_sweep_smoke`) |
| `bm25_capped_smoke`, `bm25_compare_smoke`, `bm25_idf_engine_smoke` | same (they import `bm25_sweep_smoke` first) | `src.search.merge._merge_and_rank` and the four above |
| `pooling_probe`, `single_query_pool_dump`, `stage1_pool_fetch`, `stage3_method_run`, `stage3_method_run_v3`, `value_eval_probe` | same (they import `bm25_sweep_smoke` / `rerank_probe_smoke` first) | the four above |
| `16_search_to_pdf_probe` | `ModuleNotFoundError: No module named 'src.scraper.pdf_chain'` | the whole module; the script imports `HARD_BLACKLIST`, `TIER1_DOMAINS`, `apply_tier1_transform`, `is_blacklisted`, `is_github_blob`, `parse_citation_pdf_url` from it |
| `13_timing_ablation` | `AttributeError: module 'src.search.engines.scholar' has no attribute 'MAX_WAIT_CYCLES'` | `src.search.engines.scholar.MAX_WAIT_CYCLES`, `WAIT_INTERVAL`, `_handle_consent`, `_JS_CONSENT`; also `_limiters["openalex"]` (the limiter registry holds only `google` at import time) |
| `00_single_query` | `AttributeError: module 'smoke' has no attribute 'load_config'` | `01_google_smoke.py` defines only `run_smoke_test`, `load_queries`, `run_query`, `write_report`; the six names `00` copies (`load_config`, `start_browser`, `stop_browser`, `_build_js_patches`, `_inject_consent_cookie`, `_extract_scalar`) do not exist there |

Present and fine: `src.search.search_web._query_engines_concurrent` and `_select_engines`,
`src.search.merge.build_engine_pools`, `src.search.engines.google._handle_consent` and `_JS_CONSENT`.

- `src.search.merge` stubs used by scenarios: `ACADEMIC`, `GENERAL`, `QA` frozen sets and a
  `_merge_and_rank` that dedups by URL. If the ranking family is ever repaired, rerun the scenarios
  without them.

## Stage B: unit-subfolder move

Units (entry script plus its exclusive import closure, grouped by topic):

| Folder | Content |
|---|---|
| `bee_probes/` | `cdp_starvation_probe`, `acquire_probe`, `branch_probe` and their `_*` siblings (17 files) |
| `browser_probes/` | probes 25-29, 31, `altcha_trigger_probe` and siblings (19) |
| `pdf_probes/` | probes 14, 15, 16 and siblings (10) |
| `domain_probes/` | `19_books_probe`, `20_docs_probe` and siblings (4) |
| `ranking_eval/` | stage1/3/4 scripts, `clean_pool`, `value_eval_*`, `pool_diff_v2_v3`, `single_query_pool_dump`, `pooling_probe`, `bm25_capped/compare/idf_*_smoke` (20) |
| `report_analysis/` | `engine_distribution_analysis`, `snippet_quality_analysis`, `snippet_selection_simulator`, `engine_health_audit`, `inspect_query_log` (5) |

Stayed flat: everything imported from outside the directory (`_google_fixture.py`, used by
`dev/tests/test_google_engine.py`), the two shared bases `bm25_sweep_smoke.py` and
`rerank_probe_smoke.py` with their siblings (imported by many `ranking_eval/` scripts), the
per-engine smokes, `no_google_burst_smoke.py` (named in `src/search/DOCS.md`),
`test_snippet_truncate.py`, `_lib/`, `inspections/`, `config.yml`, `queries.txt`, all output folders.

Path rule, applied with one textual replacement in each of the 75 moved files:
`Path(__file__).parent` becomes `Path(__file__).parent.parent` (and the `.resolve().parent` variant
in `altcha_trigger_probe.py`). `SCRIPT_DIR` therefore still resolves to `dev/search_pipeline/`, so
`md/`, `runs/`, `txt/`, `jsonl/`, `queries.txt`, `config.yml` and the three-level project root are
found exactly as before. Expressions that used `Path(__file__).parent.parent.parent` for the project
root grew one `.parent` automatically. Entries that import the flat shared bases keep their
existing `sys.path.insert(0, str(SCRIPT_DIR))`, which now points at the parent directory of the
subfolder; siblings resolve because Python puts the script's own directory first.

Proof: for every module name present on both sides (78 modules, 55 of them moved), each was executed
with `runpy.run_path` in its own subprocess (so module-level code ran, the `__main__` block did not),
every `Path` or path-string global and every `sys.path` entry added by the module was printed with the
tree prefix normalised, and old was compared with new. Result: identical for 77, one expected
difference (`SESSION_DIR` of `31_date_availability_probe` now lives in the `_browser` sibling from
Stage A). All Stage A scenarios were rerun on the moved layout: IDENTICAL.

Known stale text, moved unchanged because Phase 2 removes docstrings: 17 usage lines in moved
scripts still read `dev/search_pipeline/<script>.py` without the subfolder (`acquire_probe`,
`branch_probe`, `cdp_starvation_probe`, `clean_pool`, `single_query_pool_dump`, `stage1_pool_fetch`,
`stage3_method_run`, `stage3_method_run_v3`, `stage4_aggregate`, `stage4_aggregate_v3`,
`value_eval_probe`, `value_eval_aggregate`, `pool_diff_v2_v3`, `engine_health_audit` (three lines),
`inspect_query_log`) plus one prose reference to `26_brave_probe.py` in
`27_brave_headed_lane_probe.py`. Do not fix them in a Phase 1 pass; drop them with the docstrings.

## DOCS.md

Every `DOCS.md` in the area now follows the format in the code standard: Role, Public Interface, Flow,
Modules, State, no Gotchas section. Purposes are at most 25 words, roles at most 50, module headings
carry `wc -l`. Checked by script: 103 headings, 0 mismatches. The old entries of
`_lib/DOCS.md` listed callers that do not exist (`22_openlibrary_smoke.py`, `23_books_ab_smoke.py`,
`branch_probe.py`, `pool_diff_v2_v3.py`, `no_google_burst_smoke.py`, `scholar_http_probe.py`); the
rewrite lists the three real importers. The old root entries for `00_single_query` and `01_google_smoke`
said `_capture_sorry.py` imports `01`; it does not (it has no import of it). `00` loads `01` through
importlib and currently fails, see above.

Text cut from the old files is preserved below, verbatim, under the two Salvage headings.

## Phase 2 baseline (measured 2026-09-24, after Phase 1)

Over the whole area including `_lib/` and `inspections/`: 108 files, 75 docstrings, 793 comments
(shebang and the three section markers excluded). Per folder as `files/docstrings/comments`: flat
28/25/246, `bee_probes` 17/15/59, `browser_probes` 19/6/91, `pdf_probes` 10/3/78, `domain_probes`
4/2/27, `ranking_eval` 20/15/208, `report_analysis` 5/5/60, `_lib` 4/3/19, `inspections` 1/1/5.
The 2026-09-17 scan counted 59 files, 74 docstrings, 799 comments for this area, so the splits
added files but no comments.

## Incident: never pass `--help` to a script without argparse

To compare CLI help output old versus new, `--help` was passed to eleven scripts in one loop. Eight
have argparse and exited cleanly. Three have no argparse and simply RAN with the flag ignored:

- `15_citation_pdf_followup.py`, old and new copy, each ran to the end in about a minute: up to about
  250 live HTTP GETs per copy (124 source URLs, two hops) against publisher URLs.
- `20_docs_probe.py` (old copy, under `/tmp/eq/old`) started and launched a pydoll Chrome session,
  which uses the shared `~/.websearch/browser-session` profile and kills stale Chrome instances on
  that profile at start. It was stopped after under a minute with `kill <pid>` (PID confirmed by its
  command line first). Another agent's browser session that was running on that profile at that moment
  could have been terminated by this. The task forbade live probes; this was an error of the
  verification step, not of the split.
- `31_date_availability_probe.py` was next in the loop and was not reached.

Lesson: a scripted "check every entry" step must import, never execute; `--help` is only safe for
files where `grep -l argparse` says so. The path proof above uses `runpy.run_path` with a non-main
`run_name` for exactly that reason (run after the incident).

## For a successor

- Scan recursively; `find`/`glob` on the top directory misses `_lib/` and `inspections/`.
- Signature length counts. A 21-parameter function starts at 24 lines. Pass a dict or a small record.
- Order of work that worked: functions first, then re-measure modules, then module splits, because
  each function split adds about four lines and pushed five files past 400 during this pass.
- Generate sibling files by slicing the original text with a script, then verify by diff. Typing prose
  back invites silent edits; the diff of rendered output catches them either way.
- When a helper needs a value from another module, prefer a `_config` sibling over widening a
  signature once three or more values are shared.

## Salvage from the old `dev/search_pipeline/DOCS.md` (Purpose text cut to the 25-word limit)

Each entry is the full pre-split Purpose, verbatim, keyed by the module heading of the old file (LOC values are the old ones).

### 00_single_query.py (140 LOC)

Single-query debug runner — reuses `01_google_smoke.py` internals (`load_config`, `start_browser`, JS patches, consent-cookie injection) via `importlib` to hit one query and print DOM diagnostics (title, current URL) to stdout.

### 02_burst_smoke.py (263 LOC)

Burst smoke against the production CLI — invokes `cli.py search_batch` per batch (one subprocess per N queries, warm Chrome amortized). Validates the prod CLI path under the burst rate pattern.

### 05_search_smoke.py (218 LOC)

Multi-engine comparison smoke — imports the remaining 4 browser/HTTP engine classes (google, duckduckgo, google scholar, openalex), fans out per-engine in parallel (`asyncio.gather`), merges by URL preserving per-engine snippets (bypasses `_merge_and_rank`).

### 09_openalex_smoke.py (121 LOC)

OpenAlex smoke — `OpenAlexEngine().search()` per query (pure HTTP, no browser). Status taxonomy: OK / EMPTY / RATE_LIMITED / ERROR. Optional `OPENALEX_API_KEY` env var is picked up by the engine itself (no forwarding logic in this script).

### 11_pipeline_smoke.py (373 LOC)

Full-pipeline smoke — calls `search_web_workflow(query, _with_timings=True, engine_timeout=N)` per query (unlike `05`'s per-engine fanout, this goes through `_merge_and_rank`). Produces the singular baseline consumed by downstream investigation scripts (`snippet_quality_analysis.py`, `engine_distribution_analysis.py`, `snippet_selection_simulator.py`). Per-URL block: title/URL/engines + chosen `source`/`display` + `og`/`meta` + per-engine snippets. Per-query timing + slot-fill line. Per-Engine Status Aggregate section at end — `_STATUS_HINTS` and the reliability table's `STATUS_KEYS` dropped their 5 EMPTY_* sub-status entries (removed along with `src/search/status.py`'s guessed verdicts) and gained a plain `EMPTY` key, tracked explicitly so it is not miscounted into `ERROR_OTHER` by the fallback bucket.

### 12_max_results_probe.py (173 LOC)

Per-engine single-call ceiling probe — direct engine instantiation, one call per query at high `max_results` (Google/Scholar 100, others 200), observes actual returned count + latency + status.

### 13_free_word_probe.py (289 LOC)

Free-word query injection probe — appends `pdf`/`book` (no operator) to query string, measures domain-distribution shift across the 4 remaining engines. 3 queries × 3 variants (baseline/+pdf/+book).

### 13_timing_ablation.py (348 LOC)

Timing-config ablation — A (status-quo) vs B (aggressive Scholar polling/consent sleep/HTTP rate-limit) via concurrent fan-out across the 4 remaining engines. 3 queries × 2 configs, 2-min cooldown between configs.

### 15_citation_pdf_followup.py (446 LOC)

Two-hop `citation_pdf_url` validation — loads HTML_HAS_PDF_LINK URLs from probe 14's report, GETs each (Hop 1 extracts `citation_pdf_url` meta), GETs the extracted PDF URL (Hop 2). Per-domain semaphore keyed on PDF-host domain.

### 16_search_to_pdf_probe.py (495 LOC)

End-to-end search-to-PDF chain probe — runs `search_web_workflow` directly, applies full chain (Tier-1 transform / DIRECT .pdf / MULTI_STEP citation_pdf_url / BLACKLIST), saves real PDFs to `~/Downloads/`. Regression check after `pdf_chain` refactors.

### 20_docs_probe.py (455 LOC)

Empirical docs-domain probe — appends `documentation` to 12 broad tech queries, runs against Google/DDG. Evaluates H1-H13 heuristics (docs subdomain, readthedocs, gitbook, /docs/, /api/, etc.) against the URL pool. Informs `--docs` whitelist/heuristic design.

### 24_pydoll_teardown_verify.py (302 LOC)

Integration test for `kill_tab` teardown fix. T1: single hung tab (`about:blank` + never-resolving Promise, `await_promise=True`) through watchdog + `kill_tab` (wall ~ watchdog). T2: normal tab completes fine. T3: parallel batch of 5 hung tabs via `asyncio.gather` (mirrors production 5-engine fanout), verifies `Target.getTargets` delta=0 (no orphaned targets).

### 25_startpage_probe.py (384 LOC)

Go/no-go data probe for startpage.com scrapeability (self-contained — no `src/` import, dev-isolation guardrail). Drives the real homepage search form (load homepage, set `#q` via native setter + `input` event, real `.click()` on `button.search-btn`) to obtain a valid per-session `sc` token, then runs 10 queries (mainstream DE/EN, local-business DE, docs-style EN/DE) and records count/quality/block-marker per query.

### 26_brave_probe.py (378 LOC)

Go/no-go 3-condition gate probe for Brave Search (self-contained — no `src/` import, dev-isolation guardrail): real result rows + no PoW/CAPTCHA + per-query wall latency ≤5s, run one query at a time (no gather-special-casing) via the pydoll stealth stack (`src/search/browser.py` shape, inlined). Runs 10 queries, detects PoW/CAPTCHA via title/body marker scan + `a[href*="pow-captcha"]` presence, records per-query latency. Result: DROP — 4/10 OK then persistent PoW block from query 5 onward.

### 27_brave_headed_lane_probe.py (387 LOC)

Headed hard-engine lane probe (macOS) — tests whether a real Chrome window, backgrounded via `open -g` (no focus steal, isolated `--user-data-dir`), clears Brave's PoW/CAPTCHA where headless doesn't. Validates the `pydoll.browser.managers.BrowserProcessManager(process_creator=...)` override (`Chrome(options)` built, then `browser._browser_process_manager` swapped before `start()`) — `_open_process_creator` re-launches via `open -g -n -a "Google Chrome" --args --remote-debugging-port=<port> --user-data-dir=<isolated dir> ...`, teardown via CDP `browser.stop()` + unconditional `pkill` safety net (the `open` wrapper Popen gives pydoll's own reaper nothing real to kill). Result: DROP — only 2/10 clean before a persistent PoW block (worse than 26_brave_probe.py's 4/10 headless run), but the launch mechanism itself (headed-background + isolated profile + clean teardown, verified via `ps aux` showing zero orphaned processes) is validated and reusable for a future hard-engine candidate.

### 28_bing_probe.py (400 LOC)

Go/no-go scrapeability probe for bing.com (self-contained — no `src/` import) as a SECOND, independent access path to the Bing web index, redundant to DuckDuckGo's surrogate coverage. Runs 10 queries via pydoll stealth stack, headless. Result: CANDIDATE — 10/10 OK, 0 blocks, median 691ms (fastest browser-scraped engine probed to date). Confirms the old `#b_results .b_algo` selector had NOT structurally drifted (still live); new handling need: every organic href is wrapped in a `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect, unwrapped via `_clean_url` (parse `u` param, strip 2-char prefix, base64url-decode with padding, graceful fallback to raw href on failure).

### 29_yandex_probe.py (400 LOC)

Go/no-go scrapeability probe for yandex.com (self-contained — no `src/` import) as a genuine NEW-COVERAGE candidate — Yandex is one of the few remaining independent web indexes (own crawler), unlike Bing/Startpage which are redundancy paths to indexes already in the pool. Runs 10 queries via pydoll stealth stack, headless. Result: CANDIDATE under the relaxed criterion — 8/10 usable hits, longest consecutive clean run of 7, only 2 blocks (both with hard `showcaptcha` redirect-URL evidence, not just a text-marker guess). Confirms `li.serp-item` still live, `a.OrganicTitle-Link` gives a direct href (no unwrap needed, unlike Bing). Quality axis called honestly: German-query results genuinely relevant, not junk/region-skewed.

### 31_date_availability_probe.py (527 LOC)

Measurement-only probe (no wiring) — for the 8 DOM-scraped web engines (google, duckduckgo, mojeek, startpage, brave, bing, yandex, lobsters), does the live result page carry a date, and how: dedicated element (`<time>`/class-matched), snippet-text-only, nowhere, or unmeasurable (block/CAPTCHA/empty)? Self-contained (no `src/` import, matches 25/26/28/29/30_*_probe.py) — inline copy of the current `src/search/browser.py` session shape + each engine's current navigation/wait/diagnose logic, so the probe keeps measuring even if `src/` changes later. One JS pass per container captures `<time>` elements, class/id tokens matching a WORD-BOUNDARY regex (`date|time|age|publish(ed)?|when|ago` — deliberately not a substring match, which would false-positive on `update`/`candidate`/`validate`), full container text, and an HTML head — covers the dedicated-element and snippet-text cases in one pass. 3 queries per engine (2 EN news-shaped + 1 DE reference/timeless, to avoid an English-news-only bias), self-imposed (not rate-limiter-derived, since this script never goes through `src/search/rate_limiter.py`) 20s gap between same-engine queries, MINUTES-scale (180s) cooldown before a one-shot retry only when an engine is non-OK on all 3 primaries — a short gap can't distinguish a probe-induced block from a pre-existing cooldown. `google`/`duckduckgo`/`brave` pre-flagged as having returned 0 results in an earlier unrelated session run, so a repeat non-OK is annotated rather than presented as fresh.

### _capture_sorry.py (233 LOC)

Captures Google `/sorry/` block page — helper script, not a numbered experiment. Navigates to a search URL, checks if redirected to `/sorry/`, saves HTML + screenshot + MD summary.

### _cdp_starvation_probe_findings.py (173 LOC)

Narrative findings-doc assembly for `cdp_starvation_probe.py` — fixed-path investigation writeup (hypothesis, instrumentation, key numbers, per-query CDP-rate table, verdict, next steps) at a stable filename overwritten each run.

### _cdp_starvation_probe_instrument.py (45 LOC)

Passive instrumentation for `cdp_starvation_probe.py` — a pydoll `ConnectionHandler._process_single_message` monkeypatch (CDP message timestamps) plus an asyncio-logger handler capturing slow-callback warnings, both installed once and read later by the report.

### acquire_probe.py (170 LOC)

Phase 2 bee investigation — `RateLimiter.acquire()` instrumentation probe entry point. Discriminates hypotheses B (task never scheduled) / A-lock (stale lock) / A-sleep (sleeping on backoff) / C (acquire innocent). Historical verdict (as of the investigation date, see process-docs): A-sleep confirmed. Query category renamed `"captcha"` → `"empty"` (the guessed-verdict-removal milestone collapsed `EMPTY_BLOCK` into bare `EMPTY`; `engine_details`, the only status source this probe reads, carries no diagnosis to reconstruct which kind of empty a query was — an honest narrower label over a familiar wrong one). On cascade-reproduction failure this probe warns and still writes both report and findings (unlike `branch_probe.py`, which stops and writes a note instead — a real behavioural difference between the two siblings, not something this split changed). Monkeypatch, canary, analysis, and report/findings assembly are split into `_acquire_probe_*.py` siblings (own entries above).

### bm25_capped_smoke.py (243 LOC)

Per-engine top-K cap variant — pre-pool truncates each engine's results to top-K (K = google result count, fallback K=10), then BM25 vanilla on capped pool. 3-config compare: Hard-Slot, BM25 uncapped, BM25 capped.

### bm25_sweep_smoke.py (420 LOC)

BM25 parameter sensitivity sweep — 16-config main grid (b × stopwords × doc_repr at k1=1.2) + 4-config k1 sensitivity sweep, against Hard-Slot baseline. `BM25Uniform(BM25Okapi)` subclass overrides `_calc_idf` to force IDF=1.0 (TF + length-norm only). Base module for the whole `bm25_*` family — exports `QUERIES`, `VANILLA_K1`, `STOPWORDS`, `_build_pool`, `_tokenize`, `_doc_repr`, `_bm25_rank`, `BM25Uniform`.

### branch_probe.py (196 LOC)

Phase 3 bee investigation — sleep-branch discriminator entry point. Distinguishes which of the two `asyncio.sleep` branches inside `RateLimiter.acquire()` fires during zero-cascade queries: `backoff_sleep_attempt` vs `tokencap_sleep_attempt`. Structural discriminator: 6 engines have `.backoff()` calls (google, google_scholar, lobsters, mojeek, duckduckgo, semantic_scholar), 4 do not (crossref, openalex, stack_exchange, open_library). Query category renamed `"captcha"` → `"empty"` (same reason as `acquire_probe.py` above). Monkeypatch, canary, analysis, and report/findings assembly are split into `_branch_probe_*.py` siblings (own entries above).

### cdp_starvation_probe.py (153 LOC)

Phase 1 bee investigation — asyncio event-loop starvation probe entry point. Categorizes queries as normal/empty/zero_cascade (`empty` was `captcha`, keyed on `EMPTY_BLOCK` — renamed when that verdict was removed; `engine_details` carries no diagnosis to reconstruct which kind of empty a query was). Historical verdict (as of the investigation date, see process-docs): REFUTED (event loop p99=1.4ms, 0 CDP events during cascade). Unlike its two siblings (`branch_probe.py`, `acquire_probe.py`), always writes both outputs unconditionally — no `--smoke` flag, no cascade-reproduction check. Instrumentation, canary, and report/findings assembly are split into `_cdp_starvation_probe_*.py` siblings (own entries above).

### clean_pool.py (236 LOC)

Filter helper + oracle cleanup for 7-engine eval. `filter_pool(pool, drop_engines)` removes named engines from each entry's `engines`+`positions`, recomputes `min_position`, drops engine-less URLs. As script: generates `<pair>_oracle_v3clean.json` for all 16 (mode × query) pairs in the v2 ts_dir, backfilling loss-pairs where google/semantic_scholar picks are unavailable after filtering.

### empty_classify_se.py (204 LOC)

Classification probe for 15 Stack Exchange EMPTY queries from the same historical smoke baseline — direct httpx (no rate limiter, no API key) against `site=stackoverflow` (production-identical) + `site=stackexchange` (cross-site fallback). Status taxonomy: ENGINE_EMPTY/ENGINE_NICHE/RATE_LIMITED/PIPELINE_BUG/UNKNOWN.

### engine_distribution_analysis.py (301 LOC)

Per-engine slot-count and slot-share analysis over the newest `pipeline_smoke_*.md` baseline (auto-discovered via glob+sort). Sections: slot-count totals per engine (Total/GENERAL/ACADEMIC/QA/Solo/Overlap), Per-Engine Status Aggregate (quoted from smoke tail), slot-share with uniform + OK-adjusted baselines and signed delta columns, per-query distribution matrix.

### engine_health_audit.py (206 LOC)

Reads `src/logs/query_log.jsonl` and aggregates per-engine status counts. The EMPTY sub-status-aware rules (`BROKEN (DOM-DRIFT)`/`DEGRADED (ANTI-BOT)`/`HEALTHY-EMPTY`, keyed on `EMPTY_NO_CONTAINER`/`EMPTY_BLOCK`/`EMPTY_NO_RESULTS`) were removed — those sub-statuses no longer exist as of the guessed-verdict-removal milestone (every empty result now logs bare `EMPTY`, with its own diagnosis snapshot in the log record instead). The remaining `FLAG (PYDOLL-CANCEL-LEAK)` rule (`TIMEOUT_NONCOOP > 10%` of timeouts) is unaffected — `TIMEOUT_*` was never a guessed verdict. Bucket aggregation still uses `startswith("EMPTY"/"TIMEOUT"/"ERROR")` to tolerate sub-status names, which still works (`"EMPTY"` itself starts with `"EMPTY"`).

### google_selector_probe.py (250 LOC)

Google DOM-selector diagnostic — loads one query at `num=100`, counts production selector `#rso h3` matches vs `div.MjjYud` containers vs alternative selectors in the rendered DOM. Distinguishes selector limitations from server-side rendering caps.

### inspect_query_log.py (99 LOC)

Quick summary of `src/logs/query_log.jsonl` — total record count, wall_ms min/mean/max, bottleneck-engine and TIMEOUT-hit counts, full per-engine breakdown of the most recent query. Distinguishes `engine_run` (written always) vs `workflow_summary` (production-only, includes total_wall_ms + preview) vs old-style (no `record_type`, treated as `workflow_summary`).

### no_google_burst_smoke.py (217 LOC)

No-Google concurrent burst smoke — production `ScholarEngine` (HTTP) vs the 2 other remaining production engines under concurrent multi-engine burst pattern, without Google browser present. Architectural discriminator: does HTTP Scholar survive the burst pattern without the Google-driven browser warmup? Import switched from the dev-only `ScholarHTTPProbe` (see `scholar_http_probe.py`) to production `ScholarEngine` as part of an HTTP migration. The probe's whole purpose — Scholar's block rate — used to key on the removed `EMPTY_BLOCK` verdict; `_run_engine` now captures `search_with_reason`'s diagnosis dict directly (unlike `acquire_probe.py`/`branch_probe.py`/`cdp_starvation_probe.py`, which only see status through `engine_details` and cannot reconstruct this) and `_is_blocked(diagnosis)` derives the fact from `captcha_form` or a 30x `http_status`, both already in scholar's snapshot.

### pool_diff_v2_v3.py (240 LOC)

Pool diff — compares URL sets and engine counts across all 16 (mode × query) pairs between a v2 reference dir and a v3 ts_dir. Per-pair overlap_pct, new-in-v3, removed-from-v2, google_count comparison; aggregate mean overlap + per-engine OK% comparison.

### pooling_probe.py (363 LOC)

Capped-pool strategy comparison — 4 configs on the same capped pool (each engine contributes ≤ google_count URLs): C1 Overlap-Count, C2 BM25 (BM25Uniform k1=1.2 b=0.75), C3 Cross-Encoder (Qwen3-Reranker-0.6B, port 8082), C4 Embedding-Cosine (Qwen3-Embedding-0.6B, port 8084). Hard-stop: `google_count == 0` → query skipped, no fallback. Requires reranker + embedding GPU services running.

### rerank_probe_smoke.py (576 LOC)

URL-filter + BM25-Retrieve top-50 + 2-method semantic rerank. 5-config compare: Hard-Slot, Filter+BM25-only, Filter+BM25→Embedding-Cosine (Qwen3-Embedding-0.6B, port 8090/8084), Filter+BM25→Cross-Encoder (Qwen3-Reranker-0.6B, port 8082/8092), BM25-Capped reference. URL-pattern filter drops search-results-page URLs (`[?&](q|query|search|keyword|term|p)=`, `/search/`, `/sresults/`, `/scholar?q=`). Base module for `pooling_probe.py`/`single_query_pool_dump.py`/stage scripts — exports `QUERIES`, `QUERY_CATEGORIES`, `EMBEDDING_URL`, `RERANKER_URL`, `embed_batch`, `cross_encoder_rerank`, `cosine_sim`, `_bm25_score`, `_verify_services`, `close_browser`, `_query_engines_concurrent`, `_select_engines`.

### scholar_http_probe.py (149 LOC)

HTTP-based architectural alternative to `src/search/engines/scholar.py` — pure httpx + lxml against `scholar.google.com`, no browser. Status: dev-only PROBE, not wired into production `ENGINES` dict. `ScholarHTTPProbe` class (`name="scholar_http"`) uses a probe-local `RateLimiter` distinct from production `_limiters`. Its own sub-status sentinels (`_BLOCK`, `_NO_RESULTS`) are local module constants, not `src.search.status` — that module's `EMPTY_BLOCK`/`EMPTY_NO_RESULTS` were removed (the guessed-verdict-removal milestone), but this probe's own backoff experiment (`self._limiter.backoff()` on a detected block) is internal to this file and never reaches the production query log, so it keeps its own local vocabulary rather than adopting the production diagnosis-snapshot pattern.

### single_query_pool_dump.py (385 LOC)

Single-query capped-pool vs Top-N dump for 4 configs. Sections: per-engine raw, full capped pool, Top-N per config, comparison matrix (every pool URL × 4 configs → rank or —). Hard-stop: `google_count == 0` → exit, no fallback. Requires embedding (port 8084) + reranker (port 8082) GPU services.

### snippet_quality_analysis.py (384 LOC)

Per-source bloat + lexical-density analysis over the newest `pipeline_smoke_*.md` baseline (auto-discovered). 11 sources (8 engines + `scholar_strip` derived bucket + og + meta), 10 bloat-pattern regexes. Sections: per-source aggregated stats table, 8×8 engine-overlap matrix, all-URLs side-by-side per-URL block with winner annotation, "best by usefulness" aggregate, per-class breakdown (GENERAL/ACADEMIC/QA).

### snippet_selection_simulator.py (198 LOC)

Dry-run of new snippet-selection logic over the newest `pipeline_smoke_*.md` baseline. For each URL, gathers all non-empty sources (og, meta, per-engine snippets), scores each as `clean_len × lex_density`, picks the highest; falls back to best-of-worst when all sources are below `MIN_FLOOR=40` chars. Sections: summary (analyzed/no-content/floor-trigger counts + source distribution), per-query picks, floor-triggered cases list.

### stage1_pool_fetch.py (379 LOC)

Phase 12+ pool fetch (v3 schema) — 4 modes × 4 queries, per-pair `<mode>_<slug>_pool.json` + `<mode>_<slug>_engine_report.md`, global `engine_report_summary.md`. Every pool entry carries `positions: {engine: rank}` alongside `engines` + `min_position` (invariants: `set(engines)==set(positions.keys())`, `min_position==min(positions.values())`). `_STATUS_HINTS` dropped its 5 EMPTY_* sub-status entries and `engine_report_summary.md`'s per-engine table dropped its BLOCK% column (both removed along with `src/search/status.py`'s guessed verdicts — every empty result now logs bare `EMPTY`, so there is no more BLOCK-vs-EMPTY distinction left to report).

### stage3_method_run.py (209 LOC)

Phase 12+ method run (v2) — loads `<mode>_<slug>_pool.json` from a ts_dir, applies C1 Overlap / C2 BM25 / C2' BM25-Capped / C3 Cross-Encoder, writes `<mode>_<slug>_methods.json`. Dynamic reranker URL via `ensure_ready("reranker")` + `find_server_url("reranker")` (RAG server_manager). Exits with error if reranker cannot be reached.

### stage3_method_run_v3.py (489 LOC)

Phase 13 method run (12 methods) — loads `<mode>_<slug>_pool.json` (v3 schema) from `--pool-dir`, filters `{google, semantic_scholar}` via `clean_pool.filter_pool`, applies M1-M12: C1 Overlap, RRF, Structural-URL, BM25, BM25-Capped, C3 vanilla, C3+InstrPrefix, RRF+C3, SPLADE, SPLADE+C3, two-stage C3+LLM-Filter, LLM-Selector. GPU deps: reranker-0.6b (M6-M8,M10-M11), splade (M9-M10), generator-4b (M11-M12).

### stage4_aggregate.py (325 LOC)

Phase 12+ aggregate (v2) — loads pool/methods/oracle JSONs from a ts_dir, computes Jaccard overlap per C-method, writes per-pair `<mode>_<slug>_eval.md` + global `eval_summary.md` into the ts_dir. `--no-oracle` (smoke mode) generates MDs without oracle section to verify pool+methods pipeline integrity.

### stage4_aggregate_v3.py (300 LOC)

Phase 13 aggregate (12-method eval) — loads `*_pool.json` + `*_methods_v3.json` (pool_dir) + `*_oracle_v3clean.json` (oracle_dir), computes Jaccard per method, writes per-pair `<mode>_<slug>_eval_v3.md` + `eval_summary_v3.md` with per-mode mean Jaccard, per-method latency stats (mean/p50/p95/max/cold), Quality×Latency Pareto table (DOMINATED flagged).

### test_snippet_truncate.py (32 LOC)

Standalone assertion script for `src/search/snippet._truncate` — 4 regression-guard assertions (short text unchanged, clean period cut without ellipsis, word-boundary cut with ellipsis, hard cut at exactly MAX_SNIPPET_LEN+1 with ellipsis).

### value_eval_aggregate.py (325 LOC)

Pooling-investigation Stage 4 (v1, historical, superseded by `stage4_aggregate.py`/`stage4_aggregate_v3.py`) — loads `pool.json`+`methods.json`+`oracle.json` per pair, computes Jaccard `|oracle ∩ method| / |oracle ∪ method|`, writes per-query MD + summary MD with per-mode means + overall winner. Handles undersized-pool case (`undersized_pool=True AND pool_size=0` skipped in mode means). `--no-oracle` for pipeline-validation MDs without oracle section.

### value_eval_probe.py (369 LOC)

Pooling-investigation Stage 1+2 (v1, historical) — per `(mode, query)` pair fetches pool via `_query_engines_concurrent` with mode-specific query modifiers (+book/+pdf/+documentation for general engines) and post-merge URL filter, applies 4 C-methods (C1 Overlap on capped+filtered, C2 BM25 vanilla on full+filtered, C2' BM25-Capped, C3 Cross-Encoder Qwen3-Reranker-0.6B port 8082). Writes oracle-input pool.json (url+title+snippet only, alphabetical, no engine/score signals) and methods.json. Filter logic inlined (no `from src.` imports). `--smoke` runs 1 pair + auto-aggregates with `--no-oracle`.

### with_google_decoupling_smoke.py (189 LOC)

Verifies Scholar is absent from the default engine set (production `_select_engines(None)` path). Checks: Google browser engine present, `google_scholar` NOT in `engines_requested`, `engines_excluded["google_scholar"] == "decoupled_from_google"` in query log, no status attributed to Scholar at all. Runs 5 queries through `search_web_workflow(query, engines=None)` then reads the last 5 `query_log.jsonl` lines.

## Salvage from the old `dev/search_pipeline/DOCS.md` (Role and Gotchas sections)

Old Role paragraph:

Smoke tests, selector-drift probes, ranking-method eval harness, and bee-investigation instrumentation for `src/search/`. Own-level scripts range from per-engine production smokes (`0N_*_smoke.py`) to multi-stage pooling/reranking evals (`stage1..4_*`, `value_eval_*`) to one-off debugging probes (`cdp_starvation_probe.py`, `branch_probe.py`, `acquire_probe.py`). `_lib/` (own DOCS.md) holds shared parse/text helpers. `inspections/` (own DOCS.md, different level) holds DOM-selector-drift tooling.

Old Gotchas section:

`27_brave_headed_lane_probe.py` launches Chrome headed-but-backgrounded via its own inline `open -g -n -a "Google Chrome"` process_creator, with no focus-steal reclaim — `open -g` only suppresses activation at the launch moment (playwright#42343), so this window can still steal focus later in the run. Left as-is (out of scope for the milestone that added the alternative below). Any NEW headed-backgrounded Chrome launch in this area should use `dev/_lib/browser_launch.py` (own DOCS.md) instead of copying `27`'s mechanism — it adds the PID-keyed reclaim watchdog `27` is missing.

Several scripts (`bm25_capped_smoke.py`, `bm25_idf_engine_smoke.py`, `bm25_compare_smoke.py`, `pooling_probe.py`, `single_query_pool_dump.py`, `stage1_pool_fetch.py`, `stage3_method_run*.py`, `value_eval_probe.py`) import helpers directly from sibling script files (`bm25_sweep_smoke.py`, `rerank_probe_smoke.py`) via `sys.path.insert(0, str(SCRIPT_DIR))` — these are not `_lib/` modules; treat them as informal shared-code sources when editing either base file. GPU-dependent scripts (reranker/embedding/SPLADE/generator-4b at fixed localhost ports) fail hard if the corresponding RAG server isn't running — check `_verify_services()` / `ensure_ready()` calls before assuming a script is broken. `stage4_aggregate*.py` write eval MD directly into `runs/<ts_dir>/`, co-located with the pool/methods/oracle JSON they score — by design (no separate output dir; ts embedded in the dir name).

New files in this directory cannot `from src....` import at all — a repo-tooling hook blocks any `Write`/`Edit` that introduces a NEW such import line, even into a file that already has other `src/` imports (the 26 files in this directory that already import from `src/` are grandfathered, not a precedent for new files). `altcha_trigger_probe.py`'s sibling modules (`_altcha_trigger_probe_launch.py` etc.) inline-copy `src/scraper/chromium_process.py`'s launch shape instead of importing it for exactly this reason. Separately, local fixture testing during that same probe's build found that raw CDP `Input.dispatchMouseEvent` (and Playwright's own `.click()`/`page.mouse`, both tried) do not reliably reach shadow-DOM-scoped elements at all in the self-launch-plus-`connect_over_cdp` launch shape this project's chromium lane uses, even though the identical click works fine on light-DOM elements and on ANY element when Playwright owns the browser process directly instead of attaching externally — unresolved, did not block that milestone only because its real target turned out to be light DOM; see process-docs (`engine_reduction` area) before assuming a click-based trigger against a shadow-DOM target will work here.

## Salvage from the old `dev/search_pipeline/inspections/DOCS.md`

Old Role section (recovery flow):

DOM-inspection tooling for engine selector drift recovery. Use when a browser-based engine returns persistent EMPTY or TIMEOUT for queries that should match — meaning the production selectors no longer match the rendered DOM (engine updated their markup). Not for one-shot debug scripts — holds reusable methodology and committed inspection reports as historical evidence.

Recovery flow: engine returns EMPTY/TIMEOUT for N consecutive queries → run `inspect_engine_dom.py <engine_name> "<sample_query>"` → read report (H1 broken selectors + H2 new data-test-id candidates + Diagnosis) → update `_JS_WAIT`/`_JS_PARSE` in `src/search/engines/<engine>.py` → smoke-test via `dev/search_pipeline/<engine>_smoke.py`.

Old Purpose:

navigate to engine search page via production browser (pydoll stealth, JS rendered), run 7 DOM heuristics (selector presence, data-test-id inventory, repeating class clusters, class-substring scan, data-* attribute scan, HTML snippet, external link count), write timestamped MD report.

Old Gotchas section:

New engines must be added to `ENGINE_REGISTRY` in `inspect_engine_dom.py` before use — only `semantic_scholar` is configured; `google`, `google_scholar`, `duckduckgo`, `mojeek`, `lobsters` are TODO stubs. `md/semantic_scholar_20260508_*.md` are committed evidence reports (2026-05-08, diagnosed `div.cl-paper-row` selector drift → new selectors identified) — not throwaway output.
