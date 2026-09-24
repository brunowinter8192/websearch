# Phase 1 size splits outside search_pipeline, and the dev/_lib browser_launch defect (2026-09-24)

Worker entry for the hit list handed out after the 2026-09-17 resume scan (see area `refactor_sweep`,
entry of 2026-09-17). Scope: `dev/news_pipeline/`, `dev/mojeek_return/`, `dev/brave_return/`, plus two
defects in `dev/_lib/`. Not touched: `dev/tests/`, `dev/search_pipeline/`. Commits on branch `wsweep2`:
`f69c17a` (splits + DOCS.md), `09a166f` (browser_launch + its DOCS.md).

## Measured 2026-09-24 (AST walk, function length = end_lineno - lineno + 1, docstring included)

| Location | Hit |
|---|---|
| `theblock/probe_liveness.py` | module 410 LOC; `probe_liveness_workflow` 66 |
| `theblock/probe_curated_theblock_cf.py` | `write_report` 70 |
| `theblock/probe_curl_cffi_discriminator.py` | `build_report` 106 |
| `theblock/source_tracker.py` | `compute_run_stats` 51 |
| `theblock/pipe_theblock.py` | `pipe_theblock_workflow` 51, `stage3_discovery` 76, `append_pipe_log` 66 |
| `theblock/acquire_pipe/p4_loop.py` | `run_loop` 111, `_build_batch` 51 |
| `theblock/acquire_pipe/acquire_pipe.py` | `acquire_pipe_workflow` 69 |
| `theblock/acquire_pipe/p4_race.py` | `run_race` 82 |
| `mojeek_return/_mojeek_pydoll_probe_report.py` | `_build_q2_section` 52 |
| `mojeek_return/_mojeek_pydoll_pure_checks.py` | `run_pure_function_checks` 59 |
| `brave_return/_brave_pure_checks.py` | `run_pure_function_checks` 52 |

The "11 functions in dev/news_pipeline" figure counts `theblock/` and `theblock/acquire_pipe/`; all 11 sit there.
After the work: zero modules over 400 LOC, zero functions at or above 50 LOC in the three areas.

## Rules given for this task that shaped the work

- Comments and docstrings are NOT stripped in this task; Phase 2 triages them against DOCS.md. Existing
  comments move with their code. Verified with a comment/docstring multiset diff of HEAD vs working tree
  over all touched files: zero removed, zero docstrings added or removed; only the `# INFRASTRUCTURE` /
  `# FUNCTIONS` markers of the new modules are new.
- I must not add new comments. Early on I put `# noqa: E402` on three new import lines (copying the file's
  style); the multiset diff caught them and they were removed. Run that diff before committing.
- Consequence for a Phase 2 successor: three in-body label comments in
  `probe_curl_cffi_discriminator.py` (`# Failure mode breakdown`, `# ASN distribution of passing proxies`,
  `# Verdict`) now sit directly above helper `def` lines, the exact shape the 2026-09-17 entry flags as a
  Phase 2 violation. Also `# Per-protocol breakdown` in `probe_curated_theblock_cf.py` (first line inside
  `build_protocol_lines`) and `# Phase 2 - Tail` in `p4_loop._build_batch`.

## What each split did, and the non-obvious parts

**probe_liveness.py (410 -> 210).** Classification (`check_proxy`, `_res`, `classify_error`) moved verbatim to
`_probe_liveness_classify.py`; reporting (`print_console_summary`, `append_sweep_log`, `write_unknown_log`,
`DEAD_BUCKETS`, `LOG_DIR`, `SWEEP_LOG`) to `_probe_liveness_report.py`. `run_checks` stays in
`probe_liveness.py` because `pipe_theblock.py` imports it from there. The 7-way `if args.source ==` chain in the
workflow became `load_entries` with dicts `FILTERED_LOADERS` (monosans, curated: freshness-filtered) and
`EVAL_LOADERS` (label + loader; label strings preserved exactly: `TheSpeedX eval:` capitalised, others lowercase).
The mode string equals the source name except frozen, which yields `sample` or `full`. `EVAL_ONLY_SOURCES`
is kept; it still gates `record_run`.

**pipe_theblock.py (339 -> 355).** First split gave 403 LOC (over threshold). Fix: the CF primitives
(`cf_get`, `is_xml`, `stage2_cf_check`, `CONCURRENCY_CF`, `CF_TIMEOUT_S`, `TARGET_CF_CHECK`, `XML_MARKERS`)
went to `_pipe_theblock_cf.py`. `CONCURRENCY_CF` is imported back because `append_pipe_log` prints it.
Moving the log writer instead was rejected: it needs both concurrency constants and would create an import
cycle with `pipe_theblock`. Stage functions: `run_stage1/2/3`, `abort_without_cf_proxies`;
`stage3_discovery` delegates the per-sub retry loop to `fetch_one_sub(sub_url, proxy_queue, proxy_idx,
proxy_budget, b_exhausted, subs_fetched) -> (proxy_idx, subs_fetched)`. `proxy_queue`, `proxy_budget` and
`b_exhausted` are mutated in place (the loop pops exhausted proxies); only the two integers are returned.
`append_pipe_log` = `build_funnel_lines` + `build_budget_lines`.

**p4_loop.py run_loop (111).** Splitting into helpers alone left `run_loop` at 64, because its docstring is
23 lines and the signature 12. To get under 50 without deleting the docstring, mutable loop state moved into a
`LoopState` dataclass (queue, done, dead, wset, consec_fail, pool, buf, last_refresh) and one loop iteration
became `_run_iteration`; the exhaustion branch's `continue` became `return`. Helpers: `_init_state`,
`_reload_pool` (used at startup and at the refresh tick, identical four statements before), `_sleep_until_eligible`,
`_run_batch`, `_record_ok/_record_dead/_record_fail`. `_sleep` stays a module attribute (patchable).
`_record_fail` returns the new `buf` because the burn path rebuilds it.
`_build_batch` = `_assign_normal` + `_add_tail_racers`.

**p4_race.py run_race (82).** Closures over `[0]`-style cells became a `RaceState` dataclass with two locks;
`_worker/_next_url/_next_proxy/_mark_done` are module functions.

**acquire_pipe.py (69).** `_run_job` holds the body of the `with box_lock.acquire(...)` block; the
content-handler and pool-provider closures became factories (`_make_content_handler`, `_make_pool_provider`);
`_write_article_urls` split out. `LockBusyError` handling stays in the workflow.

**Report builders.** `source_tracker.compute_run_stats` -> one counter helper per statistic
(`_count_proxy_urls` shared by `cf_checked` and `cf_passed`, parameterised by field name). `write_report`
(curated) and `build_report` (discriminator) -> one renderer per report section, caller concatenates.
Mojeek `_build_q2_section` -> intro / population rows / split lines / tab lines.
Both `*_pure_checks.py`: the first block of state-classifier checks became `run_classifier_checks`; in mojeek
the verdict and session-cookie checks became `run_verdict_checks` (brave already had that function). Check order
is unchanged, so console output is identical.

## Verification method (and its limit)

For each split the original was pulled with `git show`/a copy under a temporary module name in the same
directory, both versions were run with stubbed I/O, and stdout, written files, call records and return values
were compared. All identical:

