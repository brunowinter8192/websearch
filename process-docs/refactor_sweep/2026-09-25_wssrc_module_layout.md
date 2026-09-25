# wssrc: module layout of src/ and cli.py (2026-09-25)

Task: bring `src/` and `cli.py` to the module layout of the Code-Standards (section order, one orchestrator that only calls functions, INFRASTRUCTURE without side effects, stepdown order, absolute imports, shared constants in a config module, no private cross-module imports). Zero behaviour change. Starting point was the four-eyes list of 2026-09-25; every number below was re-measured with an own AST scan (helper scripts lived in a private `/tmp` directory, not kept).

## Measured before and after (src/ and cli.py)

| Check | Before | After |
|---|---|---|
| Section order wrong | 0 | 0 |
| Modules with a def but no marker (`rate_limiter.py`) | 1 | 0 |
| Statements after a marker instead of INFRASTRUCTURE (`bing.py` constants, `register(...)` in both platforms) | 6 | 0 |
| Modules with more than one orchestrator (`pipeline.py`, `seed_feeders.py`) | 2 | 0 |
| Orchestrators containing logic (loops, try, arithmetic, comprehensions, f-strings) | 38 (incl. classes) | 0 |
| Classes standing under the ORCHESTRATOR marker | 13 | 0 |
| Classes standing in INFRASTRUCTURE | 16 | 0 |
| Stepdown inversions (callee above all its callers) | 106 in 40 files | 1 (see below) |
| Underscore names imported across modules | 56 | 0 |
| Import-time side effects (`_limiters[...] = ...`, `ENGINES = {...Engine()...}`, `register(...)`, `sys.path.insert`, logging setup, `atexit.register`) | 14 sites | 0 |
| Default suite | 664 passed | 678 passed |

The remaining stepdown finding is inherent: `pipe_scraper.py` keeps its script adapter `run_cli` below the orchestrator `scrape_urls_workflow`, because the adapter calls the orchestrator (the `__main__` guard needs a script entry). `run_cli`, `_parse_args`, `_read_url_file` are therefore unreachable from the orchestrator by design. `death_pipe.spawn_watchdog` is the same shape: a library entry next to the script orchestrator `_watchdog_main`.

## Classification rule (asked for by Main, applies to all workers)

- A module that runs as a script, or that has one entry workflow executing several steps, gets exactly one ORCHESTRATOR function that only calls functions.
- A pure library module whose functions are separate entry points called from other modules gets only INFRASTRUCTURE and FUNCTIONS.
- Test modules are libraries of independent entry points: no ORCHESTRATOR.
- The `if __name__ == "__main__":` guard stays at file end as the entry line, with one call in it.
- Applied: the four-eyes list did not name 33 modules without orchestrator. Of these, 9 turned out to have exactly one public entry that runs several steps and got an orchestrator (`seed_feeders_navtree.resolve_navigation_tree`, `seed_feeders_sitemap.resolve_sitemap_urls`, `dedup.filter_new_entries`, `proxy_pool/box_lock.acquire`, `proxy_riding/metrics.compute_stats`, both platform `cleanup`, `browser_lock.acquire`, `death_pipe._watchdog_main`). 24 modules are libraries with several independent entries and stay without orchestrator (examples: `cache.py`, `snippet.py`, `browser.py`, `pipeline_support.py`, `scrape_logger.py`, `pipe_scraper_*` helpers). Judgement calls: `degraded_notice.prepend_degraded_notice` (two steps, one branch) and `proxy_key.proxy_key` (one step) were left as library entries.

## Decisions and reasons

