# src/news/engine/proxy_pool/

## Role

Generic proxy-rotation scrape engine used when a platform's engine attribute is proxy pool. Sustains concurrent fetching through a rotating pool of HTTP and SOCKS proxies with pool refresh, strikes lifecycle, per-job lock and audit trail. No platform logic. Touch it for rotation mechanics, pool sources or job lifecycle.

## Public Interface

`__init__.py` is empty; callers import modules by path.

- scrape.py: the engine entry used by the news pipeline.
- pool_loaders.py: the pool provider consumed by platform proxy-scrape configurations.

## Flow

The pipeline takes the job lock, starts the janitor and opens the acquire logger; the engine entry builds a cooldown manager and runs the loop. The loop loads the pool, builds an active buffer and fetches (proxy, URL) batches concurrently, refreshing the pool periodically. Ok fetches are written as files; events stream to JSONL; the janitor derives a job report at the end.

## Modules

### scrape.py (81 LOC)

**Purpose:** Engine entry: wires the loop with a caller-supplied logger and returns the pipeline manifest.
**Reads:** the entry list and the pool provider.
**Writes:** one file per ok fetch in the output directory.
**Called by:** src/news/pipeline.py.
**Calls out:** none.

### loop.py (296 LOC)

**Purpose:** Sustained concurrent rotation loop with pool refresh, strikes lifecycle, tail race, wait on exhaustion and stall termination.
**Reads:** the pool provider callback and the target URL list.
**Writes:** through the logger and cooldown manager; content files via the content handler.
**Called by:** scrape.py.
**Calls out:** none.

### fetch.py (37 LOC)

**Purpose:** Chrome-impersonating HTTP fetch through a proxy with a content-type gate; returns status, content and reason.
**Reads:** the remote URL via curl_cffi.
**Writes:** none.
**Called by:** loop.py, src/news/platforms/theblock/discover.py.
**Calls out:** curl_cffi.

### cooldown.py (37 LOC)

**Purpose:** In-memory per-job proxy cooldown tracking with a fixed burn window.
**Reads:** none.
**Writes:** none.
**Called by:** buffer.py, loop.py, scrape.py.
**Calls out:** none.

### buffer.py (32 LOC)

**Purpose:** Pure helpers that build and refill the active (proxy, URL) buffer; holds the buffer and concurrency defaults.
**Reads:** the proxy pool and cooldown eligibility.
**Writes:** none; returns new lists.
**Called by:** loop.py.
**Calls out:** none.

### logger.py (52 LOC)

**Purpose:** Streams per-fetch, pool-refresh and pool-source events to a line-buffered JSONL file.
**Reads:** events pushed by callers.
**Writes:** the acquire-events JSONL in the platform's proxy-pool log directory.
**Called by:** src/news/pipeline.py, loop.py, scrape.py.
**Calls out:** none.

### janitor.py (264 LOC)

**Purpose:** Job lifecycle: wipes transient directories at start and derives the job report and cumulative plot from the JSONL at the end.
**Reads:** the acquire-events JSONL.
**Writes:** job report and plot; wipes log and report directories.
**Called by:** src/news/pipeline.py.
**Calls out:** matplotlib.

### box_lock.py (94 LOC)

**Purpose:** System-wide single-job flock with a sidecar for busy messages and stale-lock recovery.
**Reads:** the lock sidecar under the user lock directory.
**Writes:** the lock and sidecar files under the user lock directory.
**Called by:** src/news/pipeline.py.
**Calls out:** none (stdlib only).

### proxy_key.py (14 LOC)

**Purpose:** Canonical proxy key with authentication stripped.
**Reads:** none.
**Writes:** none.
**Called by:** cooldown.py, logger.py, pool_loaders.py, src/news/engine/proxy_riding/cooldown.py.
**Calls out:** none (stdlib only).

### pool_retry.py (20 LOC)

**Purpose:** Bounded exponential-backoff retry wrapper for pool-source HTTP fetches.
**Reads:** none.
**Writes:** none.
**Called by:** monosans_loader.py, pool_loaders.py.
**Calls out:** none (stdlib only).

### pool_loaders.py (184 LOC)

**Purpose:** Fetches all proxy-list sources with per-source failure isolation and returns the deduplicated pool plus per-source outcomes.
**Reads:** public GitHub-hosted proxy lists over HTTP.
**Writes:** none.
**Called by:** src/news/platforms/theblock/config.py, src/news/platforms/theblock/discover.py, src/news/engine/proxy_riding/scrape.py.
**Calls out:** httpx.

### monosans_loader.py (38 LOC)

**Purpose:** Loads the monosans JSON proxy list with retry.
**Reads:** the monosans list over HTTP.
**Writes:** none.
**Called by:** pool_loaders.py.
**Calls out:** httpx.

## State

The cooldown manager and buffer are per-job and in-memory. Durable artifacts are the acquire-events JSONL, the job report and the lock files, all managed per job.

Details, decisions and observed evidence: process-docs/pooling, process-docs/news_pipeline and process-docs/refactor_sweep.