- `probe_liveness_workflow`: 9 argv cases (6 named sources, sample, full, frozen with overrides).
- `pipe_theblock`: `append_pipe_log` (4 inputs incl. empty), `stage3_discovery` (3 scripted proxy-response
  sequences x 3 pool sizes, covering 200/403/429/transient), full workflow with and without CF-passing proxies.
- `run_loop`: 9 scenarios (plain, mixed good/bad/dead, tail race, single proxy, burn at concurrency 1 and 4,
  refresh interval 0, exhaustion-sleep with 50 ms cooldown), 3 PYTHONHASHSEEDs. Attempt lists compared sorted,
  because `as_completed` order is not deterministic. `_build_batch` compared on 3000 random inputs.
- `run_race`, `acquire_pipe_workflow` (gap/no gap x lock busy/free), `compute_run_stats` (200 random inputs),
  `write_report`, `build_report` (verdict branches a, b, c, ambiguous), mojeek q2 section and whole report,
  mojeek and brave pure-check output.
- Harness pitfall hit twice: a generator script run from the wrong cwd silently no-op'd and the harness then
  "passed" comparing a file with itself. After generating, always confirm the new file actually differs
  (LOC or the flagged function gone) before trusting SAME.
- Harness pitfall: a discriminator test fed `asn: None`; the ORIGINAL crashes on that (`p.get("asn", {}).get`
  on a None value). Inputs must use a missing key. Not a regression, not fixed here.
- Limit: no live network run of any of these scripts. As in the 2026-09-15 finding, byte-identical output
  proofs cannot see dropped `finally` guarantees; none of the extracted bodies sat inside try/finally except
  `acquire_pipe_workflow`, where the `try/except LockBusyError` and the `with box_lock` stayed in place and only
  the body moved.

## Test suite

`./venv/bin/python -m pytest dev/tests/ -q`: before 475 passed, 1 failed; after 476 passed.
The failing test was `test_brave_engine.py::test_unrelated_button_before_containers_never_leaks_into_success_diagnosis`.
`pytest dev/tests/test_brave_engine.py` alone: 13 passed. Recorded as flaky and pre-existing, not investigated
or fixed. None of the touched scripts are imported by `dev/tests/`.

## dev/_lib/browser_launch.py

Defect 1 (DOCS): `dev/_lib/DOCS.md` named `01_google_dom_probe.py` as importer; real importer is
`dev/access_recovery/_browser.py` (the entry script mentions the helper in a comment only). Fixed.

Defect 2 (behavior): the process creator hardcoded `open -g -n -a "Google Chrome"`. Now
`launch_backgrounded_chrome` calls `resolve_chromium_executable_path()` (starts `patchright.async_api.async_playwright`,
reads `pw.chromium.executable_path`, stops it), `resolve_chromium_bundle()` (walks parents to the `.app`; raises
`RuntimeError` when none, same message as production), sets `options.binary_location` to the executable, and the
creator is `functools.partial(_open_background_process_creator, bundle_path)`. Reasoning for `binary_location`:
pydoll `start()` uses `options.binary_location or _get_default_binary_location()`, and the default looks for
Google Chrome; setting it removes the dependency on Google Chrome being installed. `open -a` ignores `command[0]`
(the creator drops it), so the bundle is what actually launches. `BackgroundedBrowser` gained `executable_path`.
The helper cannot import `src.search.browser` (hook on `src/` imports in `dev/`), so the ~15 lines are a copy of
production's `_find_app_bundle`/`_resolve_chromium_bundle_path`; it is a copy, keep it in step by hand.

Verification (temporary profile, not a real session dir): resolved executable
`~/Library/Caches/ms-playwright/chromium-1228/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
`ps` on the first owned pid showed that same command with `--remote-debugging-port=... --user-data-dir=...`;
one tab opened and closed; after `teardown` `pgrep -f user-data-dir=<profile>` returned nothing.
The verification script was throwaway (`/tmp`), not committed.

Open item for whoever touches `dev/access_recovery/`: `_browser.py` uses
`SESSION_DIR = ~/.access_recovery/google-dom-probe-session`, a profile created by Google Chrome. Its next run
opens that profile with Chromium (for Testing). Not changed here; the profile may need to be recreated if the
probe misbehaves (hypothesis, not observed).

## Probes that still inline their own launch (not rewired, per instruction)

Hardcoded `Google Chrome`: `dev/mojeek_return/_mojeek_pydoll_probe_launch.py`,
`dev/search_pipeline/27_brave_headed_lane_probe.py`, `dev/browser_posture/_lib.py` (two sites: lines ~144, ~185).
Own bundle resolution: `dev/brave_return/_brave_probe_launch.py`, `dev/search_pipeline/_altcha_trigger_probe_launch.py`,
`dev/browser_posture/_cdp_launch.py` (with `dev/browser_posture/_chromium_bundle.py`).
The task text named `dev/engine_reduction/_altcha_trigger_probe_launch.py`; that file is in `dev/search_pipeline/`
(no such file under `engine_reduction`). No `2x_*_probe.py` file inlines a launch; `27_brave_headed_lane_probe.py`
is the only numbered one. `dev/brave_return/DOCS.md` Gotchas still says the shared helper hardcodes Google
Chrome; that is now stale but the section was outside this task.

## Operational notes

- `gcommit` stages everything in the worktree; make all changes for a commit before calling it.
- The bash environment in this project refused a command once with "add redirect: ... > /tmp/name.md 2>&1"
  when it combined several python runs; nothing had executed. Retrying with output redirected to a file worked.
- zsh has no `timeout`; BSD `sed -i` needs a suffix argument (`-i.bak`).


# Phase 2 - comment and docstring sweep of dev/news_pipeline (2026-09-24, same session)

Scope: every `.py` under `dev/news_pipeline/` except `theblock/jhao104/` (vendored), `monosans_*` and
`__pycache__`. Commit `42f96a5`. Standard applied: no comments, no docstrings; only the three section
markers and a line-1 shebang remain.

## Exclusion decided by the orchestrator

`theblock/jhao104/patches/helper/validator.py` (6 comments, 6 docstrings) is a patched copy of a third-party
file and stays untouched so it remains diffable against upstream. Without it the scan finds 820 items
(730 comments + 90 docstrings), which is exactly the figure the task quoted; a scan that includes it reports
736 + 96. Any future sweep must skip the whole `jhao104/` tree, not only `upstream/`.

## Method

1. `grep __doc__` over the tree: no hit, and no `argparse(description=__doc__)`. All 17 files that build an
   `ArgumentParser` pass explicit string literals, so nothing needed to be replaced by a constant.
2. Every comment token (tokenize) and every docstring (AST) was listed per module and triaged:
   (a) substance already in the directory's DOCS.md or in `process-docs/news_pipeline/`, (b) a real fact
   recorded nowhere, (c) self-evident. Facts of class (b) are in the next section. Deletion itself was
   mechanical: a script removed all comment tokens and docstring statements at once, and the triage only
   decided what had to be written down first. The (a) and (c) counts are reported merged: telling a
   description that duplicates DOCS.md from one that merely restates the next line was not worth a second
   pass, and both are deleted either way.
3. Heading comments above a `def` (the Phase 1 leftovers named in the Phase 1 section, e.g. the three in
   `probe_curl_cffi_discriminator.py`, `# Per-protocol breakdown`, `# Phase 2 - Tail`) went through the same
   triage; none carried a fact.
