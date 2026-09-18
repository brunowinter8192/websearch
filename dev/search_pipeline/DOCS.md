# dev/search_pipeline/

## Role
Smoke tests, selector-drift probes, ranking-method eval harness, and bee-investigation instrumentation for `src/search/`. Own-level scripts range from per-engine production smokes (`0N_*_smoke.py`) to multi-stage pooling/reranking evals (`stage1..4_*`, `value_eval_*`) to one-off debugging probes (`cdp_starvation_probe.py`, `branch_probe.py`, `acquire_probe.py`). `_lib/` (own DOCS.md) holds shared parse/text helpers. `inspections/` (own DOCS.md, different level) holds DOM-selector-drift tooling.

## Modules

### 00_single_query.py (140 LOC)

**Purpose:** Single-query debug runner — reuses `01_google_smoke.py` internals (`load_config`, `start_browser`, JS patches, consent-cookie injection) via `importlib` to hit one query and print DOM diagnostics (title, current URL) to stdout.
**Reads:** `config.yml`, query from `sys.argv[1]` (default `"python asyncio best practices"`).
**Writes:** stdout only.
**Called by:** CLI only. `./venv/bin/python3 dev/search_pipeline/00_single_query.py "your query here"`.
**Calls out:** `pydoll` (Chrome, PageCommands, NetworkCommands, CookieSameSite).

### 01_google_smoke.py (125 LOC)

**Purpose:** Google production-mode smoke — `GoogleEngine().search()` per query from `queries.txt`, rate-limiter active. Status OK/EMPTY.
**Reads:** `queries.txt`.
**Writes:** `md/google_smoke_<ts>.md`.
**Called by:** CLI only; also imported by `_capture_sorry.py` and `00_single_query.py` for shared helpers (`load_config`, `start_browser`, `_build_js_patches`, `_inject_consent_cookie`, `_extract_scalar`).
**Calls out:** `src.search.engines.google.GoogleEngine`, `src.search.browser.close_browser`.

### 02_burst_smoke.py (263 LOC)

**Purpose:** Burst smoke against the production CLI — invokes `cli.py search_batch` per batch (one subprocess per N queries, warm Chrome amortized). Validates the prod CLI path under the burst rate pattern.
**Reads:** `config.yml` (`queries_file`, `report.output_dir`), `queries.txt`.
**Writes:** `<config report.output_dir>/burst_<ts>.md` (config-driven, currently `md/`).
**Called by:** CLI only. Flags: `--queries-per-burst N` (default 4), `--cooldown S` (default 60), `--max-queries N`.
**Calls out:** `cli.py` (subprocess), `yaml`.

### 04_ddg_smoke.py (125 LOC)

**Purpose:** DuckDuckGo production-mode smoke — same pattern as `01_google_smoke.py` via `DuckDuckGoEngine`.
**Reads:** `queries.txt`.
**Writes:** `md/ddg_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.duckduckgo.DuckDuckGoEngine`, `src.search.browser.close_browser`.

### 05_search_smoke.py (218 LOC)

**Purpose:** Multi-engine comparison smoke — imports the remaining 4 browser/HTTP engine classes (google, duckduckgo, google scholar, openalex), fans out per-engine in parallel (`asyncio.gather`), merges by URL preserving per-engine snippets (bypasses `_merge_and_rank`).
**Reads:** `queries.txt`.
**Writes:** `md/search_smoke_<ts>.md`.
**Called by:** CLI only. Flags: `--engines` (default: google duckduckgo), `--max-queries N`.
**Calls out:** `src.search.browser.close_browser`, `src.search.engines.{google,duckduckgo,scholar,openalex}`, `src.search.result.SearchResult`.

### 08_scholar_smoke.py (134 LOC)

**Purpose:** Google Scholar production-mode smoke — `ScholarEngine().search()` per query (pydoll browser, engine-internal rate limiter). Status taxonomy: OK (≥3 results) / EMPTY / SUSPECT / ERROR.
**Reads:** `queries.txt`.
**Writes:** `md/scholar_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.scholar.ScholarEngine`, `src.search.browser.close_browser`.

### 09_openalex_smoke.py (121 LOC)

**Purpose:** OpenAlex smoke — `OpenAlexEngine().search()` per query (pure HTTP, no browser). Status taxonomy: OK / EMPTY / RATE_LIMITED / ERROR. Optional `OPENALEX_API_KEY` env var is picked up by the engine itself (no forwarding logic in this script).
**Reads:** `queries.txt`.
**Writes:** `md/openalex_smoke_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.openalex.OpenAlexEngine`.

### 11_pipeline_smoke.py (373 LOC)

