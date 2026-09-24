# dev/tests/

## Role
The project's pytest suite. Regression coverage for `src/search/`, `src/scraper/`, `src/crawler/`, `src/news/` (proxy_pool, proxy_riding/abort, theblock, coindesk/timeline, dedup, clean_pass) and `src/log_janitor.py`. I/O boundaries are mocked per test and production logic runs for real; `conftest.py` fails any test that reaches a real browser launch unmocked. Exceptions: fixture-backed sections (loopback only) and the brave/yandex engine tests (headless Chrome on loopback). Touch when test coverage changes; not when production behavior changes without an assertion needing to change.

## Public Interface
`__init__.py` is empty. Collected via `pytest` from the repo root (`pytest.ini`: `testpaths = dev/tests`, `pythonpath = .`). Files named `_*_fakes.py` and `_browser_fakes.py` are shared helpers, not collected.

## Flow
Synthetic or captured inputs (JSON items, HTML fixtures, monkeypatched clients) go into the real function under test, and assertions read its real output (parsed results, rendered markdown, JSONL records). `tmp_path` and `monkeypatch` isolate filesystem and environment per test.

## Modules

### conftest.py (27 LOC)

**Purpose:** Suite-wide autouse tripwire: every real browser-launch primitive is replaced by a failing stand-in, so an unmocked launch fails the test by name.
**Calls out:** src.search.browser, src.scraper.chromium_scrape, src.scraper.camoufox_scrape, src.crawler.pipe_scraper.

### _browser_fakes.py (23 LOC)

**Purpose:** Shared FakeChrome and state-reset helper for the browser lifecycle tests. Not collected by pytest.
**Called by:** test_browser.py, test_browser_get_tab.py.

### test_browser.py (360 LOC)

**Purpose:** src/search/browser.py: PID snapshot/kill mechanics, session-dir cleanup, watchdog cancellation, kill_own_chrome teardown, focus-steal watchdog branches.

### test_browser_get_tab.py (219 LOC)

**Purpose:** src/search/browser.py get_tab(): critical-section ordering, self-launch arguments, fresh profile per run, failure cleanup.

### test_browser_lock.py (81 LOC)

**Purpose:** src/search/browser_lock.py against real flock: immediate acquire, blocking until release, stale takeover.

### test_death_pipe.py (131 LOC)

**Purpose:** src/death_pipe.py: real spawned watchdog subprocess plus mocked terminate/kill logic.

### test_document_status.py (77 LOC)

**Purpose:** src/search/document_status.py: CDP response listener filtering and the pure merge into a diagnosis snapshot.

### test_bing_engine.py (77 LOC)

**Purpose:** src/search/engines/bing.py: _clean_url redirect unwrap, _build_results, _parse_results error propagation.

### test_brave_engine.py (384 LOC)

**Purpose:** src/search/engines/brave.py: fixture-driven regression tests (marker reflection, challenge solving, partial facts on cancellation) against a real headless pydoll Chrome on loopback.
**Calls out:** pydoll.browser, pydoll.commands.

### test_brave_build_results.py (30 LOC)

**Purpose:** src/search/engines/brave.py _build_results: field mapping, url-less items skipped, max_results cap.

### test_mojeek_engine.py (236 LOC)

**Purpose:** src/search/engines/mojeek.py: ALTCHA plumbing, parse-readiness rule, scripted-tab _await_results paths, _diagnose contract.

### test_openalex_engine.py (233 LOC)

**Purpose:** src/search/engines/openalex.py: pdf_url extraction and threading, HTTP-status diagnosis branches, request params, BaseEngine.search delegation.

### test_startpage_engine.py (30 LOC)

**Purpose:** src/search/engines/startpage.py: _build_results.

### test_yandex_engine.py (220 LOC)

**Purpose:** src/search/engines/yandex.py: self-link filter, block-URL detection, _build_results, two fixture-driven regression tests.
**Calls out:** pydoll.browser, pydoll.commands.

### test_google_engine.py (142 LOC)

**Purpose:** src/search/engines/google.py: _build_results, source-level guard for the snippet selector, _resolve_urls against a loopback fixture server.

### test_google_goto_drops.py (147 LOC)

**Purpose:** src/search/engines/google.py redirect resolution: drop-reason counting, timeout/request-error classification, diagnosis attachment.
**Calls out:** dev.search_pipeline._google_fixture.

### test_cache.py (47 LOC)

**Purpose:** src/search/cache.py: cache_write/cache_read round trip and format_engine_pool.