4. Trailing comments were trimmed to the code (`# noqa: E402`, `# type: ignore[...]`, field-meaning notes);
   where a trailing comment carried a value set or a unit it is in the (b) list below.
5. Blank-line tidy only at deletion sites (cap 1 inside indented blocks, 2 at top level, none at file start).

## Verification

- Scan (tokenize + AST) over the same file set prints nothing: 78 files, 0 hits.
- Behavior proof: for every one of the 78 files `ast.dump` of the old and new source, both with docstring
  statements removed (empty bodies get `pass` on both sides), is identical. The script refused to write a file
  where it was not, and refused none. This proves the executable code is unchanged, including every
  string literal such as argparse `description=`/`help=`.
- Parser diff (static, no script was run): `ArgumentParser`, `add_argument`, `parse_args`, `add_subparsers`
  and `add_mutually_exclusive_group` call sources compared through `ast.unparse` between HEAD and the working
  tree: 17 files carry such calls, 0 differ. So `--help` output is unchanged by construction. `--help` was not
  executed anywhere: several of these scripts import pydoll/crawl4ai or touch the network at import or
  before argument parsing, and that was not checked script by script.
- `py_compile` of all 78 files: clean.
- `./venv/bin/python -m pytest dev/tests/ -q`: 488 passed before, 488 passed after (the suite grew from 476
  to 488 when `integration` was merged into the branch at the start of this task).
- DOCS.md: the five directory DOCS.md files (`dev/news_pipeline/`, `exploration/`, `coindesk_proxy_riding/`,
  `theblock/`, `theblock/acquire_pipe/`) had 76 LOC headings out of date because every module shrank; all
  were rewritten from `wc -l` and re-checked (0 mismatches). No other DOCS.md text was changed, and no DOCS.md
  gotcha was added: every (b) item is either a coupling between two named modules or a why that only matters
  to someone editing that one line, and the standard says to keep DOCS.md slim.

## Pitfall for the next sweeper: /tmp is shared between agents

My first scan script `/tmp/scan.py` was silently overwritten by another session between two of my runs; the
second run printed `dev/browser_posture/...` hits from a different script. It was only caught because the
output paths were foreign. Use a session-unique prefix for scratch files (`/tmp/<worktree>_*.py`).

## Triage counts

Items = comment tokens + docstrings, measured before deletion. Directory totals:

| Directory | Files | Items | Recorded (b) | Deleted (a)+(c) | of which comments | of which docstrings |
|---|---|---|---|---|---|---|
| `root` | 9 | 145 | 21 | 124 | 145 | 0 |
| `coindesk_proxy_riding/` | 17 | 167 | 16 | 151 | 157 | 10 |
| `exploration/` | 26 | 222 | 13 | 209 | 221 | 1 |
| `theblock/` | 16 | 229 | 16 | 213 | 173 | 56 |
| `theblock/acquire_pipe/` | 10 | 57 | 2 | 55 | 34 | 23 |
| total | 78 | 820 | 68 | 752 | 730 | 90 |

Per module (Deleted = (a) + (c)):

| Module | Items | Recorded (b) | Deleted |
|---|---|---|---|
| `01_coindesk_discover.py` | 28 | 5 | 23 |
| `02_coindesk_scrape.py` | 6 | 0 | 6 |
| `02b_coindesk_scrape_fresh_context.py` | 24 | 3 | 21 |
| `03_coindesk_cleanup.py` | 29 | 10 | 19 |
| `04_dedup.py` | 7 | 1 | 6 |
| `05_publish.py` | 7 | 1 | 6 |
| `coindesk_proxy_riding/_p2_fetch.py` | 8 | 2 | 6 |
| `coindesk_proxy_riding/_p2_state.py` | 7 | 4 | 3 |
| `coindesk_proxy_riding/_p2_watchdog.py` | 13 | 7 | 6 |
| `coindesk_proxy_riding/_p4_plots.py` | 3 | 0 | 3 |
| `coindesk_proxy_riding/_p4_stats.py` | 6 | 0 | 6 |
| `coindesk_proxy_riding/_test_tail_race_watchdog.py` | 10 | 0 | 10 |
| `coindesk_proxy_riding/analyze_write_times.py` | 20 | 1 | 19 |
| `coindesk_proxy_riding/p0_pool.py` | 6 | 0 | 6 |
| `coindesk_proxy_riding/p2_browser_rider.py` | 7 | 1 | 6 |
| `coindesk_proxy_riding/p3_url_sampler.py` | 11 | 1 | 10 |
| `coindesk_proxy_riding/p4_reporter.py` | 2 | 0 | 2 |
| `coindesk_proxy_riding/run_coindesk_riding.py` | 2 | 0 | 2 |
| `coindesk_proxy_riding/smoke_stage1.py` | 18 | 0 | 18 |
| `coindesk_proxy_riding/test_cooldown_policy.py` | 24 | 0 | 24 |
| `coindesk_proxy_riding/test_sigint_report.py` | 5 | 0 | 5 |
| `coindesk_proxy_riding/test_tail_race.py` | 18 | 0 | 18 |
| `coindesk_proxy_riding/test_watchdog.py` | 7 | 0 | 7 |
| `exploration/01_coindesk_ui_probe.py` | 16 | 2 | 14 |
| `exploration/02_coindesk_pagination_probe.py` | 2 | 0 | 2 |
| `exploration/03_coindesk_backfill_traversal.py` | 15 | 0 | 15 |
| `exploration/04_coindesk_timeline_replay_probe.py` | 7 | 0 | 7 |
| `exploration/05_coindesk_cursor_probe.py` | 7 | 0 | 7 |
| `exploration/05b_coindesk_warmth_probe.py` | 20 | 0 | 20 |
| `exploration/06_coindesk_full_discovery.py` | 25 | 4 | 21 |
| `exploration/_01_dom.py` | 13 | 0 | 13 |
| `exploration/_02_depth.py` | 4 | 0 | 4 |
| `exploration/_02_dom.py` | 10 | 1 | 9 |
| `exploration/_02_quick.py` | 17 | 3 | 14 |
| `exploration/_02_report.py` | 7 | 0 | 7 |
| `exploration/_03_capture.py` | 18 | 1 | 17 |
| `exploration/_03_log.py` | 2 | 0 | 2 |
| `exploration/_03_report.py` | 2 | 0 | 2 |
| `exploration/_04_capture.py` | 7 | 0 | 7 |
| `exploration/_04_replay.py` | 21 | 2 | 19 |
| `exploration/_04_report.py` | 2 | 0 | 2 |
| `exploration/_05_capture.py` | 7 | 0 | 7 |
| `exploration/_05_fixed.py` | 2 | 0 | 2 |
| `exploration/_05_parse.py` | 3 | 0 | 3 |
| `exploration/_05_report.py` | 2 | 0 | 2 |
| `exploration/_05b_report.py` | 1 | 0 | 1 |
| `exploration/_06_capture.py` | 9 | 0 | 9 |
| `exploration/_06_progress.py` | 2 | 0 | 2 |
| `exploration/_06_report.py` | 1 | 0 | 1 |
| `prod_scrape_smoke.py` | 9 | 1 | 8 |
| `run_pipeline.py` | 22 | 0 | 22 |
| `scrape_isolation_smoke.py` | 13 | 0 | 13 |
| `theblock/_pipe_theblock_cf.py` | 2 | 0 | 2 |
| `theblock/_probe_discovery_report.py` | 7 | 0 | 7 |
| `theblock/_probe_liveness_classify.py` | 7 | 4 | 3 |
| `theblock/_probe_liveness_report.py` | 2 | 0 | 2 |
| `theblock/acquire_pipe/acquire_pipe.py` | 2 | 0 | 2 |
| `theblock/acquire_pipe/box_lock.py` | 8 | 1 | 7 |
| `theblock/acquire_pipe/p1_fetch.py` | 2 | 0 | 2 |
| `theblock/acquire_pipe/p2_cooldown.py` | 7 | 0 | 7 |
| `theblock/acquire_pipe/p3_target.py` | 5 | 1 | 4 |
| `theblock/acquire_pipe/p4_loop.py` | 9 | 0 | 9 |
| `theblock/acquire_pipe/p4_race.py` | 2 | 0 | 2 |
| `theblock/acquire_pipe/p5_logger.py` | 4 | 0 | 4 |
| `theblock/acquire_pipe/p6_buffer.py` | 7 | 0 | 7 |
| `theblock/acquire_pipe/p7_janitor.py` | 11 | 0 | 11 |
| `theblock/curated_sources.py` | 24 | 2 | 22 |
| `theblock/monosans_loader.py` | 4 | 0 | 4 |
| `theblock/pipe_theblock.py` | 27 | 1 | 26 |
| `theblock/probe_48h_article_fetch.py` | 8 | 0 | 8 |
| `theblock/probe_curated_theblock_cf.py` | 6 | 0 | 6 |
| `theblock/probe_curl_cffi_discriminator.py` | 31 | 0 | 31 |
| `theblock/probe_discovery.py` | 18 | 4 | 14 |
| `theblock/probe_liveness.py` | 23 | 1 | 22 |
| `theblock/probe_pool_size.py` | 15 | 2 | 13 |
| `theblock/probe_repo_cf_survey.py` | 22 | 0 | 22 |
| `theblock/proxy_status_log.py` | 6 | 0 | 6 |
| `theblock/source_tracker.py` | 27 | 2 | 25 |