**Purpose:** Full-pipeline smoke — calls `search_web_workflow(query, _with_timings=True, engine_timeout=N)` per query (unlike `05`'s per-engine fanout, this goes through `_merge_and_rank`). Produces the singular baseline consumed by downstream investigation scripts (`snippet_quality_analysis.py`, `engine_distribution_analysis.py`, `snippet_selection_simulator.py`). Per-URL block: title/URL/engines + chosen `source`/`display` + `og`/`meta` + per-engine snippets. Per-query timing + slot-fill line. Per-Engine Status Aggregate section at end — `_STATUS_HINTS` and the reliability table's `STATUS_KEYS` dropped their 5 EMPTY_* sub-status entries (removed along with `src/search/status.py`'s guessed verdicts) and gained a plain `EMPTY` key, tracked explicitly so it is not miscounted into `ERROR_OTHER` by the fallback bucket.
**Reads:** `queries.txt`, cache via `cache_key`/`cache_read`.
**Writes:** `md/pipeline_smoke_<ts>.md`.
**Called by:** CLI only. Flags: `--max-queries N`, `--language` (default `en`), `--engine-timeout N` (float seconds, per-engine watchdog).
**Calls out:** `src.search.browser.close_browser`, `src.search.cache`, `src.search.search_web.search_web_workflow`.

### 12_max_results_probe.py (173 LOC)

**Purpose:** Per-engine single-call ceiling probe — direct engine instantiation, one call per query at high `max_results` (Google/Scholar 100, others 200), observes actual returned count + latency + status.
**Reads:** hardcoded 3-query set.
**Writes:** `md/max_results_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,scholar,duckduckgo,openalex}`, `src.search.browser.close_browser`.

### 13_free_word_probe.py (289 LOC)

**Purpose:** Free-word query injection probe — appends `pdf`/`book` (no operator) to query string, measures domain-distribution shift across the 4 remaining engines. 3 queries × 3 variants (baseline/+pdf/+book).
**Reads:** hardcoded 3-query set.
**Writes:** `md/free_word_injection_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,scholar,duckduckgo,openalex}`, `src.search.browser.close_browser`.

### 13_timing_ablation.py (348 LOC)

**Purpose:** Timing-config ablation — A (status-quo) vs B (aggressive Scholar polling/consent sleep/HTTP rate-limit) via concurrent fan-out across the 4 remaining engines. 3 queries × 2 configs, 2-min cooldown between configs.
**Reads:** hardcoded 3-query set.
**Writes:** `md/timing_ablation_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,scholar,duckduckgo,openalex}` (monkeypatched via module import), `src.search.browser.close_browser`, `src.search.rate_limiter`.

### 14_download_classify_probe.py (605 LOC)

**Purpose:** Download-classify probe — sniff-classifies academic URLs from search pool without saving content. Tier-1 domain transforms (arxiv/aclanthology/openreview/pmc), per-Tier timeout, classifies outcome (PDF_OK/HTML_OK/HTML_HAS_PDF_LINK/HTML_PAYWALL/HTTP_4xx etc.). `doi.org` sampled to 300 (seed=42).
**Reads:** newest `pipeline_smoke_*.md` + `free_word_injection_probe_*.md` from `md/` (glob-discovered).
**Writes:** `md/download_classify_<ts>.md`, `txt/pool_<ts>.txt`, `txt/pool_doi_sample_<ts>.txt`.
**Called by:** CLI only.
**Calls out:** `httpx`.

### 15_citation_pdf_followup.py (446 LOC)

**Purpose:** Two-hop `citation_pdf_url` validation — loads HTML_HAS_PDF_LINK URLs from probe 14's report, GETs each (Hop 1 extracts `citation_pdf_url` meta), GETs the extracted PDF URL (Hop 2). Per-domain semaphore keyed on PDF-host domain.
**Reads:** `md/<SOURCE_REPORT>` (hardcoded filename constant), `txt/<SOURCE_POOL>`.
**Writes:** `md/citation_pdf_followup_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

### 16_search_to_pdf_probe.py (495 LOC)

**Purpose:** End-to-end search-to-PDF chain probe — runs `search_web_workflow` directly, applies full chain (Tier-1 transform / DIRECT .pdf / MULTI_STEP citation_pdf_url / BLACKLIST), saves real PDFs to `~/Downloads/`. Regression check after `pdf_chain` refactors.
**Reads:** queries via CLI positional args.
**Writes:** `md/search_to_pdf_<ts>.md`, PDF files to `~/Downloads/`.
**Called by:** CLI only. Flags: `--top-n N`, queries as positional args.
**Calls out:** `src.scraper.pdf_chain` (HARD_BLACKLIST, TIER1_DOMAINS, apply_tier1_transform, is_blacklisted, is_github_blob, parse_citation_pdf_url), `src.search.browser.close_browser`, `src.search.merge.build_engine_pools`, `src.search.result.SearchResult`, `src.search.search_web` (`_query_engines_concurrent`, `_select_engines`), `httpx`.

### 19_books_probe.py (312 LOC)

**Purpose:** Empirical book-domain inventory — appends `book` to 12 broad queries, runs against Google/DDG (max 100/200). Raw domain-pool observation, no classification. Informs `--books` whitelist/blacklist design.
**Reads:** hardcoded 12-query set.
**Writes:** `md/books_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,duckduckgo}`, `src.search.browser.close_browser`.

### 20_docs_probe.py (455 LOC)

**Purpose:** Empirical docs-domain probe — appends `documentation` to 12 broad tech queries, runs against Google/DDG. Evaluates H1-H13 heuristics (docs subdomain, readthedocs, gitbook, /docs/, /api/, etc.) against the URL pool. Informs `--docs` whitelist/heuristic design.
**Reads:** hardcoded 12-query set.
**Writes:** `md/docs_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.engines.{google,duckduckgo}`, `src.search.browser.close_browser`.

### 24_pydoll_teardown_verify.py (302 LOC)

**Purpose:** Integration test for `kill_tab` teardown fix. T1: single hung tab (`about:blank` + never-resolving Promise, `await_promise=True`) through watchdog + `kill_tab` (wall ~ watchdog). T2: normal tab completes fine. T3: parallel batch of 5 hung tabs via `asyncio.gather` (mirrors production 5-engine fanout), verifies `Target.getTargets` delta=0 (no orphaned targets).
**Reads:** none (self-contained hang simulation).
**Writes:** `md/teardown_verify_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.browser` (via `importlib`), pydoll CDP (`Target.getTargets`).

### 25_startpage_probe.py (384 LOC)

**Purpose:** Go/no-go data probe for startpage.com scrapeability (self-contained — no `src/` import, dev-isolation guardrail). Drives the real homepage search form (load homepage, set `#q` via native setter + `input` event, real `.click()` on `button.search-btn`) to obtain a valid per-session `sc` token, then runs 10 queries (mainstream DE/EN, local-business DE, docs-style EN/DE) and records count/quality/block-marker per query.
**Reads:** none (live run against production startpage.com).
**Writes:** `md/startpage_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, TargetCommands) — inline copy of the `src/search/browser.py` session-setup shape, not a shared import.

### 26_brave_probe.py (378 LOC)

**Purpose:** Go/no-go 3-condition gate probe for Brave Search (self-contained — no `src/` import, dev-isolation guardrail): real result rows + no PoW/CAPTCHA + per-query wall latency ≤5s, run one query at a time (no gather-special-casing) via the pydoll stealth stack (`src/search/browser.py` shape, inlined). Runs 10 queries, detects PoW/CAPTCHA via title/body marker scan + `a[href*="pow-captcha"]` presence, records per-query latency. Result: DROP — 4/10 OK then persistent PoW block from query 5 onward.
**Reads:** none (live run against production search.brave.com).
**Writes:** `md/brave_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, TargetCommands) — inline copy of the `src/search/browser.py` session-setup shape, not a shared import.

### 27_brave_headed_lane_probe.py (387 LOC)

