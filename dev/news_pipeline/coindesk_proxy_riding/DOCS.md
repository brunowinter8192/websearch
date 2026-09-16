# dev/news_pipeline/coindesk_proxy_riding/

## Role
Standalone dev suite for scraping CoinDesk article HTML at scale via rotating proxies. Architecture: B Playwright browser processes (pool, default B=1); N concurrent rider tasks (default 20) distributed round-robin across the B browsers (slot i → browsers[i % B]). Each task pulls raw proxies directly from the pool (no pre-validation). Each URL fetch uses `CrawlerRunConfig(proxy_config=ProxyConfig(server=...))` → fresh Playwright BrowserContext per proxy via crawl4ai's config-signature mechanism + `session_id` + `kill_session()` (fresh cookies per URL, browser stays alive). Regwall detection on `result.markdown.raw_markdown` (not raw HTML — REGWALL_SIGNALS are hidden React components always present in HTML). A proxy is burned and rotated when cumulative regwall hits reach the burn threshold. Self-contained: no imports from `src/` at module load (test modules import `src/news/engine/proxy_riding/` lazily, inside function bodies, for validating a ported production package).

## Modules

### p0_pool.py (221 LOC)

**Purpose:** Local copy of proxy pool machinery — loaders, cooldown manager, retry helper. Exports `load_backfill_pool()`, `PersistentCooldownManager`, `proxy_key()`, `fetch_with_retry()`.
**Reads:** proxy source lists (via loaders).
**Writes:** none (pure helpers).
**Called by:** `run_coindesk_riding.py`, `p2_browser_rider.py`.
**Gotcha:** local copy, not an import from `src/` — hookify blocks `from src.` imports in dev/ scripts.

### p2_browser_rider.py (283 LOC)

**Purpose:** Core riding pool orchestrator — B `AsyncWebCrawler` instances, N rider tasks round-robin across browsers, per-URL proxy context with burn/fail rotation.
**Reads:** proxy pool (via `p0_pool`), URL queue.
**Writes:** `raw/<12-char-sha256-hash>.html` per ok URL (via `_p2_fetch.py`); on stall, `remaining_urls.txt` (via `_p2_watchdog.py`).
**Called by:** `run_coindesk_riding.py`, `smoke_stage1.py`, `test_watchdog.py`, `test_tail_race.py`, `p4_reporter.py`.
**Exports:** `run_riding_pool(n_browsers=1, stall_timeout_s=3600)`, `RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`, `_watchdog`, `_abort_stall` — the last four are re-exports from `_p2_state.py`/`_p2_watchdog.py`, kept resolvable from `p2_browser_rider` for `p4_reporter.py` and `test_watchdog.py`.
**Calls out:** `_p2_state.py`, `_p2_fetch.py`, `_p2_watchdog.py` (this directory).

### _p2_state.py (77 LOC)

**Purpose:** Data model for the riding pool — `RideRecord`, `JobRecord`, `RiderState` (incl. `all_resolved` property) and the `STALL_TIMEOUT_S` default.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `p2_browser_rider.py`, `_p2_watchdog.py`.
**Calls out:** `p0_pool.py` (this directory, for the `PersistentCooldownManager` type).

### _p2_fetch.py (104 LOC)

**Purpose:** Single-URL fetch mechanics — proxy-context `crawler.arun()` call, result classification (ok/regwall/empty/failed/connect_fail), regwall detection, raw-HTML write, URL hashing.
**Reads:** nothing — takes a live `crawler` and a URL from the caller.
**Writes:** `raw/<12-char-sha256-hash>.html` per ok URL.
**Called by:** `p2_browser_rider.py` only.
**Calls out:** `crawl4ai`.

### _p2_watchdog.py (111 LOC)