## Class (b): facts moved here, grouped by module

Line numbers refer to the files before this commit (`git show 42f96a5~1:<path>`).

### root

- `01_coindesk_discover.py`: `MAX_CLICK_ROUNDS = 8` is a safety cap sized as 8 clicks x ~16 URLs per batch,
  i.e. at most about 128 URLs per run. Live-blog URLs are dropped on purpose: a live blog is a continuously
  updated multi-story container that does not fit a daily-cron pipeline with URL-dedup. `_is_live_blog` keys
  on the slug (last path segment) starting with `live-`, which also catches `live-markets-`, `live-updates-`
  and any future `live-X-` variant.
- `02b_coindesk_scrape_fresh_context.py`: `_ensure_domain_state` is asyncio-safe only because there is no
  `await` between the lookup and the creation of the per-domain entry; adding an await there reintroduces a
  race. `print_summary` keeps a fixed line format (`ok` / `failed` counts) because `run_pipeline.py` parses the
  stage's stdout; rewording those lines breaks the runner's counts silently.
- `03_coindesk_cleanup.py`: the in-body tag-footer strip matches one or more concatenated links, broader than
  the end-anchor pattern (`{2,}`), because orphan single-tag lines such as `[Tokenization](url)` also occur in
  the body. It must run before inline-link substitution, otherwise the `[text](url)` form is gone. The inline
  link substitution runs after image-line removal and does not match image markup (leading `!`), which
  `_RE_IMAGE`/`_RE_IMAGE_LINK` own. Pass 1 order: tag-footer, image, byline/date, google-badge, empty-links,
  inline-link (+ trailing-whitespace count); pass 2: paragraph normalization and blank-run collapse to 1.
- `04_dedup.py` and `05_publish.py`: both derive the target filename `coindesk__<date>__<hash>.md`. The dedup
  gate's only state is that file's presence in the collection directory, so the hash and date logic of the two
  scripts must stay identical.
- `prod_scrape_smoke.py`: the production scraper is loaded with `importlib.import_module("src.crawler.pipe_scraper")`
  after putting the repo root (`parents[2]`) on `sys.path`, to satisfy the rule that dev scripts do not write
  `from src...` imports.

### exploration/

- `01_coindesk_ui_probe.py`: the browser is started and stopped explicitly instead of `async with`, because
  `__aexit__` tries to restore `Preferences.backup`, which does not exist in a fresh temporary session dir
  (pydoll bug with ephemeral profiles).
- `_02_dom.py`: the OneTrust consent overlay is dismissed by removing its DOM node so pointer events are no
  longer blocked. `_02_quick.py` clicks through JS for the same reason (a JS click bypasses the overlay's
  pointer-event interception), reads the POST body synchronously from the Playwright impl object (no `await`
  needed, `post_data` is available synchronously) and detects gzip-compressed bodies by magic bytes.
- `_03_capture.py`: the button-state JS returns a JSON string `{found, disabled}` so pydoll's CDP result can
  be unwrapped through `_extract_value`.
- `_04_replay.py` (same strip in `_05_capture.py`, `_06_capture.py`, `05b_coindesk_warmth_probe.py`): HTTP/2
  pseudo-headers and client-managed headers of the captured request are stripped before replay; the rest of the
  headers are replayed exactly.
- `06_coindesk_full_discovery.py`: `CLICKS_WARMUP = 8` because the SSR buffer clears at about click 6;
  `CLICKS_REWARM = 7` (slightly fewer for the browser re-warm); `MAX_CURSOR_FALLBACKS = 3` is how many
  articles are tried as cursor anchor before a re-warm is declared necessary. Re-warm order: an httpx
  feed-page GET first (cheap), the browser only if that is insufficient.

### coindesk_proxy_riding/

- `_p2_fetch.py`: `_PROXY_ERR` is the list of Playwright error substrings that mark a proxy-side failure
  rather than a CoinDesk-side one. The URL hash (SHA-256, first 12 hex chars) matches the `scrape.py`
  convention, so raw files from the two tools name the same article identically.
- `_p2_state.py` and `p2_browser_rider.py`: value sets that are otherwise only visible by reading every
  assignment: `JobRecord.status` is `ok | regwall | connect_fail | failed | empty`; `RiderState.termination`
  is `all-done | stall | pool-exhausted` (initial `running`); `n_failed` counts the URLs that triggered the
  fail-rotation (2-strike drop); `ride_position` is the ordinal of the URL on the current proxy (1st, 2nd, ...);
  `FAIL_THRESHOLD = 2` counts `failed`/`empty` strikes before a proxy is dropped and mirrors the regwall
  `burn_threshold`.
