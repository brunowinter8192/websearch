# dev/scrape_pipeline/

## Role
Quality monitoring and configuration testing for the URL scraper module (`src/scraper/`). Own-level scripts cover the GH REST API docs pipe-scraper eval, dual-mode A/B comparison, raw-scrape baseline, and Cloudflare markdown-adoption probing. Sub-suites (`filter_eval/`, `browser_eval/`, `garbage_eval/`, `03_cleanup/`, `04_overview_sweep/`, `05_paper_mode/`) each document their own modules.

## Modules

### p1_pipe_scraper.py (94 LOC)

**Purpose:** Core scraper probe — `scrape_urls(urls, delay_s, page_timeout_ms, concurrency, output_dir)` → per-URL metrics dicts. Config locked to: browser, `wait_until="domcontentloaded"`, `delay_before_return_html`, hard `page_timeout`, `DefaultMarkdownGenerator()` raw, no `PruningContentFilter`, no garbage-drop. Saves `<!-- source: url -->\n\nraw_md` per URL when `output_dir` set.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DefaultMarkdownGenerator).
**Called by:** `07_pipe_scrape_eval.py`.

### 07_pipe_scrape_eval.py (61 LOC)

**Purpose:** CLI entry point and dispatch — routes `{smoke,phase1,phase2,phase3}` to the matching sibling module below; owns the smoke test.
**Reads:** URL list via `_pipe_scrape_eval_common.load_urls`.
**Writes:** nothing directly — delegates to the phase modules.
**Calls out:** `p1_pipe_scraper.scrape_urls` (smoke test only); `_pipe_scrape_eval_common.py`, `_pipe_scrape_eval_phase1.py`, `_pipe_scrape_eval_phase2.py`, `_pipe_scrape_eval_phase3.py`.
**Called by:** CLI only. `./venv/bin/python dev/scrape_pipeline/07_pipe_scrape_eval.py {smoke,phase1,phase2,phase3}`.

### _pipe_scrape_eval_common.py (44 LOC)

**Purpose:** Utilities shared by all three eval phases — URL list loading, stratified sampling, aggregate latency/outcome metrics.
**Reads:** URL list file (`DISCOVERED_URLS`, default path into `../explore_pipeline/06_discovered_urls.txt`).
**Writes:** nothing.
**Called by:** `07_pipe_scrape_eval.py`, `_pipe_scrape_eval_phase1.py`, `_pipe_scrape_eval_phase2.py`, `_pipe_scrape_eval_phase3.py`.
**Calls out:** none — stdlib only (`statistics`).

### _pipe_scrape_eval_phase1.py (92 LOC)

**Purpose:** Phase 1 — concurrency/WAF sweep at `concurrency ∈ {1,3,5,10}`, stops early on first 429, recommends the highest WAF-safe level.
**Reads:** nothing directly — takes an already-loaded URL list.
**Writes:** `md/07_concurrency_sweep_<ts>.md`.
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.scrape_urls`; `_pipe_scrape_eval_common.py`.

### _pipe_scrape_eval_phase2.py (96 LOC)

**Purpose:** Phase 2 — delay sweep at fixed concurrency, `bytes_p50` completeness proxy, picks the plateau delay (≤5% marginal byte gain).
**Reads:** nothing directly — takes an already-loaded URL list.
**Writes:** `md/07_delay_sweep_<ts>.md` (incl. WAF-contamination note).
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.scrape_urls`; `_pipe_scrape_eval_common.py`.

### _pipe_scrape_eval_phase3.py (266 LOC)

**Purpose:** Phase 3 — full 316-URL run: WAF probe, batched pacing with inter-batch pause, position-tracked 429s, one retry pass after cooldown.
**Reads:** nothing directly — takes an already-loaded URL list.
**Writes:** `md/07_full_run_<ts>.md`; `07_pipe_scrape_eval_data/full_run_<ts>/` — raw markdown corpus, one `.md` per URL.
**Called by:** `07_pipe_scrape_eval.py`.
**Calls out:** `p1_pipe_scraper.scrape_urls`; `_pipe_scrape_eval_common.py`.

### 01_dual_mode_smoke.py (350 LOC)

