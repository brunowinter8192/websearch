# dev/news_pipeline/theblock/

## Role
Discovery and proxy-pool infrastructure for scraping theblock.co past Cloudflare: proxy source aggregation, liveness and CF-pass checking, sitemap discovery, and per-source quality tracking. `acquire_pipe/` (own DOCS.md) is the fetch pipeline built on top; `jhao104/` is a vendored comparison baseline, not documented here.

## Public Interface
No `__init__.py` — not a package. The probe scripts and the pipe script are CLI entry points run via `./venv/bin/python`; underscore modules are helpers imported by flat name.

## Flow
Public proxy sources -> pool size, liveness, and CF-pass measurements -> full pipe (neutral liveness, CF-pass check, sitemap sub-URL discovery with proxy rotation) -> funnel log, cumulative per-source scoreboard, and cumulative proxy status log.

## Modules

### curated_sources.py (232 LOC)

**Purpose:** Unified proxy source hub: curated loaders, the large backfill pool merge, standalone per-repo loaders, and shared fetch and dedup helpers.
**Reads:** Public proxy-list source URLs.
**Writes:** nothing; returns proxy lists in memory.
**Called by:** `acquire_pipe/acquire_pipe.py`, `probe_liveness.py`, `pipe_theblock.py`, `probe_48h_article_fetch.py`.
**Calls out:** `monosans_loader.py`, `httpx`.

### monosans_loader.py (36 LOC)

**Purpose:** Fetches the monosans live JSON proxy list and returns protocol and host-port tuples.
**Reads:** The monosans live JSON endpoint.
**Writes:** nothing; returns a tuple list.
**Called by:** `probe_liveness.py`, `curated_sources.py`.
**Calls out:** `httpx`.

### proxy_status_log.py (92 LOC)

**Purpose:** Cumulative proxy-status log keyed by canonical proxy key, bounded by unique proxy count, with the shared key builder and freshness partition.
**Reads:** `logs/proxy_status_log.json`.
**Writes:** `logs/proxy_status_log.json`, upserted.
**Called by:** `probe_liveness.py`, `curated_sources.py`, `acquire_pipe/p2_cooldown.py`, `acquire_pipe/p5_logger.py`.
**Calls out:** none.

### probe_discovery.py (283 LOC)

**Purpose:** Measures discovery coverage and URL taxonomy over sitemap union, news sitemap, RSS, and a bounded UI crawl, resume-safe via per-sub checkpoints.
**Reads:** theblock.co sitemap index, news sitemap, RSS feed.
**Writes:** `discover_coverage_report.md`; checkpoints in `cache/`.
**Called by:** CLI only; `pipe_theblock.py`.
**Calls out:** `_probe_discovery_report.py`.

### _probe_discovery_report.py (221 LOC)

**Purpose:** Coverage report assembly with cross-method comparison, gap detection, and URL taxonomy helpers.
**Reads:** nothing; takes result data.
**Writes:** nothing; returns the rendered markdown.
**Called by:** `probe_discovery.py`.
**Calls out:** none.

### probe_pool_size.py (342 LOC)

**Purpose:** Measures raw proxy pool size from many public source URLs by pure fetch, parse, and count with no liveness checking.
**Reads:** Public proxy-list source URLs.
**Writes:** `probe_pool_size_reports/` (gitignored).
**Called by:** CLI only; `probe_repo_cf_survey.py`, `probe_liveness.py`.
**Calls out:** `httpx`.

### probe_repo_cf_survey.py (295 LOC)

**Purpose:** Ranks source repos by CF-pass rate against theblock.co on a sample per repo; its ranking decided the backfill repo set.
**Reads:** Proxy lists from `probe_pool_size.py`.
**Writes:** `probe_repo_cf_survey_reports/` (gitignored).
**Called by:** CLI only.
**Calls out:** `curl_cffi`, `probe_pool_size.py`.

### probe_liveness.py (192 LOC)

