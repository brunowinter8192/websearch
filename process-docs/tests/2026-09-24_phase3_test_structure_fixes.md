# Phase 3 test-structure fixes (2026-09-24)

Baseline before any change: `venv/bin/python -m pytest dev/tests` = 541 passed in ~37 s (serial). Environment: worktree-local `venv/` (untracked, gitignored); `pytest-xdist` and `pytest-timeout` were installed into it and added to `requirements.txt`.

## Isolation (F1, F2, F6, F9, F10)

- One autouse fixture in `dev/tests/conftest.py` sets `tempfile.tempdir` to a per-test directory under `tmp_path`. Every `tempfile.mkdtemp` / `gettempdir()` in `src/` (browser session dirs, `scrape-url-cdp-*`, `_remove_orphaned_session_dirs` glob) therefore stays inside the test. This replaced the per-file patches proposed in the findings: one place, covers all seven `get_tab` tests and the three orphan-dir tests.
- Second autouse fixture wraps `subprocess.run`; a call whose first argument is `osascript` fails the test by name, everything else passes through. `test_conftest_guards.py` provokes the trap and the tempdir redirection.
- `_patch_cdp_launch_mechanics` now also replaces `chromium_scrape._focus_steal_watchdog` with an async no-op. Proof: with the fake reverted, `test_chromium_scrape.py` gave 7 failed / 10 passed (the trap fired); with it, all pass.
- F9: `test_pipe_scraper_onward_links.py` replaces `pipe_scraper_report.Path` with a lambda mapping any path to `tmp_path / basename`. No `src/` change was needed.
- F10: `test_log_pipe_scrape_fail_soft` uses a regular file as parent ("blocker file") instead of `/nonexistent-root-dir`.

## Watchdog, drilldown, limiter (F3, F4, F5, F14)

- `test_death_pipe.py`: `monkeypatch.setenv("WEBSEARCH_DEATH_PIPE_LOG_PATH", ...)` runs BEFORE `spawn_watchdog` in every watchdog test (fixture `watchdog_log_path`); the dummy `time.sleep(60)` process is killed in the fixture teardown; sleeps replaced by `_wait_until` polling.
- F4 proof by mutation (temporary, reverted): changing `if killed or dir_removed:` to `if True:` in `src/death_pipe.py` makes `test_watchdog_is_silent_noop_when_target_already_dead` fail. Before the fix that assertion was true regardless (the child never saw the env var). The watchdog process is located through `psutil.process_iter` by cmdline (ends with `death_pipe.py`, contains the dummy pid); a finished watchdog stays a zombie (parent never waits), so "exited" means `NoSuchProcess` or `STATUS_ZOMBIE`, not `pid_exists`.
- Live-log proof: mtime of `src/logs/cli.log` unchanged across a full `test_death_pipe.py` run. Before the fix the file received a line with a pytest tmp path (observed by the scanner).
- F5: `_log_drilldown` is now tested in-process. Importing `cli` executes module-level code that opens a `TimedRotatingFileHandler` on the real `src/logs/cli.log` and calls `logging.basicConfig`. The fixture `cli_module` patches `logging.handlers.TimedRotatingFileHandler` to a factory returning `logging.NullHandler()` before `import cli` and removes `cli` from `sys.modules` afterwards. `src/` unchanged (moving `_log_drilldown` into `query_logger.py` was the alternative; rejected because Phase 5 edits both files). Log mtime unchanged.
- F14: autouse fixture in `test_query_logger.py` replaces `search_web.get_limiter` with a no-op limiter.

## Wall clock and host state (F7, F11, F12, F13)

- F7: autouse conftest fixture pins `camoufox_scrape._resolve_system_locale` to `"en-US"`. The two explicit locale tests call the original captured at import time (`_real_resolve_system_locale`).
- F11: `_install_fake_pacing(monkeypatch)` in `_pipe_scraper_fakes.py` installs a `_FakeClock`: `pipe_scraper_pacing.time`, `.asyncio.sleep` and `.random.uniform` (returns the midpoint = `download_delay`) plus `pipe_scraper_acquisition.datetime.now`. Sleeps are recorded and advance the fake clock, so the assertions became exact: 3 URLs at 0.05 give sleeps `[0.05, 0.05]` and a ts spread of 0.1 s; 6 URLs give five sleeps and 0.25 s. The fake clock starts at the real `time.time()`, NOT at an arbitrary constant: `log_pipe_scrape` calls `maybe_prune_jsonl`, which drops records older than the retention window by their `ts`, so a 1970 timestamp made the first record vanish (observed: 5 of 6 records).
- F12: `discover.datetime` replaced by a subclass whose `now()` returns a frozen instant; the expected date is computed from the same constant.
- F13: `threading.Event` handshakes; `stuck_holder` released in `finally`. For the "no stale takeover under budget" test the waiter thread signals an event from a patched `browser_lock.time.sleep` (the poll), so the holder is released only after the waiter really polled.