**Purpose:** A/B comparison harness — parses URLs from a chosen query in a search-results markdown report, scrapes each URL through BOTH production CLI modes in parallel via asyncio: Mode 1 (`scrape_url_raw`, raw markdown to file, no filter) and Mode 2 (`scrape_url_chromium`, PruningContentFilter@0.48, 15K char cap, in-memory). Reusable for library A/B testing — replace the cli.py-subprocess invocation with another extraction library.
**Reads:** `--input <path-to-search-md>` (required, e.g. `dev/search_pipeline/md/pipeline_smoke_*.md`), `--query <id-or-text>` (default 1).
**Writes:** `--output-dir` (default `01_dual_mode_data/<ts>/`) — per-mode subdirs (`mode1_raw/`, `mode2_filtered/`) with one .md per URL, plus `01_dual_mode_report.md` at parent level (per-URL byte sizes, garbage detection, first content lines).
**Called by:** CLI only.

### 02_raw_smoke.py (199 LOC)

**Purpose:** Dev-only Mode 1 raw scrape — Crawl4AI direct via `arun_many`, no prod imports, no `cli.py` subprocess. Parses Q24 URLs from a search smoke report, scrapes all in parallel. Slug includes full-URL md5 hash to prevent query-string collisions (e.g. HN `?id=N` URLs both preserved). NO fallback chain (single Crawl4AI config), NO garbage detection, NO cookie strip — fail fast, see what's actually there. Clean baseline for downstream cleanup work + comparison against filter outputs.
**Reads:** `--input <path-to-search-md>`, `--query 24`.
**Writes:** `02_raw_data/<ts>/` — 20 `<slug>_<6-char-md5>.md` files + `02_raw_report.md` triage table. Status `empty` includes optional annotation `(PDF)` or `(plugin-domain: github)`.
**Called by:** CLI only.

### 06_cloudflare_md_adoption.py (289 LOC)

**Purpose:** Adoption probe for the `Accept: text/markdown` server-side markdown convention (Cloudflare Markdown-for-Agents, Vercel edge, others). Probes a curated 29-URL set across three categories (Cloudflare-owned positive controls, likely-CF-fronted candidate sites, non-CF negative controls) with the markdown Accept header via httpx async (Semaphore concurrency 10, 15s timeout). For URLs responding `text/markdown`, fetches a baseline HTML GET to compute byte-reduction. Baseline measurement for Phase-0-fast-path adoption (`fetch_markdown_fastpath` in production); re-run periodically to track adoption growth.
**Reads:** hardcoded 29-URL set.
**Writes:** `md/06_cf_md_adoption_<YYYYMMDD_HHMMSS>.md` — per-URL table (URL, CF-fronted, MD-served, status, content-type, x-md-tokens, HTML-bytes, MD-bytes, byte-reduction, response-ms) plus summary (counts, mean/median byte-reduction on positives, positive-case URL list for run-to-run comparison, server header distribution among CF-fronted hits).
**Called by:** CLI only. `--output-dir` overridable.

## State
`domains.txt` — shared test URL list for `browser_eval/` and `filter_eval/` scripts, one URL per line, `#` comments. `failures.jsonl` (gitignored) — persistent failure log from production `scrape_url_chromium` runs; written by `log_scrape_failure()` in `src/scraper/chromium_scrape.py` at the final failure exit in `scrape_url_chromium_workflow()`. Fields: `ts` (ISO 8601 UTC), `url`, `garbage_type` (`http_error`/`cookie_wall`/`login_wall`/`cloudflare`/`nav_dump`/`crawl4ai_error`/null), `status_code` (int/null). Local analysis only — accumulates across production MCP tool calls, not committed.

## Gotchas
`failures.jsonl` inspection: `cat dev/scrape_pipeline/failures.jsonl | jq .`; by garbage_type: `jq -r '.garbage_type // "none"' | sort | uniq -c | sort -rn`; 404s only: `jq 'select(.status_code == 404)'`.
- `01_dual_mode_smoke.py` Mode 1 shells out to `cli.py scrape_url_raw`, a subcommand `cli.py` no longer has, so Mode 1 cannot succeed today; its Mode 2 parsers search the whole stdout because crawl4ai prints progress lines before the CLI output.