**Purpose:** Headed hard-engine lane probe (macOS) — tests whether a real Chrome window, backgrounded via `open -g` (no focus steal, isolated `--user-data-dir`), clears Brave's PoW/CAPTCHA where headless doesn't. Validates the `pydoll.browser.managers.BrowserProcessManager(process_creator=...)` override (`Chrome(options)` built, then `browser._browser_process_manager` swapped before `start()`) — `_open_process_creator` re-launches via `open -g -n -a "Google Chrome" --args --remote-debugging-port=<port> --user-data-dir=<isolated dir> ...`, teardown via CDP `browser.stop()` + unconditional `pkill` safety net (the `open` wrapper Popen gives pydoll's own reaper nothing real to kill). Result: DROP — only 2/10 clean before a persistent PoW block (worse than 26_brave_probe.py's 4/10 headless run), but the launch mechanism itself (headed-background + isolated profile + clean teardown, verified via `ps aux` showing zero orphaned processes) is validated and reusable for a future hard-engine candidate.
**Reads:** none (live run against production search.brave.com).
**Writes:** `md/brave_headed_lane_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager), macOS `open` CLI.

### 28_bing_probe.py (400 LOC)

**Purpose:** Go/no-go scrapeability probe for bing.com (self-contained — no `src/` import) as a SECOND, independent access path to the Bing web index, redundant to DuckDuckGo's surrogate coverage. Runs 10 queries via pydoll stealth stack, headless. Result: CANDIDATE — 10/10 OK, 0 blocks, median 691ms (fastest browser-scraped engine probed to date). Confirms the old `#b_results .b_algo` selector had NOT structurally drifted (still live); new handling need: every organic href is wrapped in a `bing.com/ck/a?...&u=<prefixed-base64>&...` tracking redirect, unwrapped via `_clean_url` (parse `u` param, strip 2-char prefix, base64url-decode with padding, graceful fallback to raw href on failure).
**Reads:** none (live run against production bing.com).
**Writes:** `md/bing_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, TargetCommands) — inline copy of the `src/search/browser.py` session-setup shape, not a shared import.

### 29_yandex_probe.py (400 LOC)

**Purpose:** Go/no-go scrapeability probe for yandex.com (self-contained — no `src/` import) as a genuine NEW-COVERAGE candidate — Yandex is one of the few remaining independent web indexes (own crawler), unlike Bing/Startpage which are redundancy paths to indexes already in the pool. Runs 10 queries via pydoll stealth stack, headless. Result: CANDIDATE under the relaxed criterion — 8/10 usable hits, longest consecutive clean run of 7, only 2 blocks (both with hard `showcaptcha` redirect-URL evidence, not just a text-marker guess). Confirms `li.serp-item` still live, `a.OrganicTitle-Link` gives a direct href (no unwrap needed, unlike Bing). Quality axis called honestly: German-query results genuinely relevant, not junk/region-skewed.
**Reads:** none (live run against production yandex.com).
**Writes:** `md/yandex_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, TargetCommands) — inline copy of the `src/search/browser.py` session-setup shape, not a shared import.

### 31_date_availability_probe.py (527 LOC)

**Purpose:** Measurement-only probe (no wiring) — for the 8 DOM-scraped web engines (google, duckduckgo, mojeek, startpage, brave, bing, yandex, lobsters), does the live result page carry a date, and how: dedicated element (`<time>`/class-matched), snippet-text-only, nowhere, or unmeasurable (block/CAPTCHA/empty)? Self-contained (no `src/` import, matches 25/26/28/29/30_*_probe.py) — inline copy of the current `src/search/browser.py` session shape + each engine's current navigation/wait/diagnose logic, so the probe keeps measuring even if `src/` changes later. One JS pass per container captures `<time>` elements, class/id tokens matching a WORD-BOUNDARY regex (`date|time|age|publish(ed)?|when|ago` — deliberately not a substring match, which would false-positive on `update`/`candidate`/`validate`), full container text, and an HTML head — covers the dedicated-element and snippet-text cases in one pass. 3 queries per engine (2 EN news-shaped + 1 DE reference/timeless, to avoid an English-news-only bias), self-imposed (not rate-limiter-derived, since this script never goes through `src/search/rate_limiter.py`) 20s gap between same-engine queries, MINUTES-scale (180s) cooldown before a one-shot retry only when an engine is non-OK on all 3 primaries — a short gap can't distinguish a probe-induced block from a pre-existing cooldown. `google`/`duckduckgo`/`brave` pre-flagged as having returned 0 results in an earlier unrelated session run, so a repeat non-OK is annotated rather than presented as fresh.
**Reads:** none (live run against production google/duckduckgo/mojeek/startpage/brave/bing/yandex/lobsters).
**Writes:** `md/date_availability_probe_<ts>.md` (raw per-engine evidence + hand-written classification section).
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, TargetCommands, NetworkCommands) — inline copy of the `src/search/browser.py` session-setup shape, not a shared import.

### _altcha_trigger_probe_cdp.py (75 LOC)

**Purpose:** Raw-CDP shadow-DOM helpers for `altcha_trigger_probe.py` — locates the widget node, reports its shadow-root mode, dispatches a coordinate-based click.
**Reads:** nothing (pure CDP session calls, `cdp` object passed in by the caller).
**Writes:** nothing (returns dicts/node IDs; the click is the one side effect, on the live page).
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** none beyond the CDP session object passed in (no imports beyond stdlib types).

### _altcha_trigger_probe_js.py (96 LOC)

**Purpose:** JS snippet constants/builders for `altcha_trigger_probe.py` — the widget-event init script plus the inspection/verify/outcome-detection strings.
**Reads:** nothing.
**Writes:** nothing (pure string builders).
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** none beyond stdlib (`json`).

### _altcha_trigger_probe_launch.py (95 LOC)

**Purpose:** Backgrounded-Chrome launch helpers for `altcha_trigger_probe.py` — an inline copy of `src/scraper/chromium_process.py`'s self-launch/watchdog shape, not a shared import.
**Reads:** nothing (pure subprocess/CDP-adjacent calls).
**Writes:** nothing directly — spawns/kills Chrome processes and an asyncio watchdog task as a side effect.
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** `patchright` (bundle resolution only), `crawl4ai.browser_manager.ManagedBrowser` (flag list), macOS `open`/`osascript`/`pkill`.

### _altcha_trigger_probe_report.py (259 LOC)

**Purpose:** Markdown report assembly for `altcha_trigger_probe.py`, split out of the main module to stay under the per-file LOC convention.
**Reads:** nothing (pure string assembly from the dataclass instances passed in).
**Writes:** `md/altcha_trigger_probe_<ts>.md` (via `write_report`).
**Called by:** `altcha_trigger_probe.py`.
**Calls out:** none beyond stdlib.

### _branch_probe_analysis.py (107 LOC)

**Purpose:** Per-query analysis for `branch_probe.py` — query loading, per-engine limiter snapshots, event-to-detail reduction, branch discriminator classification, smoke-mode diagnostic dump.
**Reads:** `queries.txt` path passed in; `_limiters` dict via `_branch_probe_instrument._rl_mod`.
**Writes:** stderr only (`_dump_smoke`, smoke mode).
**Called by:** `branch_probe.py`.
**Calls out:** `_branch_probe_instrument.py` (sibling, `_rl_mod`).

### _branch_probe_canary.py (76 LOC)

**Purpose:** Pattern B scheduling-latency canary for `branch_probe.py` — background sampling task, per-category percentile stats.
**Reads:** nothing (owns its own `_canary_samples` state).
**Writes:** nothing (returns stats dicts).
**Called by:** `branch_probe.py`, `_branch_probe_report.py`, `_branch_probe_findings.py`.
**Calls out:** none beyond stdlib.

### _branch_probe_findings.py (221 LOC)

**Purpose:** Narrative findings-doc assembly for `branch_probe.py` — fixed-path investigation writeup (hypothesis, instrumentation, verdict, next steps) at a stable filename overwritten each run.
**Reads:** nothing — takes the run's records and the sibling report's path as arguments.
**Writes:** `md/03_branch_probe.md` (path built from the `findings_dir` argument).
**Called by:** `branch_probe.py`.
**Calls out:** `_branch_probe_canary.py`, `_branch_probe_report.py` (siblings, `_canary_stats`/`_overall_verdict`).

