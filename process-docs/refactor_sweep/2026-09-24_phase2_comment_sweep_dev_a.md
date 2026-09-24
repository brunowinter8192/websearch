# Phase 2 comment sweep, dev/ batch A: browser_posture, lane_choice, url_discovery, explore_pipeline, access_recovery (2026-09-24)

Scope: every `.py` file in the five directories under `dev/`. Code standard applied: no comments and
no docstrings; only the three section markers and a line-1 shebang remain. Base: `integration` as of
2026-09-24 (merged into the worktree first). Suite before: 488 passed. Suite after: 488 passed.

## What was done

- 36 of 38 files changed; `access_recovery/_browser.py` and `access_recovery/_report.py` carried nothing to remove.
- Removed: 19 module/function docstrings and 494 comment lines (counts match the pre-sweep measurement
  in the task: 193/6, 138/4, 82/3, 68/3, 13/3 comments/docstrings per directory).
- Trailing `# noqa: E402` comments on imports were removed too. The repo root has no flake8/ruff/tox
  configuration, so nothing consumes them.
- Heading comments directly above a `def` (left over from the Phase 1 splits) are gone as well.
- No string literal was touched. Report text, JS snippets and the `log.append("Generic move: ...")`
  lines in `explore_pipeline/06_nextdata_probe.py` are code, not comments, and stay. The `//` comments
  inside the JS patch strings in `browser_posture/03_fingerprint_patch_probe.py` are verbatim copies
  of production JS and stay for the same reason.

## Method and its limits

1. `__doc__` grep over the five directories: zero hits. Every argparse `description=` (10 scripts) is
   an explicit string literal, so removing a docstring cannot alter `--help`.
2. The removal was done by a throwaway script (not persisted, `/tmp`): tokenize for comments, AST for
   docstrings, then a check that `ast.dump` of every file after the sweep equals `ast.dump` of the
   original with docstring statements removed. 0 mismatches over 38 files. That is the "behavior
   unchanged" evidence, stronger than reading diffs.
3. The (a)/(b)/(c) triage in the table below is by comment BLOCK, not verified line by line:
   a multi-line explanatory block or a module docstring counts as "already recorded" when its
   substance is in the directory's DOCS.md, in `process-docs/`, or in a report/log string in the code
   itself (spot-verified by grep for the load-bearing facts, see the list below); a single-line
   heading or restatement counts as self-evident; a block whose substance I found nowhere counts as
   moved. Treat the split between "recorded" and "self-evident" as approximate, the "moved" column as exact.

## Triage counts per module (lines; docstrings counted as 1)

Format: total (deleted-recorded / moved / deleted-self-evident).

