# dev/news_pipeline/coindesk_proxy_riding/

## Role
Standalone dev suite for scraping CoinDesk article HTML at scale through rotating proxies with a pool of browser processes and many concurrent rider tasks. Self-contained, with no `src/` imports at module load; the ported production package is validated separately.

## Public Interface
No `__init__.py` — not a package. The runner script is the CLI entry point; the analysis and smoke scripts are separate CLI entries. Other modules are helpers imported by flat name.

## Flow
Runner loads the proxy pool and samples URLs from the CoinDesk inventory -> riding pool fetches each URL through a fresh proxy context, classifying results and rotating burned proxies -> watchdog aborts on stall -> reporter renders job report and plots; raw HTML lands under the output dir. The riding pool under test is `src/news/engine/proxy_riding/`; the `_p*` helper modules split state, fetch, watchdog and report rendering.

## Modules

### p0_pool.py (260 LOC)

**Purpose:** Local copy of the proxy pool machinery: loaders, cooldown manager, and retry helper.
**Reads:** Proxy source lists via its loaders.
**Writes:** nothing.
**Called by:** `run_coindesk_riding.py`, `p2_browser_rider.py`, `_p2_state.py`.
**Calls out:** none.

### p2_browser_rider.py (334 LOC)

**Purpose:** Core riding pool orchestrator: browser instances, rider tasks distributed across them, per-URL proxy context with burn and fail rotation.
**Reads:** Proxy pool via `p0_pool.py`, URL queue.
**Writes:** Raw HTML per ok URL via `_p2_fetch.py`; remaining-URL list on stall via `_p2_watchdog.py`.
**Called by:** `run_coindesk_riding.py`, `smoke_stage1.py`, `p4_reporter.py`, `_p4_stats.py`, `dev/tests/test_riding_*.py`.
**Calls out:** none.

### _p2_state.py (78 LOC)

**Purpose:** Data model of the riding pool: ride and job records, shared run state, and the stall-timeout default.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `p2_browser_rider.py`, `_p2_watchdog.py`.
**Calls out:** none.

### _p2_fetch.py (96 LOC)

**Purpose:** Single-URL fetch mechanics: proxy-context crawl, result classification, regwall detection, raw HTML write.
**Reads:** nothing; takes a live crawler and URL.
**Writes:** Raw HTML per ok URL.
**Called by:** `p2_browser_rider.py`.
**Calls out:** `crawl4ai`.

### _p2_watchdog.py (81 LOC)

**Purpose:** Stall detection and abort-report writing before a hard process exit.
**Reads:** nothing.
**Writes:** Remaining-URL list and job report on stall.
**Called by:** `p2_browser_rider.py`.
**Calls out:** none.

### p3_url_sampler.py (131 LOC)

**Purpose:** Proportional URL sampler over the CoinDesk inventory shards with a per-year floor.
**Reads:** The CoinDesk inventory shards in the main repo's data folder.
**Writes:** nothing; returns the sampled list.
**Called by:** `run_coindesk_riding.py`.
**Calls out:** none.

### p4_reporter.py (206 LOC)

**Purpose:** Orchestrates the report write and renders the job report with count, throughput, percentile, proxy, and regwall sections.
**Reads:** The run state.
**Writes:** `job.md`.
**Called by:** `run_coindesk_riding.py`, `_p2_watchdog.py`.
**Calls out:** none.

### _p4_stats.py (163 LOC)

**Purpose:** Derives all report metrics from the run state.
**Reads:** The run state.
**Writes:** nothing.
**Called by:** `p4_reporter.py`.
**Calls out:** none.

### _p4_plots.py (58 LOC)

**Purpose:** Renders the three report plots: cumulative fetches, ride lengths, regwall rate by position.
**Reads:** nothing; takes the stats dict.
**Writes:** Three PNG files.
**Called by:** `p4_reporter.py`.
**Calls out:** `matplotlib`.

### run_coindesk_riding.py (134 LOC)

**Purpose:** CLI orchestrator wiring pool load, riding pool, and report write end to end.
**Reads:** CLI arguments.
**Writes:** Raw HTML, job report, and plots under the output dir.
**Called by:** CLI only.
**Calls out:** none.

### analyze_write_times.py (251 LOC)

**Purpose:** Reconstructs riding throughput from raw file modification times when the job report is missing.
**Reads:** The raw HTML directory.
**Writes:** `png/raw_write_times_*.png`; summary to stdout.
**Called by:** CLI only.
**Calls out:** `matplotlib`.

### smoke_stage1.py (125 LOC)

**Purpose:** Stage 1 mini live-run smoke validating the production riding package.
**Reads:** The production riding package; a few inventory URLs.
**Writes:** Raw HTML to a temp dir.
**Called by:** CLI only.
**Calls out:** none.

---

## State
`raw/` holds one HTML per ok URL, scoped to the output dir and not committed. `png/` holds tracked historical throughput plots. Design details and CLI defaults: process-docs area news_pipeline.
