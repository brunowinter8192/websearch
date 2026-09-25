# src/news/platforms/coindesk/

## Role

CoinDesk platform implementation using the proxy-riding scrape engine and raw HTML output. Imported for its registration side effect by src/news/__main__.py; nothing else imports from here directly. Touch it to change CoinDesk discovery, regwall signals or cleanup.

## Public Interface

`__init__.py` exports the CoinDesk platform class and registers an instance at import.

## Flow

Discovery warms a real Chrome session under HAR capture to obtain the timeline API request, then pages backwards through the timeline by cursor, writing per-year shard files crash-safely. Scrape-only mode reloads the shards filtered by year, date range and limit and hands them to the riding engine. The package `__init__.py` composes config, discover, shards and cleanup and registers with `src/news/registry.py`.

## Modules

### config.py (25 LOC)

**Purpose:** Platform constants: regwall signal strings, scrape configuration and timeline-API discovery parameters.
**Reads:** none.
**Writes:** none.
**Called by:** browser.py, discover.py, timeline.py, __init__.py.
**Calls out:** none.

### browser.py (158 LOC)

**Purpose:** Launches Chrome and captures the first timeline API request and response during the feed warmup.
**Reads:** the CoinDesk feed page (network).
**Writes:** none; returns headers, API URL and first body.
**Called by:** discover.py, timeline.py.
**Calls out:** pydoll, httpx.

### discover.py (279 LOC)

**Purpose:** Discovery orchestration and cursor paging with per-article shard writes and incremental discover output.
**Reads:** the timeline API (network); existing shards for the dedup seed.
**Writes:** per-year shard files via shards.py.
**Called by:** __init__.py.
**Calls out:** httpx.

### timeline.py (73 LOC)

**Purpose:** Timeline API access: response parsing, cursor URL building, feed-page fetch and session re-warm.
**Reads:** the timeline API and feed page (network).
**Writes:** none.
**Called by:** discover.py.
**Calls out:** httpx.

### shards.py (63 LOC)

**Purpose:** Per-year discover shard storage: streaming append, known-URL loading and filtered loading for scrape-only mode.
**Reads:** shard files in the discover directory.
**Writes:** shard files in the discover directory.
**Called by:** discover.py, __init__.py.
**Calls out:** none (stdlib only).

### cleanup.py (120 LOC)

**Purpose:** Strips CoinDesk page chrome from raw markdown to leave the article body.
**Reads:** raw markdown text handed in.
**Writes:** none; returns text.
**Called by:** `__init__.py`, which wraps it as the platform's cleanup method. The only call site, src/news/clean_pass.py, runs on the proxy-pool path only, so no coindesk run reaches it.
**Calls out:** none (stdlib only).

### __init__.py (42 LOC)

**Purpose:** The CoinDesk platform class wrapping config, discovery, cleanup and scrape-entry loading; registers itself on import.
**Reads:** none of its own.
**Writes:** the registry entry.
**Called by:** src/news/__main__.py (side-effect import), src/news/pipeline.py.
**Calls out:** none.

## State

Durable state is the per-year shard files in the discover directory; no in-memory state beyond a single run.

Details, decisions and observed evidence: process-docs/news_pipeline and process-docs/refactor_sweep.
