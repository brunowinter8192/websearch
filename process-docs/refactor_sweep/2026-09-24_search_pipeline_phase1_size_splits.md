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


# Phase 2 comment and docstring sweep (2026-09-24)

Second half of this session. Scope: every `.py` under `dev/search_pipeline/` including all subfolders, `_lib/` and `inspections/` (108 files). Code standard: no comments, no docstrings; only the three section markers and a line-1 shebang remain.

Measured before the sweep on the merged `integration` tip: 868 items (75 docstrings plus 793 comment lines, one item per docstring and per comment line). Triage result: 81 already documented elsewhere (deleted), 114 moved into this file (below), 673 self-evident (deleted). After the sweep: 0 comments, 0 docstrings, 0 `__doc__` uses.

## Method

- Removal was done by one script (tokenize for comments, ast for docstrings), not by hand. Trailing comments lose only the comment and the whitespace before it; full-line comments and docstring statements are deleted. Blank lines were normalised only at removal points: the blank runs around a removed block merge into the larger of the two, a removed block at the start of a body leaves no blank line, and one blank line follows the shebang when a module docstring was the next thing.
- Proof that code is untouched: for every one of the 108 files `ast.dump` of the old file with docstring statements dropped equals `ast.dump` of the new file (0 mismatches). The only deliberate code change is below.
- The one landmine: `grep __doc__` had a single hit, `inspections/inspect_engine_dom.py` (`argparse.ArgumentParser(description=__doc__)`). With the module docstring gone `__doc__` would be `None` and `--help` would lose its description line. The text became the constant `DESCRIPTION` (same string, byte for byte) next to the other module constants, and the parser reads it. The other 19 argparse scripts pass explicit `description=` strings and never read `__doc__`.
- Heading comments that Phase 1 left directly above new `def` lines (for example `# Write markdown data report and return path` above the report writers) are covered: all comments went, none of them were kept.
- Classification key: (a) substance already in a `DOCS.md`, in the Phase 1 salvage sections of this file, or in a process-docs entry of another area, or recorded verbatim under (b) of the same module; (b) a real non-obvious fact recorded nowhere else, moved below unedited; (c) self-evident (restates the name or code, section labels, format examples, task or bead labels).
- No fact went into a `DOCS.md`; the format has no place for it and the facts below are per-module detail. The LOC headings in all `DOCS.md` files were updated to the new `wc -l` values.

## Triage counts per module

| Module | Items | (a) documented | (b) moved | (c) self-evident |
|---|---|---|---|---|
| `00_single_query.py` | 4 | 1 | 0 | 3 |
| `01_google_smoke.py` | 4 | 1 | 0 | 3 |
| `02_burst_smoke.py` | 11 | 1 | 0 | 10 |
| `04_ddg_smoke.py` | 4 | 1 | 0 | 3 |
| `05_search_smoke.py` | 12 | 1 | 0 | 11 |
| `08_scholar_smoke.py` | 5 | 1 | 0 | 4 |
| `09_openalex_smoke.py` | 4 | 1 | 0 | 3 |
| `11_pipeline_smoke.py` | 22 | 8 | 0 | 14 |
| `12_max_results_probe.py` | 9 | 0 | 5 | 4 |
| `13_free_word_probe.py` | 12 | 1 | 0 | 11 |
| `13_timing_ablation.py` | 14 | 1 | 0 | 13 |
| `24_pydoll_teardown_verify.py` | 24 | 3 | 19 | 2 |
| `_bm25_sweep_smoke_report.py` | 12 | 0 | 0 | 12 |
| `_capture_sorry.py` | 10 | 1 | 2 | 7 |
| `_google_fixture.py` | 1 | 0 | 1 | 0 |
| `_lib/parse.py` | 11 | 1 | 1 | 9 |
| `_lib/test_text.py` | 4 | 1 | 0 | 3 |
| `_lib/text.py` | 7 | 0 | 2 | 5 |
| `_rerank_probe_smoke_config.py` | 2 | 0 | 0 | 2 |
| `_rerank_probe_smoke_gpu.py` | 4 | 0 | 0 | 4 |
| `_rerank_probe_smoke_rank.py` | 6 | 0 | 1 | 5 |
| `_rerank_probe_smoke_report.py` | 8 | 0 | 0 | 8 |
| `bee_probes/_acquire_probe_analysis.py` | 3 | 0 | 0 | 3 |
| `bee_probes/_acquire_probe_canary.py` | 2 | 0 | 0 | 2 |
| `bee_probes/_acquire_probe_instrument.py` | 7 | 2 | 2 | 3 |
| `bee_probes/_acquire_probe_report.py` | 1 | 0 | 0 | 1 |
| `bee_probes/_branch_probe_analysis.py` | 3 | 0 | 0 | 3 |
| `bee_probes/_branch_probe_canary.py` | 2 | 0 | 0 | 2 |
| `bee_probes/_branch_probe_instrument.py` | 10 | 0 | 4 | 6 |
| `bee_probes/_cdp_starvation_probe_canary.py` | 10 | 0 | 1 | 9 |
| `bee_probes/_cdp_starvation_probe_findings.py` | 1 | 0 | 0 | 1 |
| `bee_probes/_cdp_starvation_probe_instrument.py` | 8 | 0 | 5 | 3 |
| `bee_probes/_cdp_starvation_probe_report.py` | 4 | 0 | 0 | 4 |
| `bee_probes/acquire_probe.py` | 6 | 4 | 2 | 0 |
| `bee_probes/branch_probe.py` | 7 | 4 | 2 | 1 |
| `bee_probes/cdp_starvation_probe.py` | 10 | 5 | 2 | 3 |
| `bm25_sweep_smoke.py` | 12 | 0 | 3 | 9 |
| `browser_probes/25_startpage_probe.py` | 15 | 0 | 1 | 14 |
| `browser_probes/26_brave_probe.py` | 11 | 0 | 1 | 10 |
| `browser_probes/27_brave_headed_lane_probe.py` | 18 | 0 | 10 | 8 |
| `browser_probes/28_bing_probe.py` | 14 | 0 | 3 | 11 |
| `browser_probes/29_yandex_probe.py` | 12 | 0 | 1 | 11 |
| `browser_probes/31_date_availability_probe.py` | 7 | 4 | 1 | 2 |
| `browser_probes/_bing_probe_report.py` | 2 | 0 | 0 | 2 |
| `browser_probes/_brave_headed_lane_probe_report.py` | 3 | 0 | 0 | 3 |
| `browser_probes/_brave_probe_report.py` | 2 | 0 | 0 | 2 |
| `browser_probes/_date_availability_probe_browser.py` | 2 | 2 | 0 | 0 |
| `browser_probes/_date_availability_probe_nav.py` | 2 | 1 | 0 | 1 |
| `browser_probes/_date_availability_probe_report.py` | 3 | 2 | 0 | 1 |
| `browser_probes/_startpage_probe_report.py` | 2 | 0 | 0 | 2 |
| `browser_probes/_yandex_probe_report.py` | 4 | 0 | 0 | 4 |
| `domain_probes/19_books_probe.py` | 16 | 1 | 0 | 15 |
| `domain_probes/20_docs_probe.py` | 1 | 1 | 0 | 0 |
| `domain_probes/_docs_probe_report.py` | 12 | 0 | 0 | 12 |
| `empty_classify_se.py` | 11 | 0 | 2 | 9 |
| `google_selector_probe.py` | 5 | 0 | 1 | 4 |
| `inspections/inspect_engine_dom.py` | 6 | 2 | 0 | 4 |
| `no_google_burst_smoke.py` | 15 | 9 | 3 | 3 |
| `pdf_probes/14_download_classify_probe.py` | 3 | 1 | 0 | 2 |
| `pdf_probes/15_citation_pdf_followup.py` | 11 | 1 | 0 | 10 |
| `pdf_probes/16_search_to_pdf_probe.py` | 19 | 1 | 0 | 18 |
| `pdf_probes/_citation_pdf_followup_report.py` | 8 | 0 | 0 | 8 |
| `pdf_probes/_download_classify_probe_classify.py` | 16 | 0 | 0 | 16 |
| `pdf_probes/_download_classify_probe_pool.py` | 9 | 0 | 0 | 9 |
| `pdf_probes/_download_classify_probe_report.py` | 8 | 0 | 0 | 8 |
| `pdf_probes/_search_to_pdf_probe_report.py` | 7 | 0 | 0 | 7 |
| `pydoll_fingerprint_probe.py` | 14 | 1 | 0 | 13 |
| `ranking_eval/_single_query_pool_dump_report.py` | 9 | 0 | 0 | 9 |
| `ranking_eval/_stage1_pool_fetch_report.py` | 10 | 5 | 2 | 3 |
| `ranking_eval/_stage3_method_run_v3_cheap.py` | 7 | 0 | 1 | 6 |
| `ranking_eval/_stage3_method_run_v3_gpu.py` | 19 | 0 | 0 | 19 |
| `ranking_eval/bm25_capped_smoke.py` | 8 | 0 | 1 | 7 |
| `ranking_eval/bm25_compare_smoke.py` | 4 | 0 | 1 | 3 |
| `ranking_eval/bm25_idf_engine_smoke.py` | 8 | 0 | 1 | 7 |
| `ranking_eval/clean_pool.py` | 7 | 0 | 4 | 3 |
| `ranking_eval/pool_diff_v2_v3.py` | 10 | 1 | 4 | 5 |
| `ranking_eval/pooling_probe.py` | 15 | 0 | 4 | 11 |
| `ranking_eval/single_query_pool_dump.py` | 6 | 0 | 1 | 5 |
| `ranking_eval/stage1_pool_fetch.py` | 10 | 0 | 1 | 9 |
| `ranking_eval/stage3_method_run.py` | 18 | 0 | 1 | 17 |
| `ranking_eval/stage3_method_run_v3.py` | 25 | 0 | 1 | 24 |
| `ranking_eval/stage4_aggregate.py` | 18 | 0 | 4 | 14 |
| `ranking_eval/stage4_aggregate_v3.py` | 10 | 0 | 1 | 9 |
| `ranking_eval/value_eval_aggregate.py` | 17 | 0 | 3 | 14 |
| `ranking_eval/value_eval_probe.py` | 22 | 0 | 3 | 19 |
| `report_analysis/engine_distribution_analysis.py` | 14 | 0 | 0 | 14 |
| `report_analysis/engine_health_audit.py` | 18 | 6 | 0 | 12 |
| `report_analysis/inspect_query_log.py` | 6 | 0 | 1 | 5 |
| `report_analysis/snippet_quality_analysis.py` | 17 | 0 | 1 | 16 |
| `report_analysis/snippet_selection_simulator.py` | 10 | 0 | 0 | 10 |
| `rerank_probe_smoke.py` | 19 | 1 | 0 | 18 |
| `scholar_http_probe.py` | 15 | 4 | 3 | 8 |
| `test_snippet_truncate.py` | 6 | 0 | 0 | 6 |
| `with_google_decoupling_smoke.py` | 6 | 0 | 1 | 5 |
| **total (94 files with items)** | **868** | **81** | **114** | **673** |

