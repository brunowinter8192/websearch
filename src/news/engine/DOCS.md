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

**Purpose:** Filter discover entries to those not yet in the raw corpus by checking file existence; optionally exclude known-failure URLs permanently. As of 2026-09-09, `pub_date_str` is the ONE surviving definition (see Gotchas) — used internally by `filter_new_entries`'s `mode="pubdate"` branch and imported directly by `clean_pass.py`; returns `"unknown"` when no date is found.
**Reads:** entries list (in-memory), dir (filesystem), source name, mode, optional exclusion set.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:_run_pipeline_proxy_pool` / `_run_pipeline_browser` (mode=`"raw"`), `pipeline.py:run_scrape_only` (mode=`"raw"`); `clean_pass.py` (`pub_date_str` only).
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
- **2026-09-09: `pub_date_str` consolidated into `dedup.py` with the `unknown` fallback — user decision, Phase 4 control-flow review.** `clean_pass.py` used to define its own byte-identical copy, differing only in the final fallback (`"unknown"` vs `dedup.py`'s own `""`). `clean_pass.py` built its output filename as `theblock__{pubdate}__{h}.md` using its own `"unknown"`; `dedup.py`'s `mode="pubdate"` branch built its lookup filename the same way using its own `""` — for a date-less entry the two names differed (`theblock__unknown__{h}.md` vs `theblock____{h}.md`), so the pubdate-mode dedup lookup could never find what `clean_pass` actually wrote. `mode="pubdate"` is currently unreached in production (every `pipeline.py` call site passes `mode="raw"`), so this never manifested as an observed bug, but the divergence itself was real and would have surfaced the moment anything called `filter_new_entries` without an explicit `mode=`. `clean_pass.py` now imports `pub_date_str` from here; its own copy and `DATE_RE` are gone.
