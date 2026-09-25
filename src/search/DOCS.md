# src/search/

## Role

Parallel web-search pipeline behind the search and drilldown subcommands of cli.py. Fans one query out across eight engines, builds deduplicated per-engine pools, caches them and returns an engine-breakdown table; drilldown re-reads the cache. Touch it for fan-out, pooling, cache, rate limiting or browser lifecycle. Engine parsers live in engines/.

## Public Interface

`__init__.py` is empty; modules are imported by path.

- search_web.py: the search workflow entry used by cli.py.
- cache.py: cache key, cache read and pool formatting for the drilldown subcommand.
- query_logger.py: query log writer, also called by cli.py for drilldown records.
- browser.py: the at-exit browser cleanup registered by cli.py.

## Flow

Query in, engines selected, the shared Chrome prewarmed outside any watchdog, then engines run concurrently under a rate limiter and per-engine watchdog. Results are grouped by URL into per-engine pools, capped, formatted as a breakdown table, prefixed with a degraded-run notice when needed, cached and logged. Drilldown reads the cache and lists one engine's URLs. Browser lifecycle uses `browser_lock.py` and `src/death_pipe.py`; log pruning goes through `src/log_janitor.py`.

## Modules

### search_web.py (351 LOC)

**Purpose:** Search orchestrator: engine selection, concurrent fan-out with status classification, pool building, breakdown formatting, cache write and query logging.
**Reads:** the query and parameters; engine registry data.
**Writes:** the disk cache via cache.py; query log via query_logger.py.
**Called by:** cli.py; dev scripts.
**Calls out:** httpx, pydoll and websocket exceptions, mcp types.

### cdp_value.py (3 LOC)

**Purpose:** Unwraps the value field of a CDP script-evaluation result; the one shared copy for all engines and the CoinDesk browser module.
**Reads:** the CDP result handed in.
**Writes:** none.
**Called by:** src/search/engines/ modules, src/news/platforms/coindesk/browser.py.
**Calls out:** none.

### degraded_notice.py (61 LOC)

**Purpose:** Builds the notice prepended to the breakdown when the error or timeout share of engines is high.
**Reads:** per-engine statistics handed in.
**Writes:** none; returns text.
**Called by:** search_web.py; a dev test.
**Calls out:** none.

### merge.py (34 LOC)

**Purpose:** Groups results by URL into per-engine pools annotated with every engine's position.
**Reads:** the flat result list of the fan-out.
**Writes:** none.
**Called by:** search_web.py.
**Calls out:** none.

### cache.py (112 LOC)

**Purpose:** Atomic JSON disk cache of per-engine pools with a one-hour TTL, plus numbered-list rendering for drilldown.
**Reads:** cache files under the user cache directory.
**Writes:** cache files under the user cache directory.
**Called by:** cli.py, search_web.py.
**Calls out:** none.

### snippet.py (57 LOC)

**Purpose:** Snippet cleanup for drilldown display: unescape, bloat stripping and sentence-aware truncation.
**Reads:** raw snippet text.
**Writes:** none.
**Called by:** cache.py.
**Calls out:** none (stdlib only).

### query_logger.py (19 LOC)

**Purpose:** Append-only JSONL query log with three record types correlated by a shared search key.
**Reads:** the query-log path environment variable.
**Writes:** the query log under src/logs.
**Called by:** search_web.py, cli.py.
**Calls out:** none.

### browser.py (293 LOC)

**Purpose:** Chrome lifecycle for the browser engines: one shared headed, backgrounded Chrome with a fresh profile per run and one tab per engine.
**Reads:** nothing until first access.
**Writes:** a per-run profile directory; the cross-process lock file and its sidecar.
**Called by:** cli.py, search_web.py, engines/, many dev probes.
**Calls out:** pydoll, patchright, psutil, macOS open, pgrep and osascript.

### browser_lock.py (80 LOC)

**Purpose:** Domain-agnostic blocking cross-process file lock with stale-holder takeover via a caller-supplied callback.
**Reads:** the lock file and its sidecar.
**Writes:** the lock file and sidecar.
**Called by:** browser.py.
**Calls out:** none (stdlib only).

### rate_limiter.py (55 LOC)

**Purpose:** Per-engine token-bucket limiter registry, created lazily from a per-engine limits table.
**Reads:** in-memory registry.
**Writes:** in-memory registry.
**Called by:** search_web.py, engines/.
**Calls out:** none (stdlib only).

### result.py (17 LOC)

**Purpose:** The shared search-result dataclass carried through engines, merge and cache.
**Reads:** none.
**Writes:** none.
**Called by:** search_web.py, merge.py, cache.py, engines/.
**Calls out:** none (stdlib only).

### status.py (5 LOC)

**Purpose:** Ungrouped engine-status strings describing the tool's own runtime facts.
**Reads:** none.
**Writes:** none.
**Called by:** search_web.py; a dev smoke script.
**Calls out:** none.

### status_timeout.py (5 LOC)

**Purpose:** The timeout status cluster split out of status.py.
**Reads:** none.
**Writes:** none.
**Called by:** search_web.py, degraded_notice.py; a dev smoke script.
**Calls out:** none.

### status_error.py (6 LOC)

**Purpose:** The error status cluster split out of status.py.
**Reads:** none.
**Writes:** none.
**Called by:** search_web.py, degraded_notice.py; a dev smoke script.
**Calls out:** none.

### selector_hits.py (13 LOC)

**Purpose:** Aggregates per-item selector indexes from engine parse scripts into hit counts for the diagnosis.
**Reads:** parse-script output handed in.
**Writes:** none.
**Called by:** engines/google.py, engines/bing.py, engines/brave.py, engines/yandex.py.
**Calls out:** none.

### document_status.py (43 LOC)

**Purpose:** Shared CDP network listener capturing the ordered main-frame document statuses behind the diagnosis facts of all browser engines.
**Reads:** nothing; one CDP call per engine.
**Writes:** none; returns values.
**Called by:** engines/google.py, duckduckgo.py, mojeek.py, brave.py, bing.py, yandex.py, startpage.py.
**Calls out:** pydoll network events and types.

## State

Two module-owned states: the per-engine limiter registry in rate_limiter.py, and the on-disk pool cache written by search and read by drilldown. No cross-request in-memory search state.

Details, decisions and observed evidence: process-docs/search_pipeline, process-docs/browser_posture, process-docs/search_outage, process-docs/engine_reduction and process-docs/refactor_sweep.