## Suite-level (S1, S2, F8)

- `pytest.ini`: `addopts = -m "not browser" --timeout=60`, marker `browser` registered. `test_brave_engine.py` (module-level `pytestmark`) and the two browser tests in `test_yandex_engine.py` carry the marker: 12 tests deselected by default, `-m browser` selects exactly those (12 passed in ~22 s). No repetition measurement this cycle (decision from Main).
- Default run afterwards: 532 passed, 12 deselected, ~9.5 s wall (serial), also 532 passed with `-n auto --dist loadfile` (~6 s).
- `dev/tests/run_strands.sh`: one `pytest -x -q -p no:cacheprovider --basetemp=<own dir>` per `test_*.py`, all started in the background, all waited for; exit 5 (nothing collected, e.g. the all-`browser` brave file) is not a failure. Verified: 52 strands, 0 failed, ~9 s.

## Script-style tests (T1, T2, T3)

- T2: `test_cooldown_policy.py`, `test_sigint_report.py`, `test_tail_race.py`, `_test_tail_race_watchdog.py` were already valid pytest functions wrapped by a hand-rolled `main()`/`_run()` runner (all 19 passed under pytest unchanged). They moved with `git mv` to `dev/tests/test_riding_*.py`; runner, `sys.path` hacks and section markers removed; `test_3_no_spurious_requeue` (two private sub-cases) became `test_3a_...` and `test_3b_...`. `smoke_stage1.py` section 1 (import/defaults check) became `test_riding_imports.py`; section 2 (deterministic watchdog test, broken: `RiderState` needs `job_dir`/`target_urls`, `PersistentCooldownManager` import path gone) was deleted; section 3 stays as an explicit live verification script. `test_watchdog.py` deleted (tested the frozen dev snapshot `p2_browser_rider`, not `src/`; decision from Main). Stall behaviour of `_abort_stall` is covered by `dev/tests/test_proxy_riding_abort.py`. Hypothesis, not observed: `p2_browser_rider.py` re-exports `_watchdog`/`_abort_stall` "for test_watchdog.py"; the re-export is now only needed by `p4_reporter.py`.
- T3: `_truncate` cases and the six `strip_bloat` cases (dev copy `dev/search_pipeline/_lib/text.py`, imported as `dev.search_pipeline._lib.text`) are real tests in `dev/tests/test_snippet.py`; the two assert-at-import scripts were deleted.
- T1 (brave and mojeek): the single `test_workflow()` with accumulating `check()` became one pytest test per check, each through the async fixture `fixture_browser` (own loopback server, own temp profile, own Chrome). `check()` now raises `AssertionError` (fail-fast); `report_outcome` and the fixed `/tmp/*_fixture_report.md` path are gone (the report is written to `tmp_path`). The report check has its own test that measures the fixture queries itself (`_collect_fixture_measurements`) instead of reading state left over from earlier checks. Pure-function checks are a separate browser-free test. Equivalence: before the change both scripts printed ALL CHECKS PASSED (53 and 47 PASS lines); AST comparison of the `check("...")` name lists before/after is identical (28 / 25 literals in the test modules) and every `check_*` function is called by a test. After: 20 tests passed with `-n 8` in ~20 s (brave 11, mojeek 9). These files live outside `dev/tests`, so they are not collected by default; run them with `pytest -o addopts="" dev/brave_return/test_brave_pydoll_core.py`.

## Not done / hypotheses

- Timing thresholds in the brave/mojeek probe tests (`>= 0.9 * budget`, `< budget`) are kept as they were; no flake was observed in the runs above.
- F15, F16, F17 rejected by Main, not touched.

## Merge with Phase 5 (2026-09-24)

- Conflicts in `DOCS.md`, `test_camoufox_scrape_output.py`, `test_pipe_scraper.py`: took the integration test for the unwritable log path (raises `OSError`, already blocker-file based); kept the captured `_real_resolve_system_locale` in the locale tests and added `platform = darwin` to the new empty-output test so it stays host-independent.
- Two failures appeared only under the parallel runner and are fixed: (1) the conftest tempdir lived at `tmp_path/systmp`, which broke `test_sidecar_is_written_atomically_without_leftover_tmp` (asserts the exact content of `tmp_path`); it now uses `tmp_path_factory.mktemp("systmp")`. (2) `test_engine_with_timing_timeout*` (both) classify TIMEOUT_WATCHDOG vs TIMEOUT_NONCOOP by real elapsed ms (`< timeout*1.2`, i.e. 60 ms) and flipped to NONCOOP under CPU load (observed 2 of 10 repeats with 6 busy loops). Fixed by patching `search_web.time.perf_counter` to a 1 ms tick counter; 10 of 10 repeats pass under the same load.