Fourteen further files carried no comment or docstring.

## Facts moved out of comments and docstrings, by module

Text is verbatim from the old files (comment lines joined in order, docstrings with their own line breaks). Each entry is labelled `line` of the pre-sweep file.

### `12_max_results_probe.py`

Comment (line 32):

```text
# Per-engine max_results: high enough that post-fetch slice never binds; capped where engine hard-limits anyway
```

Comment (line 34-37):

```text
# num= capped server-side at 100; 100 avoids bot-signal of num=200
# same as Google; Scholar renders max ~20
# no count param — slice-only; page renders naturally
# per_page= API param; documented ceiling is 200
```

### `24_pydoll_teardown_verify.py`

Docstring (line 2):

```text
Verification script for TASK 1 (7u5) — deterministic pydoll tab teardown.

Three tests:
  1. Single hung tab (about:blank + never-resolving Promise) + kill_tab: wall ~= watchdog
     (<8s), registry clean.
  2. Single normal tab (about:blank, completes OK) + kill_tab: completes fine, registry clean.
  3. Parallel batch of N=5 hung tabs via asyncio.gather (mirrors production fanout):
     all 5 tabs cleaned deterministically, Target.getTargets count back to baseline,
     wall ~= watchdog (NOT 5x65s).

Hang simulation: about:blank + execute_script("return new Promise(function() {})",
await_promise=True). Browser process stays fully responsive (contrast: chrome://hang stalls
browser IPC too, making close_target itself slow — that's not the production scenario).

Measurement: Target.getTargets via browser connection (CDP) as primary tab-count metric —
reliable on macOS where pgrep --type=renderer reports 0 for headless Chrome.

Usage (from project root):
    ./venv/bin/python dev/search_pipeline/24_pydoll_teardown_verify.py

Output: MD report to dev/search_pipeline/md/teardown_verify_<ts>.md + stdout summary.
```

Comment (line 44-45):

```text
# generous: watchdog(5s) + kill_tab overhead(< 3s)
# mirrors 5-engine pydoll fanout
```

Comment (line 109-110):

```text
# Simulate TIMEOUT_NONCOOP: chrome://hang freezes renderer — same mechanism as production hang
# With kill_tab fix: wall time should be ~WATCHDOG, not watchdog+60s
```

Comment (line 150-153):

```text
# about:blank load is instant; then a never-resolving JS Promise simulates
# the production TIMEOUT_NONCOOP scenario (execute_script waiting for CDP
# Runtime.evaluate response that never comes). Browser process stays responsive
# so close_target via browser connection completes in <100ms after cancel.
```

Comment (line 223-224):

```text
# Count open CDP targets (tabs) via browser-level Target.getTargets — reliable on macOS headless
# where pgrep --type=renderer returns 0. Filters to type="page" only (excludes service workers etc.)
```

Comment (line 232-234):

```text
# End-to-end: N=5 hung tabs via asyncio.gather — mirrors production 5-engine pydoll fanout.
# All tabs hang on chrome://hang; watchdog fires on the gather; kill_tab in each finally.
# Primary metric: CDP target count (via browser connection) back to baseline after gather.
```

