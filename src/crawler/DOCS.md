# src/crawler/

## Role

URL discovery and the batch scrape step of the capture-and-index workflow. Discovery merges robots, sitemap and navigation-tree feeders over plain HTTP; the batch scraper captures a URL list as raw markdown. Single-URL scraping lives in src/scraper. Only discovery backs a CLI subcommand.

## Public Interface

`__init__.py` is empty. Entry modules run as `python -m src.crawler.<module>` and expose importable workflow entries.

- pipe_scraper.py: batch scrape entry.
- discovery.py: discovery entry used by cli.py.
- seed_feeders.py: the three feeder entries.
- seed_feeders_scope.py: shared feeder result type, URL normalization and host validation.

## Flow

Discovery: seed URL in, three feeders run concurrently over HTTP, each host-scoped and deduped, merged with the seed into a source-tagged URL set; failed feeders are reported, never treated as empty. Batch scrape: URL list in, per-domain paced raw crawl by one of two engines, out come markdown files, a report and an onward-links file in /tmp and a per-URL JSONL log. Batch scrape uses both engines from `src/scraper/`; the run log is pruned through `src/log_janitor.py`. The `pipe_scraper_*` modules split acquisition, pacing, records and constants; the `seed_feeders_*` modules split the three feeders, scope and constants.

## Modules

### pipe_scraper.py (112 LOC)

**Purpose:** Entry point of the batch scrape step; dispatches a URL list per run to the chromium or camoufox engine and prints the summary.
**Reads:** URL list from a file or the caller.
**Writes:** console summary; report files via pipe_scraper_report.py.
**Called by:** the capture-and-index skill; importable.
**Calls out:** crawl4ai.

### pipe_scraper_constants.py (7 LOC)

**Purpose:** Pacing and timeout values shared by several pipe_scraper siblings.
**Reads:** none.
**Writes:** none.
**Called by:** pipe_scraper.py, pipe_scraper_config.py.
**Calls out:** none.

### pipe_scraper_pacing.py (24 LOC)

**Purpose:** Engine-agnostic per-domain pacing gate: delay, jitter and concurrency cap.
**Reads:** none.
**Writes:** none.
**Called by:** pipe_scraper_acquisition.py.
**Calls out:** none (stdlib only).

### pipe_scraper_config.py (48 LOC)

**Purpose:** Builds the fixed anti-bot browser and run configuration of the chromium engine, optimized for reachability.
**Reads:** none.
**Writes:** none.
**Called by:** pipe_scraper.py.
**Calls out:** crawl4ai.

### pipe_scraper_acquisition.py (133 LOC)

**Purpose:** Per-URL executors for both engines; collects onward links on the chromium engine; classifies nothing.
**Reads:** the URL list from pipe_scraper.py.
**Writes:** one markdown file per URL; one JSONL record per URL via pipe_scraper_records.py.
**Called by:** pipe_scraper.py, pipe_scraper_report.py, src/scraper/index_scrapes.py.
**Calls out:** crawl4ai.

### pipe_scraper_records.py (39 LOC)

**Purpose:** Assembles the per-URL JSONL record for each engine and hands it to the logger.
**Reads:** engine results.
**Writes:** via pipe_scrape_logger.py.
**Called by:** pipe_scraper_acquisition.py.
**Calls out:** none.

### pipe_scraper_report.py (62 LOC)

**Purpose:** Writes the per-URL status table and the onward-links file to /tmp and prints a factual console summary.
**Reads:** per-URL results of the run.
**Writes:** report and links files in /tmp; console output.
**Called by:** pipe_scraper.py.
**Calls out:** none.

### pipe_scrape_logger.py (19 LOC)

**Purpose:** Per-URL JSONL log writer for the batch scraper, shared by both engines, separate from the ad-hoc scrape log.
**Reads:** the pipe-scrape log-path environment variable.
**Writes:** the pipe scrape JSONL log under src/logs (gitignored).
**Called by:** pipe_scraper_records.py.
**Calls out:** none.

### seed_feeders.py (60 LOC)

**Purpose:** The three feeder workflows (robots, sitemap, navigation tree); each returns a result object and turns orchestration failures into a not-ok result.
**Reads:** live HTTP via one fresh client per workflow call.
**Writes:** none.
**Called by:** discovery.py.
**Calls out:** httpx.

### seed_feeders_constants.py (8 LOC)

**Purpose:** Shared HTTP timeout, user agent, conventional sitemap paths and concurrency caps for the feeders.
**Reads:** none.
**Writes:** none.
**Called by:** seed_feeders.py, seed_feeders_robots.py, seed_feeders_sitemap.py, seed_feeders_navtree.py.
**Calls out:** none.

### seed_feeders_scope.py (71 LOC)

**Purpose:** Feeder result type, URL normalization, host-only scoping with order-preserving dedup, and seed validation.
**Reads:** none.
**Writes:** none.
**Called by:** seed_feeders.py, discovery.py, pipe_scraper_acquisition.py.
**Calls out:** none (stdlib only).

### seed_feeders_robots.py (40 LOC)

**Purpose:** Fetches robots.txt and parses Allow, Disallow and Sitemap directives.
**Reads:** robots.txt over HTTP.
**Writes:** none.
**Called by:** seed_feeders.py.
**Calls out:** httpx.

### seed_feeders_sitemap.py (69 LOC)

**Purpose:** Fetches and parses sitemaps, resolving sitemap indexes recursively with bounded concurrency and cycle protection.
**Reads:** sitemap documents over HTTP.
**Writes:** none.
**Called by:** seed_feeders.py.
**Calls out:** httpx.

### seed_feeders_navtree.py (267 LOC)

**Purpose:** Detects a site's own frontend navigation tree in page payloads, walks it and unions every exposed version.
**Reads:** the seed page and each version's root page over HTTP.
**Writes:** none.
**Called by:** seed_feeders.py.
**Calls out:** httpx.

### discovery.py (70 LOC)

**Purpose:** Discovery entry point: runs all three feeders concurrently and merges their output with the seed into one source-tagged URL set.
**Reads:** feeder output only; fetches nothing itself.
**Writes:** none; returns a result object.
**Called by:** cli.py.
**Calls out:** none.

## State

None in memory. Persistence is the pipe scrape JSONL log and the per-run files in /tmp and the chosen output directory.

Details, decisions and observed evidence: process-docs/url_discovery, process-docs/pipe_scraper_hardening, process-docs/scrape_pipeline and process-docs/refactor_sweep.
