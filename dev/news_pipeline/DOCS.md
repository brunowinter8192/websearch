# dev/news_pipeline/

## Role
Per-domain news scraping pipeline for the trading-bot data layer: CoinDesk articles into the `coindesk` RAG collection, runnable end to end with a single daily command. Stays in `dev/`; promotion to `src/` deferred. Sub-suites (`theblock/`, `coindesk_proxy_riding/`, `exploration/`) document their own modules.

## Public Interface
No `__init__.py` — not a package. `run_pipeline.py` is the daily entry point; each numbered stage script is also runnable alone via `./venv/bin/python`.

## Flow
Pipeline runner checks preconditions -> discover (UI pagination, 48-hour window) -> dedup against the collection directory -> fresh-context scrape -> cleanup of navigation and footer noise -> publish to the RAG collection and index.

## Modules

### run_pipeline.py (272 LOC)

**Purpose:** Single-command orchestrator chaining preconditions, discover, dedup, scrape, cleanup, and publish, clearing stage data at start.
**Reads:** Preconditions: internet reachability and rag-cli collection listing.
**Writes:** Daily pipeline log and last-run marker under `src/logs/`.
**Called by:** CLI only.
**Calls out:** the stage scripts, `rag-cli`.

### 01_coindesk_discover.py (354 LOC)

**Purpose:** Discovers CoinDesk articles via UI pagination in a background Chrome, stopping once enough articles older than the window are seen.
**Reads:** Live CoinDesk site via pydoll.
**Writes:** `01_json/discover_<ts>.json`.
**Called by:** `run_pipeline.py`, CLI.
**Calls out:** `pydoll`.

### 02_coindesk_scrape.py (154 LOC)

**Purpose:** Reference scrape over a shared crawler session that hits the regwall; superseded by the fresh-context scrape.
**Reads:** Discover JSON via `--input` or the newest one.
**Writes:** `02_output/` markdown and manifest.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 02b_coindesk_scrape_fresh_context.py (245 LOC)

**Purpose:** Production-quality scrape with a fresh crawler per URL and the production per-domain pacing, with a loud regwall guard.
**Reads:** Discover JSON via `--input` or the newest one.
**Writes:** `02b_data/` markdown and manifest.
**Called by:** `run_pipeline.py`, CLI.
**Calls out:** `crawl4ai`.

### 03_coindesk_cleanup.py (232 LOC)

**Purpose:** Extracts the clean article body from scraped markdown, strips navigation and footer noise, and normalizes structure for RAG ingestion.
**Reads:** `02b_data/` markdown and frontmatter.
**Writes:** `03_data/` clean markdown and manifest.
**Called by:** `run_pipeline.py`, CLI.
**Calls out:** none.

### 04_dedup.py (107 LOC)

**Purpose:** Drops URLs whose target file already exists in the coindesk RAG collection directory; filesystem presence is the seen-state.
**Reads:** Discover JSON via `--input` or the newest one; the collection directory.
**Writes:** `04_json/discover_filtered_<ts>.json`.
**Called by:** `run_pipeline.py`, CLI.
**Calls out:** none.

### 05_publish.py (129 LOC)

**Purpose:** Copies cleaned markdown into the coindesk RAG collection directory and triggers indexing; idempotent.
**Reads:** `03_data/` manifest and markdown; the collection directory.
**Writes:** Files in the RAG collection directory; triggers rag-cli indexing.
**Called by:** `run_pipeline.py`, CLI.
**Calls out:** `rag-cli`.

### prod_scrape_smoke.py (161 LOC)

**Purpose:** Investigation tool: empirical regwall baseline through the production shared-session scraper over a discover-filtered URL set.
**Reads:** A discover-filtered JSON.
**Writes:** `smoke_output/` raw files and regwall review (gitignored).
**Called by:** CLI only.
**Calls out:** `src/crawler/pipe_scraper.py`.

### scrape_isolation_smoke.py (249 LOC)

**Purpose:** Investigation tool: compares two isolation candidates (shared crawler with per-URL timezone, fresh crawler per URL) over the same URLs.
**Reads:** A discover-filtered JSON.
**Writes:** `smoke_output/` review files (gitignored); comparison table to stdout.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

---

## State
Stage output folders (`01_json/`, `02_output/`, `02b_data/`, `03_data/`, `04_json/`, `smoke_output/`) are gitignored intermediates. `md/` holds two tracked historical run-analysis reports. Details: process-docs area news_pipeline.
