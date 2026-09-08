# src/news/engine/proxy_riding/

## Role

Third scrape engine: browser + rotating proxies. Purpose: defeat CoinDesk's IP-rate regwall for the
61k article-body backfill. Each URL gets a fresh crawl4ai browser context bound to a distinct proxy;
the proxy is burned after `burn_threshold` regwall hits or `FAIL_THRESHOLD` (2) failed/empty strikes
and a new one is picked from the shuffled pool. A timer-based asyncio watchdog (`_watchdog`) runs
independently of the slot tasks and hard-aborts via `os._exit(1)` if no progress occurs for
`stall_timeout_s` seconds — immune to wedged Playwright I/O.

**Active as CoinDesk's `run_scrape_only` path.** `platform.scrape_engine == "proxy_riding"` dispatched
in `pipeline.py:run_scrape_only`; `RidingScrapeConfig` consumed via `getattr` (not in Protocol);
`filter_new_entries` raw_ext reconciliation done (`.html` for riding path).

Touch this package when changing proxy-riding engine behaviour. Do NOT touch `engine/scrape.py` or
`engine/proxy_pool/` — those engines are strictly independent.

## Public Interface

`__init__.py` is empty. Entry paths:

- `scrape_entries_riding(entries, output_dir, riding_cfg, job_dir)` in `scrape.py` — async; called by
  `pipeline.py:_run_scrape_only_riding`. Returns `tuple[list[dict], RiderState]`: manifest
  `[{url, hash, status, file, char_count, error}]` + full rider state (for `write_riding_report`).
  `job_dir` is threaded to the watchdog so stall-abort writes land in `scrape_jobs/{job_id}/` (same as
  normal completion), not the platform root.
- `RidingScrapeConfig` in `scrape.py` — dataclass with production defaults
  (`n_browsers=4, n_slots=64, stall_timeout_s=300.0, burn_threshold=2, page_timeout_ms=8_000`).
- `write_riding_report(state, job_dir, t_job_start)` in `reporter.py` — called by
  `pipeline.py:_run_scrape_only_riding` (normal completion) and by `abort.py`'s `_abort_stall` / `_abort_done` /
  `_abort_interrupted` (late import, abort paths).
- `run_riding_pool(url_queue, proxy_pool, cooldown_mgr, output_dir, job_dir, target_urls, …)` in
  `rider.py` — async; called by `scrape_entries_riding`. Stable entry point — this import path does
  not change even as the package's internals are split across modules.
- `RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`, `RAW_SUBDIR` defined in `state.py`;
  re-imported (not re-defined) into `rider.py` so `rider.RiderState` etc. still resolve for existing
  callers.

## Flow

1. `scrape_entries_riding` builds URL queue from entries, loads pool via `load_backfill_pool()`,
   filters to `{"http","socks5"}`, shuffles, constructs `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`.
2. `run_riding_pool` spawns B `AsyncWebCrawler` instances + N slot tasks + 1 watchdog task.
3. Each slot draws a proxy from the shuffled pool (cursor-atomic under `proxy_lock`), rides URLs
   until burn_threshold regwall or FAIL_THRESHOLD failed/empty, then rotates to the next proxy.
   **Tail-race:** when `url_queue` is empty (unresolved URLs < n_slots), slots immediately race an
   open URL (`sorted(target_urls − done_urls)[slot_id % len]`) with their current proxy — no 10 s
   wait. `asyncio.QueueEmpty` → race path; `asyncio.Queue.get_nowait()` replaces `wait_for(…, 10s)`.
4. Ok fetches write `raw/{hash}.html` guarded by first-writer check (`done_urls`); dup-race arrivals
   are discarded without write or n_ok increment. State accumulates `job_records` + `ride_records`.
5. Termination: `all_resolved = len(done_urls) >= len(target_urls)` (not queue-empty + in_flight==0).
   `state.termination` transitions from `"running"` → one of `"all-done"` | `"stall"` |
   `"pool-exhausted"` | `"interrupted"` (signal abort).
