# src/news/

## Role

Multi-platform news ingestion pipeline, run as `python -m src.news --source <platform>`. Discovers articles, dedups against the raw corpus and scrapes raw content into data/news; one platform also gets an in-pipe clean pass. Indexing stays decoupled. Touch it to add a source or change orchestration. Self-contained: never import src/crawler or src/scraper.

## Public Interface

`__init__.py` is empty. The package runs as a module through __main__.py; pipeline.py exposes the three async entries (full run, discover only, scrape only).

## Flow

Arguments in; the chosen platform module is imported (registering itself) and looked up by name. The pipeline then discovers, dedups, scrapes and persists raw files, dispatching the scrape step on the platform's engine attribute (browser, proxy pool or proxy riding), optionally followed by the clean pass. Scrape-only mode backfills from stored discover lists.

## Modules

### pipeline.py (364 LOC)

**Purpose:** Entry module: the three async orchestrators plus per-engine arm helpers, dispatching on the platform's scrape engine.
**Reads:** the per-platform raw corpus and discover files under data/news.
**Writes:** raw files, the raw manifest, discover block-lists and job reports; delegates bookkeeping and clean-pass writes to siblings.
**Called by:** __main__.py.
**Calls out:** platform.py, engine/ (dedup, scrape, scrape_job, browser_reporter, proxy_pool, proxy_riding), pipeline_support.py, clean_pass.py.

### pipeline_support.py (83 LOC)

**Purpose:** Run bookkeeping shared by the orchestrators: logging setup, connectivity precondition and the master-list, snapshot and last-run marker writers.
**Reads:** the platform's precondition URL; the existing master URL list.
**Writes:** per-day log file, last-run marker, master URL list and discover snapshot.
**Called by:** pipeline.py.
**Calls out:** none (stdlib only).

### clean_pass.py (48 LOC)

**Purpose:** In-pipe clean pass of the proxy-pool platform: cleans raw markdown and writes articles into the RAG collection directory.
**Reads:** raw markdown files; the existing body-less URL list.
**Writes:** cleaned article files in the collection directory; the body-less URL list.
**Called by:** pipeline.py.
**Calls out:** engine/dedup.py.

### __main__.py (155 LOC)

**Purpose:** Argparse entry point: imports platform modules for registration, resolves the platform and dispatches to the matching pipeline entry.
**Reads:** CLI arguments.
**Writes:** stdout.
**Called by:** the `python -m src.news` entry.
**Calls out:** platforms/, registry.py, pipeline.py.

### platform.py (35 LOC)

**Purpose:** The extension seam: the platform protocol and the scrape-configuration dataclasses.
**Reads:** none.
**Writes:** none.
**Called by:** pipeline.py, registry.py, platforms/, engine/.
**Calls out:** none (stdlib only).

### registry.py (17 LOC)

**Purpose:** In-memory name-to-platform registry filled at platform import time.
**Reads:** in-memory registry.
**Writes:** in-memory registry.
**Called by:** __main__.py, platforms/.
**Calls out:** platform.py.

## State

The registry's in-memory map, filled as a side effect of platform imports. The durable state is the per-platform corpus under data/news (raw, discover, clean, scrape jobs); the raw manifest and discover block-lists drive dedup and make reruns resumable.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
