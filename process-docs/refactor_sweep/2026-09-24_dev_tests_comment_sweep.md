# dev/tests/ comment and docstring sweep, DOCS.md reduction, brave split (2026-09-24)

Area: refactor_sweep (Phase 2 comment sweep, plus the Phase 1 size work for `dev/tests/`).

## Outcome

- Before: 52 files with docstrings or comments, 193 docstrings, 651 non-marker comment lines. After: 0 (AST + tokenize scan over `dev/tests/*.py` prints nothing; shebangs and the three section markers exempt).
- Collected tests: 488 before, 488 after. Full suite: 488 passed before, 488 passed after (35.9 s run).
- `__doc__` / argparse / `sys.argv` / `inspect.getdoc` in `dev/tests/`: no hits, so no string constants had to replace a docstring and no `--help` diff exists. Two comments mentioned a docstring in prose only (`test_pipe_scraper_onward_links.py`, `test_seed_feeders_scope.py`); both deleted with their block.
- Functions of 50 LOC or more: none, before or after.
- Sizes: after the sweep `test_query_logger.py` is 330 LOC (was 404), so its split was skipped as instructed. `test_brave_engine.py` was still 413 LOC, so the three pure `_build_results` tests moved verbatim into the new `test_brave_build_results.py` (30 LOC); `test_brave_engine.py` is now 384 LOC. Node count unchanged.
- `dev/tests/DOCS.md`: 601 lines down to 255, in the required format, LOC headings generated from `wc -l`. The old text is preserved verbatim in the appendix at the end of this file.

## Method

Every docstring is one item. Consecutive whole-line comments (with `# -----` separator lines dropped) are one block item. A trailing comment on a code line is its own item and is always deleted.

- (a) already recorded: any 7-word run of the item text also occurs in the old `dev/tests/DOCS.md` or in any pre-existing `process-docs/**/*.md`: deleted.
- (b) unrecorded substance: item of 120 characters or more that carries a date, a `process-docs` pointer, a regression/observation/removal statement or a number with unit, or any non-trailing item of 200 characters or more, plus 9 hand-promoted blocks: moved verbatim into the section below (grouped by module, anchored to the neighbouring test).
- (c) self-evident: everything else (section labels, restatements of the test name, inline notes on an assertion): deleted.

Safety check per file: the AST of the rewritten file equals the AST of the original with docstring statements removed, so no code changed. The heuristic in (b) is deliberately inclusive; over-salvage is cheaper than lost substance. Item counts are blocks, so they are lower than the raw line counts.

## Known flaky tests (recorded, not fixed)

`test_brave_engine.py::test_unrelated_button_before_containers_never_leaks_into_success_diagnosis` and `test_brave_engine.py::test_light_dom_challenge_button_is_solved_and_returns_real_results` failed intermittently in full-suite runs on 2026-09-24 (two different tests over different runs) and pass when run alone. Both run a real headless Chrome against loopback fixtures, which is where any load sensitivity would live. Not investigated. Both stayed in `test_brave_engine.py`; the split moved only the pure `_build_results` tests, so a flaky-test analysis by module still has the same population. The full suite passed 488/488 on the two runs made in this session.

## Triage counts per module

| module | docstrings | comment lines | items | (a) deleted | (b) salvaged | (c) deleted |
|---|---|---|---|---|---|---|
| _camoufox_scrape_fakes.py | 3 | 3 | 4 | 2 | 0 | 2 |
| _chromium_scrape_fakes.py | 0 | 5 | 1 | 0 | 1 | 0 |
| _pipe_scraper_fakes.py | 0 | 2 | 1 | 0 | 1 | 0 |
| _proxy_pool_fakes.py | 1 | 3 | 2 | 0 | 0 | 2 |
| _seed_feeders_fakes.py | 1 | 4 | 3 | 0 | 0 | 3 |
| conftest.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_bing_engine.py | 2 | 11 | 6 | 2 | 1 | 3 |
| test_brave_engine.py | 1 | 3 | 2 | 1 | 0 | 1 |
| test_browser.py | 1 | 7 | 7 | 1 | 0 | 6 |
| test_browser_get_tab.py | 0 | 4 | 2 | 0 | 1 | 1 |
| test_browser_lock.py | 1 | 2 | 2 | 1 | 1 | 0 |
| test_cache.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_camoufox_scrape.py | 13 | 31 | 20 | 7 | 7 | 6 |
| test_camoufox_scrape_focus.py | 4 | 20 | 8 | 1 | 1 | 6 |
| test_camoufox_scrape_output.py | 9 | 16 | 13 | 1 | 9 | 3 |
| test_chromium_process.py | 2 | 17 | 8 | 1 | 3 | 4 |
| test_chromium_scrape.py | 11 | 35 | 19 | 3 | 9 | 7 |
| test_chromium_scrape_document_status.py | 7 | 10 | 9 | 5 | 1 | 3 |
| test_chromium_scrape_facts.py | 6 | 29 | 14 | 2 | 6 | 6 |
| test_chromium_scrape_output.py | 8 | 18 | 13 | 2 | 7 | 4 |
| test_coindesk_timeline.py | 2 | 0 | 2 | 2 | 0 | 0 |
| test_death_pipe.py | 1 | 9 | 6 | 2 | 1 | 3 |
| test_dedup_exclude.py | 10 | 21 | 24 | 0 | 2 | 22 |
| test_discovery.py | 1 | 18 | 10 | 2 | 0 | 8 |
| test_document_status.py | 1 | 6 | 3 | 0 | 1 | 2 |
| test_google_engine.py | 1 | 13 | 4 | 2 | 0 | 2 |
| test_log_janitor.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_merge.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_mojeek_engine.py | 6 | 21 | 13 | 4 | 2 | 7 |
| test_openalex_engine.py | 7 | 16 | 13 | 1 | 4 | 8 |
| test_pipe_scraper.py | 13 | 19 | 22 | 1 | 7 | 14 |
| test_pipe_scraper_camoufox_engine.py | 9 | 6 | 10 | 1 | 8 | 1 |
| test_pipe_scraper_config.py | 7 | 12 | 12 | 1 | 4 | 7 |
| test_pipe_scraper_onward_links.py | 1 | 34 | 15 | 1 | 4 | 10 |
| test_pool_cap.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_proxy_pool.py | 7 | 20 | 22 | 0 | 1 | 21 |
| test_proxy_pool_retry.py | 5 | 11 | 12 | 0 | 0 | 12 |
| test_proxy_pool_run_loop.py | 2 | 38 | 18 | 2 | 2 | 14 |
| test_proxy_pool_sources.py | 9 | 12 | 15 | 0 | 0 | 15 |
| test_proxy_riding_abort.py | 1 | 0 | 1 | 1 | 0 | 0 |
| test_query_logger.py | 14 | 22 | 22 | 4 | 7 | 11 |
| test_scrape_logger.py | 2 | 0 | 2 | 2 | 0 | 0 |
| test_search_web_degraded_notice.py | 3 | 16 | 8 | 3 | 0 | 5 |
| test_seed_feeders.py | 1 | 21 | 6 | 6 | 0 | 0 |
| test_seed_feeders_navtree.py | 0 | 37 | 19 | 1 | 5 | 13 |
| test_seed_feeders_robots.py | 0 | 11 | 4 | 1 | 0 | 3 |
| test_seed_feeders_scope.py | 0 | 8 | 3 | 0 | 1 | 2 |
| test_seed_feeders_sitemap.py | 0 | 14 | 8 | 0 | 1 | 7 |
| test_startpage_engine.py | 1 | 3 | 2 | 1 | 0 | 1 |
| test_theblock_clean_pass.py | 3 | 12 | 11 | 0 | 1 | 10 |
| test_theblock_discover.py | 10 | 22 | 21 | 0 | 1 | 20 |
| test_yandex_engine.py | 1 | 9 | 4 | 1 | 0 | 3 |
| total | 193 | 651 | 451 | 73 | 100 | 278 |

## Salvaged substance (b), verbatim, by module

### _chromium_scrape_fakes.py

Anchor: comment block at `_patch_cdp_launch_mechanics` (next def).

> Shared test helper: bypass the real self-launch/port-wait/teardown mechanics so the default cdp
> path can be exercised (AsyncWebCrawler mocked separately, per test) without spawning a real
> browser — mirrors how AsyncWebCrawler itself is already mocked throughout this file.