- `_p2_watchdog.py`: the watchdog is its own asyncio task and is timer-based (`asyncio.sleep`), so it fires
  even when every slot task is suspended forever in `await crawler.arun()`. Default poll interval is
  `min(30, stall_timeout_s / 4)` so a short smoke-test timeout still gets fast detection. `_abort_stall` ends in
  `os._exit(1)` deliberately: it bypasses asyncio teardown and `browser.close()`, so wedged Chrome processes
  cannot hang the shutdown again; the raw files are already flushed to disk before it is reached. In-flight
  URLs are written to `remaining_urls.txt` first because the wedged ones are the diagnostically useful ones.
- `analyze_write_times.py`: `git rev-parse --git-common-dir` returns e.g. `/repo/.git` or
  `/repo/.git/worktrees/<name>`, which is why the repo root is derived from it (works inside worktrees).
- `p3_url_sampler.py`: `_repo_root` resolves the path returned by `git rev-parse --git-common-dir` relative
  to `Path(__file__).parent` because git reports it relative to the subprocess CWD (the script directory) when
  the repo is a main checkout; when git returns an absolute path, `dir / absolute` is the absolute path, so the
  same expression is right in both cases.

### theblock/

- `_probe_liveness_classify.py`: `socks5` is sent as `socks5h` so DNS resolves remotely through the proxy (less
  local DNS load, more representative of what a fetch through it would do). Elapsed time is measured from
  semaphore acquisition, not from queueing, and the hard Python deadline is `connect + read + 2s` slack on top
  of curl's own timeouts. In `classify_error`, `ProxyError` is checked before `CurlConnectionError` because
  curl_cffi's `code2error()` re-maps `RECV_ERROR` + "CONNECT" to `ProxyError`; that case must land in
  `proxy_handshake_error`, not `connection_refused`. Timeout split: elapsed time is the primary discriminator
  (stable across libcurl versions), message text the fallback, and a timeout matching neither goes to
  `unknown` as a version-drift signal.
- `curated_sources.py`: a source may list several URLs per protocol (jetkai: http and https both map to
  `http`). `_merge_dedup` keeps the first occurrence per canonical `proxy_key`.
- `pipe_theblock.py` (`fetch_one_sub`): when every remaining proxy fails transiently for one sub-sitemap, the
  sub is skipped and left uncached so the next run retries it.
- `probe_discovery.py`: IP-level 429 fires after about 25 sequential sub-sitemap fetches even at 5 s per sub
  (`SUB_DELAY = 5.0`); per-sub 429 retry waits are 60/120/180 s (`BACKOFF_WAIT`, `MAX_RETRIES = 3`), and
  `MAX_RETRIES = 0` gives a fast no-retry scan. The RSS sample taken before the first sitemap run held 22
  `<link>` tags, 20 of them unique `/post/` URLs. Discrepancy: `theblock/DOCS.md` says the block fires after
  about 21 fetches; two measurements, not reconciled.
- `probe_liveness.py`: the eval-only sources (`thespeedx`, `databay`, `jetkai`, `roosterkid`) skip the
  freshness filter and never call `record_run`, so `proxy_status_log` stays untouched by them.
- `probe_pool_size.py`: `BASELINE_RAW = 17_202` is the raw count of the earlier monosans single-source neutral
  run (the "OldThemes 16" baseline). In the source tables, `is_mixed = True` marks aggregate lists of unknown
  protocol that are counted in the HTTP bucket.
- `source_tracker.py`: `unique_latest` is overwritten each run (latest run only) while the other counters
  accumulate; the first freshness diff for a source is a baseline with no meaningful new/dropped numbers.
- `acquire_pipe/box_lock.py`: in `cleanup_stale`, an unreadable sidecar and a live PID owned by another user
  (`PermissionError`) are both treated as held, never cleaned.
- `acquire_pipe/p3_target.py`: a `dead` status (404/410) on the sitemap index means the proxy reached the
  origin; that is a site anomaly, not a proxy fault, so the proxy is skipped without being burned.

## Observed inconsistencies, not fixed

- `p4_loop.run_loop`'s docstring said `build_active_buffer()` returns "socks4-first"; `p6_buffer` and its
  DOCS.md say pool order is preserved with no socks4-first sort. The docstring was the stale side.
- `run_pipeline.py` carried `# searxng-cli/` on `PROJECT_ROOT` (leftover from the project rename).
- The 21-vs-25 figure above.


# Phase 4 - control-flow triage of dev/news_pipeline (2026-09-24, same session), step 1: classification only

Scope: `dev/news_pipeline/` without `jhao104/` and `monosans_*`. Scan: the orchestrator's `exscan.py` classifier
(copied into a session-private directory) run per handler: 113 handlers, 3 TRIPWIRE (not triaged), 110
non-TRIPWIRE (101 PRODUCES-OUTPUT, 7 LOG-ONLY, 2 SWALLOW-FLOW). Every one of the 110 was read in its
function, callers were followed where the return value decides what happens next. No code was changed in this step.

## Classes and verdict rule used

A status/report, B fallback, C silent swallow, D best-effort teardown, E input-shape outcome (definitions as
given in the task). A B row is `B-keep` only if the triggering condition was observed AND the path is traceable;
observation sources searched: `src/logs/` of the main checkout (`coindesk_pipeline_*.log`, `news_coindesk_*.log`,
`news_theblock_*.log`, `cli.log*`; these are production-pipeline logs from June, none of them was written by the
dev scripts of this directory), `dev/news_pipeline/**/md/` and the `05b_output` report, and the areas
`news_pipeline`, `pooling`, `refactor_sweep` of process-docs.

## Counts

| Class | Count |
|---|---|
| A status/report | 45 |
| B fallback | 24 (23 B-remove, 1 B-keep-needs-logging, 0 B-keep) |
| C silent swallow | 1 |
| D best-effort cleanup | 20 |
| E input-shape | 20 |
| total | 110 |

## Findings that decide the B rows

