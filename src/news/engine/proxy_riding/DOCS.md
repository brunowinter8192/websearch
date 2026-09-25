# src/news/engine/proxy_riding/

## Role

Third scrape engine: browser plus rotating proxies, built to get past CoinDesk's IP-rate regwall for a large article-body backfill. Each URL runs in a browser context bound to a proxy that is burned after repeated regwall or failure strikes; a watchdog hard-aborts on stall. Independent of the other two engines.

## Public Interface

`__init__.py` is empty. Entry paths:

- scrape.py: the engine entry and its configuration dataclass, used by the news pipeline in scrape-only mode.
- reporter.py: the job report writer, used after normal completion and by the abort paths.
- rider.py: the pool runner entry, a stable import path.
- state.py: the shared state and record dataclasses.

## Flow

The entry builds the URL queue, loads and filters the proxy pool and creates the cooldown manager; the runner starts several browsers, many slot tasks and one watchdog. Each slot rides URLs on a proxy until burned, racing open URLs at the tail. Ok pages are written as raw HTML on first arrival; the report and manifest are derived from the final state. Riding reuses `src/news/engine/proxy_pool/` for proxy keys and pool loaders.

## Modules

### cooldown.py (80 LOC)

**Purpose:** Riding-specific proxy cooldown manager with two per-run policies, isolated from the shared pool cooldown.
**Reads:** in-memory burn and eligibility maps.
**Writes:** the same maps when a proxy is burned.
**Called by:** rider.py, scrape.py, state.py.
**Calls out:** none.

### state.py (82 LOC)

**Purpose:** Shared riding dataclasses (job, ride and runner state); the import source for all riding modules and dev tests.
**Reads:** none.
**Writes:** none.
**Called by:** rider.py, fetch.py, abort.py, reporter.py, metrics.py, scrape.py; dev tests.
**Calls out:** none.

### fetch.py (95 LOC)

**Purpose:** Per-URL fetch and outcome classification: the crawl4ai call, regwall detection, connect-failure subtypes and raw HTML persistence.
**Reads:** none (per-call).
**Writes:** raw HTML files under the output directory.
**Called by:** rider.py.
**Calls out:** crawl4ai.

### abort.py (54 LOC)

**Purpose:** The three watchdog and signal abort paths with a shared write-report-and-hard-exit helper.
**Reads:** the rider state.
**Writes:** the job report and plots when the reporter succeeds.
**Called by:** rider.py.
**Calls out:** none.

### rider.py (381 LOC)

**Purpose:** Runner: orchestrates browsers, slot coroutines, per-URL proxy contexts, burn and fail rotation, pool refresh, the watchdog and signal handlers.
**Reads:** the URL queue, proxy pool and shared cooldown state.
**Writes:** raw HTML via fetch.py; triggers report writes on abort.
**Called by:** scrape.py.
**Calls out:** crawl4ai.

### reporter.py (200 LOC)

**Purpose:** Report orchestrator and job-summary markdown rendering from a completed rider state.
**Reads:** the rider state and job start time.
**Writes:** the job summary in the job directory; plots via plots.py.
**Called by:** src/news/scrape_only.py, abort.py.
**Calls out:** none.

### metrics.py (168 LOC)

**Purpose:** Derives job statistics from the rider state for the report and plots.
**Reads:** the rider state and job start time.
**Writes:** none; returns a stats mapping.
**Called by:** reporter.py.
**Calls out:** none.

### plots.py (74 LOC)

**Purpose:** Matplotlib writers for the cumulative and histogram plots of a job.
**Reads:** the stats mapping handed in.
**Writes:** plot files in the job directory.
**Called by:** reporter.py.
**Calls out:** matplotlib.

### scrape.py (120 LOC)

**Purpose:** Pipeline entry and manifest adapter: loads and shuffles the pool, runs the pool runner and maps job records to the pipeline manifest.
**Reads:** the entry list, the riding configuration and the proxy pool (network).
**Writes:** nothing directly; the runner writes raw HTML.
**Called by:** src/news/scrape_only.py.
**Calls out:** none.

## State

The rider state defined in state.py is the shared mutable state across slot coroutines and the watchdog; the runner owns and mutates it, the reporter, metrics and manifest adapter read it. Single-threaded asyncio, plus a lock guarding proxy cursor advancement.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