### test_merge.py (77 LOC)

**Purpose:** src/search/merge.py build_engine_pools: per-engine entries and engine_positions annotation.

### test_pool_cap.py (74 LOC)

**Purpose:** src/search/search_web.py _cap_pools: fixed per-engine cap.

### test_search_web_degraded_notice.py (233 LOC)

**Purpose:** src/search/degraded_notice.py: real recorded engine_run fixtures, threshold, drop_reason display, repair-line gate.

### test_query_logger.py (327 LOC)

**Purpose:** src/search/query_logger.py, _engine_with_timing, search_web_workflow log shape, and cli.py _log_drilldown via an isolated subprocess.

### test_scrape_logger.py (55 LOC)

**Purpose:** src/scraper/scrape_logger.py write_sidecar header content.

### test_index_scrapes.py (159 LOC)

**Purpose:** src/scraper/index_scrapes.py: sidecar resolution, collection file convention, missing-directory tripwire, rag-cli index paths.

### _camoufox_scrape_fakes.py (154 LOC)

**Purpose:** Shared Camoufox, page and crawler fakes. Not collected by pytest.
**Called by:** test_camoufox_scrape.py, test_camoufox_scrape_output.py.

### test_camoufox_scrape.py (201 LOC)

**Purpose:** src/scraper/camoufox_scrape.py try_scrape_camoufox: acquisition-error states, urlsplit regression, markdown-conversion failure, document-status chain.

### test_camoufox_scrape_output.py (197 LOC)

**Purpose:** src/scraper/camoufox_scrape.py: calibration kwargs and config stamp, scrape_url_camoufox_workflow logging, output format.

### test_camoufox_scrape_focus.py (87 LOC)

**Purpose:** src/scraper/camoufox_scrape.py no-focus-steal launch: LSUIElement plist patch and ignore_default_args.

### _chromium_scrape_fakes.py (43 LOC)

**Purpose:** Shared CDP launch-mechanics patch and fake result objects. Not collected by pytest.
**Called by:** test_chromium_scrape.py, test_chromium_scrape_facts.py, test_chromium_scrape_output.py, test_chromium_scrape_document_status.py.

### test_chromium_scrape.py (244 LOC)

**Purpose:** src/scraper/chromium_scrape.py: launch-error classification, acquisition errors, HTTP-error content preservation, content_type, og_published_time.

### test_chromium_scrape_facts.py (281 LOC)

**Purpose:** src/scraper/chromium_scrape.py: landed_url, logged fact fields, budget guard, teardown on every exit path, death_pipe watchdog spawn.

### test_chromium_scrape_output.py (123 LOC)

**Purpose:** src/scraper/chromium_scrape.py: config stamp, output format, logged field set, launch_mode.

### test_chromium_scrape_document_status.py (196 LOC)

**Purpose:** src/scraper/chromium_scrape.py before_goto document-status listener through the real acquisition machinery.

### test_chromium_process.py (214 LOC)

**Purpose:** src/scraper/chromium_process.py: self-launch mechanics, live crawl4ai flag-parity guard, profile pid parsing, orphan reaping.

### _seed_feeders_fakes.py (51 LOC)

**Purpose:** Shared fake httpx client and XML/HTML payload builders. Not collected by pytest.
**Called by:** test_seed_feeders_robots.py, test_seed_feeders_sitemap.py, test_seed_feeders_navtree.py.

### test_seed_feeders_scope.py (104 LOC)

**Purpose:** src/crawler/seed_feeders_scope.py: normalize_url merge-vs-keep-distinct boundary and scope_and_dedup.

### test_seed_feeders_robots.py (123 LOC)

**Purpose:** src/crawler/seed_feeders_robots.py: directive parsing, fetch with a fake client, feeder workflow.

### test_seed_feeders_sitemap.py (261 LOC)

**Purpose:** src/crawler/seed_feeders_sitemap.py: sitemap parsing, nested index resolution, cycle guard, feeder workflow.

### test_seed_feeders_navtree.py (305 LOC)

**Purpose:** src/crawler/seed_feeders_navtree.py: payload detection, tree finding tiers, version union, feeder workflow.

### test_seed_feeders.py (55 LOC)

**Purpose:** Fixture-backed checks of the three seed feeders against the local fixture site.
**Calls out:** dev.url_discovery._fixture_site.

### test_discovery.py (115 LOC)