- **Precedent, same handler shape already removed from src/:** `refactor_sweep` entries of 2026-09-09 removed
  (1) `parse_articles` returning `[]` on any JSON error (the stop message could not tell "API bottom" from "parse
  failure") and (2) the stub `job.md` written when the riding reporter fails. The dev copies survive here:
  `exploration/06_coindesk_full_discovery.py::parse_articles` (its stop message still says "reached API bottom or
  parse failure"), `exploration/_05_parse.py::parse_articles`, and `_p2_watchdog._write_stall_job_md` with its
  nested stub-write handler. No process-docs entry documents a real parse failure or reporter failure ever occurring.
- **The `_extract_value` family** (`raw["result"]["result"]["value"]` -> `None`, then `json.loads` failure ->
  `[]`/`{}`/`None`/`{"found": False, ...}`) exists in `01_coindesk_discover.py` and seven exploration modules. All
  the JS snippets return an explicit value (`JSON.stringify(...)`, a number or a boolean), so a missing `value` key or
  a non-JSON string means the evaluation itself went wrong, not that the page is empty. The defaults turn that into
  "no articles" (the click loop then stops as a plateau) or "button gone" (`_03_capture.check_btn_state` default
  `found: False` ends the traversal as if the feed ended). No log or report shows such a case. The daily runner
  `run_pipeline.py` executes `01_coindesk_discover.py`, so its two handlers are not only exploration code.
- **Observed condition behind the kept parts of `p3_target`/`probe_48h`:** production logs show the home IP getting
  `403 Forbidden` on `sitemap_tbco_index.xml` (`news_theblock_20260618.log`), and the `news_pipeline` area records
  the home-IP CF block. That covers the status-based path (which is not an except handler and is untouched). The
  except arm only covers raised network errors, and none was found, hence the weak B-remove.

## Rows (file paths relative to `dev/news_pipeline/`)

| file:line | function | scan | class | verdict | evidence |
|---|---|---|---|---|---|
| 01_coindesk_discover.py:195 | teardown_chrome_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| 01_coindesk_discover.py:242 | kill_chrome_on_port | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| 01_coindesk_discover.py:253 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| 01_coindesk_discover.py:264 | extract_articles | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| 01_coindesk_discover.py:289 | parse_url_date | PRODUCES-OUTPUT | E | allow | URL without a valid /YYYY/MM/DD/ path or without the host is a real input shape; callers skip it or label it unknown |
| 01_coindesk_discover.py:308 | _extract_section | PRODUCES-OUTPUT | E | allow | URL without a valid /YYYY/MM/DD/ path or without the host is a real input shape; callers skip it or label it unknown |
| 01_coindesk_discover.py:231 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| 02_coindesk_scrape.py:73 | scrape_one_url | PRODUCES-OUTPUT | A | allow | exception becomes an explicit per-URL status (failed/error field) in the manifest and stderr |
| 02b_coindesk_scrape_fresh_context.py:140 | _fetch_one | PRODUCES-OUTPUT | A | allow | exception becomes an explicit per-URL status (failed/error field) in the manifest and stderr |
| coindesk_proxy_riding/_p2_fetch.py:59 | _fetch_one_url | PRODUCES-OUTPUT | A | allow | exception becomes an explicit per-URL status (failed/error field) in the manifest and stderr |
| coindesk_proxy_riding/_p2_fetch.py:67 | _fetch_one_url | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| coindesk_proxy_riding/_p2_watchdog.py:81 | _write_stall_job_md | PRODUCES-OUTPUT | B | B-remove | stub job.md when write_riding_report fails; identical to the stub removed from src (abort_stub_removal); no reporter failure observed |
| coindesk_proxy_riding/_p2_watchdog.py:55 | _drain_queue | SWALLOW-FLOW | E | allow | QueueEmpty is the loop terminator of a drain |
| coindesk_proxy_riding/_p2_watchdog.py:99 | _write_stall_job_md | PRODUCES-OUTPUT | B | B-remove | stub job.md when write_riding_report fails; identical to the stub removed from src (abort_stub_removal); no reporter failure observed |
| coindesk_proxy_riding/_test_tail_race_watchdog.py:46 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| coindesk_proxy_riding/p0_pool.py:203 | _try_source | PRODUCES-OUTPUT | A | allow | pool source failure recorded as ok=False in the returned sources list |
| coindesk_proxy_riding/p0_pool.py:158 | fetch_with_retry | PRODUCES-OUTPUT | A | allow | bounded retry; last exception is re-raised after the final attempt (loud) |
| coindesk_proxy_riding/p2_browser_rider.py:119 | _get_next_queue_url | PRODUCES-OUTPUT | E | allow | empty queue after a 10 s wait is the normal 'nothing left' outcome; loop checks all_resolved |
| coindesk_proxy_riding/p2_browser_rider.py:255 | smoke | PRODUCES-OUTPUT | A | allow | smoke timeout printed as TIMEOUT and reported as partial results |
| coindesk_proxy_riding/run_coindesk_riding.py:100 | _raise_fd_limit | PRODUCES-OUTPUT | A | allow | warning with the manual ulimit instruction on stderr |
| coindesk_proxy_riding/smoke_stage1.py:46 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/smoke_stage1.py:49 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/smoke_stage1.py:149 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| coindesk_proxy_riding/test_cooldown_policy.py:46 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_cooldown_policy.py:49 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_sigint_report.py:40 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_sigint_report.py:43 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_sigint_report.py:156 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| coindesk_proxy_riding/test_sigint_report.py:190 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| coindesk_proxy_riding/test_tail_race.py:48 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_tail_race.py:51 | _run | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_watchdog.py:45 | _run_test | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_watchdog.py:48 | _run_test | PRODUCES-OUTPUT | A | allow | test runner: AssertionError/Exception becomes FAIL/ERROR line and a False result that sets the exit code |
| coindesk_proxy_riding/test_watchdog.py:87 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| coindesk_proxy_riding/test_watchdog.py:124 | run | PRODUCES-OUTPUT | E | allow | test intercepts the patched os._exit (SystemExit) and asserts the recorded exit code |
| exploration/01_coindesk_ui_probe.py:151 | parse_url_date | PRODUCES-OUTPUT | E | allow | URL without a valid /YYYY/MM/DD/ path or without the host is a real input shape; callers skip it or label it unknown |
| exploration/01_coindesk_ui_probe.py:53 | probe_workflow | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/03_coindesk_backfill_traversal.py:263 | parse_url_date | PRODUCES-OUTPUT | E | allow | URL without a valid /YYYY/MM/DD/ path or without the host is a real input shape; callers skip it or label it unknown |
| exploration/03_coindesk_backfill_traversal.py:289 | _extract_section | PRODUCES-OUTPUT | E | allow | URL without a valid /YYYY/MM/DD/ path or without the host is a real input shape; callers skip it or label it unknown |
| exploration/03_coindesk_backfill_traversal.py:242 | teardown_backfill_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/03_coindesk_backfill_traversal.py:247 | teardown_backfill_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/04_coindesk_timeline_replay_probe.py:126 | teardown_replay_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/04_coindesk_timeline_replay_probe.py:131 | teardown_replay_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/05_coindesk_cursor_probe.py:111 | teardown_chrome_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/05_coindesk_cursor_probe.py:116 | teardown_chrome_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/05b_coindesk_warmth_probe.py:201 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/05b_coindesk_warmth_probe.py:294 | fetch_feedpage | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/05b_coindesk_warmth_probe.py:325 | subprocess_cold_test | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/05b_coindesk_warmth_probe.py:327 | subprocess_cold_test | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/05b_coindesk_warmth_probe.py:148 | teardown_chrome_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/05b_coindesk_warmth_probe.py:153 | teardown_chrome_session | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/05b_coindesk_warmth_probe.py:189 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| exploration/05b_coindesk_warmth_probe.py:245 | run_warmth_ladder | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/06_coindesk_full_discovery.py:68 | parse_articles | PRODUCES-OUTPUT | B | B-remove | same handler as the removed src coindesk parse_articles fallback: [] on any parse error is indistinguishable from API bottom |
| exploration/06_coindesk_full_discovery.py:102 | fetch_feedpage | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/06_coindesk_full_discovery.py:330 | cursor_loop | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/_01_dom.py:178 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_01_dom.py:189 | inspect_containers | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_01_dom.py:200 | extract_articles | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_01_dom.py:221 | find_button | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_03_capture.py:166 | kill_chrome_on_port | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/_03_capture.py:173 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_03_capture.py:184 | extract_articles | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_03_capture.py:210 | check_btn_state | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_03_capture.py:158 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| exploration/_03_report.py:103 | _render_stage_b_projection | PRODUCES-OUTPUT | A | allow | projection error is written into the report text itself |
| exploration/_04_capture.py:86 | kill_chrome_on_port | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/_04_capture.py:93 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_04_capture.py:78 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| exploration/_04_replay.py:28 | replay_httpx | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/_04_replay.py:38 | replay_curl_cffi | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/_04_replay.py:45 | extract_cursor | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/_04_replay.py:80 | count_articles | PRODUCES-OUTPUT | B | B-remove | count 0 for an unparseable 200 body looks like a genuine empty batch in the report; no such body observed |
| exploration/_04_replay.py:94 | extract_json_sample | PRODUCES-OUTPUT | E | allow | optional diagnostic sample; absence is printed as no sample |
| exploration/_04_replay.py:308 | inspect_cursor_source | PRODUCES-OUTPUT | A | allow | failure becomes a sentinel status (-1 / error field) that the report table prints |
| exploration/_05_capture.py:94 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_05_capture.py:82 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| exploration/_05_parse.py:12 | parse_articles | PRODUCES-OUTPUT | B | B-remove | same handler as the removed src coindesk parse_articles fallback: [] on any parse error is indistinguishable from API bottom |
| exploration/_06_capture.py:99 | _extract_value | PRODUCES-OUTPUT | B | B-remove | CDP/JSON unwrap failure becomes None/[]/{}/found=False, which callers read as 'no articles' or 'button gone'; no log shows such a failure ever happened |
| exploration/_06_capture.py:87 | wait_for_ws_url | LOG-ONLY | E | allow | poll loop: 'not ready yet' is the expected outcome while Chrome starts; after the deadline TimeoutError is raised |
| exploration/_06_capture.py:162 | browser_load_feed | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| exploration/_06_capture.py:167 | browser_load_feed | PRODUCES-OUTPUT | D | allow | best-effort teardown; failure printed, nothing downstream depends on it |
| run_pipeline.py:97 | check_preconditions | PRODUCES-OUTPUT | A | allow | logged error plus explicit failure return; the caller aborts or skips the stage |
| run_pipeline.py:146 | run_stage_discover | PRODUCES-OUTPUT | A | allow | logged error plus explicit failure return; the caller aborts or skips the stage |
| run_pipeline.py:235 | _run | PRODUCES-OUTPUT | A | allow | logged error plus explicit failure return; the caller aborts or skips the stage |
| run_pipeline.py:238 | _run | PRODUCES-OUTPUT | A | allow | logged error plus explicit failure return; the caller aborts or skips the stage |
| scrape_isolation_smoke.py:126 | fetch_one | PRODUCES-OUTPUT | A | allow | smoke script prints a per-URL ERR line; a missing file shows as found=False in the review table |
| scrape_isolation_smoke.py:149 | fetch_one | PRODUCES-OUTPUT | A | allow | smoke script prints a per-URL ERR line; a missing file shows as found=False in the review table |
| theblock/_pipe_theblock_cf.py:24 | cf_get | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/_probe_liveness_classify.py:55 | check_proxy | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/_probe_liveness_classify.py:59 | check_proxy | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/_probe_liveness_classify.py:63 | check_proxy | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/acquire_pipe/box_lock.py:29 | cleanup_stale | PRODUCES-OUTPUT | D | allow | stale-sidecar cleanup is best effort; on failure the lock stays held (conservative), flock itself is the authority |
| theblock/acquire_pipe/box_lock.py:36 | cleanup_stale | LOG-ONLY | D | allow | stale-sidecar cleanup is best effort; on failure the lock stays held (conservative), flock itself is the authority |
| theblock/acquire_pipe/box_lock.py:38 | cleanup_stale | PRODUCES-OUTPUT | D | allow | stale-sidecar cleanup is best effort; on failure the lock stays held (conservative), flock itself is the authority |
| theblock/acquire_pipe/box_lock.py:84 | _busy_message | PRODUCES-OUTPUT | A | allow | busy message says explicitly 'sidecar unreadable' |
| theblock/acquire_pipe/p1_fetch.py:19 | fetch_url | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/acquire_pipe/p3_target.py:37 | _fetch_index_direct | PRODUCES-OUTPUT | B | B-remove | weak: direct fetch OK-or-proxy fallback path itself is observed (home IP 403) and printed; this except arm covers only raised network errors, none observed |
| theblock/probe_48h_article_fetch.py:105 | _fetch_index_direct | PRODUCES-OUTPUT | B | B-remove | weak: direct fetch OK-or-proxy fallback path itself is observed (home IP 403) and printed; this except arm covers only raised network errors, none observed |
| theblock/probe_48h_article_fetch.py:152 | _parse_url_blocks | SWALLOW-FLOW | C | remove | malformed lastmod silently drops the URL from the 48h delta list; no malformed lastmod observed |
| theblock/probe_curated_theblock_cf.py:43 | check_proxy | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_curl_cffi_discriminator.py:111 | check_one | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_curl_cffi_discriminator.py:124 | run_checks | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_discovery.py:113 | load_sub_cache | PRODUCES-OUTPUT | B | B-remove | weak: self-heal refetch/skip on corrupt cache file, printed as WARNING; no corrupt cache observed |
| theblock/probe_discovery.py:201 | _reconstruct_sub_urls_from_cache | PRODUCES-OUTPUT | B | B-remove | weak: self-heal refetch/skip on corrupt cache file, printed as WARNING; no corrupt cache observed |
| theblock/probe_discovery.py:222 | fetch_news_sitemap | PRODUCES-OUTPUT | B | B-remove | weak: self-heal refetch/skip on corrupt cache file, printed as WARNING; no corrupt cache observed |
| theblock/probe_pool_size.py:159 | fetch_source | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_pool_size.py:161 | fetch_source | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_repo_cf_survey.py:150 | check_proxy | PRODUCES-OUTPUT | A | allow | free-proxy failure is a normal outcome and is counted: status 0 / 'fail' / False / bucket, drives rotation or the Failed column |
| theblock/probe_repo_cf_survey.py:123 | fetch_one | PRODUCES-OUTPUT | B | B-keep-needs-logging | failed source (non-200 or exception) returns set(), indistinguishable from an empty source; source failures are observed (pool_size reports 'Failed sources'), but nothing is recorded here |

## Rows needing a decision

B-remove (23): the 13 `_extract_value`-family rows, the 2 `parse_articles` rows, `_04_replay.py:80`, the 2
`_p2_watchdog.py` stub rows (81 and the dependent 99), and the five weak ones (`p3_target.py:37`,
`probe_48h_article_fetch.py:105`, `probe_discovery.py:113/201/222`).
B-keep-needs-logging (1): `theblock/probe_repo_cf_survey.py:123`.
C (1): `theblock/probe_48h_article_fetch.py:152`.
Everything else is A, D or E and stays.


# Phase 4 - control-flow triage of dev/news_pipeline, step 2: removals (2026-09-24, same session)

The orchestrator approved all 23 B-remove rows, the B-keep-needs-logging row and the C row of the step 1 table.
Code commit: "refactor: remove unobserved fallbacks and swallows in dev/news_pipeline". Handler count in the
scope went from 113 to 90 (23 handlers deleted); the 79 PRODUCES-OUTPUT / 7 LOG-ONLY / 3 TRIPWIRE / 1
SWALLOW-FLOW that remain are the A, D, E rows plus the two handlers described under "kept on purpose".

## What changed, by row group

- **`_extract_value` family (13 rows).** `_extract_value` is now a bare `return raw["result"]["result"]["value"]`
  in `01_coindesk_discover.py`, `exploration/_01_dom.py`, `_03_capture.py`, `_04_capture.py`, `_05_capture.py`,
  `_06_capture.py` and `05b_coindesk_warmth_probe.py` (7 handlers), and the `json.loads(val)` handlers that
  turned a parse error into `[]`/`{}`/`None`/`{"found": False, "disabled": False}` are gone from
  `01_coindesk_discover.extract_articles`, `_01_dom` (`inspect_containers`, `extract_articles`, `find_button`) and
  `_03_capture` (`extract_articles`, `check_btn_state`) (6 handlers). Effect: a CDP result without the expected
  shape raises `KeyError`/`TypeError`, a non-JSON value raises `json.JSONDecodeError`, and the click loop or the
  daily `run_pipeline.py` discover stage stops with a traceback instead of reading it as end of feed / button gone.
  The `if not val:` early returns in front of the `json.loads` calls are not handlers and were left alone: a
  JS snippet that legitimately returns an empty string still yields the empty result.
- **`parse_articles` (2 rows).** `exploration/06_coindesk_full_discovery.py` and `exploration/_05_parse.py` now do a
  bare `json.loads(body)`. The stop message in `06`'s `process_batch` became "Empty response — reached API bottom.
  Stopping." (same wording as the src fix of 2026-09-09, `git grep "parse failure"` finds nothing left).
  `_04_replay.count_articles` also parses bare. (1 more row.)
- **Stall stub (2 rows).** `_p2_watchdog._write_stall_job_md` no longer builds a hand-written `job.md`. What
  stays, mirroring the src version: the `except Exception` around `write_riding_report` prints
  `[watchdog] write_riding_report WARN: <exc>` and the caller still flushes stderr and calls `os._exit(1)`. The
  `idle_s` parameter existed only for the stub and was removed from the function and its single caller; `idle_s`
  is still printed by `_abort_stall` itself. A missing `job.md` after a stall abort is now the signal that the
  reporter failed.
- **Weak rows (5).** `p3_target._fetch_index_direct` and `probe_48h_article_fetch._fetch_index_direct` lost their
  `except Exception` arm: a raised network error from the direct index GET now propagates (the non-200 / no-XML
  path, which is the observed home-IP 403, still prints and falls back to the proxy rotation, unchanged).
  `probe_discovery.load_sub_cache`, `_reconstruct_sub_urls_from_cache` and `fetch_news_sitemap` lost their
  corrupt-cache handlers: a corrupt JSON cache file now raises `json.JSONDecodeError`.
- **C row.** `probe_48h_article_fetch._parse_url_blocks` no longer skips a block whose `lastmod` is not ISO; the
  `ValueError` propagates. The tz-naive-to-UTC handling stays.
- **B-keep-needs-logging row.** `probe_repo_cf_survey.fetch_one` now returns `(proxies, error)` where error is
  `HTTP <status>` or `<ExceptionType>: <first 100 chars>`; `fetch_all_repos` returns
  `(repo_proxies, failed_sources)` with `(repo, protocol, url, error)` tuples; `write_fetch_summary` appends a
  `### Failed sources` table (or `None.`) to the report and the workflow prints the failed-source count. The handler
  itself stays (class A now): a failing source must not abort the survey of the other repos.

## Kept on purpose

- `_p2_watchdog._write_stall_job_md` keeps its `except Exception` (WARN only), because `_abort_stall` must reach
  `os._exit(1)` even when the reporter fails; that is the tripwire shape src kept.
- `probe_repo_cf_survey.fetch_one` keeps its `except Exception`, see above.

## Proof

- AST diff (`ast.unparse` old vs new per file, HEAD vs working tree): 15 files differ, and every changed line is one
  of the edits above; the other 63 files of the scope are byte-identical to HEAD. No file changed outside the
  listed rows (the survey diff also shows the changed signatures/call sites listed under its row).
- `py_compile` of all 15 touched `.py` files (the commit has 20 files including the 5 DOCS.md): clean. The comment/docstring scan of the scope still prints nothing
  (78 files, 0 hits).
- Full suite `./venv/bin/python -m pytest dev/tests/ -q`: 492 passed before, 492 after (none of the touched
  scripts is imported by `dev/tests/`).
- Offline propagation checks, no network, no browser: `_extract_value({})` raises `KeyError` and
  `_extract_value(None)` raises `TypeError` in all 6 modules that define it; `parse_articles(b"not json")` raises
  `JSONDecodeError` in `06` and `_05_parse`; `count_articles(b"<html>")` raises; `load_sub_cache` and
  `_reconstruct_sub_urls_from_cache` raise on a corrupt cache file; `_parse_url_blocks` raises `ValueError` on a bad
  `lastmod` and still returns the parsed pair for a good one. For the survey, `fetch_all_repos` was run against a
  stub client with an ok source, a 404 source and a raising source: the proxy sets are identical to the old
  version's, and the two failures come back as `HTTP 404` and `RuntimeError: connection reset`; the rendered
  fetch summary contains the Failed sources table (and `None.` when empty).
- The offline scripts `coindesk_proxy_riding/test_sigint_report.py`, `test_tail_race.py`,
  `test_cooldown_policy.py` exit 0 before and after; `test_watchdog.py` exits 1 before and after with identical
  output (`module 'p2_browser_rider' has no attribute 'os'` in both tests): it patches an attribute that
  `p2_browser_rider` no longer has, so it never reaches the stub and did not depend on it. Pre-existing, not
  fixed here.

## DOCS.md

Six sentences adjusted where documented behaviour changed: `theblock/DOCS.md` (`probe_repo_cf_survey` writes a
Failed sources table; `probe_48h_article_fetch` falls back on a non-XML response), `theblock/acquire_pipe/DOCS.md`
(`p3_target`: network errors from the direct GET propagate), `coindesk_proxy_riding/DOCS.md` (`_p2_watchdog`: WARN
only, no stub), root `DOCS.md` (`01_coindesk_discover`: unwrap/parse failures raise) and `exploration/DOCS.md`
(`_05_parse`: non-JSON raises). Recap re-check: all LOC headings of the five DOCS.md files match `wc -l`
(0 mismatches; 15 headings were updated, e.g. `_p2_watchdog.py` 100 -> 82, `probe_repo_cf_survey.py` 282 -> 295).

## For a successor

- The two `p3_target` / `probe_48h` direct-fetch arms were removed on the strength of "no raised network error
  observed", while the status-based fallback next to them is observed. If a raised `httpx` error from the home
  IP is ever seen in a real run, the fix is to log and fall back on that specific exception type, not to restore
  a bare `except Exception`.
- Rows with class A still lose the exception detail in several places (`cf_get` returns `(b"", 0)`,
  `check_proxy` returns `False`): they are counted as failures, which is the intended outcome for free proxies, so
  they were not touched.
