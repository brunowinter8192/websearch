# src/news/

## Role

Multi-platform news ingestion pipeline, run as `python -m src.news --source <platform>`. Discovers articles, dedups against the raw corpus and scrapes raw content into data/news; one platform also gets an in-pipe clean pass. Indexing stays decoupled. Touch it to add a source or change orchestration. Self-contained: never import src/crawler or src/scraper.

## Public Interface

`__init__.py` is empty. The package runs as a module through __main__.py; pipeline.py, discover_only.py and scrape_only.py each expose one async workflow (full run, discover only, scrape only).

## Flow

Arguments in; the chosen platform is looked up by name in registry.py. The pipeline then discovers, dedups, scrapes and persists raw files, dispatching the scrape step on the platform's engine attribute (browser, proxy pool or proxy riding), optionally followed by the clean pass. Scrape-only mode backfills from stored discover lists. The three workflow modules compose `engine/`, `pipeline_support.py`, `clean_pass.py` and `platform.py`; `registry.py` imports `platforms/`.

## Modules

### pipeline.py (201 LOC)

**Purpose:** Full-run workflow: discover, dedup, scrape and persist, dispatching on the platform's scrape engine.

**Reads:** the per-platform raw corpus and discover files under data/news.
**Writes:** raw files, the raw manifest, discover block-lists and job reports; delegates bookkeeping and clean-pass writes to siblings.
**Called by:** __main__.py.
**Calls out:** none.

### discover_only.py (23 LOC)

**Purpose:** Discover-only workflow: discover, optional master-list persistence and last-run marker.
**Reads:** the platform's discover output.
**Writes:** master URL list and last-run marker via pipeline_support.py.
**Called by:** __main__.py.
**Calls out:** none.

### scrape_only.py (178 LOC)

**Purpose:** Scrape-only workflow: loads stored discover entries, dedups against raw and scrapes through the riding or browser engine.
**Reads:** the platform's stored discover shards and the raw corpus.
**Writes:** raw files, the raw manifest and job reports.
**Called by:** __main__.py.
**Calls out:** none.

### pipeline_support.py (115 LOC)

**Purpose:** Run bookkeeping shared by the three workflows: run start, logging setup, connectivity precondition and the master-list, snapshot, last-run marker and manifest-entry helpers.
**Reads:** the platform's precondition URL; the existing master URL list.
**Writes:** per-day log file, last-run marker, master URL list and discover snapshot.
**Called by:** pipeline.py, discover_only.py, scrape_only.py, engine/scrape_job.py.
**Calls out:** none (stdlib only).

### clean_pass.py (48 LOC)

**Purpose:** In-pipe clean pass of the proxy-pool platform: cleans raw markdown and writes articles into the RAG collection directory.
**Reads:** raw markdown files; the existing body-less URL list.
**Writes:** cleaned article files in the collection directory; the body-less URL list.
**Called by:** pipeline.py.
**Calls out:** none.

### __main__.py (162 LOC)

**Purpose:** Argparse entry point: resolves the platform and dispatches to the matching workflow.
**Reads:** CLI arguments.
**Writes:** stdout.
**Called by:** the `python -m src.news` entry.
**Calls out:** none.

### platform.py (52 LOC)

**Purpose:** The extension seam: the platform protocol with declared defaults for its optional attributes, and the scrape-configuration dataclasses.
**Reads:** none.
**Writes:** none.
**Called by:** pipeline.py, registry.py, platforms/, engine/.
**Calls out:** none (stdlib only).

### registry.py (16 LOC)

**Purpose:** Name-to-platform lookup over the fixed tuple of platform classes.
**Reads:** the platform classes.
**Writes:** none.
**Called by:** __main__.py.
**Calls out:** none.

## State

No in-memory state. The durable state is the per-platform corpus under data/news (raw, discover, clean, scrape jobs); the raw manifest and discover block-lists drive dedup and make reruns resumable.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