### _pipe_scraper_fakes.py

Anchor: comment block at `_now_ts` (next def).

> log_janitor prunes any record whose "ts" falls outside the 90-day retention window (or is
> unparseable) on every write — records here must carry a real, current, ISO-parseable ts.

### test_bing_engine.py

Anchor: docstring at `test_parse_results_raises_on_invalid_json` (last def).

> 2026-09-09: the except (json.JSONDecodeError, TypeError): return [] handler was removed —
>     no supporting observation (handler dates from the first engine commit, 0 ERROR_PARSE in 4566
>     logged engine records, the value is always our own stringified JSON). A malformed value now
>     raises out of _parse_results, propagating into search_web's own _classify_engine_exception
>     (ERROR_PARSE) instead of masquerading as an empty page.

### test_browser_get_tab.py

Anchor: comment block at `test_get_tab_orders_lock_reap_launch_anchor_record` (next def).

> get_tab: critical-section ordering — lock acquired, then reap, then self-launch (no .start(),
> no initial tab — see src/search/DOCS.md for why), then own-pids recorded once the devtools port
> confirms Chrome is actually up

### test_browser_lock.py

Anchor: comment block at `test_stale_takeover_not_triggered_under_budget` (next def).

> Real held flock, simulating a stuck (never-releasing) holder — a stale sidecar alone proves
> nothing without contention, since an uncontended acquire() never reaches the age check.

### test_camoufox_scrape.py

Anchor: docstring at `test_try_scrape_camoufox_normal_fetch` (next def).

> Tests for camoufox_scrape's calibrated core acquisition module — the second, parallel
> acquisition lane (Camoufox/Playwright-Firefox) beside crawl4ai's chromium path. No CLI/logging
> wiring exists yet (later milestones); this only tests the module boundary itself.
> 
> Runs without a real Camoufox browser: camoufox_scrape.AsyncCamoufox and camoufox_scrape.launch_options
> are patched with fakes, isolating the module from the real binary/network. camoufox_scrape.AsyncWebCrawler
> (the separate throwaway crawler used for raw: markdown conversion) is patched the same way
> test_pipe_scraper.py fakes crawl4ai's own AsyncWebCrawler.

Anchor: comment block at `test_try_scrape_camoufox_captures_landed_url_raw_on_redirect` (next def).

> asyncio.sleep(CAMOUFOX_RENDER_WAIT_S) is a real stdlib sleep, not interceptable by the fakes
> above — zeroed so this test doesn't actually wait 5s.

Anchor: docstring at `test_try_scrape_camoufox_detects_binary_missing` (next def).

> A hang inside the acquisition (Camoufox never returns) is cut off at
>     TOTAL_CAMOUFOX_BUDGET_S, yielding acquisition_error=budget_exhausted — not a hang.

Anchor: docstring at `_raise` (next def).

> CamoufoxNotInstalled (raised from launch_options -> launch_path when the browser binary
>     hasn't been fetched) maps to acquisition_error=browser_missing, with the fix command named in
>     the logged message.

Anchor: docstring at `test_html_to_markdown_survives_bracket_before_first_slash` (next def).

> A non-launch-missing exception (e.g. a real browser-launch crash) degrades to
>     acquisition_error=exception — never propagates to the caller.

Anchor: docstring at `_fake_html_to_markdown` (next def).

> On a markdown-conversion failure, content is now "" (never the raw captured HTML) and
>     markdown_conversion_error carries the fact; acquisition_error stays None; content_is_raw_html
>     no longer exists in meta at all.

Anchor: docstring at `_raise` (next def).

> A path that never obtains a page/response (browser_missing) carries an empty chain, same
>     treatment as every other acquisition-error field.

### test_camoufox_scrape_focus.py

Anchor: comment block at `test_find_app_bundle_locates_dotapp_ancestor` (next def).

> No-focus-steal launch (milestone 3, Half A) — _find_app_bundle / _ensure_no_focus_steal.
> Uses a real tmp_path .app-shaped bundle + real plistlib round-trip (no fakes needed: plistlib is
> pure Python, no camoufox/OS dependency), pinning the exact mechanism verified empirically this
> session (real osascript/System Events focus-poll: LSUIElement=true stopped Camoufox from ever
> becoming the frontmost application across a real try_scrape_camoufox call).

### test_camoufox_scrape_output.py

Anchor: docstring at `test_extract_camoufox_config_stamp_reads_real_executable_path_not_redeclared` (next def).

> headless=False (visible window), os="macos" (matches real host), timeout explicit, locale
>     resolved (as of 2026-08-27, so this lane requests the same language chromium gets for free from
>     the OS) — and the deliberately-left-unset knobs (block_webgl, geoip, humanize, enable_cache,
>     proxy) are truly ABSENT from the dict, not just False, so camoufox's own library defaults apply
>     untouched.

Anchor: docstring at `test_extract_camoufox_config_stamp_excludes_randomized_fingerprint_data` (next def).

> The stamp's executable_path comes off the REAL resolved launch_options() output, not a
>     re-declared literal — changing what launch_options() resolves changes the stamp.

Anchor: docstring at `test_config_hash_stable_for_identical_kwargs` (next def).

> The stamp must NOT include per-launch randomized fingerprint data (fonts/seeds/env) even if
>     present in the resolved dict — hashing that would make config_hash unique on every call.

Anchor: docstring at `_meta` (next def).

> Two calls with the same calibration surface produce the same config_hash — a real 'same
>     config' grouping key, not per-call noise.

Anchor: comment block at `_meta` (next def).

> scrape_url_camoufox_workflow: milestone 2 — the ad-hoc CLI wiring. Logs into the SAME
> scrape_log.jsonl / log_scrape / write_sidecar as chromium_scrape.py's chromium lane, discriminated by
> the "engine" field. try_scrape_camoufox is faked at the module boundary; log_scrape/write_sidecar
> are faked to capture the record instead of touching the filesystem.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> The logged record carries engine="camoufox" — the first-class discriminator this milestone
>     adds, distinguishing it from the chromium lane's engine="chromium" records in the same file.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> No computed outcome anymore — acquisition_error (try_scrape_camoufox's own fact field:
>     "budget_exhausted"/"browser_missing"/"exception", or None) is logged straight through as its
>     own field, the same precedent pipe_scraper_records.py's _log_pipe_camoufox_record set.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> config_hash is read straight off meta (computed once, inside try_scrape_camoufox) — the
>     workflow must not re-hash it itself.

Anchor: comment block at `test_format_camoufox_output_carries_no_acquisition_facts_preamble` (next def).

> M2 milestone (2026-09-15): the printed acquisition-facts block is removed entirely — the facts
> still exist, they just stop being printed. Output shrinks; the log record does not.

### test_chromium_process.py

Anchor: comment block at `test_build_browser_flags_symbol_resolves_and_is_callable` (next def).

> Flag-parity mechanism — build_browser_flags() is called LIVE (never pinned), so its own
> existence/signature is a hard, loud-failure guard: if crawl4ai ever renames/removes/reshapes it,
> this test goes red instead of the self-launch silently losing its flag surface.

Anchor: docstring at `test_build_self_launch_flags_keeps_gpu_on_under_stealth` (next def).

> Guard against a silent posture change on a crawl4ai upgrade: if ManagedBrowser.
>     build_browser_flags disappears, gets renamed, or its signature changes incompatibly, THIS
>     test fails loudly — no try/except swallowing the import or the call.

Anchor: comment block at `test_reap_orphaned_scrapes_kills_only_pids_older_than_budget` (next def).

> Net 3 — _reap_orphaned_scrapes: kill only processes older than TOTAL_SCRAPE_BUDGET_S (parallel
> scrapes under budget are legitimate, never killed), sweep dirs with zero live processes

### test_chromium_scrape.py

Anchor: docstring at `test_is_browser_launch_error_detects_signatures` (next def).

