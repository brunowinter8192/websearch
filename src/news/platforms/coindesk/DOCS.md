# src/news/platforms/coindesk/

## Role

CoinDesk platform implementation. Imported for side-effects by `__main__.py` — the import
registers `CoinDeskPlatform()` into the registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `CoinDeskPlatform` (implements `Platform` Protocol).
Auto-registers via `register(CoinDeskPlatform())` at module end.

## Modules

### config.py (34 LOC)

**Purpose:** Platform constants — REGWALL_SIGNALS, SCRAPE_CONFIG (ScrapeConfig()), timeline-API
discovery params (TIMELINE_BASE, COINDESK_BASE, TARGET_URL, CALL_DELAY, REWARM_EVERY,
CLICKS_WARMUP, CLICKS_REWARM, MAX_CURSOR_FALLBACKS, CHECKPOINT_EVERY, DEFAULT_DELTA_DAYS,
FULL_MODE_FLOOR, DISCOVER_DIR, SKIP_HEADERS).
**Called by:** `browser.py`, `discover.py`, `timeline.py`, `__init__.py`.

### browser.py (158 LOC)

**Purpose:** Chrome browser launch + pydoll HAR-capture machinery for the initial feed warmup.
`browser_load_feed(n_clicks)` launches Chrome via `open -gna`, navigates to latest-crypto-news,
clicks "More stories" n times under HAR record, captures the first `/api/v1/articles/timeline`
request (URL + headers + first response body). Returns `(headers, api_url, body_bytes)`.
**Called by:** `discover.py:discover` (warmup); `timeline.py:try_rewarm` (re-warm fallback).
**Calls out:** `pydoll` (Chrome CDP), `httpx` (first response replay).

### discover.py (279 LOC)

**Purpose:** Discover orchestration + cursor paging — `discover(timeframe)` orchestrates warmup → load discover → `cursor_loop` (backward-paging, crash-safe per-article shard writes) → incremental discover write. Timeline-API access/re-warm and per-year shard storage were split out into `timeline.py`/`shards.py` (below, pure relocation, same behavior) once this file crossed 400 LOC by mixing three concerns.
**Called by:** `__init__.py:CoinDeskPlatform.discover` (via `discover`).
**Calls out:** `httpx` (`_fetch_next_page`'s own cursor GET); `browser.py:browser_load_feed` (warmup, in `discover` itself); `timeline.py` (`parse_articles`, `build_cursor_url`, `fetch_feedpage`, `try_rewarm`); `shards.py` (`_append_to_shard`, `load_discover`).

### timeline.py (73 LOC)

**Purpose:** Timeline-API access + session re-warm — split out of `discover.py` (pure relocation, same behavior): `parse_articles` (response-body → article dicts; as of 2026-09-09 raises on a non-JSON body instead of swallowing the parse failure, see Gotchas), `build_cursor_url` (pagination cursor URL), `fetch_feedpage` (plain-httpx feed-page GET, used both standalone and inside re-warm), `try_rewarm` (httpx feedpage re-warm first, browser re-warm fallback via `browser.py:browser_load_feed`).
**Called by:** `discover.py` — `cursor_loop` (`parse_articles`), `_fetch_next_page` (`build_cursor_url`), `_maybe_proactive_rewarm` (`fetch_feedpage`), `_handle_cursor_exhaustion` (`try_rewarm`) — the only caller module.
**Calls out:** `httpx`; `browser.py:browser_load_feed` (re-warm fallback).

### shards.py (63 LOC)

**Purpose:** Per-year discover shard storage — split out of `discover.py` (pure relocation, same behavior): `_append_to_shard` (streaming, line-buffered append to `coindesk_{year}.txt`), `load_discover` (read all shards → set of known URLs, used by `discover()`'s dedup seed), `load_discover_filtered` (read shards filtered by year/date-range/limit → `[{url, publication_date}]`, the `--scrape-only` interface).
**Called by:** `discover.py` (`_append_to_shard` via `_process_batch`, `load_discover` via `discover()`); `__init__.py:load_scrape_entries` (`load_discover_filtered`, imported directly — no re-export through `discover.py`).
**Calls out:** none (stdlib `pathlib` only).

### cleanup.py (120 LOC)

**Purpose:** Strip CoinDesk page chrome from raw crawl4ai markdown → pure article body (H1 start-anchor → first end-anchor → `clean_body` strip/normalize passes).
**Called by:** NOT called by any active pipeline path. Available to future cleanup skill.
**Calls out:** stdlib re only.

### __init__.py (40 LOC)

**Purpose:** `CoinDeskPlatform` class wrapping config + discover + cleanup + scrape-entry loading; auto-registers on import; `scrape_engine = "proxy_riding"`, raw output `.html`.
**Called by:** `__main__.py` (side-effect import); `pipeline.py:run_scrape_only` (via `platform.load_scrape_entries`, `platform.scrape_engine`); `pipeline.py:_run_scrape_only_riding` (via `platform.riding_scrape_config`).

## Gotchas

- **`_parse_stop_date` treats `"delta"` explicitly (2026-09-24 Phase 4 pass).** The CLI default `--timeframe` is `delta`, which resolved to `DEFAULT_DELTA_DAYS` only because `int("delta")` raised into a swallowing handler; the branch is now explicit and any other non-integer value raises.

- `REGWALL_SIGNALS` uses precise match strings deliberately — do NOT loosen to generic markers like "subscribe"/"register": those fire on ordinary article footers, producing false regwall positives.
- `cleanup(raw_markdown, entry)`'s `entry` param is unused but part of the platform-generic signature — do not remove as dead.
- At 60k+ article scale the fixed cleaner is fragile — articles occasionally retain the full site footer after cleanup; per-shape diagnosis against the full raw corpus is recommended before cleanup at scale.
- **REMOVED 2026-09-09: `timeline.py::parse_articles`'s parse-failure→`[]` handler — user decision, Phase 4 control-flow review.** `cursor_loop` (`discover.py`) used to log "Empty response — reached API bottom or parse failure. Stopping." on either a genuine API-exhaustion payload OR a non-JSON body, admitting it could not tell the two apart — no supporting observation existed for a real parse failure (no process-docs entry documents one). A non-JSON timeline body now raises `json.JSONDecodeError` straight out of `parse_articles`, propagating through `cursor_loop`'s own `try/finally` (year-shard files still close cleanly) and up through `discover()`, ending the run with a traceback instead of a silent stop. `cursor_loop`'s stop message was reworded to "Empty response — reached API bottom. Stopping." — an empty list from `parse_articles` now means exactly one thing.
- 2026-09-24 Phase 5: `parse_articles` reads only the recorded shape (`_id`, `pathname`, `articleDates.displayDate`) and raises `KeyError` otherwise (list-or-dict container detection stays); `_extract_value` no longer swallows KeyError/TypeError; `cleanup` returns `""` with a warning when there is no H1 and warns when no end anchor exists; `load_discover_filtered` raises `FileNotFoundError` for a missing directory or year shard. A missing recorded key now aborts discovery instead of dropping articles silently.