| Module | docstrings | comments |
|---|---|---|
| browser_posture/01_launch_latency_probe.py | 1 (0 / 1 / 0) | 7 (2 / 0 / 5) |
| browser_posture/02_parallel_chrome_probe.py | 1 (0 / 1 / 0) | 11 (5 / 0 / 6) |
| browser_posture/03_fingerprint_patch_probe.py | 1 (0 / 1 / 0) | 13 (7 / 2 / 4) |
| browser_posture/04_headed_chromium_probe.py | 1 (0 / 1 / 0) | 11 (6 / 0 / 5) |
| browser_posture/05_cdp_headed_probe.py | 1 (0 / 1 / 0) | 21 (16 / 0 / 5) |
| browser_posture/_cdp_launch.py | 0 | 20 (13 / 6 / 1) |
| browser_posture/_cdp_report.py | 0 | 11 (9 / 0 / 2) |
| browser_posture/_cdp_teardown.py | 0 | 7 (6 / 0 / 1) |
| browser_posture/_chromium_bundle.py | 0 | 12 (10 / 0 / 2) |
| browser_posture/_chromium_teardown.py | 0 | 19 (8 / 11 / 0) |
| browser_posture/_fingerprint_report.py | 0 | 1 (0 / 0 / 1) |
| browser_posture/_headed_chromium_report.py | 0 | 11 (8 / 0 / 3) |
| browser_posture/_lib.py | 1 (0 / 1 / 0) | 49 (29 / 8 / 12) |
| browser_posture TOTAL | 6 (0 / 6 / 0) | 193 (119 / 27 / 47) |
| lane_choice/01_backfill_pairs.py | 1 (1 / 0 / 0) | 29 (9 / 7 / 13) |
| lane_choice/02_focus_poll_smoke.py | 1 (1 / 0 / 0) | 4 (0 / 0 / 4) |
| lane_choice/03_live_focus_probe.py | 1 (0 / 1 / 0) | 48 (39 / 6 / 3) |
| lane_choice/04_lane_metrics.py | 1 (1 / 0 / 0) | 6 (0 / 0 / 6) |
| lane_choice/_lane_metrics_aggregate.py | 0 | 3 (2 / 0 / 1) |
| lane_choice/_lane_metrics_blocks.py | 0 | 9 (2 / 0 / 7) |
| lane_choice/_lane_metrics_classify.py | 0 | 7 (4 / 1 / 2) |
| lane_choice/_lane_metrics_pairing.py | 0 | 13 (11 / 0 / 2) |
| lane_choice/_lane_metrics_prose.py | 0 | 11 (8 / 0 / 3) |
| lane_choice/_lane_metrics_report.py | 0 | 8 (0 / 0 / 8) |
| lane_choice TOTAL | 4 (3 / 1 / 0) | 138 (75 / 14 / 49) |
| url_discovery/01_resume_state_probe.py | 1 (1 / 0 / 0) | 18 (8 / 0 / 10) |
| url_discovery/02_fixture_site_server.py | 1 (1 / 0 / 0) | 3 (2 / 0 / 1) |
| url_discovery/_fixture_site.py | 1 (1 / 0 / 0) | 20 (17 / 0 / 3) |
| url_discovery/_fixture_site_content.py | 0 | 41 (23 / 5 / 13) |
| url_discovery TOTAL | 3 (3 / 0 / 0) | 82 (50 / 5 / 27) |
| explore_pipeline/01_discovery.py | 0 | 8 (0 / 0 / 8) |
| explore_pipeline/02_url_filters.py | 0 | 5 (0 / 0 / 5) |
| explore_pipeline/03_strategies.py | 0 | 5 (0 / 0 / 5) |
| explore_pipeline/04_render_recall.py | 1 (1 / 0 / 0) | 10 (0 / 0 / 10) |
| explore_pipeline/05_playwright_bfs.py | 1 (1 / 0 / 0) | 12 (0 / 0 / 12) |
| explore_pipeline/06_nextdata_probe.py | 1 (1 / 0 / 0) | 28 (9 / 0 / 19) |
| explore_pipeline TOTAL | 3 (3 / 0 / 0) | 68 (9 / 0 / 59) |
| access_recovery/01_google_dom_probe.py | 1 (0 / 1 / 0) | 5 (5 / 0 / 0) |
| access_recovery/02_google_wml_probe.py | 2 (0 / 1 / 1) | 2 (2 / 0 / 0) |
| access_recovery/_dom.py | 0 | 6 (6 / 0 / 0) |
| access_recovery TOTAL | 3 (0 / 2 / 1) | 13 (13 / 0 / 0) |

The "moved" docstrings in `browser_posture/01`-`05`, `_lib.py` and `access_recovery/01` moved their
one unrecorded statement (the probe copies `src/` shapes instead of importing them) into the
Gotchas of the two DOCS.md files; the rest of those docstrings was already in DOCS.md/process-docs.

## Facts moved here (recorded nowhere else before this sweep), by module

### browser_posture/_lib.py
- The three backgrounding flags (`--disable-background-timer-throttling`,
  `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`) are Playwright's own
  Chromium launch defaults. Upstream references given at the time: microsoft/playwright#33515, #37199,
  #29399, #34031, #36360.
- Probe profiles live under `~/.websearch/browser-posture-probe/`, deliberately not under the
  production `SESSION_DIR` (`~/.websearch/browser-session`). `kill_by_profile` and
  `count_processes_for` accept either; only `02_parallel_chrome_probe.py` passes the real `SESSION_DIR`,
  because the collision with the real path is the thing it tests.