Comment (line 282-286):

```text
# Navigate first so the renderer is healthy (browser IPC stays responsive).
# Then execute a never-resolving Promise with await_promise=True — renderer
# waits indefinitely on the Promise; browser process stays fully responsive
# so close_target via browser connection completes instantly after cancel.
# (chrome://hang hangs Chrome's IPC too, causing close_target itself to stall.)
```

### `_capture_sorry.py`

Comment (line 59):

```text
# Build ChromiumOptions from config — mirrors 01_google_smoke.py
```

Comment (line 90):

```text
# Build JS fingerprint patch string — mirrors 01_google_smoke.py
```

### `_google_fixture.py`

Docstring (line 1):

```text
Deterministic local fixture server for src/search/engines/google.py's redirect-resolution fix
(process-docs/search_pipeline/ — google_goto_redirect_fix.md carries the investigation).

Generated, not a trimmed copy of the real 816 KB saved page (dev/access_recovery/html/
google_dom_probe_20260918_181820/best-noise-cancelling-headphones-2025_num10.html, gitignored,
read directly from the absolute path during this milestone) — the same choice _fixture_site.py
makes and for the same reason: the statement drives the page, not the other way around. The
element chain, classes and attribute shapes below (div.MjjYud > div.A6K0A > div.N54PNb.BToiNc >
div.kb0PBd.A9Y9g > div.yuRUbf > div.b8lM7 > span.V9tjod > a.zReHs[jsname=UWckNb][href^="/goto?
url="] > h3.LC20lb, sibling div.kb0PBd.A9Y9g > div.VwiC3b > span.YrbPuc + text + a.vzmbzf) are
copied verbatim from that real page's structure. Dropped: base64 inline <img> data URIs, the
multi-KB inline <script>/<style> blocks, and Google's own chrome (login/policy/footer links,
People Also Ask, ads, related searches) — none of it is read by google.py's parse JS before or
after this fix.

Unlike _fixture_site.py's one module-scoped server serving one fixed site to every test in its
file, this fixture's four required test scenarios (8 happy results, 3 unhappy /goto cases mixed
with happy ones, a duplicate-destination pair, zero results) each need genuinely different served
content — so start_fixture_server here takes the result specs as a parameter and each test starts
its own short-lived server, rather than mutating shared state via /_control/* between tests.

/goto?url=<token> tokens are short semantic strings ("ok1", "dup_a"/"dup_b", "bad_status", ...),
not realistic-looking base64 blobs — the real blob's bytes carry no recoverable meaning (see the
process-docs entry), so an opaque readable token is equally faithful to what actually matters
(a per-result opaque identifier) while being far easier to read in a test failure.
```

### `_lib/parse.py`

Comment (line 116):

```text
# og | meta line — checked before generic engine pattern ("og" not in KNOWN_ENGINES)
```

### `_lib/text.py`

Comment (line 30):

```text
# Bloat detection patterns (derived from Phase A eyeball of actual snippets)
```

Comment (line 52):

```text
# Remove Google doubled title+domain prefix (heuristic: maximize cut across all repeated-chunk matches)
```

### `_rerank_probe_smoke_rank.py`

Comment (line 56):

```text
# Filter out empty/whitespace-only texts — reranker returns 400 on empty documents
```

### `bee_probes/_acquire_probe_instrument.py`

Docstring (line 29):

```text
Wraps asyncio.Lock to record lock_attempt / lock_granted / lock_released|lock_stuck.

    lock_stuck = lock.locked() is True after __aexit__ completes — Python 3.14 regression signal.
    
```

Comment (line 50):

```text
# Distinguish correct release from stuck lock (Python 3.14 non-release hypothesis)
```

### `bee_probes/_branch_probe_instrument.py`

Comment (line 10-12):

```text
# Monkey-patch RateLimiter.acquire BEFORE any src.search imports.
# Full replacement (not wrapper) — byte-identical body to rate_limiter.py:acquire()
# with branch-discriminator event-emits before each asyncio.sleep.
```

Docstring (line 34):

```text
Byte-identical to rate_limiter.py:acquire() + branch-discriminator event-emits.
```

### `bee_probes/_cdp_starvation_probe_canary.py`

Comment (line 7):

```text
# exclude first N seconds from statistics (Chrome boot noise)
```

### `bee_probes/_cdp_starvation_probe_instrument.py`

Comment (line 9-11):

```text
# --- Monkey-patch pydoll BEFORE importing src modules ---
# Target: ConnectionHandler._process_single_message (connection_handler.py:244)
# Called exactly once per CDP message in the receive loop.
```

Comment (line 26):

```text
# Pattern A: log callbacks blocking event loop > 50ms
```

Comment (line 28):

```text
# asyncio "Executing ... took Xs" log lines
```

### `bee_probes/acquire_probe.py`

Docstring (line 2):

```text
RateLimiter.acquire() instrumentation probe — Phase 2 bee investigation.

Discriminates three hypotheses for zero_cascade queries (all 9+ engines RATE_SKIP):
  B:       enter=N                  — Task never scheduled by asyncio
  A-lock:  enter=Y, lg=N, ~5000ms  — entered acquire() but blocked waiting for the lock
  A-sleep: enter=Y, lg=Y, ~5000ms  — got lock, blocked on asyncio.sleep(backoff_s)
  C:       enter=Y, exit_ok        — acquire() innocent, bug elsewhere

Phase 1 REFUTED CDP starvation (event loop p99=1.4ms, 0 CDP events during cascade).
New hypothesis: Python 3.14 asyncio.Lock non-release under CancelledError causes
stale lock that blocks subsequent queries on same engine.

Usage:
    ./venv/bin/python3 dev/search_pipeline/acquire_probe.py [--max-queries N] [--smoke]

    --smoke: 4-query dry-run, prints per-engine event detail to stderr, no report written.
             Run first to verify instrumentation is live before full 20-query run.

Output (full run only):
    dev/search_pipeline/md/acquire_probe_<ts>.md
```

Comment (line 128):

```text
# Cascade expected: ≥5/20 based on Phase 1 baseline; for shorter smoke: 0 OK
```

### `bee_probes/branch_probe.py`

Docstring (line 2):

```text
Sleep-branch discriminator probe — Phase 3 bee investigation.

Discriminates WHICH of the two asyncio.sleep branches inside RateLimiter.acquire()
fires during zero_cascade queries (all 9 engines RATE_SKIP simultaneously):

  backoff_sleep_attempt  — if now < self._backoff_until:  (rate_limiter.py line 36)
  tokencap_sleep_attempt — if len(self._tokens) >= self._max_requests:  (line 47)

Phase 2 confirmed A-sleep: all 9 engines enter acquire(), get lock, sleep, get cancelled
at ~5001ms. Phase 2 inferred backoff-cascade but did NOT distinguish which branch fired.
Phase 3 adds branch-level events to settle this.

Structural discriminator: 6 engines have .backoff() call in engine source (google,
google_scholar, lobsters, mojeek, duckduckgo, semantic_scholar). 4 do NOT (crossref,
openalex, stack_exchange, open_library). Backoff-immune engines cannot enter the backoff
branch unless an unknown code path calls .backoff() on their limiter.

Usage:
    ./venv/bin/python3 dev/search_pipeline/branch_probe.py [--max-queries N] [--smoke]

    --smoke: 4-query dry-run. Prints per-engine detail to stderr. No report written.
             Run before full probe to verify instrumentation is live.

Output (full run only):
    dev/search_pipeline/md/branch_probe_<ts>.md
```