### _branch_probe_instrument.py (68 LOC)

**Purpose:** `RateLimiter.acquire()` monkeypatch for `branch_probe.py` — full byte-identical replacement plus branch-discriminator event emission, installed at import time.
**Reads:** nothing (patches `src.search.rate_limiter.RateLimiter` at module import).
**Writes:** nothing directly — appends to its own `_acq_events`/`_pre_snapshots` lists as a side effect of the patched `acquire()`.
**Called by:** `branch_probe.py`, `_branch_probe_analysis.py`, `_branch_probe_report.py` (siblings).
**Calls out:** `src.search.rate_limiter` (monkeypatched via `importlib`, before any other `src.search` import).

### _branch_probe_report.py (207 LOC)

**Purpose:** Timestamped markdown report assembly for `branch_probe.py` — one section-builder helper per report section, plus the shared overall-verdict classifier.
**Reads:** nothing — takes the run's records and paths as arguments.
**Writes:** `md/branch_probe_<ts>.md` (path built from the `report_dir` argument).
**Called by:** `branch_probe.py`, `_branch_probe_findings.py` (`_overall_verdict`).
**Calls out:** `_branch_probe_canary.py` (sibling, `_canary_stats`), `_branch_probe_instrument.py` (sibling, `_acq_events`).

### _capture_sorry.py (233 LOC)

**Purpose:** Captures Google `/sorry/` block page — helper script, not a numbered experiment. Navigates to a search URL, checks if redirected to `/sorry/`, saves HTML + screenshot + MD summary.
**Reads:** `config.yml`.
**Writes:** `md/sorry_<ts>.md`, `html/sorry_<ts>.html`, `png/sorry_<ts>.png`.
**Called by:** CLI only.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, PageCommands, NetworkCommands, CookieSameSite), `yaml`. Imports `load_config`/`start_browser` pattern mirrored from `01_google_smoke.py` (not imported directly).

### _google_fixture.py (243 LOC)

