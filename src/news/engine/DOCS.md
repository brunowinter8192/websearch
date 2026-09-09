# src/news/engine/

## Role

Generic, platform-agnostic pipeline engine modules. Called by `pipeline.py`; no platform-specific
logic lives here. All modules accept platform parameters explicitly (no hardcoded source names).

`pipeline.py` dispatches on `platform.scrape_engine`: `"browser"` → `scrape.py` (via
`scrape_chunks_raw` in `run_scrape_only`); `"proxy_pool"` → `proxy_pool/scrape.py` (via
`run_pipeline`); `"proxy_riding"` → `proxy_riding/scrape.py` (via `run_scrape_only`, CoinDesk
backfill path — chunk-bypass, full entry set, returns `(manifest, state)`). All three engines wired.
The two sub-engines live in their own subpackages with own-level DOCS.md: `proxy_pool/` (entry
`scrape_entries_proxy`) and `proxy_riding/` (entry `scrape_entries_riding`).

## Modules

### scrape.py (179 LOC)

**Purpose:** Browser-engine scraper — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing, regwall guard. Active when `platform.scrape_engine == "browser"`.
**Reads:** entries list (in-memory), ScrapeConfig, regwall_signals list.
**Writes:** `{hash}.md` (BODY ONLY, no frontmatter) to output_dir (raw_dir in all call paths).
**Called by:** `pipeline.py:_run_pipeline_browser`, `scrape_job.py:_scrape_one_chunk`.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig).

### dedup.py (54 LOC)

**Purpose:** Filter discover entries to those not yet in the raw corpus by checking file existence; optionally exclude known-failure URLs permanently.
**Reads:** entries list (in-memory), dir (filesystem), source name, mode, optional exclusion set.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:_run_pipeline_proxy_pool` / `_run_pipeline_browser` (mode=`"raw"`), `pipeline.py:run_scrape_only` (mode=`"raw"`).
**Calls out:** stdlib only.

### scrape_job.py (104 LOC)

**Purpose:** Raw-only chunked scrape orchestration for `run_scrape_only()` and shared raw-persist helpers.
**Reads:** chunks (list of entry lists), platform config.
**Writes:** `{hash}.md` into raw_dir per ok entry; appends to `raw/manifest.jsonl`; updates `regwall_urls.txt` / `empty_urls.txt`.
**Called by:** `pipeline.py:_run_scrape_only_browser` (`scrape_chunks_raw`); `pipeline.py:_persist_proxy_pool_results` / `_run_pipeline_browser` (`_append_to_raw_manifest`, `_update_blocked_urls`).
**Calls out:** `scrape.py:scrape_entries`.

### browser_reporter.py (196 LOC)

**Purpose:** Per-job report writer for browser-engine scrape jobs. Produces `job.md` + `cumulative.png` from `job_records`.
**Reads:** `job_records` (in-memory list from `scrape_chunks_raw`), `t_job_start`.
**Writes:** `{job_dir}/job.md` (counts, regwall rate, throughput, backfill projection, char-count percentiles p10–p95, failure table); `{job_dir}/cumulative.png` (step-plot of cumulative ok count vs elapsed seconds).
**Called by:** `pipeline.py:_run_scrape_only_browser`.
**Calls out:** `matplotlib` (lazy import inside `_write_plot`), `statistics` (stdlib).

## Gotchas

- `scrape.py` raises `RegwallGuardError` (not sys.exit) at regwall fraction ≥ `REGWALL_FAIL_THRESHOLD` (0.20); the exception's `.manifest` carries the full per-entry manifest including ok entries written before abort — callers persist aborted-run data from it.
- `dedup.py`'s `mode="raw"` takes `raw_ext` — `".html"` for the proxy_riding path, default `".md"` elsewhere.