> Tests for chromium_scrape's acquisition-facts contract: browser-launch/timeout classification, the
> outer time-budget guard, the removed status-code/content-verdict gate, the new return shape that
> surfaces facts (HTTP status, byte counts, crawl4ai's own diagnosis) alongside full content instead
> of judging it, and the single cdp-headed-backgrounded acquisition route (self-launch + connect over
> cdp_url) — the WEBSEARCH_HEADLESS escape hatch (old direct headless-shell launch) was removed.
> 
> Runs without a browser: try_scrape's AsyncWebCrawler is patched to raise a synthetic exception,
> simulating a missing patchright/chromium executable, to hang past a (monkeypatched, shortened)
> budget constant, or to return a synthetic result carrying an HTTP error status + real content.
> Tests additionally patch the self-launch/port-wait/teardown mechanics
> (`_patch_cdp_launch_mechanics`) so no real browser is spawned — those functions get their own
> dedicated, unmocked tests further down.

Anchor: comment block at `test_try_scrape_maps_launch_failure_to_browser_missing` (next def).

> try_scrape routes acquisition-level failures to meta["acquisition_error"]
> (renamed from garbage_type — these three states mean "acquisition produced no result at all",
> never a content-judgment verdict; that layer is removed). All exercise the DEFAULT cdp path
> unless noted, via _patch_cdp_launch_mechanics.

Anchor: comment block at `test_try_scrape_returns_content_on_http_403` (next def).

> The removed status-code gate: a real evidence case — an HTTP error status with real content
> must now come back AS content, not be discarded

Anchor: docstring at `_FakeCrawler` (next def).

> trustpilot-shaped case: HTTP 403 with real content must be returned, not discarded — the
>     old status>=400 early return is gone.

Anchor: comment block at `test_try_scrape_extracts_content_type_from_response_headers` (next def).

> content_type — M0 milestone (2026-09-15): read off result.response_headers, not the
> nonexistent result.headers attribute (hasattr(result, "headers") was False on every real
> CrawlResult, so this branch never once executed — a defect, not a structural gap; see
> process-docs/scrape_pipeline/ for the crawl4ai-source verification).

Anchor: docstring at `_FakeCrawler` (next def).

> A real result carrying response_headers (the actual CrawlResult field) yields a real
>     content_type — the fix this milestone makes.

Anchor: comment block at `test_try_scrape_reads_og_published_time_from_result_metadata` (next def).

> og_published_time — read off crawl4ai's own already-parsed result.metadata (an og:-prefixed meta
> tag the page itself declares), never a third-party guess. Absent whenever the page declares
> nothing, exactly like every other fact in this module.

Anchor: docstring at `_FakeCrawler` (next def).

> The page's OWN og:published_time meta tag, verbatim — crawl4ai already parses every
>     og:-prefixed <head> tag into result.metadata (extract_metadata_using_lxml), so this is a real
>     fact carried on the result this module already has in hand, not a new fetch or a guess.

Anchor: docstring at `_FakeCrawler` (next def).

> A page with real OpenGraph metadata but no published_time tag — null, not a guessed
>     fallback (e.g. never derived from a last-modified footer or any other page text).

### test_chromium_scrape_document_status.py

Anchor: docstring at `_FakeCrawler` (next def).

> Builds a fake AsyncWebCrawler class whose arun() invokes the real before_goto hook
>     registered on the crawler_strategy passed in, fires one fake main-frame document response per
>     status in `statuses` (in order), then returns a result carrying crawl4ai_status_code as its
>     OWN status_code (simulating crawl4ai's earliest-hop value, distinct from the chain's last).

### test_chromium_scrape_facts.py

Anchor: docstring at `_FakeCrawler` (next def).

> A short fit_markdown (well under the old 200-char threshold) with a much longer raw_markdown
>     available is returned AS the short fit_markdown — no fallback to raw fires, because the
>     mechanism no longer exists at all.

Anchor: docstring at `_fake_try_scrape` (next def).

> The removed field must not reappear in the JSONL record — fallback_to_raw described a
>     mechanism that no longer exists.

Anchor: docstring at `_fake_try_scrape` (next def).

> scrape_url_chromium_workflow's log_scrape record carries the raw landed_url off meta — no verdict
>     computed or stored alongside it (removed: an agent reading the log has both "url" and
>     "landed_url" in the same record and compares them itself).

Anchor: comment block at `test_scrape_url_chromium_workflow_log_record_has_no_outcome_field` (next def).

> The log record no longer carries a computed outcome — acquisition_error is logged straight
> through as its own fact instead (the same precedent pipe_scraper_records.py's own outcome
> removal set), and og_published_time replaces the old guessed published_date/date field.

Anchor: docstring at `_HangingCrawler` (next def).

> A hang inside the acquisition (browser call never returns) is cut off at
>     TOTAL_SCRAPE_BUDGET_S, yielding acquisition_error=budget_exhausted — not a hang, not a
>     traceback. Budget shortened to keep this a fast regression guard; real-budget timing is
>     verified separately (see completion checklist).

Anchor: comment block at `test_acquire_cdp_headed_spawns_watchdog_with_pids_and_cleanup_dir` (next def).

> Net 2 — death_pipe watchdog spawned once the cdp port resolves, with this call's real PIDs and
> its own throwaway profile dir as cleanup_dir (unlike the search lane, which never deletes its
> persistent session profile)

### test_chromium_scrape_output.py

Anchor: comment block at `_real_stamp_args` (next def).

> extract_config_stamp — launch_mode is a fixed constant (LAUNCH_MODE) now that the
> WEBSEARCH_HEADLESS escape hatch is gone; replaces the dead-on-the-cdp-path browser_config.headless
> field. total_budget_s stays an explicit param (read off the real constant, never re-declared).

Anchor: docstring at `test_extract_config_stamp_no_longer_carries_min_content_threshold` (next def).

> max_content_length is gone (the parameter it described no longer exists) — build_config_record
>     removed, its only job was merging it in.

Anchor: docstring at `test_htmldate_removed_entirely` (next def).

> The fit->raw fallback mechanism (MIN_CONTENT_THRESHOLD) was removed entirely as of
>     2026-08-22 — content is always fit_markdown; the stamp no longer carries a field for a
>     selection mechanism that no longer exists.

Anchor: docstring at `test_extract_config_stamp_no_longer_carries_excluded_selector_hash` (next def).

> The guessed-date mechanism (htmldate, extract_date, HTMLDATE_TIMEOUT_S) is gone, not just
>     unused — the declared date now comes from crawl4ai's own already-parsed result.metadata,
>     at zero extra acquisition time.

Anchor: docstring at `test_format_scrape_output_never_replaces_content_with_a_message` (next def).

> The hand-maintained COOKIE_CONSENT_SELECTOR list was removed — crawl4ai's own
>     remove_consent_popups=True (a vendor-maintained clicker, verified a strict superset) carries
>     consent handling alone now. The stamp no longer hashes an excluded_selector that no longer
>     exists.

Anchor: comment block at `test_format_scrape_output_never_replaces_content_with_a_message` (next def).

> _format_scrape_output: facts always precede content, crawl4ai's diagnosis reads as an
> observation not a verdict, zero content is explicit and never a substituted message

Anchor: comment block at `test_format_scrape_output_carries_no_acquisition_facts_preamble` (next def).

> M2 milestone (2026-09-15): the printed acquisition-facts block is removed entirely — the facts
> still exist, they just stop being printed. Output shrinks; the log record does not.

### test_death_pipe.py

Anchor: docstring at `_spawn_dummy` (next def).

> Tests for death_pipe's generic crash-backstop primitive: a real spawned watchdog subprocess
> that blocks on a pipe and cleans up only once that pipe's write end closes (simulating this
> process's own death without actually exiting the test process — os.close() on the fd returned by
> spawn_watchdog does that), plus the pure terminate/kill and no-op-detection logic.
> 
> Real subprocesses are spawned here (this module's own primitive IS spawning a subprocess — there is
> no meaningful way to test it without one), but the PROTECTED targets are always `sleep`/`python -c`
> dummy processes, never real Chrome/Firefox — consistent with "I/O boundaries mocked" elsewhere in
> this suite, applied to the boundary that matters here (no real browser involved).

### test_dedup_exclude.py

Anchor: docstring at `_entry` (next def).

> Tests for filter_new_entries exclude_urls param (failure-URL diff exclusion).
> 
> No network, no corpus. Covers:
> - URL in exclusion set, no raw MD  → excluded (not new)
> - URL not in exclusion set, no raw MD → new
> - URL not in exclusion set, raw MD exists → skipped (already in raw)
> - URL in exclusion set AND raw MD exists → excluded (exclusion checked first)
> - exclude_urls=None (default) → unchanged behaviour, no exclusions
> - n_excluded and n_skip_raw counts are correct

