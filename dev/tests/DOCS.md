# dev/tests/

## Role
The project's pytest suite: regression coverage for `src/search/`, `src/scraper/`, `src/crawler/`, `src/news/`, and the log janitor. I/O boundaries are mocked per test and production logic runs for real. Touch it when coverage changes, not when production behavior changes without an assertion needing to change.

## Public Interface
`__init__.py` is empty. Collected via `pytest` from the repo root (settings in `pytest.ini`). Real-browser tests carry the `browser` marker and run only with `-m browser`. Files named `_*_fakes.py` are shared helpers, not collected. `run_strands.sh` runs one fail-fast pytest per file in parallel, skips modules marked browser-only with a printed SKIP line, and counts any other nonzero exit (including 5, no tests collected) as a failure.

## Flow
Synthetic or captured inputs (JSON items, HTML fixtures, monkeypatched clients) go into the real function under test, and assertions read its real output. `tmp_path` and `monkeypatch` isolate filesystem and environment per test; `conftest.py` fails any test that reaches an unmocked real browser launch.

## Modules

### conftest.py (54 LOC)

**Purpose:** Suite-wide autouse tripwire replacing every real browser-launch primitive with a failing stand-in, so an unmocked launch fails the test by name.

### run_strands.sh (39 LOC)

**Purpose:** Runs one fail-fast pytest per test file in parallel with separate temp directories and logs; skips browser-only modules, fails on exit 5.

### test_conftest_guards.py (22 LOC)

**Purpose:** Provokes the conftest guards: osascript trap, subprocess pass-through, per-test temp directory.

### test_riding_cooldown_policy.py (158 LOC)

**Purpose:** Riding cooldown manager fixed and exponential policies: bounds, cap, reset, and counting.

### test_riding_imports.py (25 LOC)

**Purpose:** Import check of the proxy-riding package, config defaults, and absence of path hacks.

### test_riding_sigint_report.py (164 LOC)

**Purpose:** Riding abort on interrupt: exit codes 130 and 143 and report writes.

### test_riding_tail_race.py (281 LOC)

**Purpose:** Riding slot tail-race cases with the per-URL fetch and proxy selection mocked.

### test_riding_watchdog.py (91 LOC)

**Purpose:** Riding watchdog: wedge after all URLs resolved, and pool refresh.

### test_snippet.py (40 LOC)

**Purpose:** Snippet truncation cases and the dev-side copy of the bloat stripper in `dev/search_pipeline/_lib/text.py`.

### _browser_fakes.py (23 LOC)

**Purpose:** Shared fake Chrome and state-reset helper for the browser lifecycle tests. Not collected by pytest.

### test_browser.py (363 LOC)

**Purpose:** `src/search/browser.py`: PID snapshot and kill mechanics, session-dir cleanup, watchdog cancellation, own-Chrome teardown, focus-steal watchdog branches.

### test_browser_get_tab.py (219 LOC)

**Purpose:** `src/search/browser.py` tab acquisition: critical-section ordering, self-launch arguments, fresh profile per run, failure cleanup.

### test_browser_lock.py (92 LOC)

**Purpose:** `src/search/browser_lock.py` against a real file lock: immediate acquire, blocking until release, stale takeover.

### test_death_pipe.py (141 LOC)

**Purpose:** `src/death_pipe.py`: a real spawned watchdog subprocess plus mocked terminate and kill logic.

### test_document_status.py (77 LOC)

**Purpose:** `src/search/document_status.py`: CDP response listener filtering and the pure merge into a diagnosis snapshot.

### test_bing_engine.py (77 LOC)

**Purpose:** `src/search/engines/bing.py`: redirect unwrapping, result building, and parse-error propagation.

### test_brave_engine.py (392 LOC)

**Purpose:** `src/search/engines/brave.py`: fixture-driven regressions (marker reflection, challenge solving, partial facts on cancellation) against a real headless Chrome on loopback.

### test_brave_build_results.py (30 LOC)

**Purpose:** `src/search/engines/brave.py` result building: field mapping, url-less items skipped, result cap.

### test_mojeek_engine.py (236 LOC)

**Purpose:** `src/search/engines/mojeek.py`: ALTCHA plumbing, parse-readiness rule, scripted-tab result waiting, diagnosis contract.

### test_openalex_engine.py (233 LOC)

**Purpose:** `src/search/engines/openalex.py`: PDF URL extraction and threading, HTTP-status diagnosis branches, request params, base-engine delegation.

### test_startpage_engine.py (30 LOC)

**Purpose:** `src/search/engines/startpage.py` result building.

### test_yandex_engine.py (223 LOC)

**Purpose:** `src/search/engines/yandex.py`: self-link filter, block-URL detection, result building, two fixture-driven regressions.

