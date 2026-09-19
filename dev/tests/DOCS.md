# dev/tests/

## Role
The project's pytest suite. Regression coverage for `src/search/`, `src/scraper/`, `src/crawler/`,
`src/news/engine/proxy_pool/`, `src/news/engine/proxy_riding/` (abort.py only, as of 2026-09-09),
`src/news/platforms/theblock/`, `src/news/platforms/coindesk/` (timeline.py only, as of 2026-09-09),
and `src/log_janitor.py` (as of 2026-09-09) — pure-logic branch coverage,
library-upgrade guards (live calls into installed `crawl4ai`), and production-failure regression
repros. Almost entirely no network/browser dependency: I/O boundaries (HTTP clients, browser
automation, subprocess) are mocked per-test; production logic itself is exercised for real — as of the M4 milestone (2026-09-15) this is enforced, not just described: `conftest.py`'s autouse tripwire fails any test outright the moment it reaches a real browser-launch primitive unmocked (see its own entry below). The one
deliberate exception is `test_discovery.py`/`test_seed_feeders.py`'s fixture-backed sections, which
run real network (plain HTTP only — neither file constructs a `crawl4ai` browser), but ONLY ever
against the local `dev/url_discovery/_fixture_site.py` server, never a live host or a third-party
network call — see
`process-docs/url_discovery/2026-08-28_validation_against_live_sites_was_the_wrong_unit.md` for why
a live host stopped being an acceptable test dependency. Touch this directory when adding/removing
test coverage for the modules above; do not touch when only production behavior changes without an
assertion needing to change.

## Public Interface
`__init__.py` is empty — collected via `pytest` from the repo root (`pytest.ini`: `testpaths =
dev/tests`, `pythonpath = .`). No importable package surface.

## Flow
Synthetic/captured-sample inputs (JSON items, HTML fixtures, monkeypatched clients) → real
production function/class under test → assert on real output (parsed results, rendered
markdown/job.md, JSONL records, classification verdicts). `tmp_path`/`monkeypatch` isolate
filesystem and environment per test; no test writes outside `tmp_path` or reads the real
production log paths.

## Modules

### conftest.py (41 LOC)
**Purpose:** Suite-wide autouse tripwire (M4, 2026-09-15) — replaces `src.search.browser.Chrome`,
`src.scraper.chromium_scrape._self_launch_chrome`, `src.scraper.camoufox_scrape.AsyncCamoufox`, and
`src.crawler.pipe_scraper.AsyncWebCrawler` with a failing stand-in before every test, so a test that
reaches a real browser-launch primitive without having mocked it fails loudly and by name instead
of silently opening a real window. Not a fallback: it produces no output and refuses to let the
test continue. A test's own `monkeypatch.setattr` on the same target, inside the test body, runs
after this fixture's setup and simply wins for that test's duration — this is a standard pytest
fixture-ordering guarantee, not something each test has to opt into. See
`process-docs/browser_posture/` for the investigation this closes: three real Chrome launches per
full suite run, all inside `test_query_logger.py`, invisible to a grep-only audit.
**Calls out:** `src.search.browser`, `src.scraper.chromium_scrape`, `src.scraper.camoufox_scrape`,
`src.crawler.pipe_scraper` (import only, to reach the four names above).

### test_bing_engine.py
**Purpose:** `src/search/engines/bing.py` — `_clean_url` (ck/a redirect unwrap, real captured
sample), `_build_results`. `_classify_diagnosis` coverage removed with the function itself (the
guessed-verdict-removal milestone) — its marker/ready_state inputs are now plain diagnosis fields.
As of 2026-09-09, also `_parse_results`: `test_parse_results_raises_on_invalid_json` proves the
removed `except (json.JSONDecodeError, TypeError): return []` handler's replacement — a `_FakeTab`
whose `execute_script` returns a malformed JSON string makes `_parse_results` raise
`json.JSONDecodeError` instead of silently returning `[]`. The five sibling engines
(`brave`/`duckduckgo`/`google`/`startpage`/`yandex`) share the identical removed handler shape but
are not separately tested for it — one engine's coverage stands for all six, since the code path
is byte-for-byte the same. Also as of 2026-09-09, `test_clean_url_raises_when_decode_raises`
(renamed from `..._falls_back_to_raw_href_when_decode_raises`) proves `_clean_url`'s own removed
decode-failure passthrough: the same `base64.urlsafe_b64decode` monkeypatch now asserts
`pytest.raises(ValueError)` instead of a fallback return value.
**Calls out:** none (pure function tests, one `monkeypatch` on `base64.urlsafe_b64decode`).

### test_brave_engine.py (403 LOC)
**Purpose:** `src/search/engines/brave.py` — `_build_results`, plus fixture-driven regression tests
for three milestones: the marker-reflection fix and the challenge-solving milestone, both recorded
in `process-docs/marker_reflection/`, and the partial-diagnosis-on-timeout milestone in
`process-docs/search_pipeline/`. `_classify_diagnosis` coverage removed with the function itself
(the guessed-verdict-removal milestone). The regression tests run a real headless pydoll Chrome
against loopback fixture servers, because every defect and every fix here lives in the engine's
injected JS reading real DOM state. One test bounds how long a genuine block may take against the
engine watchdog. One guards against an unrelated button leaking into a success record; it proves
the mechanism, not how often staggered loading occurs live, and the process-docs entry says why
that number could not be measured cleanly. One cancels the real engine mid-poll from outside and
asserts the facts it had already written survive the cancellation.
**Calls out:** `pydoll.browser` (`Chrome`, `ChromiumOptions`), `pydoll.commands.TargetCommands` —
monkeypatches `brave.py`'s own already-imported `new_tab`/`kill_tab` names directly, never touches
`src.search.browser.Chrome`, so `conftest.py`'s `_no_real_browser_launch` trap never fires. Reads
the real challenge fixtures from `dev/brave_return/fixtures/` rather than reimplementing them.