Comment (line 59):

```text
# 4 engines have NO .backoff() call in engine source — cannot enter backoff branch legitimately
```

### `bee_probes/cdp_starvation_probe.py`

Docstring (line 2):

```text
CDP starvation probe — Pattern A (asyncio debug) + Pattern B (canary latency) + CDP event counter.

Hypothesis: Chrome CDP event flooding during CAPTCHA navigation starves the asyncio event loop,
causing all 9 engines' asyncio.wait_for(limiter.acquire(), 5.0) to time out simultaneously.
Builds on prior zero-query diagnosis analysis.

Usage:
    ./venv/bin/python3 dev/search_pipeline/cdp_starvation_probe.py [--max-queries N]

Output:
    dev/search_pipeline/md/cdp_probe_<ts>.md
```

Comment (line 94):

```text
# All-RATE_SKIP = zero-cascade query (post-CAPTCHA starvation cascade)
```

### `bm25_sweep_smoke.py`

Docstring (line 2):

```text
BM25 Sweep Probe vs Hard-Slot Baseline.

Ranks the same deduplicated URL pool per query using:
  A) Hard-Slot: _merge_and_rank from src.search.merge (12/6/2 class slots)
  B) BM25 sweep: 16-config main grid (b x stopwords x doc_repr, k1 fixed at 1.2)
               + 4-config k1 sensitivity sweep at default-other-knobs

IDF handling: uniform IDF=1.0 per user design (query-word relevance is user-defined,
not corpus-derived; stopword filter replaces IDF discrimination). Reduces BM25 to
TF + length-normalization only.

Implementation choice: BM25Uniform subclasses rank_bm25.BM25Okapi and overrides
_calc_idf to set self.idf[word]=1.0 for all terms. Preferred over a custom 30-LOC
implementation because _calc_idf is an explicit extension point in BM25Okapi and
the override is 5 LOC. Library (rank_bm25) already in venv; k1/b tunable via
constructor.

Stopword list: ~45-word inline English set (determiners, prepositions, auxiliaries).
NLTK (~180 words) not used — no dependency, and for short title+snippet text the
marginal coverage gain of 180 vs 45 words is small.

Output: dev/search_pipeline/md/bm25_sweep_<ts>.md
```

Comment (line 159):

```text
# Merge raw results by URL — Step 1 of _merge_and_rank extracted to avoid slot allocation
```

Comment (line 208):

```text
# b=1.0 + empty-doc edge case
```

### `browser_probes/25_startpage_probe.py`

Docstring (line 2):

```text
Startpage go/no-go probe — empirically checks scrapeability of startpage.com from this IP.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Historical note: Startpage was dropped previously at "0/30 results, root cause unclear".
Empirical finding here: a direct GET to /sp/search?query=... (no prior homepage visit) returns
a degraded empty shell with zero organic results and NO captcha/block marker — the request is
missing the per-session `sc` token embedded in the homepage's search form. That silent-empty
behavior is the most likely explanation for the historical 0/30. This probe instead drives the
real homepage search form (load homepage -> set #q -> click .search-btn) to get a valid session
token, then measures actual result count/quality/block behavior per query.
```

### `browser_probes/26_brave_probe.py`

Docstring (line 2):

```text
Brave Search go/no-go probe — empirically checks the 3-condition gate for browser-scrape viability:
real result rows + no PoW/CAPTCHA trigger + per-query wall latency consistently <= 5s, run one query
at a time the way the production asyncio.gather pool would run each engine (no special-casing).

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup below
is a copy of the shape used by src/search/browser.py, not a shared import.

Background: Brave was previously dropped — PoW CAPTCHA across an 8-combination pydoll stealth matrix
(best 10/30), Patchright-with-Chromium (slider CAPTCHA instead of PoW, 0/30), Camoufox/Firefox (7/30).
Decisive killer was latency (10-15s/query on any CAPTCHA path). The untested angle per the stealth
resume note was Patchright with a REAL Chrome binary (channel="chrome", headless) — tried here FIRST
(see inline exploration below the module docstring in process-docs, not in this script) and found to
still trigger a slider CAPTCHA in headless mode (title "Captcha - Brave Search") on the very first
query, while the SAME real-Chrome binary succeeds headed (no CAPTCHA) — i.e. headless-ness itself is
the dominant signal for Patchright+real-Chrome against Brave, not the Chromium-vs-Chrome binary
identity the resume note suspected. Headed is not a viable production mode (server pipeline, no
display), so that angle is closed without a production candidate.

This probe instead runs the SECOND angle from scope: the pydoll stealth stack already used by the
production engines (src/search/browser.py fingerprint patches), which in initial hand-testing reached
Brave's results page headless WITHOUT a CAPTCHA — the opposite of the Patchright-headless outcome.
That is the stack measured here across the full query set.
```

### `browser_probes/27_brave_headed_lane_probe.py`

Docstring (line 2):

```text
Headed hard-engine lane probe (macOS) — Brave via headed-but-backgrounded Chrome.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll session setup below
follows the shape of src/search/browser.py, not a shared import.

Background: dev/search_pipeline/26_brave_probe.py established that headless (both pydoll-stealth
and Patchright+real-Chrome) trips Brave's PoW/CAPTCHA — pydoll-stealth got 4/10 clean before a
persistent block, Patchright+real-Chrome was blocked immediately headless but passed HEADED. Xvfb
is irrelevant here (Linux-only virtual-display trick; this Mac has a real screen). The lever tested
in this probe: run the system Google Chrome HEADED (a real window renders) but BACKGROUNDED via
macOS `open -g` so it never steals focus — pydoll connects to it over CDP exactly as if it had
launched it directly.

Launch mechanism (the actual novel piece of this probe):
- pydoll's BrowserProcessManager accepts a `process_creator` callback: a function taking the full
  launch command list (`[binary_location, "--remote-debugging-port=<port>", *other_args]`) and
  returning a subprocess.Popen. Chrome(options) does not expose this via its constructor, so the
  manager is swapped in AFTER construction, BEFORE start():
      browser = Chrome(options)
      browser._browser_process_manager = BrowserProcessManager(process_creator=_open_process_creator)
      tab = await browser.start()
- `_open_process_creator` drops the resolved binary_location (unused — `open -a` targets the app
  bundle directly) and re-launches via:
      open -g -n -a "Google Chrome" --args --remote-debugging-port=<port> --user-data-dir=<isolated dir> ...
  `-g` = no foreground activation (no focus steal). `-n` = force a new instance (belt-and-suspenders;
  the isolated --user-data-dir alone already forces a fresh process since Chrome's singleton check
  is a lock file inside the profile dir).
- `open -g` returns immediately, so the Popen handed back to pydoll is the short-lived `open`
  wrapper, not Chrome itself — pydoll's own stop_process() has nothing to reap. Teardown is CDP
  `browser.stop()` (Browser.close command — quits the whole isolated-profile Chrome instance since
  it's the only window in that profile) PLUS an explicit `pkill -f user-data-dir=<isolated dir>`
  safety net regardless of whether stop() succeeds.
```