**Purpose:** src/crawler/discovery.py: seed assembly and merge priority (pure), plus one shared fixture-backed discovery run checked against ground truth.
**Calls out:** dev.url_discovery._fixture_site.

### _pipe_scraper_fakes.py (49 LOC)

**Purpose:** Shared timestamp helper, fake crawler and camoufox meta builder. Not collected by pytest.
**Called by:** test_pipe_scraper.py, test_pipe_scraper_camoufox_engine.py, test_pipe_scraper_onward_links.py.

### test_pipe_scraper_config.py (88 LOC)

**Purpose:** src/crawler/pipe_scraper_config.py: config stamp, live crawl4ai stealth wiring guard, fixed anti-bot posture, headed flag effect.

### test_pipe_scraper.py (248 LOC)

**Purpose:** src/crawler/pipe_scraper*.py: per-URL JSONL log, run_id sharing, request-start timing, exception tripwire record, landed_url.

### test_pipe_scraper_camoufox_engine.py (196 LOC)

**Purpose:** src/crawler/pipe_scraper*.py camoufox engine dispatch: defaults, record shape, acquisition_error and document-status-chain pass-through.

### test_pipe_scraper_onward_links.py (199 LOC)

**Purpose:** src/crawler/pipe_scraper_acquisition.py and pipe_scraper_report.py onward-link collection, file writing and summary wording.

### _proxy_pool_fakes.py (18 LOC)

**Purpose:** Shared event builders and job.md render helper. Not collected by pytest.
**Called by:** test_proxy_pool.py, test_proxy_pool_sources.py.

### test_proxy_pool.py (98 LOC)

**Purpose:** src/news/engine/proxy_pool/janitor.py: window stats and job.md counters.

### test_proxy_pool_retry.py (117 LOC)

**Purpose:** src/news/engine/proxy_pool: fetch_with_retry backoff and load_backfill_pool per-source isolation.

### test_proxy_pool_sources.py (150 LOC)

**Purpose:** src/news/engine/proxy_pool: pool-source logging, grouping, job.md source section.

### test_proxy_pool_run_loop.py (117 LOC)

**Purpose:** src/news/engine/proxy_pool/loop.py run_loop across a refresh boundary: pool swap and state continuity.

### test_proxy_riding_abort.py (39 LOC)

**Purpose:** src/news/engine/proxy_riding/abort.py: _abort_stall writes no job.md when the reporter raises.

### test_dedup_exclude.py (120 LOC)

**Purpose:** src/news/engine/dedup.py filter_new_entries exclude_urls precedence and pub_date_str fallback.

### test_theblock_clean_pass.py (123 LOC)

**Purpose:** src/news/clean_pass.py _run_clean_pass: clean file write, bodyless URL union, raw files read-only.

### test_theblock_discover.py (213 LOC)

**Purpose:** src/news/platforms/theblock/discover.py: sub:A-B range selection and dispatch error paths.

### test_coindesk_timeline.py (50 LOC)

**Purpose:** src/news/platforms/coindesk/timeline.py parse_articles: malformed body raises, article-less payload returns [], recorded shape parsed, missing required key raises, alternative date keys not accepted.

### test_coindesk_cleanup_and_shards.py (44 LOC)

**Purpose:** coindesk cleanup (no H1 returns empty and logs, missing end anchor logs) and load_discover_filtered (missing directory / year shard raise).

### test_proxy_pool_fetch.py (48 LOC)

**Purpose:** proxy_pool fetch_url: transport errors become fail with the exception class name, non-transport exceptions propagate, status reasons.

### test_coindesk_stop_date.py (27 LOC)

**Purpose:** src/news/platforms/coindesk/discover.py _parse_stop_date: full, explicit delta, integer days, unparseable value raises.

### test_log_janitor.py (92 LOC)

**Purpose:** src/log_janitor.py get_retention_days: default and malformed-value behavior.

## State
No module owns shared mutable state. `conftest.py` patches four browser-launch names per test through an autouse fixture; every other state (module globals of the code under test, environment variables, log paths) is reset per test through `monkeypatch` and `tmp_path`.

## Gotchas
- Any test that resolves the repo root through `Path(__file__).parent...` breaks silently when the directory moves.
- `test_brave_engine.py` and `test_yandex_engine.py` run a real headless Chrome and patch `brave.py`/`yandex.py` `new_tab`/`kill_tab` directly, so `conftest.py`'s trap never fires for them. Two brave tests have failed intermittently in full-suite runs; details in `process-docs/refactor_sweep/`.
