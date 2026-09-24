# src/news/platforms/theblock/

## Role

The Block platform implementation. Uses the `proxy_pool` scrape engine (curl_cffi rotation,
no browser) and its own RAG collection `"theblock"`. Discovery is sitemap-based (not feed-scroll).
`dedup_mode` attribute is not used by `run_pipeline` (which always uses `mode="raw"` against
`data/news/theblock/raw/`). The Block has no `publication_date` at discover time — the date
comes from JSON-LD post-fetch and is mutated into `entry["publication_date"]` by `cleanup.py`.

Imported for side-effects by `__main__.py` — the import registers `TheBlockPlatform()` into the
registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `TheBlockPlatform` (implements `Platform` Protocol).
Auto-registers via `register(TheBlockPlatform())` at module end.

Extra platform attributes (not in Protocol):
- `timeframe: str` — discovery mode (`"delta"` default); overwritten by `__main__` from `--timeframe`.
- `dedup_mode: str = "hash_only"` — legacy attribute, not consumed by `run_pipeline` (which uses `mode="raw"`).
- `uses_master_list: bool = True` — signals `pipeline.py` to write a single `data/news/theblock/discover/master_urls.txt`
  instead of per-year shards. Consumed via `getattr(platform, "uses_master_list", False)` in both
  `run_discover_only()` and `run_pipeline()` proxy_pool path.

## Modules

### config.py (14 LOC)

**Purpose:** Platform constants — `SITEMAP_INDEX`, `DIRECT_TIMEOUT`, `DEFAULT_TIMEFRAME`,
`PROXY_SCRAPE_CONFIG` (`ProxyScrapeConfig(pool_provider=load_backfill_pool, content_type="html")`),
`SCRAPE_CONFIG` (default `ScrapeConfig()`, required by Protocol but ignored by proxy path).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `__init__.py`, `discover.py`.
**Calls out:** `engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

---

### discover.py (155 LOC)

**Purpose:** Sitemap-based article discovery. Fetches theblock sitemap index (direct httpx →
proxy pool fallback), selects `post_type_post_*` sub-sitemaps by mode (`delta`/`full`/`sub:N`/`sub:A-B`),
parses `<url>/<loc>/<lastmod>` blocks — no date filtering. Returns `[{url, lastmod}]` — NO
`publication_date` (comes from JSON-LD post-fetch in cleanup). The proxy-pool fallback triggers on the observed direct-fetch outcome (HTTP status other than 200 or no XML marker); a direct-fetch exception and an unparseable `lastmod` propagate (2026-09-24 Phase 4 pass).
**Reads:** `https://www.theblock.co/sitemap_tbco_index.xml` + selected sub-sitemaps (network).
**Writes:** nothing.
**Called by:** `__init__.py:TheBlockPlatform.discover`.
**Calls out:** `httpx`, `engine/proxy_pool/fetch.py:fetch_url`,
`engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

---

### cleanup.py (111 LOC)

**Purpose:** Parse JSON-LD `NewsArticle` block from raw HTML fetched by proxy engine →
extract `articleBody` (HTML) → convert to Markdown via `crawl4ai.html2text.HTML2Text` →
apply `_post_clean()` regex pass → mutate `entry["publication_date"] = datePublished`.
**Reads:** raw HTML string (proxy engine output), entry dict (scrape manifest).
**Writes:** mutates `entry["publication_date"]` in place.
**Called by:** `clean_pass.py:_run_clean_pass` (proxy_pool arm, dispatched from `pipeline.py:_run_pipeline_proxy_pool`).
**Calls out:** `crawl4ai.html2text` (bundled, no new dep).

---

### __init__.py (30 LOC)

**Purpose:** `TheBlockPlatform` class wrapping config + discover + cleanup; auto-registers on import; `scrape_engine="proxy_pool"`, `uses_master_list=True`.
**Called by:** `__main__.py` (side-effect import).

## Gotchas

- `precondition_url` is `https://www.google.com`, not theblock.co — theblock.co returns 403 on plain urllib.
- `_SPONSOR_BLOCK_RE` in `cleanup.py` strips from the sponsor-block header to END OF STRING (no closing anchor) — corpus-verified safe on the validated 22,995-file corpus, but re-check that assumption against new corpus shapes before trusting it on fresh scrapes.