### Engines: each engine module is the engine
Callers found before changing anything: `search_web.ENGINES` (instantiated 8 objects at import), `dev/tests` (`OpenAlexEngine()`, `GoogleEngine().search_with_reason`, `BraveEngine()`, `YandexEngine()`, mock engines with `.name` and `.search_with_reason` in `test_query_logger`, a `SimpleNamespace` engine in `test_search_control_flow_removals`), 10 `dev/search_pipeline` scripts (class imports and `engine.search(...)`), and string-based lookups (`importlib.import_module(f"src.search.engines.{name}")` in `selector_js_equivalence_check.py`, which only reads `_JS_PARSE` and therefore keeps working). A method on a class is not a module-level orchestrator, so every engine module now has a lowercase `name` constant plus one orchestrator function `search_with_reason(query, language, max_results, partial)`. `ENGINES` maps names to the modules themselves; the duck-typed use `engine.name` / `engine.search_with_reason` in `search_web` did not change, and mock engines in tests still fit. No engine object exists at import any more.
- The try/finally around the tab moved into `_search_and_close`, the old branching body into `_search_in_tab`. `new_tab` and `kill_tab` are still called through the engine module, because tests patch `google_mod.new_tab` / `kill_tab`.
- `BaseEngine` and its `search()` wrapper were deleted. Users of `search()` were two openalex tests (converted to `search_with_reason`: results with `pdf_url`, exception propagation) and dev scripts (now `(await engine.search_with_reason(...))[0]`).
- `scholar.py` follows the same shape although no production code imports it.
- Not fixed on purpose: `dev/search_pipeline/bee_probes/_acquire_probe_instrument.py` and `_branch_probe_instrument.py` iterate `rate_limiter._limiters` at start; limiters are now created lazily, so that snapshot lists only limiters used so far. Behaviour of those probes is not verified (they need live engines).

### Rate limits
The eight `_limiters[name] = RateLimiter(4, 60)` import-time registrations became one table `ENGINE_LIMITS` in `rate_limiter.py`; `get_limiter(name)` creates the limiter on first use from the table (default 10 / 60 s for unlisted names such as `google_scholar`). Equivalent in production because `search_web` imported every engine anyway. `get_limiter` lost its two optional parameters (no caller passed them). New test file covers the table.

### Platforms
`CoinDeskPlatform` and `TheBlockPlatform` are declarative data plus one-line delegates, not workflows: classes stay, no orchestrator. The `register(...)` import side effect is gone. `registry.py` lists the classes and `get(name)` instantiates the matching one (a new object per call; only `__main__` calls it, once). `__main__` no longer imports the platform packages for their side effect.

### Splitting modules that had several workflows
- `pipeline.py` became three modules with one orchestrator each: `pipeline.py` (`run_pipeline`), `discover_only.py`, `scrape_only.py`. Shared helpers went into `pipeline_support.py` under public names (`start_run`, `require_internet`, `master_list_path`, `build_ok_manifest_entries`, ...) because they are used by more than one module. The two log-line orders that differ (discover-only writes the marker before the completion line, the full run after) are kept as the original by calling `log_run_complete` and `write_marker` in the original order inside each orchestrator.
- `seed_feeders.py` became `robots_feeder.py`, `sitemap_feeder.py`, `navtree_feeder.py`. The identical try/except-to-not-ok-result shell is `run_guarded` in `seed_feeders_scope.py`, `base_url` moved next to it.
- `discovery.py` still calls the three feeder workflows; tests that patched `seed_feeders.httpx` now patch the feeder module (same global `httpx` object).

### Orchestrators with logic
Extraction only: loops, try blocks, arithmetic, comprehensions and f-strings moved into named helpers; the original bodies were moved, not rewritten. Sites: `search_web_workflow` (timing via `_timed` / `_elapsed_ms`, fan-out with browser cleanup in `_fanout_with_browser`), `discover_urls_workflow`, `scrape_urls_workflow`, `run_loop` (loop in `_drain_queue`), `load_backfill_pool` (source order kept 1:1 through `_try_roosterkid_sources` / `_try_bare_txt_sources`, which look the fetcher up at call time so patches keep working), `load_monosans_proxies`, `fetch_url`, `scrape_entries_proxy`, `scrape_entries`, `scrape_entries_riding`, `run_riding_pool`, coindesk `browser_load_feed` and `discover`, theblock `discover`, `scrape_url_chromium_workflow`, `scrape_url_camoufox_workflow` (shared `utc_timestamp`, `domain_of`, `elapsed_ms` in `scrape_logger.py`), `index_scrapes_workflow`, `death_pipe._watchdog_main`, `src/news/__main__.main`. `box_lock.acquire` is now a plain function returning the context manager `_held_lock` (the generator with try/finally could not be an orchestrator).
Classes that stood under the ORCHESTRATOR marker (`Janitor`, `AcquireLogger`, both cooldown managers, and the engine classes) are stateful objects, not workflows: they moved to FUNCTIONS.