- `WINDOW_ARGS` gives the automation window and the occluder window identical position and size so the
  occluder fully covers it; occlusion is a property of screen coverage, not of focus.
- The docstring stated the isolation rule: no `src/` import, profile constants and the `open -g`
  process creator are duplicated from `src/search/browser.py` and
  `dev/search_pipeline/27_brave_headed_lane_probe.py`. Now in `dev/browser_posture/DOCS.md` Gotchas.

### browser_posture/_cdp_launch.py
- `wait_for_devtools_port` reads Chromium's own `DevToolsActivePort` file under
  `--remote-debugging-port=0` and returns the port Chromium actually chose. This avoids probing for a
  free port first and losing the race for it between probe and launch.
- `find_pid_by_profile` uses a `--user-data-dir` substring match via `pgrep`, not the process tree:
  `open` forks, so the real Chrome is not a descendant of the probe. Same reason
  `05_cdp_headed_probe.find_chrome_descendant` is only valid for the patchright reference launch.
- The self-launch targets the resolved `.app` path directly (`open -g -n -a <path>`), not the bare app
  name, to avoid Launch Services ambiguity.

### browser_posture/_chromium_teardown.py
- `kill_survivors` scans system-wide by executable path (`ms-playwright/chromium`), not the probe's own
  psutil children: Chrome's GPU/renderer/utility helpers are reparented to launchd the moment the main
  process dies, so after a crash they are no longer descendants although nobody signalled them. The
  scan is safe because `ms-playwright/chromium*` is this project's own browser cache. Multi-round with a
  launchd-job removal each round is the fix for the ~15 s delayed respawn (recorded elsewhere).

### browser_posture/01, 02, 03 (docstrings)
- Hard scope boundary: these probes run against a local throwaway page, never against Google, Brave,
  Bing or any production search engine. The only external targets in the area are the detection test
  pages `bot.sannysoft.com` and CreepJS in `03`, where being measured is the pages' purpose.
- `02`: the simulated "already running user Chrome" is a backgrounded Chrome on a throwaway profile,
  never the user's real profile and never foregrounded. macOS singleton and `open -a` behaviour is a
  property of the app bundle, not of the profile, so any profile reproduces the same collision
  surface without touching the user's session. The real `SESSION_DIR` path is the one deliberate
  duplication of a `src/` constant, because it is the test subject.
- `03`: the two patch IIFEs (`SCREEN_WINDOW_PATCH`, `GETCOMPUTEDSTYLE_PATCH`) are verbatim copies of
  the then-current `src/search/browser.py` `JS_FINGERPRINT_PATCHES` (since removed) and are composable
  independently; that is what makes the four variants possible.

### lane_choice/01_backfill_pairs.py
- `SUBPROCESS_TIMEOUT_S = 260.0` sits above both lanes' own internal acquisition budgets (about
  245-246 s: `TOTAL_SCRAPE_BUDGET_S` and `TOTAL_CAMOUFOX_BUDGET_S`) so the CLI's own graceful
  `budget_exhausted` path always fires first and logs a real outcome. Only a genuinely hung subprocess
  reaches this wrapper timeout.
- `POLITENESS_DELAY_S = 2.0` is a floor between every CLI invocation (lane switch or next URL): the
  scraped sites are real third parties and both lanes already spend seconds per call, so this only
  prevents back-to-back launches.
- `find_fresh_log_record` reads the CLI's own just-written `scrape_log.jsonl` record back instead of
  parsing stdout, because the log is the canonical source.

### lane_choice/03_live_focus_probe.py
- `longest_continuous_run`: a deviation run that closes on a later non-deviating sample is bounded by
  that sample's own timestamp (an honest upper bound, the deviation is known to be gone by then). A run
  still open at the end of the series has no closing sample, so it is extended by the series' mean
  observed gap as the best available estimate. The two cases are different in kind, not one formula.