6. `scrape_entries_riding` maps `state.job_records` → manifest via `_build_manifest`.

## Modules

### cooldown.py (85 LOC)

**Purpose:** Riding-specific proxy cooldown manager (`RidingCooldownManager`, isolated from the theblock-shared `proxy_pool/cooldown.py`) with two per-run policies via `RidingScrapeConfig.cooldown_policy` — `"fixed"` (60-min flat) and `"exp"` (full-jitter backoff, reset on productive ride).
**Reads:** `_burned_at` / `_next_eligible` / `_failed_attempts` (in-memory dicts keyed by `proxy_key`).
**Writes:** same dicts on `mark_burned(proto, hp, ride_ok=0)`.
**Called by:** `rider.py:_finalize_ride` (via `state.cooldown_mgr.mark_burned`);
`rider.py:_next_proxy` (via `state.cooldown_mgr.eligible_candidates`);
`rider.py:_watchdog` (via `state.cooldown_mgr.eligible_candidates` + `cooldown_count`);
`scrape.py:scrape_entries_riding` (instantiation: `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`);
`reporter.py:_write_md` (via `state.cooldown_mgr.policy`).
**Calls out:** `src.news.engine.proxy_pool.proxy_key.proxy_key`.

---

### state.py (87 LOC)

**Purpose:** Shared riding dataclasses (`RiderState`, `JobRecord`, `RideRecord`) + calibrated constants — the one canonical import source for every other module and the dev/ tests.
**Reads:** n/a (data-shape module).
**Writes:** n/a.
**Called by:** `rider.py` (imports all of it), `fetch.py` (`DELAY_BEFORE_HTML`, `RAW_SUBDIR`),
`abort.py` (`RiderState` type hint), `reporter.py` (`RiderState` type hint only), `metrics.py`
(`RiderState`, `FAIL_THRESHOLD`), `scrape.py` (`RiderState`), dev/ tests under
`dev/news_pipeline/coindesk_proxy_riding/`.
**Calls out:** `src.news.engine.proxy_riding.cooldown.RidingCooldownManager` (type hint on
`RiderState.cooldown_mgr`).

### fetch.py (108 LOC)

**Purpose:** Per-URL fetch + outcome classification — the crawl4ai call, regwall detection, connect-fail subtype classification, and raw-HTML persistence.
**Reads:** n/a (pure per-call).
**Writes:** `output_dir/raw/{url_hash}.html` (`_write_raw`, called from `rider.py:_apply_ok_result`
on first-writer OK).
**Called by:** `rider.py:_fetch_and_build_job` (`_fetch_one_url`, `_url_hash`), `rider.py:_apply_ok_result`
(`_write_raw`, `_url_hash`), `rider.py:_apply_connect_fail_result` (`_classify_connect_fail`).
**Calls out:** `crawl4ai` (`AsyncWebCrawler`, `CrawlerRunConfig`, `CacheMode`, `ProxyConfig`,
`DefaultMarkdownGenerator`).

### abort.py (96 LOC)

**Purpose:** The three watchdog/signal abort paths (`_abort_done`, `_abort_interrupted`, `_abort_stall`) plus their shared write-report-and-exit helper `_abort_write_report_and_exit`.
**Reads:** `RiderState` (in-memory, for the report + fallback stub).
**Writes:** `state.job_dir/job.md` (+ `cumulative.png`/histograms via `write_riding_report`, or the
minimal fallback stub on any reporter error).
**Called by:** `rider.py:_watchdog` (`_abort_done`, `_abort_stall`); `rider.py:run_riding_pool`
(`_abort_interrupted`, registered as the SIGINT/SIGTERM handler).
**Calls out:** late import of `reporter.write_riding_report` inside `_abort_write_report_and_exit`
(avoids a circular top-level import — `reporter.py` imports from `state.py` (directly) and from
`metrics.py`/`plots.py` (which themselves import from `state.py`), not from `abort.py`, but the
cycle would still exist through `rider.py`).

### rider.py (371 LOC)