**Purpose:** Instrumented async liveness checker with freeze, sample, full, and live-source modes, dead-reason classification, and cumulative status folding.
**Reads:** Source lists, live sources, and the frozen pool.
**Writes:** `probe_liveness_logs/sweep_log.md`, the status log, and `frozen_pool/`.
**Called by:** CLI only; `pipe_theblock.py`.
**Calls out:** `_probe_liveness_classify.py`, `_probe_liveness_report.py`, `probe_pool_size.py`, `curated_sources.py`, `proxy_status_log.py`, `curl_cffi`.

### _probe_liveness_classify.py (108 LOC)

**Purpose:** Single-proxy liveness check and mapping of request exceptions to dead-reason buckets.
**Reads:** The check URL through the given proxy.
**Writes:** nothing; returns one result per proxy.
**Called by:** `probe_liveness.py`.
**Calls out:** `curl_cffi`.

### _probe_liveness_report.py (100 LOC)

**Purpose:** Console summary, sweep-log entry, and unknown-bucket log for a liveness run.
**Reads:** nothing; takes the result list.
**Writes:** `probe_liveness_logs/` sweep log and unknown-error logs; stdout.
**Called by:** `probe_liveness.py`.
**Calls out:** none.

### source_tracker.py (291 LOC)

**Purpose:** Per-source attribution, cumulative scoreboard, and freshness tracking, called once per pipe run.
**Reads:** The fresh-pool output of the pipe, scoreboard JSON, snapshots.
**Writes:** Scoreboard JSON and markdown, freshness log, snapshots.
**Called by:** `pipe_theblock.py`.
**Calls out:** none.

### pipe_theblock.py (327 LOC)

**Purpose:** Full proxy pipeline: neutral liveness, CF-pass check, and sitemap sub-URL discovery with sequential proxy exhaustion.
**Reads:** The curated fresh source pool.
**Writes:** `pipe_log.md` funnel entry; sub-sitemap checkpoints in `cache/`.
**Called by:** CLI only.
**Calls out:** `_pipe_theblock_cf.py`, `probe_liveness.py`, `probe_pool_size.py`, `probe_discovery.py`, `source_tracker.py`, `curated_sources.py`.

### _pipe_theblock_cf.py (55 LOC)

**Purpose:** CF-pass primitives: chrome-impersonating GET through a proxy, XML marker check, threaded check.
**Reads:** The CF check target through each proxy.
**Writes:** stdout progress.
**Called by:** `pipe_theblock.py`.
**Calls out:** `curl_cffi`.

### probe_curated_theblock_cf.py (163 LOC)

**Purpose:** Standalone direct CF-pass probe on the curated list without an alive pre-filter.
**Reads:** The curated proxy list.
**Writes:** `probe_curated_theblock_cf_reports/` (gitignored).
**Called by:** CLI only.
**Calls out:** `curl_cffi`, `curated_sources.py`.

### probe_curl_cffi_discriminator.py (268 LOC)

**Purpose:** Discriminates an ambiguous zero-pass result by retesting the neutral pool with browser-impersonating curl_cffi.
**Reads:** The neutral proxy pool and a real sub-sitemap.
**Writes:** `probe_curl_cffi_discriminator_reports/` (gitignored).
**Called by:** CLI only.
**Calls out:** `curl_cffi`.

### probe_48h_article_fetch.py (160 LOC)

**Purpose:** 48-hour article delta probe using parallel wave fetching over the full pool.
**Reads:** The backfill pool and the theblock sitemap.
**Writes:** `probe_48h_output/` (gitignored).
**Called by:** CLI only.
**Calls out:** `acquire_pipe/p1_fetch.py`, `curated_sources.py`.

### probe_monosans.sh (81 LOC)

**Purpose:** Evidence probe for the monosans scraper-checker pool yield against theblock.co via Docker, with a neutral and a theblock check URL.
**Reads:** The monosans scraper-checker Docker image and two config files.
**Writes:** `monosans_out_neutral/`, `monosans_out_theblock/` (ephemeral, gitignored).
**Called by:** CLI only.
**Calls out:** Docker.

---

## State
Tracked state: the funnel log, the cumulative per-source scoreboard (JSON canonical, markdown rendered), the freshness log, the liveness sweep log, and the cumulative proxy status log. Everything else (caches, pools, snapshots, probe reports, monosans outputs, unknown-error logs) is ephemeral and gitignored. Findings and numbers: process-docs area news_pipeline.