### cli.py
- The `sys.path.insert` is gone: running `python cli.py` puts the script directory on `sys.path[0]` (checked in a sandbox from another cwd and through a symlink; help output identical to the `integration` version).
- Logging setup and `atexit.register` moved from INFRASTRUCTURE into `configure_logging()` and `register_exit_hook()`, the first two calls of `main`. This was safe only after measuring that no `src` module emits a log record at import time (imported every `src` module with a root capture handler: 0 records). Consequence: importing `cli` no longer writes to `src/logs/cli.log` and no longer registers the exit hook. `get_retention_days()` (raises on a malformed value) now runs at the start of `main` instead of at import; same traceback either way.
- Old process-docs of this area say "logging before src imports"; that ordering rule no longer holds and the root DOCS.md was changed accordingly.
- Proof: `--help`, `-h` and no argument of the CLI and its 5 subcommands plus an unknown subcommand give identical output and exit code 2 against a `git archive integration` copy; `index_scrapes` with a missing collection and the `.pdf` shortcut give identical output.

## Shared constants (`src/config.py`)
Moved: `PROJECT_ROOT`, `LOG_DIR`, `NEWS_DATA_ROOT`, `CDP_PORT_WAIT_TIMEOUT_S`, `FOCUS_STEAL_POLL_INTERVAL_S` (search/browser.py and scraper/chromium_process.py), `BACKFILL_TOTAL`, `XML_MARKERS` (proxy_pool/fetch.py and theblock/discover.py), `PROXY_LIST_FETCH_TIMEOUT` (monosans_loader.py and pool_loaders.py), `PROXY_TS_FMT` (box_lock.py and janitor.py), `REGWALL_SIGNALS` (coindesk config and riding fetch: same list), `RAW_SUBDIR`, `DELAY_BEFORE_HTML`, `FAIL_THRESHOLD` (were imported from `proxy_riding/state.py` by fetch, rider and metrics).
Left on purpose:
- `DEFAULT_LOG_PATH` in three logger modules: same name, three different files.
- `_TS_FMT` in `browser_lock.py`: different format (with microseconds).
- `FETCH_TIMEOUT = 15` in `proxy_pool/fetch.py`: a fetch through a proxy, not the proxy-list download, so different meaning although the same number.
- `STALL_TIMEOUT_S` in `proxy_pool/loop.py` (3600) and `proxy_riding/state.py` (3600.0): two independent loops, tuned separately.
- `PAGE_TIMEOUT_MS`: 15000 versus 8000.
- `SCRAPE_CONFIG` in both platform configs: separate instances of one dataclass.
- `SEARCH_URL`, `MAX_WAIT_CYCLES`, `WAIT_INTERVAL` and the `_JS_*` strings in the engines: per-engine values with equal names.
- `ABSENT_STATUSES`, `HTTP_TIMEOUT_S`, `USER_AGENT` in `seed_feeders_constants.py` and the `pipe_scraper_constants.py` values: these two modules already are the dedicated shared-constants modules of their group; renaming them to `config.py` was not done.
- Per-platform `config.py` files stay (single-platform constants shared by several modules of that platform).

## Deduplication
- `_extract_value` (7 engines and the coindesk browser module) is `extract_value` in `src/cdp_value.py`. It sits at `src/` level, not in `src/search/`, because `src/news/` is documented as self-contained and must not import search code. The seven parametrized engine tests for it became two tests on the shared function (652 instead of 664 before other additions).
- `_terminate_then_kill` existed in `search/browser.py` (no return value) and `death_pipe.py` (returns the killed pids). One public `death_pipe.terminate_then_kill` remains; `browser.py` ignored the return value, so behaviour is the same. Three duplicate tests of the browser copy were dropped (`test_death_pipe.py` covers the same three cases). `browser.py` lost its now unused `psutil` import.
- `_build_ok_manifest_entries` and the same comprehension inside `scrape_job._scrape_one_chunk` are now one `pipeline_support.build_ok_manifest_entries`.

## Private names imported across modules
38 names renamed by script (definition, importers, `module._name` attribute uses, `setattr(module, "_name")` string targets) in `src/`, `dev/tests/` and dev scripts: pipe_scraper helpers, riding fetch/abort/plots/metrics, coindesk `append_to_shard`, chromium_process, `url_slug`, `url_to_filename`, snippet helpers, `_prepend_degraded_notice`, the news `pipeline_support` / `scrape_job` / `clean_pass` names. The renaming script skipped files that define the same name themselves; `browser.py` keeps its own private `_resolve_chromium_bundle_path` / `_wait_for_devtools_port` (they are not the chromium_process ones). Check afterwards: every `from src... import name` in `src/`, `dev/` and `dev/tests/` was resolved by importing the module (1 broken import found and fixed: `google_selector_probe.py` used the removed engine `_extract_value`).