### test_google_engine.py (142 LOC)

**Purpose:** `src/search/engines/google.py`: result building, source-level guard for the snippet selector, URL resolution against a loopback fixture server.

### test_google_goto_drops.py (143 LOC)

**Purpose:** `src/search/engines/google.py` redirect resolution: drop-reason counting, timeout and request-error classification, diagnosis attachment.

### test_cache.py (47 LOC)

**Purpose:** `src/search/cache.py`: cache write/read round trip and engine-pool formatting.

### test_merge.py (77 LOC)

**Purpose:** `src/search/merge.py`: per-engine pool entries and engine-position annotation.

### test_pool_cap.py (74 LOC)

**Purpose:** `src/search/search_web.py` fixed per-engine pool cap.

### test_search_web_degraded_notice.py (233 LOC)

**Purpose:** `src/search/degraded_notice.py`: real recorded engine-run fixtures, threshold, drop-reason display, repair-line gate.

### test_query_logger.py (347 LOC)

**Purpose:** `src/search/query_logger.py`, per-engine timing, the search workflow's log shape, and the CLI drill-down via an isolated subprocess.

### test_scrape_logger.py (55 LOC)

**Purpose:** `src/scraper/scrape_logger.py` sidecar header content.

### test_index_scrapes.py (159 LOC)

**Purpose:** `src/scraper/index_scrapes.py`: sidecar resolution, collection file convention, missing-directory tripwire, rag-cli index paths.

### _camoufox_scrape_fakes.py (154 LOC)

**Purpose:** Shared Camoufox, page, and crawler fakes. Not collected by pytest.

### test_camoufox_scrape.py (201 LOC)

**Purpose:** `src/scraper/camoufox_scrape.py`: acquisition-error states, URL-split regression, markdown-conversion failure, document-status chain.

### test_camoufox_scrape_output.py (200 LOC)

**Purpose:** `src/scraper/camoufox_scrape.py`: calibration kwargs, config stamp, workflow logging, output format.

### test_camoufox_scrape_focus.py (87 LOC)

**Purpose:** `src/scraper/camoufox_scrape.py` no-focus-steal launch: plist patch and ignored default args.

### _chromium_scrape_fakes.py (47 LOC)

**Purpose:** Shared CDP launch-mechanics patch and fake result objects. Not collected by pytest.

### test_chromium_scrape.py (244 LOC)

**Purpose:** `src/scraper/chromium_scrape.py`: launch-error classification, acquisition errors, HTTP-error content preservation, content type, published time.

### test_chromium_scrape_facts.py (281 LOC)

**Purpose:** `src/scraper/chromium_scrape.py`: landed URL, logged fact fields, budget guard, teardown on every exit path, watchdog spawn.

### test_chromium_scrape_output.py (123 LOC)

**Purpose:** `src/scraper/chromium_scrape.py`: config stamp, output format, logged field set, launch mode.

### test_chromium_scrape_document_status.py (196 LOC)

**Purpose:** `src/scraper/chromium_scrape.py` document-status listener through the real acquisition machinery.

### test_chromium_process.py (214 LOC)

**Purpose:** `src/scraper/chromium_process.py`: self-launch mechanics, live crawl4ai flag-parity guard, profile pid parsing, orphan reaping.

### _seed_feeders_fakes.py (51 LOC)

**Purpose:** Shared fake HTTP client and XML/HTML payload builders. Not collected by pytest.

### test_seed_feeders_scope.py (104 LOC)

**Purpose:** `src/crawler/seed_feeders_scope.py`: URL normalization merge-versus-distinct boundary and scoping with dedup.

### test_seed_feeders_robots.py (123 LOC)

**Purpose:** `src/crawler/seed_feeders_robots.py`: directive parsing, fetch with a fake client, feeder workflow.

### test_seed_feeders_sitemap.py (261 LOC)

**Purpose:** `src/crawler/seed_feeders_sitemap.py`: sitemap parsing, nested index resolution, cycle guard, feeder workflow.

### test_seed_feeders_navtree.py (305 LOC)

**Purpose:** `src/crawler/seed_feeders_navtree.py`: payload detection, tree finding tiers, version union, feeder workflow.

### test_seed_feeders.py (55 LOC)

**Purpose:** Fixture-backed checks of the three seed feeders against the local fixture site.

### test_discovery.py (115 LOC)

**Purpose:** `src/crawler/discovery.py`: seed assembly and merge priority (pure) plus one fixture-backed run checked against ground truth.

### _pipe_scraper_fakes.py (83 LOC)

**Purpose:** Shared timestamp helper, fake crawler, and camoufox meta builder. Not collected by pytest.

### test_pipe_scraper_config.py (88 LOC)