Comment (line 56-57):

```text
# Dedicated, isolated profile — NOT the shared engine session dir (src/search/browser.py's
# SESSION_DIR) — for block-isolation from production engines and to force a fresh Chrome instance.
```

Comment (line 149-150):

```text
# Launch the system Google Chrome headed-but-backgrounded via macOS `open -g` — the actual novel
# launch mechanism this probe tests (see module docstring for the full rationale)
```

Comment (line 152):

```text
# drop resolved binary_location; `open -a` targets the app bundle directly
```

Comment (line 172):

```text
# options.headless left at its default False — headed is the whole point of this probe
```

Comment (line 178-180):

```text
# Stop the browser via CDP Browser.close, then a pkill safety net regardless of outcome — the
# process_creator's Popen (the short-lived `open` wrapper) gives pydoll's own stop_process() nothing
# real to reap, so the pkill is not optional cleanup, it's the actual teardown guarantee.
```

### `browser_probes/28_bing_probe.py`

Docstring (line 2):

```text
Bing Search go/no-go probe — empirically checks scrapeability of bing.com for a SECOND,
independent access path to the Bing web index (redundant to DuckDuckGo, which already surrogates
the same index) — symmetric to google(direct)+startpage(surrogate).

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Historical note: Bing was dropped 2026-05-04 on COVERAGE grounds (DDG already IS Bing's index —
no new URLs) and its old selector `#b_results .b_algo` had drifted. This probe answers a DIFFERENT
question — scrapeability + latency for redundancy, not coverage — and re-derives the CURRENT DOM
from scratch rather than trusting the old selector.

Empirical finding: `#b_results .b_algo` had NOT actually drifted in the way the drop note implied —
`li.b_algo` containers are still present and populated (10/page). What DID change/needs handling:
Bing wraps every organic result href in a `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking
redirect (not present historically at prior evaluation, or not documented) — the destination URL
must be unwrapped: parse the `u` query param, strip its 2-char prefix (observed as `a1`), then
base64-urlsafe-decode (with padding) to get the real URL. A cookie/consent banner ("Microsoft und
unsere Drittanbieter verwenden Cookies...") is present in the DOM but is NON-BLOCKING for scraping —
it renders as an overlay alongside full results, not a gate (unlike Google's consent redirect or
Startpage's homepage-token flow); no click/accept step is needed to read `li.b_algo` content.
```

Comment (line 203-204):

```text
# Unwrap Bing's `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect to the real
# destination URL — the `u` param is base64url-encoded with a 2-char prefix (observed: "a1")
```

### `browser_probes/29_yandex_probe.py`

Docstring (line 2):

```text
Yandex Search go/no-go probe — empirically checks scrapeability of yandex.com, one of the few
remaining INDEPENDENT web indexes (own crawler, distinct from Google/Bing) — a genuine new-coverage
candidate for the general axis, and a hard anti-bot target (Yandex SmartCaptcha), in the Brave league.

Self-contained: does NOT import src/ (dev-script isolation) — the pydoll Chrome session setup
below is a copy of the shape used by src/search/browser.py, not a shared import.

Decision criterion (relaxed, per task): DROP only if there is truly no way through — blocked from
the very first query, never a single usable result. A handful of clean hits before any eventual
block is a CANDIDATE (real usage is 3-4 queries every few days — comfortably inside any clean
window observed), same reasoning that landed Brave as a production candidate. Quality (relevance
of results, especially for German/Western queries against a Russia-based index) is tracked as a
SEPARATE axis from access/blocking.