**Purpose:** Entry module — orchestrates B `AsyncWebCrawler` instances, N slot coroutines, per-URL proxy context, burn/fail rotation, 30-min pool refresh, and the watchdog (`run_riding_pool`); installs SIGINT/SIGTERM handlers so manual aborts also produce a report. `_run_slot` and `_apply_fetch_result` were each split into single-responsibility helpers to stay under the 50-LOC function threshold (pure extraction, same behavior/log output — see Gotchas): `_run_slot` → `_next_url_for_slot` (dequeue-or-tail-race, returns an explicit `"continue"|"break"|"proceed"` action so the caller's own loop control is preserved) → `_fetch_and_apply` (per-attempt orchestrator) → `_fetch_and_build_job` (fetch + `JobRecord` construction) and `_apply_fetch_result` (now a pure dispatcher) → one helper per status (`_apply_ok_result`, `_apply_regwall_result`, `_apply_connect_fail_result`, `_apply_generic_failure_result`) sharing `_maybe_requeue` for the repeated requeue-if-dequeued check.
**Reads:** URL queue (asyncio.Queue), proxy pool list, `RidingCooldownManager` (shared state).
**Writes:** `output_dir/raw/{hash}.html` for each ok URL (via `fetch.py:_write_raw`); triggers
`state.job_dir/job.md` + `cumulative.png` writes on abort (via `abort.py`).
**Called by:** `scrape.py:scrape_entries_riding` (via `run_riding_pool`).
**Calls out:** `crawl4ai` (`AsyncWebCrawler`, `BrowserConfig`); `state.py` (`RiderState`,
`RideRecord`, `JobRecord`, constants); `fetch.py` (`_fetch_one_url`, `_classify_connect_fail`,
`_write_raw`, `_url_hash`); `abort.py` (`_abort_done`, `_abort_interrupted`, `_abort_stall`).

### reporter.py (213 LOC)

**Purpose:** Orchestrator (`write_riding_report`) + the `job.md` markdown-rendering concern (counts, throughput, riding stats, regwall counts, connect-fail breakdown, load-time distribution, plot links) from a completed `RiderState`. Metric derivation and plot-file writing were split out into `metrics.py`/`plots.py` (below, pure relocation, same behavior) once this file crossed 400 LOC by mixing three concerns; this module is left as the orchestrator plus the one remaining concern (markdown rendering) since that alone keeps it well under any split threshold.
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** `{job_dir}/job.md`. Plot files (`cumulative.png`, `success_load_hist.png`, `connect_fail_hist.png`) are written by `plots.py`, called from this module's own orchestrator.
**Called by:** `pipeline.py:_run_scrape_only_riding` (normal completion, via `write_riding_report`);
`abort.py:_abort_stall` (late import, stall abort); `abort.py:_abort_done` (late import,
wedge-after-done); `abort.py:_abort_interrupted` (late import, SIGINT/SIGTERM abort).
**Calls out:** `src.news.engine.proxy_riding.state` (`RiderState`, type hints only); `src.news.engine.proxy_riding.metrics` (`_compute_stats`); `src.news.engine.proxy_riding.plots` (`_write_cumulative_plot`, `_write_load_hist`, `_write_cf_hist`).

### metrics.py (160 LOC)

**Purpose:** Metric derivation from `RiderState` — split out of `reporter.py` (pure relocation, same behavior): `_compute_stats` (the single entry point `write_riding_report` calls), `_compute_fetch_counts` (per-fetch counts/elapsed-time stats/completion times, extracted from `_compute_stats` itself to keep it under 50 LOC — see Gotchas), `_compute_retry_outcome`, `_compute_pool_windows`, `_compute_load_percentiles`, `_compute_connect_fail_stats`, `_distribution_stats`, and the `_BACKFILL_TOTAL = 61_000` constant.
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** nothing — returns a plain `dict` (the `stats` shape `reporter.py`/`plots.py` both consume).
**Called by:** `reporter.py` (`write_riding_report` via `_compute_stats`) — the only caller.
**Calls out:** `statistics` (stdlib, incl. `statistics.quantiles` with `method='inclusive'` — bounds p-values within observed [min, max]); `src.news.engine.proxy_riding.state` (`RiderState`, `FAIL_THRESHOLD`).

### plots.py (77 LOC)

**Purpose:** Matplotlib plot-file writers — split out of `reporter.py` (pure relocation, same behavior): `_write_cumulative_plot`, `_write_load_hist`, `_write_cf_hist`. All histograms: 0.25 s bins, x-axis auto-ranges to data max, page_timeout_s red vertical line. Pure functions of `job_dir: Path` + the `stats` dict `metrics.py` produces — no `proxy_riding`-internal import at all.
**Reads:** nothing of its own — takes the `stats` dict as a parameter.
**Writes:** `{job_dir}/cumulative.png`; `{job_dir}/success_load_hist.png` (only when ≥2 OK `load_s` values, gated by the caller); `{job_dir}/connect_fail_hist.png` (only when ≥2 `connect_fail_records`, gated by the caller).
**Called by:** `reporter.py` (`write_riding_report`) — the only caller.
**Calls out:** `matplotlib` (lazy import inside each plot function); `math` (stdlib, bin count).

### scrape.py (111 LOC)

**Purpose:** Pipeline entry point + manifest adapter. Loads pool, shuffles, calls `run_riding_pool`,
maps `RiderState.job_records` → pipeline manifest.
**Reads:** entries list (in-memory), `RidingScrapeConfig`, proxy pool (network via `load_backfill_pool`).
**Writes:** delegates to `rider.py` (raw HTML writes to `output_dir/raw/{hash}.html`); writes nothing directly.
**Called by:** `pipeline.py:_run_scrape_only_riding` (proxy_riding dispatch arm).
**Calls out:** `src.news.engine.proxy_pool.pool_loaders.load_backfill_pool`;
`src.news.engine.proxy_riding.cooldown.RidingCooldownManager`;
`src.news.engine.proxy_riding.rider.run_riding_pool`;
`src.news.engine.proxy_riding.state.RiderState`.

## State

`RiderState` (defined in `state.py`, re-exported through `rider.py`) is the shared mutable state
across all slot coroutines and the watchdog. Owned and mutated by `rider.py:run_riding_pool`,
`rider.py:_run_slot` and its per-attempt/per-status helpers (`_fetch_and_apply`,
`_fetch_and_build_job`, `_apply_fetch_result` and its four status handlers), `rider.py:_finalize_ride`. Read by
`reporter.py:write_riding_report`, `metrics.py:_compute_stats` (called from `write_riding_report`),
and `scrape.py:_build_manifest` (read-only, after run completes).
`asyncio` single-threaded: `set.add/discard` on `in_flight_urls` and `int` increments on counters
are safe without explicit locking. `proxy_lock` (asyncio.Lock) guards `proxy_cursor` advancement.

## Gotchas

- `file` field in manifest points to `.html` (not `.md`). `dedup.py:filter_new_entries` mode `"raw"`
  now accepts `raw_ext` param — pass `".html"` for riding path (done in `pipeline.py:run_scrape_only`).
  `clean_pass.py:_run_clean_pass` still hardcodes `{h}.md` but is NOT on CoinDesk's path (proxy_pool /
  TheBlock only) — out of scope unless CoinDesk gains a clean-pass step.