**Purpose:** Local HTTP fixture for `src/search/engines/google.py`'s goto-redirect fix — a generated Google-shaped results page plus a `/goto?url=<token>` route table, parameterized per test.
**Reads:** nothing (in-memory specs passed to `start_fixture_server`).
**Writes:** nothing (serves HTTP responses; no disk output).
**Called by:** `dev/tests/test_google_engine.py`.
**Calls out:** none (stdlib `http.server`, `threading`, `dataclasses`, `urllib.parse` only — no `src.` import, per this directory's own import-hook restriction below).

### acquire_probe.py (588 LOC)

**Purpose:** Phase 2 bee investigation — `RateLimiter.acquire()` instrumentation probe. Monkey-patches `RateLimiter.__init__` (installs `_WatchedLock`) + `acquire()` (enter/exit events). Discriminates hypotheses B (task never scheduled) / A-lock (stale lock) / A-sleep (sleeping on backoff) / C (acquire innocent). Historical verdict (as of the investigation date, see process-docs): A-sleep confirmed. Query category renamed `"captcha"` → `"empty"` (the guessed-verdict-removal milestone collapsed `EMPTY_BLOCK` into bare `EMPTY`; `engine_details`, the only status source this probe reads, carries no diagnosis to reconstruct which kind of empty a query was — an honest narrower label over a familiar wrong one).
**Reads:** none (live instrumented run against production engines).
**Writes:** `md/acquire_probe_<ts>.md` (full run only; `--smoke` writes nothing).
**Called by:** CLI only. Flags: `--max-queries N`, `--smoke` (4-query dry-run, no report).
**Calls out:** `src.search.rate_limiter` (monkeypatched via `importlib`), full engine set via production search path.

### altcha_trigger_probe.py (392 LOC)

**Purpose:** M1 go/no-go probe — can Mojeek's ALTCHA challenge be started and completed by automation alone, via three isolated live trigger attempts?
**Reads:** none (live run against production mojeek.com + a neutral control URL).
**Writes:** `md/altcha_trigger_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `patchright` (browser launch/connect/control), `crawl4ai`/`crawl4ai.browser_manager` (flag-building only, no crawler use) — via `_altcha_trigger_probe_launch.py`; `_altcha_trigger_probe_cdp.py`, `_altcha_trigger_probe_js.py`, `_altcha_trigger_probe_report.py` (siblings, own entries above).

### bm25_capped_smoke.py (243 LOC)

**Purpose:** Per-engine top-K cap variant — pre-pool truncates each engine's results to top-K (K = google result count, fallback K=10), then BM25 vanilla on capped pool. 3-config compare: Hard-Slot, BM25 uncapped, BM25 capped.
**Reads:** imports `QUERIES`, `VANILLA_K1`, `_build_pool`, `_tokenize`, `_doc_repr`, `BM25Uniform` from `bm25_sweep_smoke.py`.
**Writes:** `md/bm25_capped_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py` (sibling), `rank_bm25`.

### bm25_compare_smoke.py (174 LOC)

**Purpose:** 5-config visual compare — Hard-Slot, Vanilla BM25, b=0 extreme, b=1 extreme, Title3x. Top-10 stacked tables per query.
**Reads:** imports `QUERIES`, `VANILLA_K1`, `_bm25_rank`, `_build_pool` from `bm25_sweep_smoke.py`.
**Writes:** `md/bm25_compare_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py` (sibling), `src.search.browser.close_browser`, `src.search.merge._merge_and_rank`, `src.search.search_web` (`_query_engines_concurrent`, `_select_engines`).

### bm25_idf_engine_smoke.py (258 LOC)

**Purpose:** IDF + engine-inverse-weighting orthogonal axes. 5-config compare: Hard-Slot, Vanilla BM25, +per-pool IDF (BM25Okapi default), +engine-inv-weighting (`1/engine_count` multiplier), +IDF+Weighting combined.
**Reads:** imports `QUERIES`, `VANILLA_K1`, `STOPWORDS`, `_build_pool`, `_tokenize`, `_doc_repr`, `BM25Uniform` from `bm25_sweep_smoke.py`.
**Writes:** `md/bm25_idf_engine_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py` (sibling), `rank_bm25`.

### bm25_sweep_smoke.py (420 LOC)

**Purpose:** BM25 parameter sensitivity sweep — 16-config main grid (b × stopwords × doc_repr at k1=1.2) + 4-config k1 sensitivity sweep, against Hard-Slot baseline. `BM25Uniform(BM25Okapi)` subclass overrides `_calc_idf` to force IDF=1.0 (TF + length-norm only). Base module for the whole `bm25_*` family — exports `QUERIES`, `VANILLA_K1`, `STOPWORDS`, `_build_pool`, `_tokenize`, `_doc_repr`, `_bm25_rank`, `BM25Uniform`.
**Reads:** none (queries hardcoded, live pool fetch via production engines).
**Writes:** `md/bm25_sweep_<ts>.md`.
**Called by:** CLI + imported by `bm25_compare_smoke.py`, `bm25_idf_engine_smoke.py`, `bm25_capped_smoke.py`, `pooling_probe.py`, `rerank_probe_smoke.py`, `single_query_pool_dump.py`, `stage1_pool_fetch.py`, `stage3_method_run.py`, `stage3_method_run_v3.py`, `value_eval_probe.py`.
**Calls out:** `rank_bm25` (BM25Okapi).

### branch_probe.py (196 LOC)

**Purpose:** Phase 3 bee investigation — sleep-branch discriminator entry point. Distinguishes which of the two `asyncio.sleep` branches inside `RateLimiter.acquire()` fires during zero-cascade queries: `backoff_sleep_attempt` vs `tokencap_sleep_attempt`. Structural discriminator: 6 engines have `.backoff()` calls (google, google_scholar, lobsters, mojeek, duckduckgo, semantic_scholar), 4 do not (crossref, openalex, stack_exchange, open_library). Query category renamed `"captcha"` → `"empty"` (same reason as `acquire_probe.py` above). Monkeypatch, canary, analysis, and report/findings assembly are split into `_branch_probe_*.py` siblings (own entries above).
**Reads:** none (live instrumented run).
**Writes:** `md/branch_probe_<ts>.md` and `md/03_branch_probe.md` (full run only, via the sibling report/findings modules).
**Called by:** CLI only. Flags: `--max-queries N`, `--smoke` (4-query dry-run, no report).
**Calls out:** `src.search.browser`, `src.search.search_web` (both monkeypatch-order-sensitive, imported via `importlib` after `_branch_probe_instrument.py`), `_branch_probe_instrument.py`, `_branch_probe_canary.py`, `_branch_probe_analysis.py`, `_branch_probe_report.py`, `_branch_probe_findings.py` (siblings).

### cdp_starvation_probe.py (581 LOC)

**Purpose:** Phase 1 bee investigation — asyncio event-loop starvation probe. Pattern A (slow-callback logger), Pattern B (scheduling-latency canary), CDP event counter (monkey-patch on `ConnectionHandler._process_single_message`). Categorizes queries as normal/empty/zero_cascade (`empty` was `captcha`, keyed on `EMPTY_BLOCK` — renamed when that verdict was removed; `engine_details` carries no diagnosis to reconstruct which kind of empty a query was). Historical verdict (as of the investigation date, see process-docs): REFUTED (event loop p99=1.4ms, 0 CDP events during cascade).
**Reads:** `queries.txt` (20-30 queries).
**Writes:** `md/cdp_probe_<ts>.md`.
**Called by:** CLI only. Flags: `--max-queries N`.
**Calls out:** `pydoll.connection.connection_handler.ConnectionHandler` (monkeypatched).

### clean_pool.py (236 LOC)

**Purpose:** Filter helper + oracle cleanup for 7-engine eval. `filter_pool(pool, drop_engines)` removes named engines from each entry's `engines`+`positions`, recomputes `min_position`, drops engine-less URLs. As script: generates `<pair>_oracle_v3clean.json` for all 16 (mode × query) pairs in the v2 ts_dir, backfilling loss-pairs where google/semantic_scholar picks are unavailable after filtering.
**Reads:** `runs/<v2 ts_dir>/*_oracle.json`.
**Writes:** `runs/<v2 ts_dir>/<pair>_oracle_v3clean.json`, `runs/<v2 ts_dir>/oracle_v3clean_summary.md`.
**Called by:** CLI only; `filter_pool` importable by other stage scripts. Flags: `--v2-dir PATH`.
**Calls out:** none beyond stdlib.

### empty_classify_se.py (204 LOC)

**Purpose:** Classification probe for 15 Stack Exchange EMPTY queries from the same historical smoke baseline — direct httpx (no rate limiter, no API key) against `site=stackoverflow` (production-identical) + `site=stackexchange` (cross-site fallback). Status taxonomy: ENGINE_EMPTY/ENGINE_NICHE/RATE_LIMITED/PIPELINE_BUG/UNKNOWN.
**Reads:** hardcoded query list embedded in-file.
**Writes:** `md/empty_classify_se_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

### engine_distribution_analysis.py (301 LOC)

**Purpose:** Per-engine slot-count and slot-share analysis over the newest `pipeline_smoke_*.md` baseline (auto-discovered via glob+sort). Sections: slot-count totals per engine (Total/GENERAL/ACADEMIC/QA/Solo/Overlap), Per-Engine Status Aggregate (quoted from smoke tail), slot-share with uniform + OK-adjusted baselines and signed delta columns, per-query distribution matrix.
**Reads:** newest `md/pipeline_smoke_*.md`.
**Writes:** `md/engine_distribution_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `_lib.parse` (`KNOWN_ENGINES`, `parse_smoke_report`).

### engine_health_audit.py (206 LOC)

**Purpose:** Reads `src/logs/query_log.jsonl` and aggregates per-engine status counts. The EMPTY sub-status-aware rules (`BROKEN (DOM-DRIFT)`/`DEGRADED (ANTI-BOT)`/`HEALTHY-EMPTY`, keyed on `EMPTY_NO_CONTAINER`/`EMPTY_BLOCK`/`EMPTY_NO_RESULTS`) were removed — those sub-statuses no longer exist as of the guessed-verdict-removal milestone (every empty result now logs bare `EMPTY`, with its own diagnosis snapshot in the log record instead). The remaining `FLAG (PYDOLL-CANCEL-LEAK)` rule (`TIMEOUT_NONCOOP > 10%` of timeouts) is unaffected — `TIMEOUT_*` was never a guessed verdict. Bucket aggregation still uses `startswith("EMPTY"/"TIMEOUT"/"ERROR")` to tolerate sub-status names, which still works (`"EMPTY"` itself starts with `"EMPTY"`).
**Reads:** `src/logs/query_log.jsonl`.
**Writes:** `md/<report>.md`.
**Called by:** CLI only. Flags: `--last N` (default 100), `--since ISO_TS`, `--engine NAME`.
**Calls out:** none beyond stdlib.

### google_selector_probe.py (250 LOC)

**Purpose:** Google DOM-selector diagnostic — loads one query at `num=100`, counts production selector `#rso h3` matches vs `div.MjjYud` containers vs alternative selectors in the rendered DOM. Distinguishes selector limitations from server-side rendering caps.
**Reads:** none (live DOM fetch, hardcoded `QUERY`, `NUM=100`).
**Writes:** `md/google_selector_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.browser` (new_tab, close_browser), `src.search.engines.google` (`_inject_socs_cookie`, `_build_url`, `_wait_for_results`, `_extract_value`).

### inspect_query_log.py (99 LOC)

**Purpose:** Quick summary of `src/logs/query_log.jsonl` — total record count, wall_ms min/mean/max, bottleneck-engine and TIMEOUT-hit counts, full per-engine breakdown of the most recent query. Distinguishes `engine_run` (written always) vs `workflow_summary` (production-only, includes total_wall_ms + preview) vs old-style (no `record_type`, treated as `workflow_summary`).
**Reads:** `src/logs/query_log.jsonl` (path resolution: `--log-path` arg → `SEARXNG_QUERY_LOG_PATH` env → default).
**Writes:** stdout only.
**Called by:** CLI only. Flags: `--tail N`, `--log-path PATH`, `--all-types` (include `engine_run` records).
**Calls out:** none beyond stdlib.

### no_google_burst_smoke.py (217 LOC)

**Purpose:** No-Google concurrent burst smoke — production `ScholarEngine` (HTTP) vs the 2 other remaining production engines under concurrent multi-engine burst pattern, without Google browser present. Architectural discriminator: does HTTP Scholar survive the burst pattern without the Google-driven browser warmup? Import switched from the dev-only `ScholarHTTPProbe` (see `scholar_http_probe.py`) to production `ScholarEngine` as part of an HTTP migration. The probe's whole purpose — Scholar's block rate — used to key on the removed `EMPTY_BLOCK` verdict; `_run_engine` now captures `search_with_reason`'s diagnosis dict directly (unlike `acquire_probe.py`/`branch_probe.py`/`cdp_starvation_probe.py`, which only see status through `engine_details` and cannot reconstruct this) and `_is_blocked(diagnosis)` derives the fact from `captcha_form` or a 30x `http_status`, both already in scholar's snapshot.
**Reads:** hardcoded 12-query set (academic queries, 3 bursts × 4).
**Writes:** `jsonl/no_google_burst_<ts>.jsonl` (per-query records); summary table to stderr.
**Called by:** CLI only.
**Calls out:** `httpx`, `pydoll.exceptions`, `websockets.exceptions`, `src.search.status`, `src.search.browser.close_browser`, `src.search.engines.{duckduckgo,openalex,scholar}`.

### pool_diff_v2_v3.py (240 LOC)

**Purpose:** Pool diff — compares URL sets and engine counts across all 16 (mode × query) pairs between a v2 reference dir and a v3 ts_dir. Per-pair overlap_pct, new-in-v3, removed-from-v2, google_count comparison; aggregate mean overlap + per-engine OK% comparison.
**Reads:** `runs/value_eval_v2_20260523_000156/` (hardcoded `V2_REF` default), `runs/value_eval_v3_<ts>/` (`--v3-dir` or newest auto-detected).
**Writes:** `md/pool_diff_v2_vs_v3.md`.
**Called by:** CLI only. Flags: `--v3-dir PATH`.
**Calls out:** none beyond stdlib.

### pooling_probe.py (363 LOC)

**Purpose:** Capped-pool strategy comparison — 4 configs on the same capped pool (each engine contributes ≤ google_count URLs): C1 Overlap-Count, C2 BM25 (BM25Uniform k1=1.2 b=0.75), C3 Cross-Encoder (Qwen3-Reranker-0.6B, port 8082), C4 Embedding-Cosine (Qwen3-Embedding-0.6B, port 8084). Hard-stop: `google_count == 0` → query skipped, no fallback. Requires reranker + embedding GPU services running.
**Reads:** imports pure BM25/pool utilities from `bm25_sweep_smoke.py`, GPU API helpers + 20-query set from `rerank_probe_smoke.py`.
**Writes:** `md/pooling_probe_<ts>.md`, `jsonl/pooling_probe_<ts>.queries.jsonl`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py`, `rerank_probe_smoke.py` (siblings), GPU services (embedding-0.6b, reranker-0.6b).

### pydoll_fingerprint_probe.py (200 LOC)

**Purpose:** Measures the production `browser.py` Chrome fingerprint against `bot.sannysoft.com` (JS bot-detection checks table). Extracts pass/fail per fingerprint vector + high-signal `navigator` properties.
**Reads:** none (live page load).
**Writes:** `/tmp/pydoll_probe_sannysoft.png` (screenshot); JSON summary to stdout.
**Called by:** CLI only.
**Calls out:** `src.search.browser` (new_tab, close_browser).

### rerank_probe_smoke.py (576 LOC)

**Purpose:** URL-filter + BM25-Retrieve top-50 + 2-method semantic rerank. 5-config compare: Hard-Slot, Filter+BM25-only, Filter+BM25→Embedding-Cosine (Qwen3-Embedding-0.6B, port 8090/8084), Filter+BM25→Cross-Encoder (Qwen3-Reranker-0.6B, port 8082/8092), BM25-Capped reference. URL-pattern filter drops search-results-page URLs (`[?&](q|query|search|keyword|term|p)=`, `/search/`, `/sresults/`, `/scholar?q=`). Base module for `pooling_probe.py`/`single_query_pool_dump.py`/stage scripts — exports `QUERIES`, `QUERY_CATEGORIES`, `EMBEDDING_URL`, `RERANKER_URL`, `embed_batch`, `cross_encoder_rerank`, `cosine_sim`, `_bm25_score`, `_verify_services`, `close_browser`, `_query_engines_concurrent`, `_select_engines`.
**Reads:** hardcoded 20-query set (5 academic/5 product/5 technical/5 mixed-intent).
**Writes:** `md/rerank_probe_<ts>.md`.
**Called by:** CLI + imported by `pooling_probe.py`, `single_query_pool_dump.py`, `stage1_pool_fetch.py`, `stage3_method_run.py`, `stage3_method_run_v3.py`, `value_eval_probe.py`.
**Calls out:** `httpx`, `numpy`, GPU services (embedding-0.6b, reranker-0.6b).

### scholar_http_probe.py (149 LOC)

**Purpose:** HTTP-based architectural alternative to `src/search/engines/scholar.py` — pure httpx + lxml against `scholar.google.com`, no browser. Status: dev-only PROBE, not wired into production `ENGINES` dict. `ScholarHTTPProbe` class (`name="scholar_http"`) uses a probe-local `RateLimiter` distinct from production `_limiters`. Its own sub-status sentinels (`_BLOCK`, `_NO_RESULTS`) are local module constants, not `src.search.status` — that module's `EMPTY_BLOCK`/`EMPTY_NO_RESULTS` were removed (the guessed-verdict-removal milestone), but this probe's own backoff experiment (`self._limiter.backoff()` on a detected block) is internal to this file and never reaches the production query log, so it keeps its own local vocabulary rather than adopting the production diagnosis-snapshot pattern.
**Reads:** none (live HTTP fetch).
**Writes:** returns `SearchResult` list — no file I/O.
**Called by:** imported historically by `no_google_burst_smoke.py` (that script has since switched to production `ScholarEngine`; import is currently unused there, see module docstring cross-reference).
**Calls out:** `httpx`, `lxml.html`, `src.search.rate_limiter.RateLimiter`, `src.search.result.SearchResult`, `src.search.status`.

### single_query_pool_dump.py (385 LOC)

**Purpose:** Single-query capped-pool vs Top-N dump for 4 configs. Sections: per-engine raw, full capped pool, Top-N per config, comparison matrix (every pool URL × 4 configs → rank or —). Hard-stop: `google_count == 0` → exit, no fallback. Requires embedding (port 8084) + reranker (port 8082) GPU services.
**Reads:** imports `_build_pool`, `_doc_repr` from `bm25_sweep_smoke.py`; GPU helpers from `rerank_probe_smoke.py`.
**Writes:** `md/<output>.md` (default naming; `--output` overridable).
**Called by:** CLI only. Flags: `--query TEXT` (default: postgresql index query), `--output PATH`.
**Calls out:** `bm25_sweep_smoke.py`, `rerank_probe_smoke.py` (siblings), GPU services.

### snippet_quality_analysis.py (384 LOC)

**Purpose:** Per-source bloat + lexical-density analysis over the newest `pipeline_smoke_*.md` baseline (auto-discovered). 11 sources (8 engines + `scholar_strip` derived bucket + og + meta), 10 bloat-pattern regexes. Sections: per-source aggregated stats table, 8×8 engine-overlap matrix, all-URLs side-by-side per-URL block with winner annotation, "best by usefulness" aggregate, per-class breakdown (GENERAL/ACADEMIC/QA).
**Reads:** newest `md/pipeline_smoke_*.md`.
**Writes:** `md/snippet_quality_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `_lib.parse` (`KNOWN_ENGINES`, `parse_smoke_report`), `_lib.text` (`strip_bloat`, `lexical_density`, `detect_bloat`).

### snippet_selection_simulator.py (198 LOC)

**Purpose:** Dry-run of new snippet-selection logic over the newest `pipeline_smoke_*.md` baseline. For each URL, gathers all non-empty sources (og, meta, per-engine snippets), scores each as `clean_len × lex_density`, picks the highest; falls back to best-of-worst when all sources are below `MIN_FLOOR=40` chars. Sections: summary (analyzed/no-content/floor-trigger counts + source distribution), per-query picks, floor-triggered cases list.
**Reads:** newest `md/pipeline_smoke_*.md`.
**Writes:** `md/snippet_selection_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `_lib.parse.parse_smoke_report`, `_lib.text` (`strip_bloat`, `lexical_density`).

### stage1_pool_fetch.py (379 LOC)

**Purpose:** Phase 12+ pool fetch (v3 schema) — 4 modes × 4 queries, per-pair `<mode>_<slug>_pool.json` + `<mode>_<slug>_engine_report.md`, global `engine_report_summary.md`. Every pool entry carries `positions: {engine: rank}` alongside `engines` + `min_position` (invariants: `set(engines)==set(positions.keys())`, `min_position==min(positions.values())`). `_STATUS_HINTS` dropped its 5 EMPTY_* sub-status entries and `engine_report_summary.md`'s per-engine table dropped its BLOCK% column (both removed along with `src/search/status.py`'s guessed verdicts — every empty result now logs bare `EMPTY`, so there is no more BLOCK-vs-EMPTY distinction left to report).
**Reads:** imports pool-build utilities from `bm25_sweep_smoke.py`, `rerank_probe_smoke.py`.
**Writes:** `runs/value_eval_v3_<ts>/` — per-pair `*_pool.json` + `*_engine_report.md`, `engine_report_summary.md`.
**Called by:** CLI only. Flags: `--smoke` (1-pair), `--ts-dir PATH`.
**Calls out:** `bm25_sweep_smoke.py`, `rerank_probe_smoke.py` (siblings).

### stage3_method_run.py (209 LOC)

**Purpose:** Phase 12+ method run (v2) — loads `<mode>_<slug>_pool.json` from a ts_dir, applies C1 Overlap / C2 BM25 / C2' BM25-Capped / C3 Cross-Encoder, writes `<mode>_<slug>_methods.json`. Dynamic reranker URL via `ensure_ready("reranker")` + `find_server_url("reranker")` (RAG server_manager). Exits with error if reranker cannot be reached.
**Reads:** `<ts_dir>/*_pool.json`.
**Writes:** `<ts_dir>/<mode>_<slug>_methods.json`.
**Called by:** CLI only. Flags: `--ts-dir PATH` (required), `--smoke`.
**Calls out:** `httpx`, RAG `server_manager` (via hardcoded `RAG_SRC` path insert), reranker GPU service.

### stage3_method_run_v3.py (489 LOC)

**Purpose:** Phase 13 method run (12 methods) — loads `<mode>_<slug>_pool.json` (v3 schema) from `--pool-dir`, filters `{google, semantic_scholar}` via `clean_pool.filter_pool`, applies M1-M12: C1 Overlap, RRF, Structural-URL, BM25, BM25-Capped, C3 vanilla, C3+InstrPrefix, RRF+C3, SPLADE, SPLADE+C3, two-stage C3+LLM-Filter, LLM-Selector. GPU deps: reranker-0.6b (M6-M8,M10-M11), splade (M9-M10), generator-4b (M11-M12).
**Reads:** `<pool_dir>/*_pool.json`.
**Writes:** `<pool_dir>/<mode>_<slug>_methods_v3.json`.
**Called by:** CLI only. Flags: `--pool-dir PATH` (required), `--smoke`.
**Calls out:** `clean_pool.filter_pool`, reranker/SPLADE/generator-4b GPU services.

### stage4_aggregate.py (325 LOC)

**Purpose:** Phase 12+ aggregate (v2) — loads pool/methods/oracle JSONs from a ts_dir, computes Jaccard overlap per C-method, writes per-pair `<mode>_<slug>_eval.md` + global `eval_summary.md` into the ts_dir. `--no-oracle` (smoke mode) generates MDs without oracle section to verify pool+methods pipeline integrity.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `<ts_dir>/<mode>_<slug>_eval.md`, `<ts_dir>/eval_summary.md`.
**Called by:** CLI only. Flags: `--ts-dir PATH` (required), `--no-oracle`.
**Calls out:** none beyond stdlib.

### stage4_aggregate_v3.py (300 LOC)

**Purpose:** Phase 13 aggregate (12-method eval) — loads `*_pool.json` + `*_methods_v3.json` (pool_dir) + `*_oracle_v3clean.json` (oracle_dir), computes Jaccard per method, writes per-pair `<mode>_<slug>_eval_v3.md` + `eval_summary_v3.md` with per-mode mean Jaccard, per-method latency stats (mean/p50/p95/max/cold), Quality×Latency Pareto table (DOMINATED flagged).
**Reads:** `<pool_dir>/*_pool.json`, `*_methods_v3.json`; `<oracle_dir>/*_oracle_v3clean.json` (default: hardcoded v2 dir `value_eval_v2_20260523_000156`).
**Writes:** `<pool_dir>/<mode>_<slug>_eval_v3.md`, `<pool_dir>/eval_summary_v3.md`.
**Called by:** CLI only. Flags: `--pool-dir PATH` (required), `--oracle-dir PATH`, `--no-oracle`.
**Calls out:** none beyond stdlib.

### test_snippet_truncate.py (32 LOC)

**Purpose:** Standalone assertion script for `src/search/snippet._truncate` — 4 regression-guard assertions (short text unchanged, clean period cut without ellipsis, word-boundary cut with ellipsis, hard cut at exactly MAX_SNIPPET_LEN+1 with ellipsis).
**Reads:** none.
**Writes:** stdout (`OK`) or `AssertionError`.
**Called by:** CLI only. `./venv/bin/python dev/search_pipeline/test_snippet_truncate.py`.
**Calls out:** `src.search.snippet` (`_truncate`, `MAX_SNIPPET_LEN`).

### value_eval_aggregate.py (325 LOC)

**Purpose:** Pooling-investigation Stage 4 (v1, historical, superseded by `stage4_aggregate.py`/`stage4_aggregate_v3.py`) — loads `pool.json`+`methods.json`+`oracle.json` per pair, computes Jaccard `|oracle ∩ method| / |oracle ∪ method|`, writes per-query MD + summary MD with per-mode means + overall winner. Handles undersized-pool case (`undersized_pool=True AND pool_size=0` skipped in mode means). `--no-oracle` for pipeline-validation MDs without oracle section.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `md/value_eval_<mode>_<slug>_<ts>.md`, `md/value_eval_summary_<ts>.md`.
**Called by:** CLI only. Flags: `--ts-dir PATH` (required), `--ts-out TS`, `--no-oracle`.
**Calls out:** none beyond stdlib.

### value_eval_probe.py (369 LOC)

**Purpose:** Pooling-investigation Stage 1+2 (v1, historical) — per `(mode, query)` pair fetches pool via `_query_engines_concurrent` with mode-specific query modifiers (+book/+pdf/+documentation for general engines) and post-merge URL filter, applies 4 C-methods (C1 Overlap on capped+filtered, C2 BM25 vanilla on full+filtered, C2' BM25-Capped, C3 Cross-Encoder Qwen3-Reranker-0.6B port 8082). Writes oracle-input pool.json (url+title+snippet only, alphabetical, no engine/score signals) and methods.json. Filter logic inlined (no `from src.` imports). `--smoke` runs 1 pair + auto-aggregates with `--no-oracle`.
**Reads:** hardcoded 4-mode × 4-query matrix, live engine fetch.
**Writes:** `runs/value_eval_<ts>/<mode>_<slug>_pool.json`, `<mode>_<slug>_methods.json`.
**Called by:** CLI only. Flags: `--smoke`, `--ts-dir PATH`.
**Calls out:** `httpx`, reranker GPU service (port 8082).

### with_google_decoupling_smoke.py (189 LOC)

**Purpose:** Verifies Scholar is absent from the default engine set (production `_select_engines(None)` path). Checks: Google browser engine present, `google_scholar` NOT in `engines_requested`, `engines_excluded["google_scholar"] == "decoupled_from_google"` in query log, no status attributed to Scholar at all. Runs 5 queries through `search_web_workflow(query, engines=None)` then reads the last 5 `query_log.jsonl` lines.
**Reads:** `src/logs/query_log.jsonl` (tail, before/after count).
**Writes:** `md/with_google_decoupling_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `src.search.search_web.search_web_workflow`, `src.search.browser.close_browser`.

## State
`config.yml` — run params (`queries_file`, `page_load_timeout`, `consent_settle`) and report path (`output_dir`, currently `./md`); consumed by `02_burst_smoke.py`, `_capture_sorry.py`, `00_single_query.py` (latter two via shared helper import, not direct config read). `queries.txt` — 30 baseline queries (Tech 8 + Science 6 + German 6 + Niche 5 + Broad 5), shared across most per-engine smokes. Report outputs live in `md/` (readable reports); run-payload/corpus data lives in type-named folders — `jsonl/` (pool/query JSONL dumps), `txt/` (pool dumps), `png`/`html` (screenshots, raw captures), `runs/` (multi-file per-run pool/methods/oracle JSON co-located with their eval MD, `value_eval*_<ts>/` subfolders) — kept separate from `md/` per the dev/ layout convention.

## Gotchas
`27_brave_headed_lane_probe.py` launches Chrome headed-but-backgrounded via its own inline `open -g -n -a "Google Chrome"` process_creator, with no focus-steal reclaim — `open -g` only suppresses activation at the launch moment (playwright#42343), so this window can still steal focus later in the run. Left as-is (out of scope for the milestone that added the alternative below). Any NEW headed-backgrounded Chrome launch in this area should use `dev/_lib/browser_launch.py` (own DOCS.md) instead of copying `27`'s mechanism — it adds the PID-keyed reclaim watchdog `27` is missing.

Several scripts (`bm25_capped_smoke.py`, `bm25_idf_engine_smoke.py`, `bm25_compare_smoke.py`, `pooling_probe.py`, `single_query_pool_dump.py`, `stage1_pool_fetch.py`, `stage3_method_run*.py`, `value_eval_probe.py`) import helpers directly from sibling script files (`bm25_sweep_smoke.py`, `rerank_probe_smoke.py`) via `sys.path.insert(0, str(SCRIPT_DIR))` — these are not `_lib/` modules; treat them as informal shared-code sources when editing either base file. GPU-dependent scripts (reranker/embedding/SPLADE/generator-4b at fixed localhost ports) fail hard if the corresponding RAG server isn't running — check `_verify_services()` / `ensure_ready()` calls before assuming a script is broken. `stage4_aggregate*.py` write eval MD directly into `runs/<ts_dir>/`, co-located with the pool/methods/oracle JSON they score — by design (no separate output dir; ts embedded in the dir name).

New files in this directory cannot `from src....` import at all — a repo-tooling hook blocks any `Write`/`Edit` that introduces a NEW such import line, even into a file that already has other `src/` imports (the 26 files in this directory that already import from `src/` are grandfathered, not a precedent for new files). `altcha_trigger_probe.py`'s sibling modules (`_altcha_trigger_probe_launch.py` etc.) inline-copy `src/scraper/chromium_process.py`'s launch shape instead of importing it for exactly this reason. Separately, local fixture testing during that same probe's build found that raw CDP `Input.dispatchMouseEvent` (and Playwright's own `.click()`/`page.mouse`, both tried) do not reliably reach shadow-DOM-scoped elements at all in the self-launch-plus-`connect_over_cdp` launch shape this project's chromium lane uses, even though the identical click works fine on light-DOM elements and on ANY element when Playwright owns the browser process directly instead of attaching externally — unresolved, did not block that milestone only because its real target turned out to be light DOM; see process-docs (`engine_reduction` area) before assuming a click-based trigger against a shadow-DOM target will work here.