## Stepdown, class placement
Done by a tool, not by hand: per module it rebuilt the FUNCTIONS section as a depth-first order from the orchestrator (callees directly below their first caller), moved classes out of INFRASTRUCTURE into FUNCTIONS, and refused to write when a decorator, default argument or base class needed a name that would then stand below it. Proof per file: the sorted multiset of `ast.dump` of all top-level statements (except an added `from __future__ import annotations`) is equal before and after; the tool aborts otherwise. Over 50 files were reordered, none aborted. Where a class is used in annotations of functions above it, the module got `from __future__ import annotations` (`platform.py`, `seed_feeders_scope.py`, `index_scrapes.py`, `browser_lock.py`, and others); this only makes annotations lazy strings.
A mid-class `# FUNCTIONS` marker in `proxy_riding/cooldown.py` (the marker line sat between two methods of one class) was carried along by the tool and removed by hand.

## Tests
- Baseline 664 passed (default suite). After: 678 passed. Delta: -12 (parametrized `_extract_value` tests) -3 (browser terminate tests) -0 (openalex wrapper tests rewritten one to one) +29 new.
- New test files: `test_rate_limiter_limits.py`, `test_coindesk_browser_feed.py` (fakes for Chrome, tab, httpx; checks the returned triples and that tab, chrome, port kill and temp dir cleanup run on each path), `test_news_entrypoints.py` (registry lookup and error text, timeframe handling, date-filter exclusion, discover-only and scrape-only early exits), `test_cli_bootstrap.py`.
- Edited existing tests (only because a rename or reshape forced it): riding tests (`RAW_SUBDIR` import, `fetch_one_url` patch target), `test_platform_optional_attributes.py` (preamble moved to `scrape_only`), `test_theblock_clean_pass.py`, seed feeder tests, engine tests, `test_browser.py`, chromium tests and `conftest.py` / `_chromium_scrape_fakes.py` (patch names of `chromium_scrape`), `test_index_scrapes.py`, `test_pipe_scraper.py`, `test_death_pipe*.py`, `test_search_web_degraded_notice.py`, `test_search_control_flow_removals.py`.
- Hazard seen: a monkeypatch on a string name of a moved function is not found by a rename; run the whole suite after each rename step. `dev/tests/run_strands.sh` uses a fixed `/tmp/websearch_strands` output directory; two workers running it at once would overwrite each other's logs. I ran `pytest -n 8` with a private `--basetemp` instead.

## Dev files touched (Main asked for the callers of renamed or reshaped names)
`dev/search_pipeline/`: `01_google_smoke.py`, `04_ddg_smoke.py`, `05_search_smoke.py`, `08_scholar_smoke.py`, `09_openalex_smoke.py`, `12_max_results_probe.py`, `13_free_word_probe.py`, `no_google_burst_smoke.py`, `domain_probes/19_books_probe.py`, `domain_probes/20_docs_probe.py`, `google_selector_probe.py`. None was run (they need live engines); verified only by pyflakes and by resolving every import. `dev/tests/DOCS.md`: four new entries and corrected LOC headings.

## Findings noticed, not touched
- `src/news/engine/proxy_riding/rider.py` imports `os` without using it; `src/search/browser.py:248` has an unused `global _browser`.
- `dev/search_pipeline/browser_probes/27_...` and `29_...` reference an undefined `_longest_clean_run` (pre-existing).
- The three `sha256(url)[:12]` implementations (news scrape, riding scrape, riding fetch) and the timestamp `strftime` in `cli.py` and `search_web.py` are duplicates outside the named findings.
- Shebang lines stay (recorded decision).

## Lessons for a successor
- Re-measure with a scan that skips annotations: `-> X | None` shows up as an arithmetic operation in a naive orchestrator check and produced about 25 false positives.
- Do the reshaping before the mechanical reorder; the reorder tool is only safe on code that already has its final function set.
- A contextmanager cannot be an orchestrator with a `yield` in try/finally; return the decorated inner function instead.
- Before removing a class in favour of a module, list what tests and scripts do with it (instantiation, `.search`, attribute patches, mock objects); the duck-typed use in `search_web` is what made the module-as-engine shape a small change.