- `output_dir` passed to `scrape_entries_riding` must be `platform_dir` (`data/news/{name}/`), NOT
  `raw_dir`. The rider writes to `output_dir/raw/{hash}.html`; passing `raw_dir` puts files at
  `raw/raw/` (wrong), breaking dedup.
- All three abort functions (`_abort_stall`, `_abort_done`, `_abort_interrupted`, in `abort.py`) call
  `os._exit` — no Python teardown, no atexit, no `browser.close()`. Raw files flushed before the call
  are durable; in-flight writes at the moment of abort are lost. All write to `state.job_dir`
  (= `scrape_jobs/{job_id}/`), NOT to `output_dir`; each creates the dir itself (`mkdir`) before
  the first write because the dir may not exist at abort time. Exit codes follow Unix signal-kill
  convention: 130 = 128+SIGINT(2), 143 = 128+SIGTERM(15); 0 = wedge-after-done (work complete), 1 = stall.
- Late import of `reporter.write_riding_report` inside `abort.py`'s shared helper is intentional:
  `reporter.py` imports from `state.py` (directly, for the `RiderState` type hint) and from
  `metrics.py`/`plots.py` (which themselves import from `state.py`); importing `reporter` at
  `abort.py`'s top level would still create a cycle through `rider.py` (which imports both
  `state.py` and `abort.py`). Splitting `reporter.py` into `reporter.py`/`metrics.py`/`plots.py`
  did not change this — none of the three import `abort.py` or `rider.py`, so the late import
  remains necessary and sufficient.