Anchor: comment block at `test_pub_date_str_returns_unknown_when_no_date_found` (next def).

> pub_date_str / mode="pubdate" — consolidated 2026-09-09 (was also defined, with a diverging
> "" fallback, in src/news/clean_pass.py; that copy is gone, this is the one surviving definition)

### test_document_status.py

Anchor: docstring at `_FakeTab` (next def).

> Tests for src/search/document_status.py — the CDP Network.responseReceived listener that backs
> the search lane's HTTP-status fact, and the pure merge that attaches it to a diagnosis snapshot.
> 
> No real browser/CDP — a fake tab exposes just what start_document_status_capture touches
> (_target_id, enable_network_events, on) and lets the test fire synthetic CDP event dicts directly
> at the registered callback.

### test_mojeek_engine.py

Anchor: docstring at `__init__` (next def).

> Returns a queued value per _JS_POLL call; every other script gets a fixed reply.
> 
>     Poll replies are dicts (serialised on the way out, the way the real page does). The last entry
>     repeats once exhausted, so a test only has to describe the states it cares about.

Anchor: docstring at `test_parse_results_returns_empty_on_an_unreadable_read` (next def).

> Matches the 2026-09-09 decision recorded in src/search/engines/DOCS.md: the swallowing
>     handler was removed from the browser engines so a parse failure surfaces as ERROR_PARSE
>     instead of masquerading as an empty page.

### test_openalex_engine.py

Anchor: docstring at `test_403_stays_plain_empty_no_reason_but_carries_http_status` (next def).

> 429 used to surface a guessed EMPTY_BLOCK verdict; that verdict carried no information the
>     observed HTTP status (already in diagnosis) did not already carry, so it is gone — reason is
>     now None like every other empty branch, and the real fact (429) lives in diagnosis alone.

Anchor: docstring at `test_success_with_results_has_no_diagnosis` (next def).

> 403 keeps reason=None (unchanged status/reason semantics) but the diagnosis now carries the
>     real observed HTTP status — the exact fact a bare EMPTY verdict used to discard.

Anchor: docstring at `test_api_key_sent_when_env_var_set` (next def).

> A 200 response that parses to zero results still returns WITHOUT results, so it carries the
>     observed HTTP status even though reason stays None (unchanged).

Anchor: docstring at `test_build_engine_pools_preserves_pdf_url_on_winner` (next def).

> 2026-09-09: search()'s own try/except that swallowed exceptions into [] was removed — a
>     code-standards violation (silently hiding an error affecting business logic). search() now
>     inherits BaseEngine's plain delegation to search_with_reason and lets an exception through
>     unchanged.

### test_pipe_scraper.py

Anchor: docstring at `test_log_pipe_scrape_writes_jsonl_record` (next def).

> Tests for pipe_scraper's per-URL JSONL log (pipe_scrape_logger.py) and the config stamp
> it carries.
> 
> Runs without a browser: _scrape_all's AsyncWebCrawler is patched with a fake crawler returning
> synthetic results, isolating the logging path from the real network/browser call.

Anchor: docstring at `_capturing_build_configs` (next def).

> _scrape_all's own headed parameter reaches _build_configs unchanged — the wiring this
>     milestone adds, proven the same way the camoufox lane's block_images wiring already is.

Anchor: docstring at `test_scrape_all_records_carry_config_hash_and_config` (next def).

> Regression guard: ts must be stamped AFTER the per-domain gate, not when asyncio.gather
>     queues the coroutine. concurrency_per_domain=1 fully serializes 6 same-domain URLs through
>     the gate at download_delay=0.05s (jitter 0.025-0.075s/hop) — real elapsed request-start times
>     must spread across the run. A ts taken before the gate collapses to one identical value for
>     all 6 records regardless of this pacing (the bug this guards against).

Anchor: comment block at `test_scrape_all_records_carry_config_hash_and_config` (next def).

> 5 gate hops at >=0.025s jitter each (serialized, concurrency_per_domain=1) — real lower bound ~0.125s

Anchor: comment block at `_FakeRedirectingCrawler` (next def).

> landed_url on the plain success route. No same_target verdict is computed anywhere in this
> module (milestone 5: removed — an agent reading a record has both "url" and "landed_url" and
> compares them itself).

Anchor: docstring at `__init__` (next def).

> Plain success route (no fallback engaged either way) — result carries a real
>     redirected_url, differing from the requested URL on a different host.

Anchor: docstring at `test_landed_url_recorded_on_plain_success_no_redirect` (next def).

> The plain success route (neither fallback engaged) gets a real landed_url — a deviating
>     redirect (different host) is recorded raw, no verdict computed alongside it.

### test_pipe_scraper_camoufox_engine.py

Anchor: comment block at `test_camoufox_concurrency_default_is_conservative` (next def).

