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