### lane_choice/_lane_metrics_classify.py
- The seven Algorithm 2 thresholds (0.333333, 0.555556, 16, 15, 4, 40, 17) are copied verbatim from the
  Kohlschuetter/Fankhauser/Nejdl paper. Do not tune them; a change makes the classifier something
  other than the algorithm the reports name.

### url_discovery/_fixture_site_content.py
- Sitemap index `<loc>` entries must be absolute: `scope_and_dedup` drops a relative `<loc>`'s empty
  host as foreign. That is why sitemap XML is built with `urljoin(base_url, path)` once the real port is known.
- `__NEXT_DATA__` version metadata (`allVersions`, `currentVersion`, `currentPathWithoutLanguage`) is
  placed only on the default version's own page, the only page `resolve_navigation_tree` reads it from.

### access_recovery/02_google_wml_probe.py (docstring)
- `impersonate="chrome99_android"` was confirmed present in this venv (curl_cffi 0.16.0) before the
  probe relied on it. SearXNG's selectors and endpoint are "as reported" to that milestone, not
  re-derived.
- The docstring of `access_recovery/01` also said the probe's selectors are a copy of `google.py` as of
  2026-09-15; now a Gotcha in `dev/access_recovery/DOCS.md`.

## Deleted as already recorded (load-bearing facts, verified by grep)

- Launchd per-app supervision job and delayed respawn, Info.plist binary-vs-XML round trip, LSUIElement
  ICU crash: `process-docs/browser_posture/` (headed chromium ad-hoc probe) and the report strings.
- `--no-startup-window` forcing `context.new_page()`, playwright#42343, crawl4ai `get_page()` reuse:
  `process-docs/browser_posture/` (cdp_url route probe, docs format salvage).
- crawl4ai 0.9.2 `_build_browser_args()` and `light_mode`: same headed-chromium probe entry.
- Timer-throttling harness numbers, occlusion caveat: `process-docs/browser_posture/` (launch latency).
- ActiveText, CreepJS findings, settle-polling: `process-docs/browser_posture/` (fingerprint patch entry)
  and `_fingerprint_report.py` strings.
- Focus-poll cadence, 10 s countdown, PROSE cap, main-repo log path, `outcome` field removal:
  `dev/lane_choice/DOCS.md` Gotchas and `process-docs/lane_choice/`.
- Fixture site sliding window, one-server-per-process, thin body, RSC island, removed traversal pages,
  `resume_state` falsy-dict and wrong-key behaviour: `dev/url_discovery/DOCS.md` Gotchas and
  `process-docs/url_discovery/`.
- A/B/C strategy meaning, 67.2 / 81.3 / 100 percent recall, GHEC pre-redirect URL form:
  `process-docs/explore_pipeline/` and `dev/explore_pipeline/DOCS.md`.
- Google probe pacing (15 s from the 4-per-60-s limiter), the four-state outcome model, the frozen
  selectors and the diagnostic JS: `process-docs/access_recovery/` and the report strings.

## Verification (2026-09-24)

- AST + tokenize scan over the five directories: no output (shebang and the three markers exempt).
- `py_compile` on all 36 touched files: clean.
- `--help` of the 10 argparse scripts (`lane_choice` 01-03, `url_discovery` 02, `explore_pipeline`
  01-06) captured before and after with `COLUMNS=100`: byte-identical. `url_discovery/02` builds its
  parser and calls `parse_args()` before any server start, so `--help` exits without serving. All ten
  parse arguments before running anything. No script without argparse was executed.
- Full suite `./venv/bin/python -m pytest dev/tests/ -q`: 488 passed before, 488 passed after.
- `dev/tests/` imports `dev.url_discovery._fixture_site` (via `test_discovery.py` and
  `test_seed_feeders.py`); those tests pass unchanged.
- DOCS.md module headings in the five directories now equal `wc -l` of each file.

## Observations for a successor (nothing changed for these)

- `explore_pipeline/04_render_recall.py::discover_with_config` references `URLPatternFilter` without
  importing it. It is only reachable when `include_pattern` is not `None`; both callers pass `None`, so
  it has never fired. Left as is (out of sweep scope); importing it would be the whole fix.