**Purpose:** Stall detection and abort-report writing — `_watchdog` polls for progress staleness; `_abort_stall` drains the queue, writes `remaining_urls.txt`, writes `job.md` (via a late import of `p4_reporter` to avoid a module-level cycle, falling back to a minimal stub on any reporter error), then `os._exit(1)`.
**Reads:** nothing.
**Writes:** `remaining_urls.txt`, `job.md` (on stall).
**Called by:** `p2_browser_rider.py`, `test_watchdog.py` (via `p2_browser_rider`'s re-export).
**Calls out:** `p4_reporter.py` (this directory, lazy import inside `_write_stall_job_md`).

### p3_url_sampler.py (136 LOC)

**Purpose:** Proportional 500-URL sampler from CoinDesk inventory shards (2017-2026); floor 5 URLs/year. Resolves `data/news/coindesk/inventory/` from main repo root via `git rev-parse --git-common-dir` (works inside worktrees).
**Reads:** `data/news/coindesk/inventory/` shards.
**Writes:** returns sampled URL list (in-memory).
**Called by:** `run_coindesk_riding.py`.
**Exports:** `sample_urls(n_total, seed)`.

### p4_reporter.py (208 LOC)

**Purpose:** Orchestrates the report write (`write_riding_report`) and renders `job.md` — counts/throughput tables, HTML/markdown percentile sections, proxy/regwall sections, failed/regwall URL lists, plot links. Counts table includes `Browsers` and `Contexts/browser` (`n_slots // n_browsers`) for self-documenting runs.
**Reads:** `RiderState`.
**Writes:** `job.md`.
**Called by:** `run_coindesk_riding.py`, `p2_browser_rider.py` (on abort, via `_p2_watchdog.py`'s lazy import).
**Exports:** `write_riding_report(state, job_dir, t_job_start)`.
**Calls out:** `_p4_stats.py`, `_p4_plots.py` (this directory).

### _p4_stats.py (169 LOC)

**Purpose:** Derives all report metrics from a `RiderState` — counts, throughput/backfill projection, HTML/markdown size percentiles, completion-time series, ride-length distribution, regwall rate by ride position, retry outcomes. `n_connect_fail` reads `state.n_connect_fail` (the authoritative counter) rather than counting `job_records`, because `p2_browser_rider.py` never appends a `JobRecord` for a connect_fail attempt.
**Reads:** `RiderState`.
**Writes:** nothing.
**Called by:** `p4_reporter.py` only.
**Calls out:** `p2_browser_rider.py` (this directory, for `RiderState`/`FAIL_THRESHOLD`).

### _p4_plots.py (62 LOC)

**Purpose:** The three matplotlib plots — cumulative OK fetches over time, ride-length histogram, regwall-rate-by-position bar chart.
**Reads:** nothing — takes the `stats` dict from `_p4_stats.py`.
**Writes:** `cumulative.png`, `ride_lengths.png`, `regwall_position.png`.
**Called by:** `p4_reporter.py` only.
**Calls out:** `matplotlib`.

### run_coindesk_riding.py (123 LOC)

**Purpose:** CLI orchestrator — loads pool via `load_backfill_pool()`, wires `run_riding_pool` + `write_riding_report` end-to-end; raises `RLIMIT_NOFILE` at startup.
**Reads:** CLI args (`--n-urls` default 500, `--concurrency` default 20, `--burn-threshold` default 2, `--output-dir` default `output`, `--page-timeout` default 8000, `--browsers` default 1, `--stall-timeout` default 3600).
**Writes:** `<output-dir>/raw/*.html`, `<output-dir>/job.md`, `<output-dir>/cumulative.png`, `<output-dir>/ride_lengths.png`, `<output-dir>/regwall_position.png`.
**Called by:** CLI only. Entry point `__main__` via `asyncio.run(_run(_parse_args()))`. `./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/run_coindesk_riding.py --n-urls 500 --concurrency 20 --burn-threshold 2 --output-dir data/news/coindesk/riding_output`.

### analyze_write_times.py (288 LOC)

**Purpose:** Reconstructs proxy-riding throughput from `raw/*.html` file mtimes. Used when `job.md`/`cumulative.png` are missing (manual abort before fix, or any crash that skips the report write). Reads mtime of every `.html` in `--raw-dir`, optionally filters to a `--since` cutoff (needed when `raw/` is a cumulative dedup corpus spanning multiple runs), plots cumulative OK fetches over time (top) and per-bin rate + rolling mean + 30-min pool-refresh markers (bottom).
**Reads:** `--raw-dir` (default `data/news/coindesk/raw`, resolved from repo root via `git rev-parse --git-common-dir`).
**Writes:** `png/raw_write_times_<YYYYMMDD>[_since<stamp>].png`. Stdout: filter summary, files, span, mean/median rate, longest gap.
**Called by:** CLI only. `--bin-minutes` (default 1), `--rolling` (default 5), `--since 'YYYY-MM-DD HH:MM'`.

### test_cooldown_policy.py (251 LOC)

**Purpose:** Deterministic tests for `RidingCooldownManager` (both `fixed` and `exp` policies). No browser or proxy infrastructure needed. `src/` imports lazy (worktree-root `sys.path` insert). 8 tests: fixed 60min eligibility boundary, fixed-default equivalence, exp unproductive-burn backoff bounds, exp cap at 3600s, exp reset on productive ride, exp eligible-after-backoff, exp `cooldown_count()` gate (A/B correctness gate for watchdog pool_samples), fixed `cooldown_count()` mirror check.
**Reads:** none (in-memory state construction).
**Writes:** stdout PASS/FAIL, exit code.
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_cooldown_policy.py`.

### smoke_stage1.py (274 LOC)

**Purpose:** Stage 1 smoke validating the `src/news/engine/proxy_riding/` package — import check, deterministic watchdog test, and a mini live run (10 inventory URLs, 2 slots, 1 browser).
**Reads:** `src/news/engine/proxy_riding/` package (import validation); 10 inventory URLs (live run).
**Writes:** live-run raw `.html` files to a temp dir.
**Called by:** CLI only, run from main checkout: `./venv/bin/python .claude/worktrees/<worktree>/dev/news_pipeline/coindesk_proxy_riding/smoke_stage1.py`.

### test_sigint_report.py (227 LOC)

**Purpose:** Deterministic SIGINT/SIGTERM report tests for `abort.py:_abort_interrupted` — asserts exit codes 130/143 and report writes, no browser or proxy infrastructure.
**Reads:** none (constructed state).
**Writes:** `job.md`, `cumulative.png` to a temp dir (assertion targets).
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_sigint_report.py`.

### test_tail_race.py (367 LOC)

**Purpose:** Deterministic tail-race tests (5 cases, tests 1-5) for `rider.py:_run_slot` with `_fetch_one_url`/`_next_proxy` mocked — no browser or proxy infrastructure. Test 3 (`no_spurious_requeue`) has two sub-cases, each its own private helper (`_test_3_sub_a`/`_test_3_sub_b`) called from the one public `test_3_no_spurious_requeue` so the printed test name/count stay unchanged.
**Reads:** none (mocked fetch/proxy).
**Writes:** none beyond test assertions.
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`.
**Calls out:** `_test_tail_race_watchdog.py` (this directory, tests 6-7).

### _test_tail_race_watchdog.py (104 LOC)

**Purpose:** Deterministic watchdog tests (tests 6-7) for `rider.py:_watchdog` — wedge-after-all-resolved (`os._exit(0)`) and pool-refresh-on-interval.
**Reads:** none (mocked fetch/proxy).
**Writes:** none beyond test assertions.
**Called by:** `test_tail_race.py` only.
**Calls out:** none.

### test_watchdog.py (159 LOC)

**Purpose:** Deterministic watchdog verification — no browser or proxy infrastructure needed. `test_watchdog_task_fires_and_writes_files`: constructs `RiderState` with `last_progress_mono` aged 200s past a 1s threshold + 2 queued + 1 in-flight URL; patches `os._exit` → `SystemExit(code)`; runs `_watchdog(poll_interval=0.1)`; asserts `os._exit(1)` called, `remaining_urls.txt` has both section headers + all 3 URLs, `job.md` exists with `stall`. `test_abort_stall_directly`: same assertions via direct `_abort_stall(idle_s=999.0)` call; also checks `"999"` in the header line.
**Reads:** none (constructed state).
**Writes:** `remaining_urls.txt`, `job.md` to a temp dir (assertion targets).
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/coindesk_proxy_riding/test_watchdog.py`.

## State
`raw/` — one HTML per ok URL fetched (output-dir scoped, not committed). `png/` — historical throughput reconstruction plots (tracked).
