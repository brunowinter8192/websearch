# src/news/engine/

## Role

Generic, platform-agnostic engine modules called by the news pipeline; no platform-specific logic lives here. The browser engine sits directly in this directory; the proxy-pool and proxy-riding engines live in their own subpackages. Touch it to change shared scraping, dedup or reporting behavior.

## Public Interface

`__init__.py` is empty; modules are imported by path. Engine choice is made in the pipeline from the platform's engine attribute.

## Flow

Entries and platform parameters in, all passed explicitly. Dedup filters entries against the raw corpus; the browser scraper fetches the rest with per-URL crawlers and a regwall guard; the chunked job runner persists raw output and block-lists; the reporter renders a job summary.

## Modules

### scrape.py (163 LOC)

**Purpose:** Browser-engine scraper with a fresh crawler per URL, per-domain pacing and a regwall guard.
**Reads:** the entry list and scrape configuration.
**Writes:** body-only markdown files into the output directory.
**Called by:** src/news/pipeline.py, scrape_job.py.
**Calls out:** crawl4ai.

### dedup.py (54 LOC)

**Purpose:** Filters entries to those not yet in the raw corpus and hosts the single publication-date helper.
**Reads:** the entry list, a directory listing and an optional exclusion set.
**Writes:** none.
**Called by:** src/news/pipeline.py, src/news/clean_pass.py.
**Calls out:** none (stdlib only).

### scrape_job.py (104 LOC)

**Purpose:** Chunked raw-only scrape orchestration for scrape-only mode, plus shared raw-persist helpers.
**Reads:** entry chunks and platform configuration.
**Writes:** raw files, the raw manifest and the regwall and empty block-lists.
**Called by:** src/news/pipeline.py.
**Calls out:** none.

### browser_reporter.py (196 LOC)

**Purpose:** Per-job report for browser-engine jobs: a markdown summary and a cumulative progress plot.
**Reads:** in-memory job records and the job start time.
**Writes:** the job summary and plot in the job directory.
**Called by:** src/news/pipeline.py.
**Calls out:** matplotlib.

## State

None owned here. State lives in the pipeline and on disk in the platform's raw directory.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