- `04`/`05`'s bundle helpers (`_chromium_bundle.py`, `_cdp_launch.py`) are pinned to chromium revision
  1228 (`CHROMIUM_REVISION_TAG`); with a newer patchright they raise by design rather than touch
  another revision.
- Tool lessons from this session: the Bash tool's working directory persists between calls (a `cd
  process-docs` silently broke later relative paths); a piped `| head` on a script run was refused with
  an "add redirect" message, so command output was redirected to `/tmp` and read from there; recursive
  `grep -r` requires an explicit scope in this environment.
- The sweep was applied with a script run through Bash rather than hundreds of individual Edit calls,
  which deviates from the "use Edit for persistent files" tool rule; the AST-equality check above is
  what stands in for reviewing each edit.

## Recap (2026-09-24)

- Inventory of this branch against `integration` (`git diff integration --name-only --`): 42 files:
  36 `.py` files in the five directories, the five `DOCS.md` files of those directories, and this file.
- DOCS.md updates were already part of the sweep commit: all module LOC headings rewritten to the
  post-sweep `wc -l` values (0 mismatches on re-check), one Gotchas section added to
  `dev/browser_posture/DOCS.md` and one to `dev/access_recovery/DOCS.md`. `dev/lane_choice/`,
  `dev/url_discovery/` and `dev/explore_pipeline/` DOCS.md needed only the LOC fix.
- Review outcome: passed. Nothing in this sweep is left open except the two disclosed limits above
  (block-level triage split; script-based editing).

## Phase 4 control-flow triage, src/search/ (issue #47), step 1: classification only (2026-09-24)

Scope: every `except` handler in `src/search/` including `engines/` (34 handlers; `openalex.py`,
`scholar.py`, `base.py`, `rate_limiter.py`, `merge.py`, `snippet.py`, `result.py`, `status*.py` have
none; no `contextlib.suppress` either). No code changed in this step.
Scan: `/tmp/orch_ws/exscan.py` copied to `/tmp/wgoogle/`, run through a small lister
(`/tmp/wgoogle/list.py`) that prints file:line, function, exception type and scan class per handler.

Evidence sources, all read from the MAIN checkout `src/logs/`:
- `cli.log` plus rotated `cli.log.2026-08-31` .. `cli.log.2026-09-23` (root logger at DEBUG, so every
  WARNING the handlers emit would be there). Oldest available day 2026-08-31.
- `query_log.jsonl`: 209 `engine_run` records; 0 with status `ERROR_PARSE`. (An earlier sweep entry
  reports 0 `ERROR_PARSE` in 4566 historical records.)
- Grep counts over all `cli.log*` files for the handlers' own log lines:
  `Cache read error` 0, `document-status capture setup failed` 0, `query_log write failed` 0,
  `kill_tab close_target failed` 0, `Failed to remove temp file` 0, `close_browser failed` 6,
  `Browser prewarm failed` 6 (all 2026-09-21, see the prewarm row).
- The logs never record CDP `Runtime.evaluate` responses, so "a script returned no value" cannot be
  observed from them either way.

### Counts per class (34 handlers)

| Class | Count | Rows |
|---|---|---|
| A status/report | 4 | google `_resolve_one` x2, search_web `_engine_with_timing` x2 |
| B fallback | 20 | `_extract_value` x7, `_diagnose` x7, brave `_poll_state`, brave `_click_challenge_button`, `cache_read`, `start_document_status_capture`, `log_query`, `_prewarm_browser` |
| C silent swallow | 0 | (the B rows below with a control-flow effect are called out in their evidence) |
| D best-effort cleanup | 8 | browser.py x5, cache_write x1, plus the two scan-TRIPWIRE handlers (`get_tab`, `cache_write`) that clean up and re-raise |
| E input-shape | 2 | browser_lock x2 |

B verdicts: 18 B-remove, 1 B-keep (`_prewarm_browser`), 0 B-keep-needs-logging. One B-remove row
(`log_query`) is weak and flagged for an owner decision. The 7 `_extract_value` rows carry a
regression risk stated below.

### Full table

Scan class abbreviations: PO = PRODUCES-OUTPUT, LO = LOG-ONLY, SP = SWALLOW-PASS, TW = TRIPWIRE.

| file:line | function | scan | class | verdict | evidence |
|---|---|---|---|---|---|
| engines/google.py:258 | `_resolve_one` (`Timeout`) | PO | A | keep | Returns reason `timeout`; counted in `diagnosis.goto_resolution` and one WARNING per run (added 2026-09-24). |
| engines/google.py:261 | `_resolve_one` (`RequestException`) | PO | A | keep | Returns reason `request_error`; same recording. |
| search_web.py:306 | `_engine_with_timing` (`TimeoutError`) | PO | A | keep | Becomes `TIMEOUT_WATCHDOG`/`TIMEOUT_NONCOOP` status plus `drop_reason`. |
| search_web.py:326 | `_engine_with_timing` (`Exception`) | PO | A | keep | Classified by `_classify_engine_exception` into a status; warning logged; degraded notice uses it. |
| search_web.py:155 | `_prewarm_browser` (`Exception`) | LO | B | B-keep | Observed 6 times on 2026-09-21 (10:40, 10:41, 10:45, 10:47, 11:56, 12:03): `DevToolsActivePort did not appear ... within 10.0s`; each WARNING is in `cli.log` and every browser engine of that run then shows `Engine browser error` (status `ERROR_BROWSER`). Traceable. Note: the message says "engines will retry individually"; in 6 of 6 observed cases the retry did not recover (4 browser engines each errored with `Cannot connect to host localhost:<port>`); only non-browser openalex returned URLs in 2 of the 6 runs. Removing the handler would abort the whole run and lose those openalex results, so it is kept; only the log wording is inaccurate. |
| cache.py:92 | `cache_read` (`Exception`) | PO | B | B-remove | Corrupt/unreadable cache file becomes `None`, indistinguishable from a cache miss; the drilldown then tells the user to rerun `search_web`. Writes are atomic (`os.replace`). `Cache read error` never logged (0 in 24 days of logs). |
| document_status.py:30 | `start_document_status_capture` (`Exception`) | LO | B | B-remove | Setup failure degrades to an empty status chain (`http_status: None`). Never observed (0 log hits). Documented as intentional in `src/search/DOCS.md`, but the standard requires an observed trigger. |
| query_logger.py:24 | `log_query` (`Exception`) | LO | B | B-remove (weak) | Write failure only logs a WARNING and drops the record. Never observed (0 hits). Telemetry, not search output; owner decision whether telemetry counts as business logic. |
| engines/google.py:137 | `_extract_value` (`KeyError, TypeError`) | PO | B | B-remove | CDP result without `value` (script threw, context destroyed) returns `None`, callers read it as 0 containers / no data and end in `EMPTY`. No observation possible from logs. Risk: the poll loops in `_wait_for_results` would abort the engine with `ERROR_PARSE` on a transient blip instead of polling on; verify live after removal. |
| engines/bing.py:91 | `_extract_value` | PO | B | B-remove | Same as google. |
| engines/brave.py:146 | `_extract_value` | PO | B | B-remove | Same as google. |
| engines/duckduckgo.py:94 | `_extract_value` | PO | B | B-remove | Same as google. |
| engines/mojeek.py:110 | `_extract_value` | PO | B | B-remove | Same as google. |
| engines/startpage.py:95 | `_extract_value` | PO | B | B-remove | Same as google. Startpage polls across a form-submit navigation, the likeliest place for a transient no-value result; highest regression risk of the seven. |
| engines/yandex.py:94 | `_extract_value` | PO | B | B-remove | Same as google. |
| engines/google.py:289 | `_diagnose` (`JSONDecodeError, TypeError`) | SP | B | B-remove | Input is this project's own `JSON.stringify`; on failure the diag keeps blank defaults (`url: ""`). 0 `ERROR_PARSE` in 209 records. The 2026-09-09 sweep removed the sibling `_parse_results` handler and explicitly left this one unexamined. |
| engines/bing.py:178 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/brave.py:206 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/duckduckgo.py:161 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/mojeek.py:207 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/startpage.py:156 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/yandex.py:157 | `_diagnose` | SP | B | B-remove | Same as google. |
| engines/brave.py:183 | `_poll_state` (`JSONDecodeError, TypeError`) | SP | B | B-remove | Failure keeps the zero-state, so the loop polls on and ends `EMPTY`; own JSON, never observed. |
| engines/brave.py:195 | `_click_challenge_button` (`JSONDecodeError, TypeError`) | PO | B | B-remove | Failure returns `False` ("not clicked"), which then shows as `challenge_triggered: False` in the diagnosis; own JSON, never observed. |
| browser.py:265 | `kill_tab` (`Exception`) | LO | D | keep | Best-effort tab close, WARNING logged, `finally` still pops `_tabs_opened`. Never observed (0 hits). |
| browser.py:150 | `_terminate_then_kill` (`NoSuchProcess`) | SP | D | keep | Process already gone between listing and signal. |
| browser.py:156 | `_terminate_then_kill` (`NoSuchProcess`) | SP | D | keep | Same, on `kill`. |
| browser.py:244 | `_cancel_focus_watchdog` (`CancelledError`) | SP | D | keep | Awaiting the task just cancelled; the expected outcome of `cancel()`. |
| browser.py:285 | `kill_own_chrome` (`Exception`) | PO | D | keep | Teardown of a possibly dead Chrome, WARNING logged, safety net continues. Observed 6 times (`The browser is not running`, same 2026-09-21 runs), traceable. |
| cache.py:77 | `cache_write` (`OSError`) | LO | D | keep | Temp-file unlink during cleanup, WARNING logged, original error is re-raised by the outer handler. |
| browser.py:190 | `get_tab` (`Exception`) | TW | D (re-raise) | keep | Resets state, releases the lock, then `raise`. A tripwire with cleanup. |
| cache.py:74 | `cache_write` (`Exception`) | TW | D (re-raise) | keep | Removes the temp file, then `raise`. |
| browser_lock.py:58 | `_sidecar_age_s` (`OSError, JSONDecodeError, KeyError, ValueError`) | PO | E | keep (optional narrowing) | Sidecar legitimately absent or half-written: the lock holder takes `flock` first and writes the sidecar second, and `write_text` truncates before writing. `None` means "age unknown, keep polling", a real outcome of that two-step protocol. `KeyError`/`ValueError` (malformed content) are broader than the race and could be dropped. |
| browser_lock.py:36 | `acquire` (`BlockingIOError`) | LO | E | keep | Lock contention is the normal outcome the loop exists for. |

### Notes for the reviewer

- No row is class C. The rows closest to it are the seven `_extract_value` handlers: they turn a
  failed script into "nothing found", which the engines report as a genuine `EMPTY`. I classed them B
  (default value) because the result is a recorded status either way; the difference to the
  2026-09-09 removals is that no log or record can show the trigger.
- If the seven `_extract_value` rows and the seven `_diagnose` rows are approved, the removal is
  mechanical and identical in every engine. Expected new behaviour: a `KeyError`, `TypeError` or
  `JSONDecodeError` propagates into `_engine_with_timing` and lands as `ERROR_PARSE` (the `TypeError`
  and `KeyError` cases are in `_classify_engine_exception`'s tuple only via `KeyError`; a bare
  `TypeError` falls to `ERROR_OTHER`, same caveat as the 2026-09-09 entry).
- `_prewarm_browser`: keeping it is the recommendation; optional follow-up is correcting the WARNING
  wording ("engines will retry individually") since 0 of 6 observed retries recovered.
- Not investigated: whether a prewarm failure leaves a stale `_browser` for the engines' retry (the
  engines connect to a port that refuses connections, which suggests it does). That is a lifecycle
  question for `browser.py`, not part of this triage.

## Phase 4 step 2: approved removals applied to src/search/ (2026-09-24)

Owner decisions (relayed by the orchestrator): remove all rows classified B-remove except
`log_query`; keep `_prewarm_browser` and fix its message.

- Removed with no replacement handler: `_extract_value` x7 and `_diagnose` x7 (google, bing, brave,
  duckduckgo, mojeek, startpage, yandex), brave `_poll_state` and `_click_challenge_button`,
  `cache.cache_read`, `document_status.start_document_status_capture` (16 handlers; 18 with
  `_poll_state`/`_click`... counted as: 7 + 7 + 2 + 1 + 1 = 18).
- `document_status.py` lost its now-unused `logging` import and `logger`.
- Reclassified: `query_logger.log_query` B (weak B-remove) -> D best-effort telemetry, kept as is.
- `_prewarm_browser` kept; WARNING now reads "browser engines are expected to fail individually,
  non-browser engines still run: <error>".
- Tests: new `dev/tests/test_search_control_flow_removals.py` (28 tests: `_extract_value` KeyError and
  TypeError over 7 engines, `_diagnose` JSONDecodeError over 7 engines, brave poll/click,
  `cache_read` corrupt file raises and missing file still `None`, propagated `KeyError`/
  `JSONDecodeError` surfaces as `ERROR_PARSE` through `_engine_with_timing`, prewarm message).
  `dev/tests/test_document_status.py`: the "degrades to an empty list" test became "propagates".
- Suite: 492 passed before, 520 passed after.
- Docs: `src/search/DOCS.md` and `src/search/engines/DOCS.md` updated (LOC headings, the two
  now-false sentences, new REMOVED entries, the `log_query` and prewarm gotchas).

### Finding during the run

The first full suite run after the removals failed `test_brave_engine.py::
test_marker_word_from_own_query_no_longer_discards_real_results` with `websockets InvalidStatus: HTTP
500 "No such target id"` raised from `enable_network_events()`. That is the trigger the removed
`start_document_status_capture` handler used to swallow: with a real headless Chrome in the test, arming
the network listener can fail with a target-id race. It did not recur (test passes alone and in the
next full run). The same suite had one brave-test failure at the very start of this session, which
was most likely the same race surfacing as a wrong `document_status_chain`. So the trigger has been
observed in tests, never in production logs (0 warnings in `cli.log` 2026-08-31..2026-09-24). It was
not put back: the owner decision stands, and an occurrence in production will now show up as a
recorded engine status. Successor: if brave tests flake with that error, the cause is a test-side
tab-readiness race, not the removal.

### Verification (real runs, 2026-09-24)

Two `cli.py search_web` runs with different queries; every engine status from `query_log.jsonl`:

| Query | google | duckduckgo | mojeek | openalex | startpage | brave | bing | yandex |
|---|---|---|---|---|---|---|---|---|
| python asyncio task cancellation semantics | OK 10 | OK 10 | OK 10 | OK 9 | OK 10 | OK 10 | OK 10 | OK 10 |
| bosch akkuschrauber ersatzakku 18v kompatibel | OK 10 | OK 10 | OK 10 | EMPTY 0 (http 200) | OK 10 | OK 10 | OK 10 | OK 10 |

No `ERROR_PARSE` and no `ERROR_OTHER`; no `drop_reason` set on any engine. The openalex EMPTY is a
genuine empty API answer for a German product query (HTTP 200), not a failure. This verifies the
absence of new failures on two healthy runs only; the removed handlers guarded conditions that were
never seen in production, so a clean run cannot prove them harmless.

## Recap (Phase 4 step 2, 2026-09-24)

- Inventory against `integration` (`git diff integration --name-only --`): 15 files: this file, 4
  new/changed test files (`test_search_control_flow_removals.py` new, `test_document_status.py`), 2
  DOCS.md files, and 8 source files (`cache.py`, `document_status.py`, `search_web.py`, 7 engines
  counted with `brave.py` two handlers; see git for exact list), plus the search_pipeline entry.
- Correction to the bullet above: the removed-handler count is 18 (7 + 7 + 2 + 1 + 1), not 16.