Empirical finding: `https://yandex.com/search/?text=<q>` (yandex.com, NOT yandex.ru) redirects to
`&lr=<region_id>` (a region parameter, auto-detected from IP geolocation — no block, no consent
step) and renders full results immediately. The old `li.serp-item` container selector is STILL the
live shape (confirmed via direct DOM inspection) — title is `a.OrganicTitle-Link` (direct href, NO
URL-wrapping/redirect unlike Bing's ck/a), snippet is `.OrganicText .OrganicTextContentSpan`.
```

### `browser_probes/31_date_availability_probe.py`

Docstring (line 2):

```text
Date-availability probe — Milestone 2 measurement for the 8 DOM-scraped web engines
(google, duckduckgo, mojeek, startpage, brave, bing, yandex, lobsters).

Question: does the live result page carry a date, and if so how (dedicated element vs
snippet-text-only vs nowhere)? Not a feature change — no src/ touched, no wiring.

Self-contained: does NOT import src/ (dev-script isolation, matches 25/26/28/29/30_*_probe.py) —
the pydoll Chrome session setup and each engine's navigation/wait/diagnose logic below are an
inline copy of the CURRENT shape in src/search/browser.py + src/search/engines/*.py, not a
shared import — the probe keeps measuring even if src/ changes underneath it later.

Evidence capture, one JS pass per container (covers case 1 and case 2 together):
  - <time> elements (tag + datetime attribute + text) -> dedicated-element evidence
  - class/id tokens matching a WORD-BOUNDARY regex for date/time/age/publish/when/ago
    (not a raw substring — substring would false-positive on 'update'/'candidate'/'validate')
  - full container text (600 chars) -> snippet-text-only date-prefix evidence
  - outerHTML head (3000 chars) -> structural context

Pacing: self-imposed politeness gap between requests to the SAME engine — this script does NOT
go through src/search/rate_limiter.py at all (self-contained), so there is no quota being
respected here, just avoiding a rapid-fire burst against a live server. If an engine is non-OK
across ALL primary queries, one retry follows a MINUTES-scale cooldown (not seconds) — a short
gap cannot distinguish a probe-induced block from an engine that was already in a cooled-down
state from unrelated earlier activity this session. google, duckduckgo, and brave are flagged
up front as having returned 0 results in an EARLIER live run this session (unrelated to this
probe) — a repeat non-OK on those three is annotated as pre-existing, not attributed to the probe.
```

### `empty_classify_se.py`

Docstring (line 2):

```text
Classify 15 StackEx EMPTY queries from smoke_20260504_023641: SO probe + cross-site probe via httpx.
```

Comment (line 19):

```text
# (smoke_row, query) for all 15 StackEx EMPTY entries from smoke_20260504_023641
```

### `google_selector_probe.py`

Docstring (line 2):

```text
Google DOM selector probe — diagnoses why num=100 returns only 9-11 results.
```

### `no_google_burst_smoke.py`

Docstring (line 2):

```text
No-Google concurrent burst smoke — production ScholarEngine vs 8 production engines.

Architectural discriminator test: does HTTP Scholar survive the concurrent multi-engine
burst pattern when Google browser is absent?

Engine set (9 total, no Google):
  google_scholar (production HTTP), duckduckgo, mojeek, lobsters, crossref, openalex,
  stack_exchange, semantic_scholar, open_library

Queries: 12 canonical academic queries from ciw_concurrent_block_20260508.md
(3 bursts × 4), reused for cross-test comparability.

Import switched from ScholarHTTPProbe (dev probe) to ScholarEngine (production) 2026-05-09
as part of bead searxng-f3i HTTP migration.

Output: JSONL per-query records → dev/search_pipeline/jsonl/no_google_burst_<ts>.jsonl
        Summary table → stderr
```

Comment (line 52-53):

```text
# Watchdog timeouts per engine (seconds) — this probe's own values, independent of
# search_web.py's ENGINE_WATCHDOG_TIMEOUT (uniform 6.0s across all engines as of 2026-08-25)
```

### `ranking_eval/_stage1_pool_fetch_report.py`

Comment (line 6-7):

```text
# NOTE: _STATUS_HINTS duplicated from 11_pipeline_smoke.py, keep in sync manually
# until extracted to shared helper.
```

### `ranking_eval/_stage3_method_run_v3_cheap.py`

Comment (line 11):

```text
# Cormack 2009
```

### `ranking_eval/bm25_capped_smoke.py`

Docstring (line 2):

```text
BM25 per-engine top-K cap probe — 3 configs, top-10, 4 queries.

Tests whether capping each engine's contribution to top-K URLs (where
K = google result count for this query) before building the dedup pool
improves BM25 result quality vs the uncapped full pool.

Rationale: crossref/openalex return 200 results each — keyword-matched
but often irrelevant. Google returns ~11 highly-curated results. Capping
all engines to K~11 equalises engine contribution and removes the long
tail of low-quality academic matches before BM25 scoring.

Config matrix:
  1. Hard-Slot   — _merge_and_rank baseline (12/6/2 slots)
  2. BM25 UNCAPPED — BM25Uniform on full dedup pool
  3. BM25 CAPPED   — BM25Uniform on pool built from top-K per engine
     K = engine_stats['google']['result_count'] for this query;
     fallback K=10 if google absent or returned 0.

Report header per query shows:
  raw=N, K=K, capped_pre_dedup=C, unique_capped=U, unique_full=F

Imports: QUERIES, VANILLA_K1, STOPWORDS, _build_pool, _tokenize, _doc_repr,
BM25Uniform from bm25_sweep_smoke.py (same directory).
```

### `ranking_eval/bm25_compare_smoke.py`

Docstring (line 2):

```text
BM25 focused comparison — top-10 URL dumps for 5 configs side-by-side (stacked).

Imports pool/ranking helpers from bm25_sweep_smoke.py (same directory).
Runs 5 configs per query:
  1. Hard-Slot baseline  — _merge_and_rank (12/6/2 slots)
  2. Vanilla BM25        — k1=1.2, b=0.75, sw=on, repr=title+snippet
  3. b=0 extreme         — k1=1.2, b=0.00, sw=on, repr=title+snippet (no length-norm)
  4. b=1 extreme         — k1=1.2, b=1.00, sw=on, repr=title+snippet (full length-norm)
  5. Title3x variant     — k1=1.2, b=0.75, sw=on, repr=title3x

Output: dev/search_pipeline/md/bm25_compare_<ts>.md
Top-10 per config (not 20) — keeps tables eyeball-readable.
```

### `ranking_eval/bm25_idf_engine_smoke.py`

Docstring (line 2):

```text
BM25 IDF vs Engine-Weighting probe — 5 configs, top-10, 4 queries.

Tests IDF and engine-count-inverse-weighting as separate and combined axes
relative to the Vanilla BM25 baseline.

Config matrix:
  1. Hard-Slot         — _merge_and_rank baseline (12 General / 6 Academic / 2 QA)
  2. Vanilla BM25      — BM25Uniform (no IDF, no weighting), b=0.75, k1=1.2
  3. BM25 + IDF        — BM25Okapi (standard per-pool IDF), same params
  4. BM25 + Weighting  — BM25Uniform × engine-count-inverse weight per URL
  5. BM25+IDF+Weighting— BM25Okapi × engine-count-inverse weight per URL

Engine-count-inverse weight for URL u:
  wt(u) = sum(1.0 / engine_counts[e] for e in u.engines)
  engine_counts[e] = number of raw results from engine e this query.
  Multi-engine URLs accumulate summed weights; high-volume engines
  (crossref=200, openalex=200) are naturally discounted vs low-volume
  (google~11, mojeek~10). Weighted score = bm25_score × wt.

Weighting applied to full pool (not truncated to 20 first) so re-ordering
by weighting does not miss candidates outside vanilla top-20.

Imports: QUERIES, VANILLA_K1, STOPWORDS, _build_pool, _tokenize, _doc_repr,
BM25Uniform from bm25_sweep_smoke.py (same directory).
```

### `ranking_eval/clean_pool.py`

Docstring (line 2):

```text
clean_pool.py — Filter helper + oracle cleanup for 7-engine eval.

filter_pool(pool, drop_engines) removes drop_engines from each entry's
engines+positions; drops URLs whose engines list becomes empty after filter.
min_position is recomputed from remaining positions; falls back to original
when positions is absent (v2 schema pool entries).

When run as script: generates <pair>_oracle_v3clean.json for all 16 (mode × query)
pairs in the v2 ts_dir, backfilling 4 loss pairs where google/semantic_scholar picks
are unavailable after the engine filter.

Usage:
  ./venv/bin/python dev/search_pipeline/clean_pool.py [--v2-dir PATH]
```

Comment (line 36-38):

```text
# Hardcoded backfill picks per loss pair {mode_slug: [{url, rationale}]}
# Selection criterion: canonical/authoritative source for the query, NOT SEO/listicle.
# Each backfill pick was chosen from the filtered pool (min_position rank), engine provenance noted.
```

### `ranking_eval/pool_diff_v2_v3.py`

Docstring (line 61):

```text
Return {engine: {ok: N, total: N}} from engine_report.md files — parse pool JSONs instead.
```

Comment (line 62-64):

```text
# Pool JSONs don't carry engine stats; we rebuild from per-pair pool.json google_count field
# and from parsing engine_report.md files.
# Simpler: read engine_report_summary.md text table per ts_dir.
```

### `ranking_eval/pooling_probe.py`

Docstring (line 2):

```text
Capped-Pool Pooling Strategy Comparison — 4 configs, top-google_count each, 20 queries.

Architecture (user-driven, bead searxng-g82):
  Pool per query: each engine contributes at most google_count URLs (position <= google_count).
  Pool bounded by 9 × google_count minus dedup overlap (~50-100 URLs per query).
  Hard-stop: google_count == 0 → query SKIPPED, no fallback.
  Output: top-google_count URLs per config.

4 configs on the same capped pool:
  C1 — Overlap-Count: sort (-n_engines, min_position) — structural signal only
  C2 — BM25: BM25Uniform k1=1.2, b=0.75, sw=on, title+snippet
  C3 — Cross-Encoder: Qwen3-Reranker-0.6B at port 8082, direct on full pool (no BM25 pre-filter)
  C4 — Embedding-Cosine: Qwen3-Embedding-0.6B at port 8084, one-batch, cosine sort

Services required (preset names: embedding-0.6b, reranker-0.6b):
  Embedding:     http://127.0.0.1:8084/v1/embeddings
  Cross-encoder: http://127.0.0.1:8082/v1/rerank

Output:
  dev/search_pipeline/md/pooling_probe_<ts>.md
  dev/search_pipeline/jsonl/pooling_probe_<ts>.queries.jsonl

All src/ dependencies routed through the already-committed dev/ modules that carry those imports.
```

Comment (line 96):

```text
# Cascade guard: >1 RATE_SKIP on same query → bee-fix regression, stop immediately
```

Comment (line 148):

```text
# Cross-encoder rerank with one retry on API error (500s are transient on llama-server)
```

Comment (line 239):

```text
# Pre-filter empty docs for C3/C4 API calls (reranker returns 400 on empty documents)
```

### `ranking_eval/single_query_pool_dump.py`

Docstring (line 2):

```text
Single-Query Pool Dump — capped pool vs Top-N for 4 configs (bead searxng-g82).

Sections: (1) per-engine raw  (2) full capped pool  (3) Top-N per config
          (4) comparison matrix (every pool URL × 4 configs → rank or —)

Hard-stop: google_count == 0 → exit. No fallback.
Services: embedding port 8084 (Qwen3-0.6B) / reranker port 8082 (Qwen3-0.6B)

Usage:
  ./venv/bin/python dev/search_pipeline/single_query_pool_dump.py [--query TEXT] [--output PATH]
```

### `ranking_eval/stage1_pool_fetch.py`

Docstring (line 2):

```text
Stage 1 — Pool Fetch (value_eval_v3).

Fetches results for 16 (mode, query) pairs (4 modes × 4 queries).
Writes per-pair pool.json + engine_report.md, then engine_report_summary.md.

No URL filter applied — C-methods (BM25, Cross-Encoder) handle topic relevance from
title+snippet. Query modifier (+book / +pdf / +documentation) still biases engine results.

pool.json schema:
  pool      — oracle input + C1/C2'/C3: capped_pool sorted by URL, ALL fields
               (url / title / snippet / engines / min_position / positions)
  pool_full — C2 BM25 vanilla: full_pool (all deduped results) sorted by URL, ALL fields

positions: {engine_name: rank} — per-engine position (additive v3 field; Methods 2-5 RRF).
Invariants: set(engines)==set(positions.keys()), min_position==min(positions.values()).

Oracle workers: read pool[*].{url, title, snippet} only — ignore engines/min_position/positions.

Usage:
  ./venv/bin/python dev/search_pipeline/stage1_pool_fetch.py [--smoke] [--ts-dir PATH]
```

### `ranking_eval/stage3_method_run.py`

Docstring (line 2):

```text
Stage 3 — Method Run (value_eval_v2).

Reads *_pool.json files from a Stage 1 ts_dir, runs 4 C-methods on each pool,
writes per-pair methods.json.

Methods:
  C1  — Overlap-Count: sort (-n_engines, min_position) on pool (filt_capped)
  C2  — BM25 vanilla (k1=1.2, b=0.75, sw=on, title+snippet) on pool_full (filt_pool)
  C2' — BM25-Capped: BM25 on pool (filt_capped, same as oracle input)
  C3  — Cross-Encoder rerank (Qwen3-Reranker, dynamic port via RAG server_manager)

Requires reranker server running (or startable via RAG). Script exits with error
if reranker cannot be reached after ensure_ready.

Usage:
  ./venv/bin/python dev/search_pipeline/stage3_method_run.py --ts-dir PATH [--smoke]
```

### `ranking_eval/stage3_method_run_v3.py`

Docstring (line 2):

```text
Stage 3 v3 — 12-Method Run (Phase 13 eval).

Reads *_pool.json (v3 schema, with positions field) from pool_dir, applies
filter_pool(drop_engines={'google','semantic_scholar'}), then runs 12 methods
per pair. Writes per-pair {mode}_{slug}_methods_v3.json to pool_dir.

Methods:
  M1  C1 Overlap-Count (no GPU)
  M2  RRF post-bucket using positions field (no GPU)
  M3  Structural URL Features — penalty scoring (no GPU)
  M4  C2 BM25 vanilla on pool_full (no GPU)
  M5  C2' BM25-Capped on pool (no GPU)
  M6  C3 Cross-Encoder vanilla — also saves c3_scores for M8/M10
  M7  C3 + Instruction-Prefix (same reranker model, new query prefix)
  M8  RRF + C3 Hybrid — 0.5*norm(c3_scores) + 0.5*norm(rrf_scores), NO new GPU call
  M9  SPLADE standalone — dot product on sparse vectors
  M10 SPLADE + C3 Hybrid — 0.5*norm(c3_scores) + 0.5*norm(splade_scores), NO new GPU call
  M11 Two-Stage C3 + LLM-Filter — C3 top-20 → generator-4b filter → top-10
  M12 LLM-as-Selector direct — full filtered pool → generator-4b → top-10

Execution order: M1-M5 (cheap), M6-M8 (reranker warm), M9-M10 (SPLADE warm), M11-M12 (generator).
Per-GPU model group: pre-flight warmup on first query only; cold_ms tracked separately.

Requires:
  - reranker-0.6b running (M6, M7, M8, M10, M11): rag-cli server start reranker-0.6b
  - splade running (M9, M10):                      rag-cli server start splade
  - generator-4b running (M11, M12):               rag-cli server start generator-4b

Usage:
  ./venv/bin/python dev/search_pipeline/stage3_method_run_v3.py \
      --pool-dir dev/search_pipeline/runs/value_eval_v3_<ts> \
      [--smoke]
```

### `ranking_eval/stage4_aggregate.py`

Docstring (line 2):

```text
Stage 4 — Aggregate (value_eval_v2).

Loads pool/methods/oracle JSONs from ts_dir, computes Jaccard overlap per method,
writes per-pair eval MD and summary eval MD into ts_dir.

Differences from value_eval_aggregate.py (v1 historical artifact):
  - Output files written to ts_dir/ (co-located with pool/methods/oracle JSONs)
  - No --ts-out flag (ts embedded in dir name)
  - Reads pool.json v2 schema (pool_sizes dict; pool items may have engines/min_position, ignored)

Smoke mode (--no-oracle): generates MDs without oracle section — verifies pool+methods
pipeline integrity only.

Usage:
  ./venv/bin/python dev/search_pipeline/stage4_aggregate.py \
      --ts-dir dev/search_pipeline/runs/value_eval_v2_YYYYMMDD_HHmmss \
      [--no-oracle]
```

Comment (line 103):

```text
# Skip empty-pool pairs (undersized_pool=True AND pool_size=0)
```

Comment (line 107):

```text
# top_10 items may be dicts {"url": ...} (B1 format) or plain strings (B2 format)
```

Comment (line 114):

```text
# pool_size: v2 schema stores in pool_sizes.filtered_capped; v1 stored top-level pool_size
```

### `ranking_eval/stage4_aggregate_v3.py`

Docstring (line 2):

```text
Stage 4 v3 — Aggregate (Phase 13, 12-method eval).

Loads pool_v3/*_pool.json + pool_v3/*_methods_v3.json + oracle_dir/*_oracle_v3clean.json,
computes Jaccard per method, writes per-pair eval MD and summary MD into pool_dir.

Summary includes:
  - Per-mode mean Jaccard (12 methods)
  - Per-method latency statistics (mean, p50, p95, max, cold)
  - Quality × Latency Pareto table (DOMINATED flagged)

Usage:
  ./venv/bin/python dev/search_pipeline/stage4_aggregate_v3.py \
      --pool-dir  dev/search_pipeline/runs/value_eval_v3_<ts> \
      --oracle-dir dev/search_pipeline/runs/value_eval_v2_20260523_000156 \
      [--no-oracle]
```

### `ranking_eval/value_eval_aggregate.py`

Docstring (line 2):

```text
Value Eval Aggregator — Stage 4: per-pair MD + summary MD (bead searxng-g82).

Loads pool/methods/oracle JSONs from ts_dir, computes Jaccard overlap per method,
writes per-query MDs and one summary MD.

Smoke mode (--no-oracle): generates MDs without oracle section — verifies pool+methods
pipeline integrity only.

Usage:
  ./venv/bin/python dev/search_pipeline/value_eval_aggregate.py \
      --ts-dir dev/search_pipeline/runs/value_eval_YYYYMMDD_HHmmss \
      [--ts-out YYYYMMDD_HHmmss] [--no-oracle]
```

Comment (line 100):

```text
# Skip empty-pool pairs (undersized_pool=True AND pool_size=0) in scoring
```

Comment (line 104):

```text
# top_10 items may be dicts {"url":...} (B1 format) or plain strings (B2 format)
```

### `ranking_eval/value_eval_probe.py`

Docstring (line 2):

```text
Value Eval Probe — Stage 1+2: pool fetch + C-method scoring (bead searxng-g82).

Fetches results for each (mode, query) pair; saves pool.json (oracle input: url/title/snippet only,
no scores) and methods.json (C1/C2/C2'/C3 Top-10 URLs) per pair.

Methods:
  C1  — Overlap-Count: sort (-n_engines, min_position)
  C2  — BM25 vanilla (k1=1.2, b=0.75, sw=on, title+snippet) on full filtered pool
  C2' — BM25-Capped: BM25 on capped pool (position ≤ google_count, then filtered)
  C3  — Cross-Encoder rerank (Qwen3-Reranker-0.6B, port 8082) on full filtered pool

Smoke mode (--smoke): one pair only (general × transformer attention mechanism),
  then auto-runs Stage 4 aggregator with --no-oracle to verify the chain.

Usage:
  ./venv/bin/python dev/search_pipeline/value_eval_probe.py [--smoke] [--ts-dir PATH]
```

Comment (line 71):

```text
# --- URL filter data (mirrors src/search/{pdf_filter,book_whitelist,docs_filter}.py) ---
```

Comment (line 325):

```text
# Oracle sees capped+filtered pool sorted by URL (neutral ordering, ~40-80 URLs, practical to review)
```

### `report_analysis/inspect_query_log.py`

Docstring (line 1):

```text
Inspect query_log.jsonl — summary stats over logged queries.

Usage:
  python dev/search_pipeline/inspect_query_log.py [--tail N] [--log-path PATH] [--all-types]

Log path resolution: --log-path arg → SEARXNG_QUERY_LOG_PATH env var → src/logs/query_log.jsonl

Record types in the log:
  engine_run       — written by _query_engines_concurrent (always; probes write only this type)
  workflow_summary — written by search_web_workflow (production only; includes total_wall_ms + preview)
  (no record_type) — old-style entries; treated as workflow_summary (backward compat)

Default mode: shows workflow_summary + old-style records only. Use --all-types to include engine_run.
```

### `report_analysis/snippet_quality_analysis.py`

Comment (line 95):

```text
# scholar_strip: unescape HTML entities then strip bloat (mirrors Rule 7)
```

### `scholar_http_probe.py`

Docstring (line 2):

```text
HTTP Scholar probe — architectural alternative to src/search/engines/scholar.py.

Status: PROBE (not in production). Tests whether HTTP-based Scholar can survive
concurrent multi-engine burst patterns when Google browser is absent.

Lives in dev/ per documentation rule "dev/ vs src/ for Exploratory Rewrites" —
production stays browser-based until empirical evidence converges on a known-good
fix that addresses the actual production problem.

Source: cherry-picked from commit 82bc88f (discarded pydoll-stealth-probe branch),
modeled on SearXNG's `searx/engines/google_scholar.py`.

Usage: imported by `dev/search_pipeline/no_google_burst_smoke.py`. Not invoked by
production cli.py or ENGINES dict in search_web.py.
```

Comment (line 50):

```text
# CONSENT=YES+ bypasses Google's cookie-consent gate without browser interaction
```

Comment (line 53):

```text
# 6.0s — Scholar HTTP latency 1-5s range; matches crossref/open_library override in production
```

### `with_google_decoupling_smoke.py`

Docstring (line 2):

```text
With-Google decoupling smoke — verifies Scholar is absent from default engine set.

Tests the production _select_engines(None) path end-to-end:
  - Google browser engine IS in the set
  - google_scholar is NOT in engines_requested
  - engines_excluded["google_scholar"] == "decoupled_from_google" in query log
  - No status attributed to Scholar at all (it never fired)

Runs 5 queries through search_web_workflow(query, engines=None) — the real production
path — then reads the last 5 lines of query_log.jsonl to verify the exclusion machinery.

Output: markdown summary → dev/search_pipeline/md/with_google_decoupling_<ts>.md
```

## Phase 2 verification

Measured after the sweep, 2026-09-24:

- AST plus tokenize scan over all 108 files (shebang on line 1 and the three markers exempt): 0 comments, 0 docstrings. `py_compile` of all 108 files passes.
- Suite: `pytest dev/tests/ -q` 488 passed before the sweep (measured with the working tree stashed, after merging the current `integration`) and 488 passed after.
- `--help` for the 20 argparse scripts, old tree versus new tree in separate copies: 14 byte-identical, including `inspections/inspect_engine_dom.py` with its description line. The other 6 (`16_search_to_pdf_probe`, `single_query_pool_dump`, `stage1_pool_fetch`, `stage3_method_run`, `stage3_method_run_v3`, `value_eval_probe`) do not import at baseline (see the import-failure table above) and print the same traceback in both trees; only the `line N` numbers inside the traceback moved because comment lines above the failing import are gone. Before running anything, every script's `__main__` block was read to confirm argparse runs first; no script without argparse was executed.
- All Phase 1 rendered-output scenarios (the same 27 targets) rerun against the pre-Phase-1 snapshot: IDENTICAL. Path proof over 78 modules: unchanged (the one known `SESSION_DIR` difference from Phase 1).
- All `DOCS.md` LOC headings re-derived from `wc -l`: 92 headings changed, 0 mismatches afterwards.
