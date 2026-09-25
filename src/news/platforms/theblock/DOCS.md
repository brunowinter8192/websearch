# src/news/platforms/theblock/

## Role

The Block platform implementation using the proxy-pool scrape engine (no browser) and its own RAG collection. Discovery is sitemap-based; the publication date arrives only after fetch. Instantiated by src/news/registry.py; nothing else imports it.

## Public Interface

`__init__.py` exports the platform class. The class subclasses the platform protocol and inherits its declared defaults for the optional attributes the pipeline reads directly; a legacy dedup-mode attribute is unused.

## Flow

Sitemap index fetched directly, via the proxy pool when the direct fetch does not yield XML; sub-sitemaps are selected by mode and parsed into URL and lastmod entries. After the proxy engine fetches raw HTML, the clean pass extracts the JSON-LD article body, converts it to markdown and sets the publication date on the entry. Proxy-pool fetch and loader helpers come from `src/news/engine/proxy_pool/`; the package `__init__.py` composes config, discover and cleanup.

## Modules

### config.py (14 LOC)

**Purpose:** Platform constants and the proxy-scrape configuration wired to the backfill pool loader.
**Reads:** none.
**Writes:** none.
**Called by:** __init__.py, discover.py.
**Calls out:** none.

### discover.py (179 LOC)

**Purpose:** Sitemap-based article discovery with direct-then-proxy fetching and mode-based sub-sitemap selection.
**Reads:** the sitemap index and selected sub-sitemaps (network).
**Writes:** none.
**Called by:** __init__.py.
**Calls out:** httpx.

### cleanup.py (112 LOC)

**Purpose:** Parses the JSON-LD article from raw HTML, converts the body to markdown, post-cleans it and stamps the publication date.
**Reads:** raw HTML text and the manifest entry.
**Writes:** mutates the entry's publication date in place.
**Called by:** `__init__.py`, which exposes it as the platform's cleanup method that src/news/clean_pass.py invokes.
**Calls out:** crawl4ai html2text.

### __init__.py (26 LOC)

**Purpose:** The platform class wrapping config, discovery and cleanup.
**Reads:** none of its own.
**Writes:** none.
**Called by:** src/news/registry.py.
**Calls out:** none.

## State

None in memory. Discovery output is the single master URL list written by the pipeline.

Details, decisions and observed evidence: process-docs/news_pipeline, process-docs/pooling and process-docs/refactor_sweep.