> Engine switch — milestone 3 of the camoufox_lane area: a per-RUN choice between the chromium
> engine (default, unchanged) and the camoufox engine (try_scrape_camoufox), never per-URL, never
> auto-selected. pipe_scraper_acquisition.try_scrape_camoufox is faked at the module boundary (same convention
> as camoufox_scrape's own tests faking AsyncCamoufox) — no real browser launched here either.

Anchor: docstring at `test_scrape_all_default_engine_is_chromium_and_unchanged` (next def).

> No measurement exists yet for how many concurrent Camoufox instances this machine
>     tolerates — the default must be the most conservative value (fully serialized), unlike the
>     chromium engine's measured/validated 8.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> engine defaulted/omitted -> the existing chromium path runs, untouched: AsyncWebCrawler is
>     used, try_scrape_camoufox is never called at all.

Anchor: docstring at `_UnreachableCrawler` (next def).

> engine="camoufox" -> try_scrape_camoufox is called per URL; AsyncWebCrawler/AsyncCamoufox
>     (the chromium engine's own machinery) is never touched.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> concurrency_per_domain=None + engine="camoufox" -> resolves to
>     CAMOUFOX_CONCURRENCY_PER_DOMAIN, not the chromium default. Proven via timing: 3 same-domain
>     URLs at concurrency=1 must serialize through the pacing gate (spread > 0), unlike the
>     chromium default of 8 which would let them all start together.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> The camoufox-engine record carries engine="camoufox", landed_url,
>     markdown_conversion_error, acquisition_error (try_scrape_camoufox's own fact field, logged
>     directly — None here since this meta doesn't set it) — and does NOT carry the chromium-only
>     crawl4ai_* fields at all (absent, not null/false).

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> A hard acquisition failure (budget_exhausted/browser_missing/exception) is logged verbatim
>     as its own fact, not collapsed into a computed verdict — try_scrape_camoufox already knows
>     exactly which of the three it was; that specific value is what lands in the record, alongside
>     the plain status_code=None/bytes=0 facts a total acquisition failure naturally produces.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> M2: try_scrape_camoufox now reports the LAST main-frame document response's status, not a
>     stale challenge-page status. A meta shaped like a resolved Cloudflare challenge (status_code=200
>     from the corrected acquisition primitive, document_status_chain=[403, 302, 200] as the fact
>     trail) must flow through as the recorded http_status=200 — no special-casing of the chain
>     anywhere in this module, it only ever reads meta['status_code'] and passes it straight to the
>     log. The JSONL record also carries the chain field.

### test_pipe_scraper_config.py

Anchor: docstring at `test_build_configs_sets_fixed_anti_bot_posture` (next def).

> simulate_user/override_navigator/magic/remove_consent_popups are read off the real
>     CrawlerRunConfig, not re-declared — changing the object changes the stamp.

Anchor: docstring at `test_build_configs_produces_live_stealth_adapter` (next def).

> _build_configs's real BrowserConfig/CrawlerRunConfig carry the milestone's exact
>     calibration: stealth + simulate_user + override_navigator on, magic explicitly off,
>     consent popups dismissed, pacing/timeout values untouched.

Anchor: comment block at `test_build_configs_default_stays_headless` (next def).

> use_undetected resolves False (default PlaywrightAdapter, pipe_scraper passes no adapter) —
> the precondition browser_manager.py requires to build the stealth adapter at all

Anchor: docstring at `test_extract_pipe_config_stamp_reflects_headed` (last def).

> The config stamp reads headless straight off the real object — no separate wiring
>     needed for headed to reach the log.

### test_pipe_scraper_onward_links.py

Anchor: comment block at `test_onward_link_identity_strips_query_and_fragment` (next def).

> _onward_link_identity — the query/fragment-stripped comparison key onward-link collection uses.
> Deliberately NOT seed_feeders_scope.normalize_url (which keeps the query on purpose) — see the
> function's own docstring for why this file's worst case inverts that reasoning.

Anchor: comment block at `test_onward_link_identity_none_for_hostless_url` (next def).

> The real motivating case: 50 scraped pages each linked the SAME login page with a different
> returnTo= query string — a plain string-dedup kept all 50 distinct.

Anchor: comment block at `test_collect_onward_links_returns_none_for_camoufox_engine` (next def).

> A rescued/exception-path result never carries a 'links' key at all (see
> pipe_scraper_acquisition.py's own Gotchas) — must not raise, contributes nothing.

Anchor: docstring at `_fake_try_scrape_camoufox` (next def).

> A camoufox run must not be able to look like a chromium run that found nothing — the key
>     itself is absent, never present-and-empty.

### test_proxy_pool.py

Anchor: docstring at `_md` (next def).

> Tests for proxy_pool engine: janitor window stats (D3), retry resilience (D1),
> and source-list reporting (D2). Tests are self-contained: synthetic JSONL events,
> no network, no filesystem state beyond tmp_path.

### test_proxy_pool_run_loop.py

Anchor: comment block at `test_run_loop_refresh_swaps_pool_and_preserves_state` (next def).

> time.monotonic sequence — 9 real calls (corrected 2026-08-20, same undercounting fix as
> test_run_loop_refresh_swaps_pool_and_preserves_state above — see this milestone's process-docs
> entry for the traced call-by-call evidence):
>   #1 _last_refresh=0.0 (startup)  #2 _last_progress=0.0 (startup)
>   #3 now(iter1)=0.0 → no refresh
>   [batch 1: only A1 in pool → A1→url1 ok; wset={A1}]  #4 _last_progress=0.0 (post-batch1)
>   #5 now(iter2)=15.0 → REFRESH  #6 _last_refresh=15.0 (post-refresh)
>   [batch 2: concurrency=3; A1(wset)→url2, B1(buf)→url3, B2(buf)→url4; all ok —
>    3 futures each call _last_progress once]  #7,#8,#9 _last_progress=15.0 (post-batch2 x3)
>   queue empty after n_urls_consumed=3 → return

Anchor: docstring at `test_run_loop_refresh_fresh_candidates_from_new_pool` (next def).

> run_loop calls pool_provider twice, preserves queue/done/wset across the swap.
> 
>     Proves:
>     - pool_provider called exactly 2× (startup + one refresh).
>     - All 3 target URLs reach done — none dropped at the swap boundary.
>     - Pool A proxy A1:80 enters wset pre-refresh and is still dispatched for url2
>       post-refresh (wset is never touched by _refresh_pool — only pool/buf are).
>     - Logger receives 2 record_pool_refresh events with correct pool sizes.

### test_query_logger.py

Anchor: docstring at `_make_mock_engine_with_reason` (next def).

> Tests for query_logger + per-engine stats capture in search_web_workflow.
> 
> Runs without network: mock engines return fixed results immediately.
> Uses tmp_path (via WEBSEARCH_QUERY_LOG_PATH) so production log is never touched.

Anchor: comment block at `_now_ts` (next def).

> Current-time ts — log_janitor prunes lines with a "ts" older than the 90-day retention window on every write.

Anchor: docstring at `test_engine_with_timing_timeout_preserves_facts_written_before_cancellation` (next def).

> _engine_with_timing returns TIMEOUT_WATCHDOG + drop_reason when engine exceeds watchdog.
>     diagnosis stays None when the engine never wrote anything into partial before cancellation —
>     the same "don't invent a fact" rule the guessed-verdict-removal milestone settled.

Anchor: docstring at `test_engine_with_timing_empty` (next def).

> A poll-loop checkpoint reached before the watchdog fires survives the cancellation, merged
>     with diagnosis_partial=True — the mechanism this milestone adds. asyncio.wait_for cancels the
>     engine's own Task, not _engine_with_timing itself, so a mutable dict handed to the engine by
>     reference and written into before that cancellation is the only thing that can still be read
>     afterward; this proves exactly that channel.

Anchor: docstring at `test_search_web_workflow_writes_search_key_matching_cache_key` (next def).

> log_query writes a well-shaped drilldown record — the generic writer, exercised with the
>     new record_type's fields (mirrors test_log_query_writes_jsonl's pattern for engine_run/
>     workflow_summary).

Anchor: docstring at `test_log_drilldown_all_cache_status_and_pool_combinations` (next def).

> workflow_summary's search_key equals the real cache.cache_key(...) output for the same
>     call — the exact join value a drilldown record must reproduce to correlate back to this
>     search. Real engine fanout mocked (no network); cache_write mocked (no real cache-dir write);
>     cache_key itself is NOT mocked — it must be the real function for this assertion to mean
>     anything.

Anchor: docstring at `test_log_drilldown_all_cache_status_and_pool_combinations` (last def).

> Real cli.py._log_drilldown, exercised for the sub-cases that matter: a hit with the engine
>     present (real urls, result_count matches); a hit with the engine absent from pools
>     (engine_in_pools=False, urls empty — distinguishing 'excluded upstream' from 'zero results');
>     and a cache-miss-then-search-failure (cache_status names the failure explicitly rather than
>     looking like an ordinary hit).

### test_seed_feeders_navtree.py

Anchor: comment block at `test_find_navigation_tree_tier2_filters_fragment_and_internal_asset_paths` (next def).

> Real shape observed on ui.shadcn.com: a rendered <button> element whose "children" prop is
> a list of OTHER React elements (each itself a 4-item ["$", tag, key, props] list), not a
> list of plain data dicts — must not be mistaken for a navigation-tree node.

Anchor: comment block at `test_navtree_feeder_workflow_next_data_shape_end_to_end` (next def).

> The seed is the target of the whole run, unlike a version root or robots.txt/a sitemap —
> its own fetch failure must not look like "this site has no navigation tree" (review note).

Anchor: comment block at `test_navtree_feeder_workflow_rsc_dom_only_shape_falls_back_to_flat_tier` (next def).

> The App Router shape carrying a genuine structured tree (the ui.shadcn.com/Fumadocs case)
> — a detector that only knows __NEXT_DATA__ would silently find nothing here at all.

Anchor: comment block at `test_navtree_feeder_workflow_neither_shape_is_ok_empty` (next def).

> The App Router shape with no structured tree at all (the nextjs.org/docs case) — a single
> rendered <a> element, href present but "children" is text, not a list of tree nodes.

Anchor: comment block at `test_navtree_feeder_workflow_invalid_seed_url_is_failed_not_empty` (next def).

> Contrast with the test above: here the seed itself never loads at all (every URL 404s) —
> must be ok=False, not indistinguishable from "reachable, no navigation tree" (review note).

### test_seed_feeders_scope.py

Anchor: comment block at `test_normalize_url_raises_on_bad_port` (next def).

> urlparse would split ";jsessionid=ABC" into its own .params field and drop it on rebuild;
> normalize_url uses urlsplit specifically so this stays part of path (review note #3)

### test_seed_feeders_sitemap.py

Anchor: comment block at `test_sitemap_feeder_workflow_falls_back_to_conventional_paths` (next def).

> conventional paths deliberately NOT routed — if the feeder fell back to them
> instead of the robots-declared one, this test would see an empty result

### test_theblock_clean_pass.py

Anchor: docstring at `_hash` (next def).

> Tests for the proxy_pool clean-pass helper: _run_clean_pass.
> 
> Synthetic raw HTML fixtures — no corpus, no network.
> Covers: good fixture → clean file written with correct name; body-less → bodyless_urls.txt;
>         raw retention (A1); stats correctness.

### test_theblock_discover.py

Anchor: docstring at `_make_urls` (next def).

> Tests for theblock discover.py range-mode helpers.
> 
> Synthetic sub-sitemap URL list — no network calls.
> Covers: _subs_in_range, _sub_by_index (regression), and the discover() dispatch
>         error paths for sub:A-B.

## Process notes (recap)

- Order used: comment sweep first, re-measure, then split only what stayed at 400 LOC or more, then the DOCS.md rewrite. This order avoided splitting `test_query_logger.py` at all.
- The sweep is scripted (tokenize for comments, AST for docstrings, per-file AST-equality check against the original minus docstrings). A file whose AST differed would have been skipped and reported; none was.
- The `/tmp` directory is shared between workers: a generic `/tmp/scan.py` written early was overwritten by another worker's script. Use a private subdirectory (`/tmp/<name>/`) for scratch files.
- Tool hooks in this environment refuse piping a CLI into another command and reading a redirected CLI output with `cat` in the same call; redirect first, read with Read in the next call.
- Files touched (`git diff integration --name-only --`): 52 `dev/tests/*.py` files swept, `dev/tests/test_brave_build_results.py` added, `dev/tests/test_brave_engine.py` reduced, `dev/tests/DOCS.md` rewritten (255 lines, LOC headings match `wc -l`), this file.
- Not done: no investigation of the two intermittent brave tests; no manual review of every (b) decision.

## Phase 4 control-flow triage, step 1: src/ (excluding src/search/) and cli.py (2026-09-24)

Scope: 70 except handlers, 4 TRIPWIRE (`box_lock.py:50`, `box_lock.py:95`, `theblock/discover.py:62`, `theblock/discover.py:73`, all correct as they are) and 66 non-TRIPWIRE, which are classified below. `cli.py` has no except handler. Nothing was changed in code. Scan: the orchestrator scan copied to a private directory; classes are the coarse AST heuristic, the "class" column is my reading of the surrounding function.

Evidence sources searched: `process-docs/**` in this worktree and the main checkout logs `src/logs/` (`query_log.jsonl`, `scrape_log.jsonl`, `pipe_scrape_log.jsonl`, `news_theblock_*.log`, `news_coindesk_*.log`, `cli.log*`). Feeder failures are returned as data and never logged, so the logs cannot show a feeder-level network failure either way; that absence is stated, not proof.

Counts by class: A status/report 25, B fallback 9, C silent swallow 1, D cleanup 20, E input shape 11.
Verdicts: keep 56, B-remove 8, B-keep-needs-logging 1, C remove 1.

Trade-off shared by 5 B-remove rows (`navtree:215`, `robots:19`, `sitemap:17`, `sitemap:25`, `sitemap:44`): the feeder workflows already turn any exception into `FeederResult(ok=False, error=...)`, so removing the inner handler makes a network or parse failure a visible failed feeder instead of a clean-looking empty result. The cost: for `sitemap:17` one failing sub-sitemap fails the whole sitemap feeder instead of losing only that sub. Decision belongs to the orchestrator.

| file:line | function | scan | class | verdict | evidence |
|---|---|---|---|---|---|
| src/crawler/discovery.py:37 | discover_urls_workflow | PRODUCES-OUTPUT | A | keep | invalid seed returns DiscoveryResult(ok=False, error=...); the CLI shows it |
| src/crawler/pipe_scrape_logger.py:24 | log_pipe_scrape | LOG-ONLY | D | keep | JSONL log write is best-effort telemetry; warning logged; test asserts it never breaks a scrape |
| src/crawler/pipe_scraper_acquisition.py:31 | _onward_link_identity | PRODUCES-OUTPUT | E | keep | hrefs come from third-party HTML; a malformed one (bad port, bare "[") is not a link, so it is excluded from onward links |
| src/crawler/pipe_scraper_acquisition.py:78 | _scrape_one | PRODUCES-OUTPUT | A | keep | hard crawler exception logged as status=None/bytes=0 record and returned in the same dict shape (2026-09-09 tripwire replacing the curl_cffi rescue) |
| src/crawler/seed_feeders.py:23 | robots_feeder_workflow | PRODUCES-OUTPUT | A | keep | FeederResult(ok=False, error=str(exc)); discovery lists it in failed_feeders |
| src/crawler/seed_feeders.py:37 | sitemap_feeder_workflow | PRODUCES-OUTPUT | A | keep | FeederResult(ok=False, error=str(exc)); discovery lists it in failed_feeders |
| src/crawler/seed_feeders.py:48 | navtree_feeder_workflow | PRODUCES-OUTPUT | A | keep | FeederResult(ok=False, error=str(exc)); discovery lists it in failed_feeders |
| src/crawler/seed_feeders_navtree.py:30 | _extract_next_data_payloads | PRODUCES-OUTPUT | B | B-remove | malformed __NEXT_DATA__ JSON returns [] and looks like "page has no payload"; no observation in process-docs/logs; propagating gives ok=False + error via the feeder |
| src/crawler/seed_feeders_navtree.py:47 | _extract_rsc_stream_payloads | SWALLOW-FLOW | E | keep | RSC stream rows are not all JSON (the suite already pins "I[...]" module-reference rows); a non-JSON row is a real row type, not a failure |
| src/crawler/seed_feeders_navtree.py:215 | _fetch_html | PRODUCES-OUTPUT | B | B-remove | network error becomes None, the same as a 404; no observed network failure; propagating gives ok=False + error. Trade-off: one unreachable version root would fail the feeder instead of being skipped |
| src/crawler/seed_feeders_robots.py:19 | fetch_robots_txt | PRODUCES-OUTPUT | B | B-remove | network error becomes None, the same as "no robots.txt"; only 404/empty robots.txt observed (docs.github.com); same trade-off as navtree _fetch_html |
| src/crawler/seed_feeders_scope.py:52 | scope_and_dedup | SWALLOW-FLOW | E | keep | documented decision (url_discovery 2026-08-28): one malformed URL in untrusted sitemap/robots content is dropped; CPython 3.14 urlparse().port raises lazily, verified |
| src/crawler/seed_feeders_sitemap.py:17 | fetch_sitemap | PRODUCES-OUTPUT | B | B-remove | network error becomes None, the same as a 404; unobserved. Trade-off: one failing sub-sitemap would fail the whole sitemap feeder (ok=False) instead of losing only that sub |
| src/crawler/seed_feeders_sitemap.py:25 | fetch_sitemap | PRODUCES-OUTPUT | B | B-remove | corrupt .gz returns None as if the sitemap were absent; no observation |
| src/crawler/seed_feeders_sitemap.py:44 | parse_sitemap_xml | PRODUCES-OUTPUT | B | B-remove | unparseable XML returns ("unknown", []); only a unit test pins it, no observed soft-404 HTML sitemap; plausible on SPA hosts, so flag as the riskiest removal (feeder would report ok=False + ParseError instead of a clean empty) |
| src/death_pipe.py:45 | _terminate_then_kill | SWALLOW-FLOW | D | keep | process already gone between listing and terminate; goal (gone) achieved |
| src/death_pipe.py:53 | _terminate_then_kill | SWALLOW-FLOW | D | keep | process already gone between wait_procs and kill |
| src/death_pipe.py:64 | _log_intervention | LOG-ONLY | D | keep | intervention-log write is best-effort; warning logged on the logger |
| src/log_janitor.py:26 | maybe_prune_jsonl | LOG-ONLY | D | keep | prune is housekeeping; failure logged as warning, appended record already written |
| src/log_janitor.py:36 | maybe_prune_sidecars | LOG-ONLY | D | keep | same as maybe_prune_jsonl for sidecars |
| src/log_janitor.py:43 | _is_recent | PRODUCES-OUTPUT | E | keep | no .lastprune marker is a real state (first run), means "not recent" |
| src/log_janitor.py:60 | _prune_jsonl | LOG-ONLY | A | keep | unparseable/ts-less log line is dropped with one logged warning per line (documented in DOCS) |
| src/log_janitor.py:76 | _prune_sidecars | LOG-ONLY | D | keep | single unlink failure logged with the file name; rest of the prune continues |
| src/news/engine/proxy_pool/box_lock.py:27 | cleanup_stale | PRODUCES-OUTPUT | D | keep | sidecar is advisory metadata; flock is the real lock, unreadable sidecar just skips stale cleanup |
| src/news/engine/proxy_pool/box_lock.py:34 | cleanup_stale | LOG-ONLY | D | keep | pid is dead, so the stale sidecar is unlinked |
| src/news/engine/proxy_pool/box_lock.py:36 | cleanup_stale | PRODUCES-OUTPUT | E | keep | pid exists under another user, i.e. alive; real outcome of os.kill(pid, 0) |
| src/news/engine/proxy_pool/box_lock.py:84 | _busy_message | PRODUCES-OUTPUT | A | keep | error message states "lock held, sidecar unreadable"; message text only, the lock behaviour is unaffected |
| src/news/engine/proxy_pool/fetch.py:18 | fetch_url | PRODUCES-OUTPUT | A | keep | per-proxy attempt returns ("fail", b"") and record_attempt logs it; free proxies failing is the normal outcome |
| src/news/engine/proxy_pool/pool_loaders.py:172 | _try_source | PRODUCES-OUTPUT | A | keep | sources list records ok=False,count=0 and job.md renders a source breakdown (D2) |
| src/news/engine/proxy_pool/pool_retry.py:18 | fetch_with_retry | PRODUCES-OUTPUT | A | keep | retry with backoff then raise last_exc (scan mislabels it: the raise sits after the loop); retry is not a second output path |
| src/news/engine/proxy_riding/abort.py:50 | _abort_write_report_and_exit | PRODUCES-OUTPUT | A | keep | WARN on stderr naming the exception, then os._exit anyway (stub job.md fallback removed 2026-09-09) |
| src/news/engine/proxy_riding/fetch.py:51 | _fetch_one_url | PRODUCES-OUTPUT | A | keep | status="connect_fail" and err=str(exc) are returned and recorded per URL |
| src/news/engine/proxy_riding/fetch.py:58 | _fetch_one_url | PRODUCES-OUTPUT | D | keep | kill_session teardown; warning printed |
| src/news/engine/proxy_riding/rider.py:142 | _next_url_for_slot | PRODUCES-OUTPUT | E | keep | asyncio.QueueEmpty is the normal control-flow signal for an empty queue, not an error |
| src/news/engine/proxy_riding/rider.py:343 | _teardown_pool | PRODUCES-OUTPUT | D | keep | remove_signal_handler at teardown; warning printed |
| src/news/engine/scrape.py:106 | _fetch_one | PRODUCES-OUTPUT | A | keep | status="failed" and error=str(exc) in the manifest entry, plus stderr line |
| src/news/engine/scrape_job.py:53 | _scrape_one_chunk | PRODUCES-OUTPUT | A | keep | RegwallGuardError logged at ERROR, chunk marked aborted, partial manifest persisted |
| src/news/pipeline.py:343 | _run_pipeline_browser | PRODUCES-OUTPUT | A | keep | RegwallGuardError logged at ERROR, partial manifest persisted |
| src/news/pipeline_support.py:44 | _check_internet | PRODUCES-OUTPUT | A | keep | logs [FAIL] Internet unreachable and returns False to the caller |
| src/news/platforms/coindesk/browser.py:90 | browser_load_feed | PRODUCES-OUTPUT | D | keep | tab.close teardown, message printed |
| src/news/platforms/coindesk/browser.py:95 | browser_load_feed | PRODUCES-OUTPUT | D | keep | chrome.close teardown, message printed |
| src/news/platforms/coindesk/browser.py:132 | wait_for_ws_url | LOG-ONLY | E | keep | polling for Chrome readiness: connection refused while starting is the expected state; TimeoutError raised after the deadline |
| src/news/platforms/coindesk/browser.py:144 | _extract_value | PRODUCES-OUTPUT | E | keep | only caller prints OK/miss for a click; a CDP result without a value is the "miss" outcome, display only |
| src/news/platforms/coindesk/discover.py:61 | _parse_stop_date | PRODUCES-OUTPUT | B | B-keep-needs-logging | CLI default --timeframe is "delta" (src/news/__main__.py:76), which int() rejects, so "delta" and any typo silently become DEFAULT_DELTA_DAYS; observed (default invocation) but no log line and the --help text does not name it. Suggested fix: explicit "delta" branch, log the resolved stop_date (already printed at discover.py:31), let garbage raise |
| src/news/platforms/coindesk/discover.py:244 | _close_year_files | PRODUCES-OUTPUT | D | keep | year shard close at teardown; message printed |
| src/news/platforms/coindesk/timeline.py:49 | fetch_feedpage | PRODUCES-OUTPUT | A | keep | error printed, -1 returned and printed by every caller as the feedpage status |
| src/news/platforms/theblock/cleanup.py:61 | _find_news_article | SWALLOW-FLOW | E | keep | a page carries several ld+json blocks; a malformed one is skipped, and if no NewsArticle is found cleanup prints "no JSON-LD NewsArticle found" and the URL lands in bodyless_urls |
| src/news/platforms/theblock/discover.py:105 | _fetch_direct | PRODUCES-OUTPUT | B | B-remove | exception branch only: direct-fetch exceptions fall through to the proxy pool. Observed trigger is HTTP 403 without XML marker (news_pipeline 35, 15), which is the status path in the try body and stays. No observed direct-fetch exception; propagate it |
| src/news/platforms/theblock/discover.py:158 | _parse_url_blocks | SWALLOW-FLOW | C | remove | sitemap entry with an unparseable lastmod is dropped silently, so discovery loses URLs with no trace; no observed bad lastmod (all observed values ISO) |
| src/scraper/camoufox_scrape.py:89 | _ensure_no_focus_steal | LOG-ONLY | A | keep | warning "no-focus-steal not applied" names the consequence; scrape continues |
| src/scraper/camoufox_scrape.py:103 | _resolve_system_locale | SWALLOW-PASS | B | B-remove | failed `defaults read -g AppleLocale` falls back to locale.getlocale() then en-US; the process-docs record only that the fallback exists, never a failure. Removal lets the error surface as acquisition_error=exception |
| src/scraper/camoufox_scrape.py:135 | _on_response | PRODUCES-OUTPUT | E | keep | request.frame raises for requests whose frame does not exist yet (vendor docstring, cited in scrape_pipeline 2026-09-03); such a response is by definition not the main frame |
| src/scraper/camoufox_scrape.py:194 | try_scrape_camoufox | PRODUCES-OUTPUT | A | keep | acquisition_error=budget_exhausted plus warning |
| src/scraper/camoufox_scrape.py:197 | try_scrape_camoufox | PRODUCES-OUTPUT | A | keep | acquisition_error=browser_missing plus ERROR naming the repair command |
| src/scraper/camoufox_scrape.py:203 | try_scrape_camoufox | PRODUCES-OUTPUT | A | keep | acquisition_error=exception plus warning |
| src/scraper/camoufox_scrape.py:218 | _html_to_markdown | PRODUCES-OUTPUT | A | keep | returned as markdown_conversion_error and logged (raw-HTML fallback removed 2026-09-09) |
| src/scraper/chromium_process.py:128 | _reap_orphaned_scrapes | SWALLOW-FLOW | D | keep | orphan candidate already exited |
| src/scraper/chromium_process.py:156 | _live_scrape_profile_dirs | SWALLOW-FLOW | D | keep | candidate already exited while listing live profile dirs |
| src/scraper/chromium_scrape.py:136 | try_scrape | PRODUCES-OUTPUT | A | keep | acquisition_error=budget_exhausted plus warning |
| src/scraper/chromium_scrape.py:139 | try_scrape | PRODUCES-OUTPUT | A | keep | acquisition_error=browser_missing (ERROR) or exception (warning) |
| src/scraper/chromium_scrape.py:180 | _acquire_cdp_headed | SWALLOW-PASS | D | keep | awaiting the cancelled watchdog task in finally |
| src/scraper/chromium_scrape.py:202 | _on_response | PRODUCES-OUTPUT | E | keep | same as camoufox_scrape.py:135 |
| src/scraper/chromium_scrape.py:214 | _close_popup_page | LOG-ONLY | D | keep | popup page close, debug-logged |
| src/scraper/index_scrapes.py:65 | _index_one | PRODUCES-OUTPUT | A | keep | IndexOutcome status "failed" with the exception text, reported per URL |
| src/scraper/scrape_logger.py:47 | write_sidecar | PRODUCES-OUTPUT | D | keep | sidecar write is best-effort; warning logged; the log record carries sidecar_path None |
| src/scraper/scrape_logger.py:60 | log_scrape | LOG-ONLY | D | keep | JSONL log write is best-effort telemetry; warning logged |

## Phase 4 control-flow triage, step 2: removals (2026-09-24)

Orchestrator decisions applied exactly as approved. Suite: 492 passed before, 513 passed after (21 new tests; the old `parse_sitemap_xml` malformed test was rewritten to assert the raise, not deleted). Comment/docstring scan of `dev/tests` still prints nothing.

| site | change | test |
|---|---|---|
| `seed_feeders_navtree._extract_next_data_payloads` | `json.loads` error propagates | malformed `__NEXT_DATA__` raises `JSONDecodeError`; feeder returns `ok=False` with error |
| `seed_feeders_navtree._fetch_html` | `httpx.HTTPError` propagates, non-200 still returns `None` | `ConnectError` propagates from `resolve_navigation_tree`; feeder `ok=False` with the message |
| `seed_feeders_robots.fetch_robots_txt` | network error propagates, 404 still `None` | `ConnectError` propagates; feeder `ok=False` |
| `seed_feeders_sitemap.fetch_sitemap` | network error and corrupt gzip propagate, non-200 still `None` | `ReadTimeout` propagates; corrupt `.gz` raises `OSError`; a valid `.gz` is still decompressed |
| `seed_feeders_sitemap.parse_sitemap_xml` | `ParseError` propagates; a well-formed unrelated root still returns `("unknown", [])` | rewritten test asserts `ParseError`; an HTML 200 on `/sitemap.xml` makes the sitemap feeder `ok=False` |
| `theblock/discover._fetch_direct` | exception branch removed; 200 with XML marker returns content, anything else returns `None` so the proxy-pool fallback (observed: HTTP 403) still triggers | 403 without marker returns `None`; 200 with marker returns content; `ConnectError` propagates |
| `theblock/discover._parse_url_blocks` | unparseable `lastmod` raises `ValueError` | ISO `lastmod` parses; `not-a-date` raises |
| `camoufox_scrape._resolve_system_locale` | failed or timed-out `defaults read -g AppleLocale` propagates; the `locale.getlocale()` / `en-US` tail stays for non-darwin and empty output | `CalledProcessError` propagates; `de_DE` becomes `de-DE` |
| `coindesk/discover._parse_stop_date` | explicit `"delta"` branch (same `DEFAULT_DELTA_DAYS`), other unparseable value raises; the `stop_date` line printed by `discover()` is untouched | new `test_coindesk_stop_date.py`: full, delta, integer, `"deltaa"` raises |

Live verification (real runs, this worktree, `./venv/bin/python cli.py discover_urls`):

- `https://docs.python.org/3/`: `ok=True`, `failed_feeders: {}`, 29 URLs (robots=21, seed=1, sitemap=7).
- `https://platform.claude.com/docs`: `ok=True`, `failed_feeders: {}`, 3631 URLs (navtree_flat=6, robots=1, seed=1, sitemap=3623).

No feeder failed after the removals on either host. The claim in step 1 that soft-404 HTML sitemaps might turn a clean empty into `ok=False` is therefore still only a hypothesis: neither host triggered it.

Not run live, by instruction: theblock and coindesk (proven by tests only).

Gotchas for the next agent:
- Shell cwd: a `cd process-docs` in one Bash call persists into the next call and broke relative paths; use absolute paths or a subshell.
- The `/tmp` directory is shared between workers; scratch files live in `/tmp/wnotice/`.
- The sitemap feeder now fails as a whole when one sub-sitemap fetch raises (the trade-off named in step 1). If this shows up in real use, the fix is a decision about a visible per-sub failure fact, not a handler that returns `None`.

## Process notes (recap, Phase 4 step 2)

- Files touched relative to `integration` for this task: `src/crawler/seed_feeders_navtree.py`, `seed_feeders_robots.py`, `seed_feeders_sitemap.py`, `src/news/platforms/theblock/discover.py`, `src/news/platforms/coindesk/discover.py`, `src/scraper/camoufox_scrape.py`; tests `test_seed_feeders_navtree.py`, `test_seed_feeders_robots.py`, `test_seed_feeders_sitemap.py`, `_seed_feeders_fakes.py`, `test_theblock_discover.py`, `test_camoufox_scrape_output.py`, new `test_coindesk_stop_date.py`; `dev/tests/DOCS.md`, `src/crawler/DOCS.md`, `src/news/platforms/theblock/DOCS.md`, `src/news/platforms/coindesk/DOCS.md`, `src/scraper/DOCS.md`.
- DOCS.md LOC headings of the touched modules were already stale before this task (for example the crawler sitemap entry said 76, the file had 67); they now match `wc -l`. Other headings in `src/news/` DOCS files were not re-checked.
- The finding that mattered most from step 1 was not a removal: the CLI default `--timeframe delta` was reaching CoinDesk's `_parse_stop_date` only through a swallowed `ValueError`. Read the caller's default before judging a handler.
- Not done: no live theblock, coindesk or camoufox run (by instruction).

## Appendix: previous `dev/tests/DOCS.md` (601 lines), verbatim

The DOCS.md rewrite cut per-module detail that repeated code. The full previous text follows so nothing is lost.

~~~markdown
# dev/tests/

## Role
The project's pytest suite. Regression coverage for `src/search/`, `src/scraper/`, `src/crawler/`,
`src/news/engine/proxy_pool/`, `src/news/engine/proxy_riding/` (abort.py only, as of 2026-09-09),
`src/news/platforms/theblock/`, `src/news/platforms/coindesk/` (timeline.py only, as of 2026-09-09),
`src/log_janitor.py` (as of 2026-09-09), and `src/scraper/index_scrapes.py` (as of 2026-09-20) —
pure-logic branch coverage,
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

### test_brave_engine.py (425 LOC)
**Purpose:** `src/search/engines/brave.py` — `_build_results`, plus fixture-driven regression tests
for four milestones: the marker-reflection fix, the challenge-solving milestone and the
button-click-unreachable-under-`pow_link` fix, all recorded in `process-docs/marker_reflection/`,
and the partial-diagnosis-on-timeout milestone in `process-docs/search_pipeline/`.
`_classify_diagnosis` coverage removed with the function itself (the guessed-verdict-removal
milestone). The regression tests run a real headless pydoll Chrome against loopback fixture
servers, because every defect and every fix here lives in the engine's injected JS reading real
DOM state. One test bounds how long a genuine block may take against the engine watchdog and now
also bounds it well under the full budget, proving the `pow_link`-with-no-button grace exit fires.
One test drives the `pow_link`-plus-clickable-button fixture and asserts the click still happens
and real results come back. One guards against an unrelated button leaking into a success record;
it proves the mechanism, not how often staggered loading occurs live, and the process-docs entry
says why that number could not be measured cleanly. One cancels the real engine mid-poll from
outside and asserts the facts it had already written survive the cancellation.
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
2026-09-09: raises `ValueError` when `WEBSEARCH_LOG_RETENTION_DAYS` is set to a non-integer string
(the removed silent-fallback-to-14 behavior's replacement — see `src/DOCS.md`'s Gotchas). As of
2026-09-20: defaults to 90 (raised from 14) when the env var is unset — the sidecar retention
window a user needs to still find a scrape's sidecar on disk when deciding, after reading it in
chat, whether to index it into a RAG collection. `maybe_prune_jsonl`/`maybe_prune_sidecars` are not
covered here — see `dev/logging/` for their own dev-script exploration, out of scope for this file.

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

### test_index_scrapes.py (159 LOC)
**Purpose:** `src/scraper/index_scrapes.py` — first test coverage for this module (M2, 2026-09-20). Sidecar
resolution with multiple scrapes of the same URL (latest-by-filename wins, proven against a
synthetic three-sidecar fixture modeled on the real multi-scrape mojeek case documented in
`src/scraper/DOCS.md`'s own Gotchas); `_url_to_filename`/`_write_collection_file` convention match
(filename, `<!-- source: url -->` header, header-stripped content, real byte count returned);
`_sidecar_content`'s header-stripping in isolation; the missing-collection-directory tripwire
(`RAG_CLI_COLLECTIONS_ROOT` monkeypatched to a tmp_path with no subdirectory — `ok is False`, no
directory created, `subprocess.run` proven never called); a no-sidecar URL (`subprocess.run`
likewise proven never called for it); `rag-cli index` success and non-zero-exit paths
(`subprocess.run` monkeypatched to a fake `CompletedProcess`); one end-to-end
`index_scrapes_workflow` run mixing a found and a missing URL. No test touches a real sidecar, a
real collection directory, or a real `rag-cli` process — see `process-docs/adhoc_persistence/` for
the real, by-hand verification run against production data.

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
~~~