### test_mojeek_engine.py (297 LOC)
**Purpose:** `src/search/engines/mojeek.py` — the one engine that solves its own challenge, so the
plumbing is tested, not only the parse. Pure seams: `_is_ready_to_parse` (the
sufficiency-or-stability parse rule, including the partial-render case observed live three times —
1 link at the instant the poll first matches after a solved challenge), `_should_fire_verify`,
`_parse_target`, `_build_results`. Driven seams: `_await_results` (via the local
`_run_await_results` wrapper, added for the partial-diagnosis-on-timeout milestone — every existing
call site already used `deadline=`/`target=` keywords, so the wrapper supplies the 3 new positional
parameters `_await_results` gained, `status_chain=[]`/`t0=time.perf_counter()`/`partial=None`,
without rewriting 6 call sites individually) against a `_ScriptedTab` that dispatches on script
identity and counts calls, covering the unchallenged fast path (parses on poll 1, `verify()` never
fired), the challenged path (`verify()` fired exactly once, parse waits out the partial render),
budget behaviour (gives up at the deadline still reporting `challenge_triggered`, and polls zero
times on an already-spent budget), and `_diagnose`'s empty-record contract (an unsolved challenge
is distinguishable from a page that never had one; `marker` stays `None`).
`test_block_boilerplate_from_first_poll_does_not_short_circuit` is the regression guard for the
terminal-verdict-on-a-start-true-condition defect that cost two live runs in the
`engine_reduction` area — every poll in it carries a live challenge widget and its note text while
results only arrive on poll 3.
**Calls out:** none (fake tab, one `monkeypatch` on the module's `WAIT_INTERVAL`).

### test_openalex_engine.py (274 LOC)
**Purpose:** `src/search/engines/openalex.py` (2026 API migration) — `_extract_pdf_url`/
`_parse_results` populate `SearchResult.pdf_url` from `best_oa_location.pdf_url` (null when the
location or the pdf_url itself is null); `search_with_reason`'s 429/403/zero-results-at-200
branches all carry `diagnosis={"http_status": <code>}` while `reason` stays `None` on every one of
them (the guessed-verdict-removal milestone deleted the 429→`EMPTY_BLOCK` verdict, since it carried
no information the fact didn't already); non-empty results are diagnosis-free; `api_key` query
param present only when `OPENALEX_API_KEY` is set, `mailto` never sent; `per_page` clamped to the
vendor's 100-max. Also covers the pdf_url chain end to end: `build_engine_pools` (merge.py) carries
the winner's `pdf_url`, `format_engine_pool` (cache.py) renders a `PDF:` line directly after `URL:`
when present and omits it when absent or when the cached dict predates the key (`.get()` compat).
As of 2026-09-09, also the only file exercising `BaseEngine.search()` (the sole engine test that
calls it at all): `test_search_base_method_returns_plain_list` (renamed from the old
"legacy_wrapper" name — `search()` is no longer an engine-specific wrapper, it's `BaseEngine`'s own
one concrete method) proves the success path still returns a plain list; the new
`test_search_base_method_propagates_exception` proves the replacement contract — with the fake
client's `get` raising, `await engine.search(...)` now raises too, since the per-engine
`try/except Exception: return []` swallowing wrapper was removed (Phase 4 control-flow review,
user decision) and `search()` is a bare delegation to `search_with_reason` with no exception
handling of its own.
**Calls out:** none (pure function tests, `httpx.AsyncClient` monkeypatched with a fake client
that records request params, the pattern established in `test_seed_feeders.py`).

### test_startpage_engine.py (42 LOC)
**Purpose:** `src/search/engines/startpage.py` — `_build_results`. `_classify_diagnosis` (iframe
challenge) coverage removed with the function itself (the guessed-verdict-removal milestone).

### test_yandex_engine.py (244 LOC)
**Purpose:** `src/search/engines/yandex.py` — `_is_self_referential`, `_is_block_url` (kept: also
the early short-circuit optimization inside `search_with_reason`, independent of the removed
verdict; scoped to the URL path only as of the marker-reflection fix, covered here by two pure
cases), `_build_results` (self-link filtering). `_classify_diagnosis` coverage removed with the
function itself (the guessed-verdict-removal milestone). Also carries two fixture-driven
regression tests for the same fix, in the same real-browser shape as `test_brave_engine.py`: an
ordinary results URL whose query string carries a block marker, and a genuine captcha redirect.
See `process-docs/marker_reflection/`.

### test_document_status.py (92 LOC)
**Purpose:** `src/search/document_status.py` — `start_document_status_capture` (a fake tab exposing
`_target_id`/`enable_network_events`/`on` proves the `Network.responseReceived` filter: main-frame
document responses collected in order, non-document/other-frame events ignored, setup failure
degrades to an empty list rather than raising) and `attach_document_status` (last-entry-wins
`http_status`, `None` — never a fabricated default — on an empty chain, does not mutate the input
diagnosis dict).

### test_browser_lock.py (91 LOC)
**Purpose:** `src/search/browser_lock.py` — real-flock behavior against `tmp_path` (no mocking):
immediate acquire when free, genuine blocking until a background thread's `release()`, and the
stale-takeover path (a real held flock + a backdated sidecar triggers `on_stale` then reacquires).

### test_death_pipe.py (149 LOC)
**Purpose:** `src/death_pipe.py` — real spawned-watchdog-subprocess behavior (no mocking for
`spawn_watchdog` itself): a dummy `python -c "time.sleep(60)"` process is protected, then
`os.close()` on the fd `spawn_watchdog` returns simulates this process dying WITHOUT actually
exiting the test process; asserts the watchdog kills the dummy and removes `cleanup_dir` once that
happens, stays completely silent when the target was already dead (net-1-already-handled path),
and logs an intervention line only when it actually had to act. `_terminate_then_kill` gets its own
mocked-psutil pure-logic tests separately. A killed dummy is OUR OWN child (unlike a real detached
Chrome/Firefox) so it zombies until reaped — tests check `Popen.poll()`, not `psutil.pid_exists()`.

### test_log_janitor.py (17 LOC)
**Purpose:** `src/log_janitor.py::get_retention_days` — first test coverage for this module. As of
2026-09-09: defaults to 14 when `WEBSEARCH_LOG_RETENTION_DAYS` is unset; raises `ValueError` when
it is set to a non-integer string (the removed silent-fallback-to-14 behavior's replacement — see
`src/DOCS.md`'s Gotchas). `maybe_prune_jsonl`/`maybe_prune_sidecars` are not covered here — see
`dev/logging/` for their own dev-script exploration, out of scope for this file.

### _browser_fakes.py (23 LOC)
**Purpose:** Shared `FakeChrome` and `_reset_state(monkeypatch, browser)` used by both
`test_browser.py` and `test_browser_get_tab.py` — not collected by pytest (no `test_*.py` name),
and cannot import `src/` itself (dev-script import boundary), so `_reset_state` takes the already-
imported `browser` module as a parameter instead of importing it directly.
**Called by:** `test_browser.py`, `test_browser_get_tab.py`.

### test_browser.py (386 LOC)
**Purpose:** `src/search/browser.py` — `_find_app_bundle` (real function, no mocking, same
walk-up-to-`.app` behavior as `chromium_process.py`'s own copy) and
`_open_background_process_creator` (as of the M2 no-Spaces-drag milestone, 2026-09-17, asserts the
built `open -g -n -a <bundle_path> --args ...` command targets the resolved bundle path passed in,
not the literal `"Google Chrome"` string it used before); `_pids_matching_session_profiles`/
`_record_own_pids`/`_terminate_then_kill` pgrep-output parsing and psutil dispatch (subprocess+psutil
mocked). As of the fresh-profile-per-run milestone (`process-docs/browser_posture/`):
`_remove_orphaned_session_dirs` and `_reap_session_profile` (which now calls it) run against the
REAL filesystem — `tempfile.mkdtemp(prefix=browser.SESSION_DIR_PREFIX)` creates a genuine leftover
directory, the function call is real, `Path(...).exists()` is checked after — same precedent
`test_chromium_scrape_facts.py` already established for the sibling scrape lane's identically-shaped
per-run directory; a directory with an unrelated prefix is confirmed left alone, not just assumed
safe. `kill_own_chrome()`'s full teardown sequence (now including real removal of a `_session_dir`
it owns), its no-op path when the browser was never touched, and the
PID-safety-net-and-lock-release-still-run path when `close_browser()` itself raises (Chrome already
dead mid-sweep) — both of those two tests now also assert the session directory is gone from disk
and the module global reset to `None`. `close_browser()`'s own unconditional cancellation of a live
focus-steal watchdog task, and its no-op path when none was ever spawned; `_get_frontmost_pid`/
`_activate_pid`'s subprocess wrapping; `_focus_steal_watchdog_by_pid`'s three PID-membership
branches, including reclaiming immediately when an owned pid is already frontmost on the very first
loop iteration given a valid externally-supplied anchor (the regression guard for the anchor-race
bug `test_browser_get_tab.py` covers).

### test_browser_get_tab.py (225 LOC)
**Purpose:** `src/search/browser.py`'s `get_tab()` — the critical-section ordering (resolve-bundle
-> lock -> reap -> [fresh `tempfile.mkdtemp`, as of the fresh-profile-per-run milestone] ->
anchor-capture -> launch -> record-own-pids -> spawn death_pipe watchdog -> spawn the PID-keyed
focus-steal watchdog with that anchor) and that the watchdog receives `_owned_pids` WITH
`cleanup_dir=` this run's own fresh directory (a behavior change from the persistent-profile era,
when `cleanup_dir` was always `None` — the session profile now IS deletable, and death_pipe already
supported the parameter, just unused from this call site until now).
`_resolve_chromium_bundle_path` is mocked in every test that reaches it (`_fake_resolve_bundle`,
module-level, returns a fixed fake `.app` path) — never called for real, same precedent as
`chromium_scrape.py`'s own tests never calling its identical-shaped function for real either.
`test_get_tab_self_launches_with_port_zero_and_forwards_arguments` also asserts the
`functools.partial`-wrapped process creator actually carries the resolved bundle path through to
`BrowserProcessManager` — the one line that makes the fix real rather than just resolving a path
nothing downstream uses. Also covers `get_tab()`'s self-launch sequence with
`FakeChrome`/`FakeProcessManager` (no more `.start()`): `_setup_user_dir()`
called directly, `--remote-debugging-port=0` and the full `options.arguments` (including
`--no-startup-window`) reaching `start_browser_process`, and the post-launch `_connection_port`/
`_connection_handler` fixup once `_wait_for_devtools_port` resolves a port — `_wait_for_devtools_port`/
`ConnectionHandler` are mocked at the module boundary; `tempfile.mkdtemp` itself is NOT mocked
anywhere in this file (real, tiny, throwaway directories, cleaned up by each test's own `finally`).
Fresh-profile-per-run milestone additions: two real `get_tab()` calls back to back (browser/session
reset by hand between them, simulating two runs) prove the resulting directories differ and both
carry `SESSION_DIR_PREFIX`, and that `browser_lock.acquire` saw the identical `LOCK_PATH` both
times; a standalone pure-constant assertion pins `LOCK_PATH` to its fixed, non-derived value; a
launch-failure test proves `get_tab()` removes its own partially-created directory (captured via a
raising fake `Chrome` that reads `browser._session_dir` at the moment of failure) rather than
leaking it.

### test_scrape_logger.py (44 LOC)
**Purpose:** `src/scraper/scrape_logger.py` — `write_sidecar`'s real header content (no prior
direct coverage; the scrape-lane tests only mock it as a no-op). Engine field present and correct
per lane (chromium/camoufox), existing fields unaffected, empty-content still returns `None`.

### test_query_logger.py (404 LOC)
**Purpose:** `src/search/query_logger.py` (`log_query` fail-soft JSONL write) + per-engine timing
capture in `src/search/search_web.py` (`_engine_with_timing`, `search_web_workflow` log shape,
`search_key` matches real `cache.cache_key`) + `cli.py:_log_drilldown` via an isolated subprocess.
As of the M4 milestone (2026-09-15), the three tests calling `search_web_workflow` directly also
patch `search_web._prewarm_browser` with an async no-op (`_fake_prewarm_browser`) — before this
fix, `_DEFAULT_ENGINES={"google","duckduckgo"}` intersecting `_BROWSER_ENGINES` made
`search_web_workflow` launch a REAL Chrome via `get_tab()` on every one of these three tests, torn
down again in the same call's own `finally` before anyone could observe it. Patching
`_prewarm_browser` itself (the one function whose entire purpose is starting the browser) rather
than `_BROWSER_ENGINES` keeps the fix correct even if the gate condition around it moves later —
see `process-docs/browser_posture/` for the investigation and why `_BROWSER_ENGINES` was
deliberately NOT the patch target.
**Gotchas:** the subprocess test resolves repo root as `Path(__file__).parent.parent.parent`
(three levels — `dev/tests/<file>` → `dev/tests` → `dev` → repo root); this depth was silently
wrong (`.parent.parent`) for one relocation cycle when the file lived at `tests/` before the
milestone-2 move to `dev/tests/` and must be re-checked on any future relocation. As of the
partial-diagnosis-on-timeout milestone, `_make_mock_engine_with_reason` gained a `partial_facts`
parameter — if given, the mock writes those facts into the caller-supplied `partial` dict before
its own `asyncio.sleep(delay)`, simulating a poll-loop checkpoint reached before a cancellation.
`test_engine_with_timing_timeout_preserves_facts_written_before_cancellation` uses it to prove
`_engine_with_timing`'s exception branch merges whatever the engine wrote into `partial` with
`diagnosis_partial: True`; the pre-existing `test_engine_with_timing_timeout` (unchanged mock, no
`partial_facts`) proves the sibling case — nothing captured still means `diagnosis is None`, not an
invented fact.

### test_dedup_exclude.py (155 LOC)
**Purpose:** `src/news/engine/dedup.py:filter_new_entries` — `exclude_urls` param precedence over
raw-file-exists skip, mixed-entry counts, `None`/empty-set backward compat. As of 2026-09-09, also
`pub_date_str` (the single surviving definition, consolidated from a diverging duplicate in
`clean_pass.py` — see `src/news/engine/DOCS.md`'s Gotchas): returns `"unknown"` for a date-less
entry, and `filter_new_entries(mode="pubdate")` on such an entry correctly matches a pre-existing
`{source}__unknown__{hash}.md` as already present — the exact lookup the diverging `""` fallback
used to miss.

### test_theblock_clean_pass.py (138 LOC)
**Purpose:** `src/news/clean_pass.py:_run_clean_pass` — good-article clean-file write, bodyless
URL recording/union-merge, raw-file read-only invariant, stats.

### test_theblock_discover.py (169 LOC)
**Purpose:** `src/news/platforms/theblock/discover.py` — `_subs_in_range`, `_sub_by_index`,
`discover()`'s `sub:A-B` dispatch error paths (A>B, non-int, no match).

### test_coindesk_timeline.py (20 LOC)
**Purpose:** `src/news/platforms/coindesk/timeline.py::parse_articles` — first test coverage for
this module. As of 2026-09-09: a non-JSON body raises `json.JSONDecodeError` (the removed
parse-failure→`[]` handler's replacement — see `src/news/platforms/coindesk/DOCS.md`'s Gotchas); a
valid JSON payload carrying no article list (the real API-bottom shape) still returns `[]`, now the
only outcome that means it.

### _proxy_pool_fakes.py (23 LOC)
**Purpose:** Shared `_attempt`/`_refresh` event builders and `_write_and_read_md` used by
`test_proxy_pool.py` and `test_proxy_pool_sources.py` — not collected by pytest, cannot import
`src/` itself, so `_write_and_read_md` takes the janitor module's `_compute_stats`/`_write_md`
functions as parameters instead of importing them directly.
**Called by:** `test_proxy_pool.py`, `test_proxy_pool_sources.py`.

### test_proxy_pool.py (123 LOC)
**Purpose:** `src/news/engine/proxy_pool/janitor.py` — window stats + job.md rendering
(distinct-URL vs. total-attempt counters, D3).

### test_proxy_pool_retry.py (109 LOC)
**Purpose:** `src/news/engine/proxy_pool/` — `pool_retry.fetch_with_retry` backoff/re-raise (D1),
`pool_loaders.load_backfill_pool` per-source isolation (D1).

### test_proxy_pool_sources.py (157 LOC)
**Purpose:** `src/news/engine/proxy_pool/` — `logger.AcquireLogger`/`_group_pool_sources`, job.md
pool-source breakdown section rendering (D2).

### test_proxy_pool_run_loop.py (170 LOC)
**Purpose:** `src/news/engine/proxy_pool/loop.py::run_loop` refresh-boundary integration (pool
swap + wset state-continuity, confirmed production-correct not a test bug). The two integration
tests share a `_run_loop_with_mocked_time` helper (the triple-patch + `run_loop()` call) and their
own per-test scenario builders (`_swap_preserves_state_scenario`/`_fresh_candidates_scenario`) —
each test's own docstring, `time.monotonic` sequence explanation, and assertions stay in the test
itself; only the mechanical mock setup and pool/URL/`mono_seq` construction were factored out.

### test_proxy_riding_abort.py (43 LOC)
**Purpose:** `src/news/engine/proxy_riding/abort.py` — proves the 2026-09-09 tripwire replacement
for the removed stub-`job.md` fallback: `_abort_stall` with `write_riding_report` monkeypatched to
raise writes NO `job.md`, prints the WARN line naming the exception to stderr, and still calls
`os._exit` with the caller's exit code. First test coverage for `proxy_riding/` under this
directory — the package's other tests live as offline dev scripts under
`dev/news_pipeline/coindesk_proxy_riding/`, not here.

### _camoufox_scrape_fakes.py (174 LOC)
**Purpose:** Shared fakes (`_fake_launch_options`, `_FakePage`/`_FakeBrowser`/`_make_fake_camoufox`,
`_RaisingAsyncCamoufox`/`_HangingAsyncCamoufox`, `_FakeAsyncWebCrawler`/`_UrlsplitAsyncWebCrawler`)
used across all three `test_camoufox_scrape*.py` files — not collected by pytest, no `src/` import
needed (none of these fakes touch `camoufox_scrape.py` directly).
**Called by:** `test_camoufox_scrape.py`, `test_camoufox_scrape_output.py`.

### test_camoufox_scrape.py (274 LOC)
**Purpose:** `src/scraper/camoufox_scrape.py` — `try_scrape_camoufox` acquisition-error states
(budget/browser_missing/exception), the "Invalid IPv6 URL" urlsplit regression. As of 2026-09-09,
`test_try_scrape_camoufox_conversion_failure_yields_empty_content` replaces the three tests that
used to cover the removed raw-HTML-as-content fallback (two "preserves HTML on conversion failure"
tests plus the sidecar `mode="raw_html"` test) and `test_format_camoufox_output_raw_html_shape_
states_it_plainly` (the `_format_camoufox_output` "Content format: RAW HTML" block it exercised is
also gone) — the new test proves the tripwire instead: `_html_to_markdown` monkeypatched to return
`("", "simulated conversion failure")` yields `content == ""`, `markdown_conversion_error` set,
`acquisition_error is None`, and `content_is_raw_html` absent from `meta` entirely. REMOVED
2026-08-27: the 8 tests covering `_get_frontmost_app`/`_activate_app`/`_is_key_window_owner`/
`_key_window_steal_watchdog` and its `_acquire_camoufox` wiring, together with the watchdog module
code itself — see `process-docs/camoufox_lane/`. `_make_document_status_listener` (registered on
`_FakePage` via `.on("response", ...)` BEFORE `goto()`, mirroring the real registration order): the
last main-frame document response overriding the goto Response's own (possibly stale) status, the
single-entry ordinary-page case, the empty-chain fallback, and non-document/non-main-frame responses
excluded — `_FakePage.goto()` fires its configured `document_statuses` sequence before returning
(render wait is zeroed in these tests, so there is no real "later" window to fire into; firing the
whole chain inside `goto()` is an equivalent, deterministic stand-in).

### test_camoufox_scrape_output.py (208 LOC)
**Purpose:** `src/scraper/camoufox_scrape.py` — calibration surface (`_build_camoufox_kwargs`/
`_extract_camoufox_config_stamp`/config_hash stability), `scrape_url_camoufox_workflow` logging,
`_format_camoufox_output`. As of the M2 acquisition-facts-removal milestone (2026-09-15),
`_format_camoufox_output`'s tests were cut down to the two-arg `(url, content)` signature and now
only check the printed shape (heading, content, no `## Acquisition facts` preamble) — the three
tests that used to assert on removed block lines (landed URL, document status chain) were deleted,
and a new test proves `scrape_url_camoufox_workflow`'s log record still carries its full
pre-milestone field set.

### test_camoufox_scrape_focus.py (100 LOC)
**Purpose:** `src/scraper/camoufox_scrape.py` — no-focus-steal launch (`_find_app_bundle`/
`_ensure_no_focus_steal`, real plistlib round-trip against a real `tmp_path` `.app`-shaped bundle;
`ignore_default_args` kwarg presence, the playwright#41306 `-foreground` opt-out).

### _chromium_scrape_fakes.py (49 LOC)
**Purpose:** Shared `_patch_cdp_launch_mechanics`, `_FakeMarkdown`/`_FakeResult`, `_meta` used
across the `test_chromium_scrape*.py` files (not `test_chromium_process.py`, which mocks
`chromium_process` directly and needs none of these) — not collected by pytest, cannot import
`src/` itself, so `_patch_cdp_launch_mechanics` takes the already-imported `chromium_scrape`/
`chromium_process` modules as parameters instead of importing them directly.
**Called by:** `test_chromium_scrape.py`, `test_chromium_scrape_facts.py`,
`test_chromium_scrape_output.py`, `test_chromium_scrape_document_status.py`.

### test_chromium_scrape.py (316 LOC)
**Purpose:** `src/scraper/chromium_scrape.py` — `is_browser_launch_error`, `try_scrape`'s core
acquisition-error classification (browser_missing/exception), the removed HTTP-status gate
(HTTP-error-with-real-content preservation), `content_type` extraction, the removed
`crawl4ai_fallback_fetch_used` field, `og_published_time`.

### test_chromium_scrape_facts.py (329 LOC)
**Purpose:** `src/scraper/chromium_scrape.py` — the removed fit->raw fallback, `landed_url`
capture + logging, the removed computed-`outcome` field / `acquisition_error`-as-its-own-fact
logging, the outer `TOTAL_SCRAPE_BUDGET_S` guard, cdp-headed self-launch teardown-on-every-exit-path,
net 2 (`_acquire_cdp_headed` spawns `death_pipe.spawn_watchdog` with this call's real pids +
throwaway dir once the cdp port resolves) — all exercised via `chromium_scrape`'s own imported
names (`_acquire_cdp_headed`/`try_scrape` resolve `_kill_by_profile`/`_pids_on_profile`/
`_reap_orphaned_scrapes` through `chromium_scrape`'s own globals, not `chromium_process`'s).

### test_chromium_scrape_output.py (162 LOC)
**Purpose:** `src/scraper/chromium_scrape.py` — `extract_config_stamp` (`launch_mode` fixed
constant, the removed `max_content_length`/`min_content_threshold`/`excluded_selector_hash`
fields, the removed `htmldate` guessed-date mechanism), `_format_scrape_output` (facts always
precede content, zero content explicit, no acquisition-facts preamble as of the M2 milestone),
`scrape_url_chromium_workflow`'s full logged-field-set guard, `LAUNCH_MODE` truthfulness on the
cdp path.

### test_chromium_scrape_document_status.py (223 LOC)
**Purpose:** `src/scraper/chromium_scrape.py` — `_make_document_status_listener`'s `before_goto`
hook, exercised through the real `_acquire_cdp_headed`/`_acquire_scrape` machinery (a fake
`AsyncWebCrawler.arun` invokes `crawler_strategy.execute_hook("before_goto", ...)` itself, the same
call crawl4ai's own `async_crawler_strategy.py` makes, against a fake page/request/response trio):
the last main-frame document response status overriding crawl4ai's own (earliest-hop) `status_code`,
the single-entry ordinary-page case, the empty-chain fallback to crawl4ai's value, and
non-document/non-main-frame responses being filtered out of the chain; `_reap_orphaned_scrapes`
called at the start of `try_scrape`.

### test_chromium_process.py (196 LOC)
**Purpose:** Direct unit coverage of `src/scraper/chromium_process.py` itself (monkeypatched on
`chromium_process`, not `chromium_scrape` — that module's own functions resolve `subprocess`/
`psutil`/`tempfile`/internal helper names via ITS OWN globals, not the caller's): self-launch
mechanics (`_wait_for_devtools_port`/`_find_app_bundle`, real filesystem), live `crawl4ai.browser_
manager.ManagedBrowser.build_browser_flags` parity guard + `_build_self_launch_flags` GPU/window-
size, `_pids_on_profile`/`_kill_by_profile`, and net 3 (`chromium_process._reap_orphaned_scrapes`
kills only `scrape-url-cdp-*` pids older than `chromium_process.TOTAL_SCRAPE_BUDGET_S`, never a
young/legitimate parallel scrape, and sweeps only dirs with zero live processes).

As of the M2 acquisition-facts-removal milestone (2026-09-15), `_format_scrape_output`'s tests were
cut down to the two-arg `(url, content)` signature: 11 tests asserting on removed block lines
(landed URL, og:published_time, document status chain, the crawl4ai-diagnosis wording, the two
`_acquisition_error_message`/`_ACQUISITION_ERROR_MESSAGES` tests — both symbols removed with the
block) were deleted; 2 tests covering still-real behavior (content appears verbatim, zero content
renders `(no content returned)`) were rewritten to the new signature; 2 new tests were added proving
the printed text carries no `## Acquisition facts` preamble and that
`scrape_url_chromium_workflow`'s log record still carries its full pre-milestone field set. As of
the M0 dead-field milestone (2026-09-15), `_FakeResult` gained a `response_headers` parameter
(replacing the unused `headers` attribute the old, buggy production code read) — 2 new tests prove
`content_type` extraction against a real `response_headers` dict and its graceful-None fallback when
absent, 1 new test proves `crawl4ai_fallback_fetch_used` no longer appears in the logged record, and
the full-field-set test's own expected-keys set was updated to match.

### _seed_feeders_fakes.py (42 LOC)
**Purpose:** Shared `_FakeResponse`/`_FakeAsyncClient` fake httpx client and `_xml`/
`_next_data_html`/`_rsc_html` builders, used by `test_seed_feeders_robots.py`,
`test_seed_feeders_sitemap.py`, and `test_seed_feeders_navtree.py` — not collected by pytest, no
`src/` import needed.
**Called by:** `test_seed_feeders_robots.py`, `test_seed_feeders_sitemap.py`,
`test_seed_feeders_navtree.py`.

### test_seed_feeders_scope.py (103 LOC)
**Purpose:** `src/crawler/seed_feeders_scope.py` — the `normalize_url`/`scope_and_dedup` merge-vs-
keep-distinct boundary (default port, empty path, fragment, `www.`/apex, legacy `;params`
segment all merged; query string, `http` vs `https`, non-root trailing slash, `;params` all kept
distinct).

### test_seed_feeders_robots.py (104 LOC)
**Purpose:** `src/crawler/seed_feeders_robots.py` — `parse_robots_directives` (Allow/Disallow +
`Sitemap:` extraction, multi-block collection, comment stripping), `fetch_robots_txt` (DI'd fake
client), and `robots_feeder_workflow` end-to-end (monkeypatched `seed_feeders.httpx.AsyncClient`).

### test_seed_feeders_sitemap.py (191 LOC)
**Purpose:** `src/crawler/seed_feeders_sitemap.py` — `parse_sitemap_xml` (`urlset`/`sitemapindex`/
unknown), a 2-level-nested `<sitemapindex>` resolved via `resolve_sitemap_urls` plus its 404-sub
and cycle-guard behavior, and `sitemap_feeder_workflow` end-to-end (robots-declared-sitemap
preference over the conventional fallback, the docs.github.com-shaped all-404 clean-empty case,
foreign-host URLs dropped).

### test_seed_feeders_navtree.py (274 LOC)
**Purpose:** `src/crawler/seed_feeders_navtree.py` — `extract_payloads` detection of both the
`__NEXT_DATA__` blob and the RSC `self.__next_f.push` stream shapes (plus the neither-shape empty
case) and `find_navigation_tree`'s tier 1/tier 2 split — a synthetic React-element-shaped
`{"href":..., "children": [[...]]}` fixture proves the tree-finder does NOT mistake rendered DOM
for tree data (the false-positive shape found live on `ui.shadcn.com` before the shape check was
tightened), a fragment/`_next/`-internal filter test for the tier 2 fallback; `_build_version_urls`/
`canonicalize_version_url` (including the seed-is-a-non-default-version case that exposed a real
`lang_prefix` derivation bug, and the missing-field/content-path-mismatch graceful-empty cases);
`resolve_navigation_tree` end-to-end with a synthetic 2-version fixture proving the union recovers
a page that exists in only one version while deduping the pages both versions share (asserting the
returned `version_keys` too — the list `discovery.py`'s traversal now reads via
`FeederResult.version_keys`); and `navtree_feeder_workflow` end-to-end (an RSC-tree-shape page
proving the navtree detector does not fall through on the App Router shape, an RSC-DOM-only page
proving the tier 2 fallback engages, an invalid `seed_url` producing `ok=False` not a silent empty
result, `FeederResult.source` asserted on every happy path).

### test_seed_feeders.py (90 LOC)
**Purpose:** Fixture-backed section only (real network, only ever against
`dev/url_discovery/_fixture_site.py`, one module-scoped server for the whole file): each of the
three feeders checked against the exact fixture feature built for it — robots against the
Allow/Disallow paths, sitemap against the 2-level nested `<sitemapindex>`, navtree against the
3-version union (recovering the 2 oldest-version-only pages) and, separately, against the isolated
`/rsc-demo` island for the App Router RSC-stream shape — replacing the one-off
docs.github.com/theblock.co/ui.shadcn.com/nextjs.org runs process-docs/url_discovery/
2026-08-28_robots_sitemap_seed_feeders.md and 2026-08-28_navtree_seed_feeder.md recorded.

### test_discovery.py (138 LOC)
**Purpose:** `src/crawler/discovery.py` — the feeder-merge discovery entry point (a browser-driven
link-graph traversal used to run after the feeders; it was removed as a duplicate fetch of every
page in the run — see `src/crawler/DOCS.md`'s Gotchas — and every test that exercised it was
deleted with it, not weakened). Pure-logic, no network: `_assemble_seeds` (literal `seed_url`
always included, first-write-wins merge priority across the three feeders, a failed feeder's error
landing in `failed_feeders` rather than being silently treated as an empty result, `seed_url`
normalization dedup against an equivalent feeder-found URL), and `discover_urls_workflow`'s one
network-free path (an invalid `seed_url` produces `ok=False`, not an empty result). Fixture-backed
(real network, only ever against `dev/url_discovery/_fixture_site.py`, one module-scoped server +
ONE shared `discover_urls_workflow` run for the whole file, `discovery_result`, read by several
small assertion-only tests rather than re-run per assertion): total URL count and per-source
breakdown checked against the fixture's own `ground_truth()`; every `DiscoveredURL` confirmed to
carry only `url`/`source` (no `fetched`/`canonical_url` — there is nothing left for either to
distinguish once no page is fetched by discovery itself).
**Calls out:** `dev.url_discovery._fixture_site` (fixture-backed section only) — otherwise none
beyond `src.crawler.discovery`/`src.crawler.seed_feeders_scope`, no network in the pure-logic
section.

### _pipe_scraper_fakes.py (51 LOC)
**Purpose:** Shared `_now_ts`, `_FakeMarkdown`/`_FakeResult`/`_FakeCrawler`, and `_camoufox_meta`
used across the `test_pipe_scraper*.py` files — not collected by pytest, no `src/` import needed.
**Called by:** `test_pipe_scraper.py`, `test_pipe_scraper_camoufox_engine.py`,
`test_pipe_scraper_onward_links.py`.

### test_pipe_scraper_config.py (124 LOC)
**Purpose:** `src/crawler/pipe_scraper_config.py` — config stamp extraction off real
BrowserConfig/CrawlerRunConfig, live crawl4ai `AsyncPlaywrightCrawlerStrategy`/`StealthAdapter`
wiring guard, `_build_configs`'s fixed anti-bot posture, and `_build_configs(headed=...)`'s
config-level effect (`headless` flips, the fixed anti-bot posture and the config stamp's own
`headless` key do not diverge) — as of the M3 milestone (2026-09-15); no test exercises the
`-g`/`--headed` argparse flag itself, matching this file's own established boundary
(`--engine`/`--block-images` have no argparse-level test either).

### test_pipe_scraper.py (283 LOC)
**Purpose:** `src/crawler/pipe_scraper*.py` — `pipe_scrape_logger.log_pipe_scrape` fail-soft JSONL,
`_scrape_all` (run_id sharing, request-start `ts` timing regression, config hash), `_scrape_all`'s
own `headed` parameter reaching `_build_configs` unchanged (M3 milestone). As of 2026-09-09, both
curl_cffi fallback paths (a and b: crawl4ai's own `fallback_fetch_function` wiring and
`_own_fallback_rescue`) were REMOVED — a user decision in the Phase 4 control-flow review that a
branch producing output by a second method is a fallback. Every test whose subject was
`_fallback_fetch`, `_own_fallback_rescue`, `fallback_armed`, or `is_blocked`'s branch-selection
framing for that design was deleted with it (14 tests total); `test_scrape_one_exception_becomes_
tripwire_record` replaces them, proving the new tripwire instead: a hard crawler exception now
logs a `status=None`/`bytes=0` record with no `pipe_fallback_*` keys, writes no file for that URL,
and the run continues to the next one — reusing the shared `_FakeCrawler` (already raises on any
URL containing `"fail"`), no new fixture needed. `landed_url` correctness across the remaining
routes (plain success with/without a redirect). No test asserts on an `outcome` field anywhere in
this file anymore — it was removed from `pipe_scraper*.py` along with the field itself (see
`src/crawler/DOCS.md`'s Gotchas); every assertion that used to read `outcome` now reads the
underlying fact (`http_status`, `bytes`) directly.

### test_pipe_scraper_camoufox_engine.py (233 LOC)
**Purpose:** `src/crawler/pipe_scraper*.py` — camoufox-engine dispatch switch
(default/concurrency/block_images/record shape). As of 2026-09-03, a resolved-challenge
`try_scrape_camoufox` meta shape (`status_code=200`, `document_status_chain=[403,302,200]`) is
proven end to end through `_scrape_one_camoufox` as a plain `http_status=200` in the JSONL record,
with the chain field alongside it — no code change needed in the camoufox engine itself, only this
proof (see `src/scraper/DOCS.md`'s Gotchas for the acquisition-primitive fix this proves). The
camoufox engine's `acquisition_error` fact (`try_scrape_camoufox`'s own
`"budget_exhausted"`/`"browser_missing"`/`"exception"`) is asserted directly in the JSONL record
(`test_scrape_all_camoufox_acquisition_error_is_logged_as_its_own_fact`), replacing the removed
`outcome="error"` mapping test.

### test_pipe_scraper_onward_links.py (236 LOC)
**Purpose:** `src/crawler/pipe_scraper_acquisition.py`/`pipe_scraper_report.py` — onward-link
collection (the milestone that moved discovery.py's removed browser traversal's job onto pages
already being fetched — see `src/crawler/DOCS.md`'s Gotchas): `_onward_link_identity`
(query/fragment stripped, scheme/host lowercased, including the real motivating case — two
`/login?returnTo=...` variants collapsing to one key); `_extract_onward_links` (unions crawl4ai's
own internal/external buckets, `host_key`-restricts to the page's own host with `www.`/apex
collapsed but sibling/child subdomains rejected, `_NON_PAGE_EXTENSIONS` drops asset links, dedups
within the page, degrades to `[]` when the result has no `.links` attribute at all);
`_collect_onward_links` (excludes the run's own input URLs after identical normalization, dedups
run-wide preserving first-seen order, ignores a result with no `'links'` key at all, returns `None`
— not `[]` — for the camoufox engine regardless of what any individual result happens to carry);
`_write_onward_links_file` (one URL per line, an empty file for an empty list, no file at all for
`None`, real `/tmp` writes cleaned up per test via a fixture); `_print_summary`'s new onward-link
wording (a plain count, or the explicit "not collected (camoufox engine)" string — never a bare
`0` a reader could mistake for "chromium looked and found nothing"); and the wiring itself —
`_scrape_one` populates `'links'` from a fake result carrying a real `.links` attribute,
`_scrape_one_camoufox`'s own return dict is asserted to never carry a `'links'` key at all, the
engine-scope distinction the milestone requires.

## Gotchas
Any file under this directory that resolves its own path to locate the repo root (subprocess
`cwd`, `sys.path` injection) breaks silently on relocation — the depth is baked into `Path(
__file__).parent...` chains, not derived from a fixture. Grep for `Path(__file__).parent` before
moving this directory again.

`test_brave_engine.py`/`test_yandex_engine.py` are a second deliberate exception to `conftest.py`'s
autouse `_no_real_browser_launch` trap (alongside `test_discovery.py`/`test_seed_feeders.py`,
described in Role above), and for the same reason as that one — production logic exercised for
real, network kept to loopback only. `conftest.py`'s trap patches `src.search.browser.Chrome`
specifically; these two files never import that module at all — they monkeypatch `brave.py`'s/
`yandex.py`'s own already-imported `new_tab`/`kill_tab` names directly to a small headless pydoll
`Chrome` instance (`options.headless = True; await browser.start()`), independent of
`src/search/browser.py`'s production single-shared-browser lifecycle (cross-process lock, focus
watchdog, macOS Spaces-drag avoidance — none of it applies to a fixture-only test). See
`process-docs/marker_reflection/` for why a real browser is unavoidable here: the bug and its fix
both live inside the engines' own injected JS reading real DOM state, which a pure-Python fixture
cannot exercise.
