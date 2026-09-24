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