- `metrics.py:_compute_stats` was 61 LOC before `_compute_fetch_counts` was extracted from it — the
  per-fetch-record block (`n_total_fetches`/`n_ok`/`n_regwall_fetches`/`n_failed`/`n_connect_fail`,
  elapsed-time `mean_s`/`median_s`, `wall_s`/`urls_per_min`, `ok_completion_s`), everything derivable
  from `jobs`/`t_job_start` alone before any ride/proxy/pool/load/connect-fail-specific computation
  begins. `_compute_stats` now spreads `**_compute_fetch_counts(...)` into its returned dict — same
  keys/values as before, dict-equal return shape, not a behavior change.
- Pool load (`load_backfill_pool`) is blocking network I/O, run via `run_in_executor` to avoid
  blocking the event loop during the async entry point.
- `_run_slot` and `_watchdog` MUST stay defined in `rider.py`: the dev/ tests patch
  `_fetch_one_url`/`_next_proxy`/`POOL_REFRESH_INTERVAL_S`/`os` via
  `unittest.mock.patch.object(rider_mod, ...)`, which only resolves through the DEFINING module's
  globals — moving these to `fetch.py`/`state.py` silently breaks the test suite. The helpers
  extracted from `_run_slot`/`_apply_fetch_result` (`_next_url_for_slot`, `_fetch_and_apply`,
  `_fetch_and_build_job`, `_apply_fetch_result` and its four status handlers, `_maybe_requeue`) all
  stay in `rider.py` too — none of `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`'s
  patches target these, so no patch target changed, but keeping them here preserves the same
  DEFINING-module-globals guarantee for any future patch.
- `_next_url_for_slot`'s three-way `("continue"|"break"|"proceed", ...)` return exists specifically
  because a bare `continue`/`break` inside an extracted helper does not affect the caller's own
  loop — the original inline block had one `continue` (stale dequeued dup) and two `break`s
  (all_resolved; no open URL left to race), and collapsing all three into a single sentinel (e.g.
  `None`) would have silently turned the `continue` case into a `break`. Verified live, not just by
  inspection: `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`'s
  `test_3_no_spurious_requeue` sub-case A depends on exactly this distinction (a stale dequeued dup
  must retry the inner loop, not exit the ride) and passed unchanged (7/7) after the split.
- Regwall detection (`fetch.py:_is_regwall`) checks `result.markdown.raw_markdown` (browser-rendered
  visible text), NOT `result.html` — `REGWALL_SIGNALS` are embedded as hidden React components in the
  raw HTML of every CoinDesk page, so an html-based check would silently never fire.
- `state.py:STALL_TIMEOUT_S = 3600.0` is only the module-level fallback default (used when
  `run_riding_pool`/`RiderState` are constructed without an explicit `stall_timeout_s`). Production
  runs override it via `RidingScrapeConfig.stall_timeout_s = 300.0` — don't read the module constant
  as "the" production stall timeout.
- `plots.py:_write_load_hist`'s x-axis auto-ranges to data max rather than clamping at
  `page_timeout_s` — `load_s` (elapsed minus the fixed `DELAY_BEFORE_HTML`) can legitimately exceed
  `page_timeout_s` due to post-navigation processing time not covered by the nav timeout; the red
  vertical line marks the nav cap, it is not the axis bound.
