# src/news/platforms/theblock/

## Role

The Block platform implementation using the proxy-pool scrape engine (no browser) and its own RAG collection. Discovery is sitemap-based; the publication date arrives only after fetch. Imported for its registration side effect by src/news/__main__.py; nothing else imports it.

## Public Interface

`__init__.py` exports the platform class and registers an instance at import. Optional attributes read by the pipeline through getattr: discovery timeframe, a master-URL-list flag and a legacy dedup-mode attribute that is unused.

## Flow

Sitemap index fetched directly, via the proxy pool when the direct fetch does not yield XML; sub-sitemaps are selected by mode and parsed into URL and lastmod entries. After the proxy engine fetches raw HTML, the clean pass extracts the JSON-LD article body, converts it to markdown and sets the publication date on the entry.

## Modules

### config.py (14 LOC)

**Purpose:** Platform constants and the proxy-scrape configuration wired to the backfill pool loader.
**Reads:** none.
**Writes:** none.
**Called by:** __init__.py, discover.py.
**Calls out:** src/news/engine/proxy_pool/pool_loaders.py.

### discover.py (161 LOC)

**Purpose:** Sitemap-based article discovery with direct-then-proxy fetching and mode-based sub-sitemap selection.
**Reads:** the sitemap index and selected sub-sitemaps (network).
**Writes:** none.
**Called by:** __init__.py.
**Calls out:** httpx, src/news/engine/proxy_pool/fetch.py, src/news/engine/proxy_pool/pool_loaders.py.

### cleanup.py (111 LOC)

**Purpose:** Parses the JSON-LD article from raw HTML, converts the body to markdown, post-cleans it and stamps the publication date.
**Reads:** raw HTML text and the manifest entry.
**Writes:** mutates the entry's publication date in place.
**Called by:** src/news/clean_pass.py.
**Calls out:** crawl4ai html2text.

### __init__.py (30 LOC)

**Purpose:** The platform class wrapping config, discovery and cleanup; registers itself on import.
**Reads:** none of its own.
**Writes:** the registry entry.
**Called by:** src/news/__main__.py (side-effect import).
**Calls out:** config.py, discover.py, cleanup.py, src/news/registry.py.

## State

None in memory. Discovery output is the single master URL list written by the pipeline.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