**Purpose:** `src/crawler/pipe_scraper_config.py`: config stamp, live crawl4ai stealth wiring guard, fixed anti-bot posture, headed flag effect.

### test_pipe_scraper.py (250 LOC)

**Purpose:** `src/crawler/pipe_scraper*.py`: per-URL JSONL log, run-id sharing, request-start timing, exception tripwire record, landed URL.

### test_pipe_scraper_camoufox_engine.py (198 LOC)

**Purpose:** `src/crawler/pipe_scraper*.py` camoufox engine dispatch: defaults, record shape, acquisition-error and document-status pass-through.

### test_pipe_scraper_onward_links.py (199 LOC)

**Purpose:** `src/crawler/pipe_scraper_acquisition.py` and the report module: onward-link collection, file writing, summary wording.

### _proxy_pool_fakes.py (18 LOC)

**Purpose:** Shared event builders and job.md render helper. Not collected by pytest.

### test_proxy_pool.py (98 LOC)

**Purpose:** `src/news/engine/proxy_pool/janitor.py`: window stats and job.md counters.

### test_proxy_pool_retry.py (117 LOC)

**Purpose:** `src/news/engine/proxy_pool`: fetch backoff and per-source isolation of the backfill pool load.

### test_proxy_pool_sources.py (150 LOC)

**Purpose:** `src/news/engine/proxy_pool`: pool-source logging, grouping, job.md source section.

### test_proxy_pool_run_loop.py (117 LOC)

**Purpose:** `src/news/engine/proxy_pool/loop.py` across a refresh boundary: pool swap and state continuity.

### test_proxy_riding_abort.py (39 LOC)

**Purpose:** `src/news/engine/proxy_riding/abort.py`: stall abort writes no job.md when the reporter raises.

### test_dedup_exclude.py (120 LOC)

**Purpose:** `src/news/engine/dedup.py`: exclude-URL precedence and publication-date fallback.

### test_theblock_clean_pass.py (123 LOC)

**Purpose:** `src/news/clean_pass.py`: clean file write, bodyless URL union, raw files read-only.

### test_theblock_discover.py (213 LOC)

**Purpose:** `src/news/platforms/theblock/discover.py`: range selection and dispatch error paths.

### test_coindesk_timeline.py (50 LOC)

**Purpose:** `src/news/platforms/coindesk/timeline.py` article parsing: malformed body raises, article-less payload returns empty, recorded shape parsed, missing key raises.

### test_coindesk_cleanup_and_shards.py (44 LOC)

**Purpose:** Coindesk cleanup edge cases (missing heading or end anchor) and filtered discover loading (missing directory or year shard raises).

### test_proxy_pool_fetch.py (48 LOC)

**Purpose:** Proxy-pool single fetch: transport errors become failures, other exceptions propagate, status reasons.

### test_selector_hits.py (69 LOC)

**Purpose:** Selector-hit aggregation; selectors never reach search results; parse returns results with hits for google, bing, brave, yandex.

### test_search_web_select_engines.py (16 LOC)

**Purpose:** Engine selection: default set, case-insensitive names, unknown name raises.

### test_browser_lock_tripwires.py (46 LOC)

**Purpose:** Browser lock: stale-takeover warning, unreadable sidecar raises, atomic sidecar write.

### test_browser_osascript.py (43 LOC)

**Purpose:** Browser focus helpers log a warning once on failing osascript.

### test_death_pipe_tripwires.py (47 LOC)

**Purpose:** Death-pipe intervention-log write failure raises; removed-dir reflects the real outcome.

### test_coindesk_stop_date.py (41 LOC)

**Purpose:** `src/news/platforms/coindesk/discover.py` stop-date parsing: full, explicit delta, integer days, unparseable raises.

### test_log_janitor.py (108 LOC)

**Purpose:** `src/log_janitor.py` retention days: default and malformed-value behavior.

### test_search_control_flow_removals.py (116 LOC)

**Purpose:** Removed swallow handlers: engine extraction, diagnosis, brave polling and cache read raise on corrupt input; parse failures surface as a parse-error status.

### test_platform_optional_attributes.py (58 LOC)

**Purpose:** Platform protocol defaults, registered platforms' attribute values, and the scrape-only support check.

### test_drop_reporting.py (145 LOC)

**Purpose:** Dropped items are reported: frameless document responses, unreadable lock sidecars raise, malformed links, RSC rows and JSON-LD blocks.

## State
No module owns shared mutable state. `conftest.py` patches the browser-launch names per test via an autouse fixture, redirects the temp dir to a per-test path, and traps osascript calls. All other state is reset per test through `monkeypatch` and `tmp_path`. Gotchas: process-docs area tests.
