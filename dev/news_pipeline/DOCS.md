# dev/news_pipeline/

## Role
Per-domain news scraping pipeline for the trading-bot data layer. CoinDesk → RAG collection `coindesk`. End-to-end runnable (discover → dedup → scrape → cleanup → publish); single-command daily runner. Stays in `dev/`, `src/` promotion deferred. Sub-suites (`theblock/`, `coindesk_proxy_riding/`, `exploration/`) each document their own modules.

## Flow
`run_pipeline.py` chains: `01_coindesk_discover.py` (48h article discovery via UI pagination) → `04_dedup.py` (drop already-indexed) → `02b_coindesk_scrape_fresh_context.py` (production-quality scrape) → `03_coindesk_cleanup.py` (strip nav/footer noise) → `05_publish.py` (copy to RAG collection dir + `rag-cli index`).

## Modules

### run_pipeline.py (293 LOC)

**Purpose:** Single-command orchestrator. Chains precondition checks → discover (48h) → dedup → scrape → cleanup → publish. Clears `02b_data/` and `03_data/` at start so publish only indexes current-run articles.
**Reads:** Preconditions — internet reachable (HTTP to coindesk.com), `rag-cli list_collections` exits 0.
**Writes:** `src/logs/coindesk_pipeline_YYYYMMDD.log` (per-stage counts + failure modes), `src/logs/coindesk_pipeline_last_run.txt` (on successful completion).
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/run_pipeline.py`.

### 01_coindesk_discover.py (384 LOC)

**Purpose:** Discover CoinDesk articles via UI pagination on `/latest-crypto-news`. Background Chrome launched via `open -gna "Google Chrome" --args --remote-debugging-port=<PORT> ...` (macOS, no focus steal); pydoll connects via `Chrome().connect(ws_url)`. Clicks "More stories" until ≥3 articles older than 48h found (`PRE_48H_THRESHOLD=3`, `CUTOFF_DAYS=2`, `MAX_CLICK_ROUNDS=8` safety cap). `lastmod`/`publication_date` derived from URL's `/YYYY/MM/DD/` path → UTC midnight ISO string. Live-blog URLs filtered post-discovery via `_is_live_blog` (slug starts with `live-`). Chrome killed via `pkill -f remote-debugging-port=<PORT>` on cleanup.
**Reads:** live CoinDesk site via pydoll DOM traversal (`_JS_EXTRACT`, `_JS_CLICK_BTN`, `_JS_COUNT` poll loop).
**Writes:** `01_json/discover_<UTC-timestamp>.json` — list of `{url, lastmod, publication_date, title, section}` sorted by lastmod desc.
**Called by:** `run_pipeline.py`, CLI.

### 02_coindesk_scrape.py (160 LOC)

**Purpose:** Scrape each URL from a discover JSON via crawl4ai raw markdown (no PruningContentFilter), shared `AsyncWebCrawler` session — hits CoinDesk regwall after ~3 URLs (iter 1 baseline, 21/25 regwall'd). Kept as reference for shared-session behaviour; superseded by `02b_coindesk_scrape_fresh_context.py` for production use.
**Reads:** `--input <path>` or auto-picks newest `01_json/discover_*.json`.
**Writes:** `02_output/<sha256[:12]>.md` per article (YAML frontmatter + raw markdown body), `02_output/manifest.json` (`[{url, hash, file, char_count, status, error?}]`). Console-only progress output — no run-report file.
**Called by:** CLI only.

### 02b_coindesk_scrape_fresh_context.py (267 LOC)

**Purpose:** Scrape each URL with a fresh `AsyncWebCrawler` per URL — new Chromium process + clean cookie jar per fetch. Runs concurrently via `asyncio.gather` + prod's deterministic per-domain Scrapy gate (ported from `src/crawler/pipe_scraper.py`: `_ensure_domain_state` + `_gate_domain`, `DOWNLOAD_DELAY=1.0`, `CONCURRENCY_PER_DOMAIN=8`, jitter=uniform(0.5×,1.5×)). `domcontentloaded` + `delay_before_return_html=0.5`, `page_timeout=15000`, no networkidle, no custom UA. Loud regwall guard: per-page WARN + per-run ERROR + exit non-zero if ≥20% regwalled. Only deviation from `pipe_scraper.py`: fresh crawler per URL (isolation) — pacing identical. Production-quality scrape path.
**Reads:** `--input <path>` or auto-picks newest `01_json/discover_*.json`; pipeline passes `04_dedup` output explicitly.
**Writes:** `02b_data/<sha256[:12]>.md` per article (YAML frontmatter incl. scraped_at + raw markdown body; regwalled pages NOT written), `02b_data/manifest.json` (status: `ok`/`empty`/`failed`/`regwall`).
**Called by:** `run_pipeline.py`, CLI.

### 03_coindesk_cleanup.py (261 LOC)

**Purpose:** Extract clean article body from `02b_data/*.md`, strip nav/footer noise, normalize structure for RAG ingestion. Anchors: H1 start-anchor + earliest-occurrence end-anchor (`More For You` / `## More For You` / `## We Care About Your Privacy` / tag-footer `{2,}` pattern, TAG_FOOTER requires ≥2 concatenated `[text](url)` to avoid single-link false-fires). Strip rules: Google News badge, date/read-time byline, author byline, standalone image lines, inline links → text, empty links, trailing whitespace. Normalization: blank line between consecutive body paragraphs, blank-run collapse-to-1.
**Reads:** `02b_data/*.md` + YAML frontmatter.
**Writes:** `03_data/<hash>.md` (pure content, no frontmatter), `03_data/manifest.json` (`[{hash, url, lastmod, publication_date, title, section, scraped_at, original_chars, cleaned_chars, reduction_pct, end_anchor_used}]`). Stdout reports trailing-ws strip count + para blank insert count.
**Called by:** `run_pipeline.py`, CLI.

### 04_dedup.py (114 LOC)

**Purpose:** Dedup gate — drops URLs whose `coindesk__<YYYY-MM-DD>__<hash>.md` already exists in the `coindesk` RAG collection dir. Pure Python, no browser, no network. Filesystem presence of the target filename IS the seen-state; no separate state file.
**Reads:** `--input <path>` or auto-picks newest `01_json/discover_*.json`; collection dir `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/coindesk/`.
**Writes:** `04_json/discover_filtered_<UTC-timestamp>.json` — same schema as discover, subset of entries.
**Called by:** `run_pipeline.py`, CLI.

### 05_publish.py (136 LOC)

**Purpose:** Copy cleaned MDs from `03_data/` to the `coindesk` RAG collection dir as `coindesk__<YYYY-MM-DD>__<hash>.md`, then run `rag-cli index --collection coindesk`. Idempotent — safe to re-run, rag-cli hash-skip handles re-index of already-indexed files.
**Reads:** `03_data/manifest.json` + `03_data/*.md`; collection dir (same as `04_dedup.py`).
**Writes:** files copied to `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/coindesk/coindesk__<date>__<hash>.md`. Triggers rag-cli indexing.
**Called by:** `run_pipeline.py`, CLI. `--skip-index` to skip the rag-cli call.

### prod_scrape_smoke.py (170 LOC)

**Purpose:** Investigation tool — Smoke A, empirical regwall baseline. Runs all 32 URLs from a discover-filtered JSON through the PRODUCTION `scrape_urls_workflow` (from `src/crawler/pipe_scraper.py`, shared session). Verdict heuristic: `REGWALL?` if bytes<3000 OR marker_hits≥3.
**Reads:** discover-filtered JSON, 32 URLs.
**Writes:** `smoke_output/raw/` + `smoke_output/regwall_review.md` (summary table + 50-line previews). Gitignored, not committed.
**Called by:** CLI only.

### scrape_isolation_smoke.py (262 LOC)

**Purpose:** Investigation tool — Smoke B, two isolation candidates over the same 32 URLs. B1: shared crawler + per-URL `timezone_id` (intended to bust crawl4ai 0.8.6 context cache). B2: fresh `AsyncWebCrawler` per URL, concurrent via `asyncio.gather` + `Semaphore(8)`.
**Reads:** discover-filtered JSON, 32 URLs.
**Writes:** `smoke_output/b1_regwall_review.md` + `smoke_output/b2_regwall_review.md` + comparison table (stdout). Gitignored, not committed.
**Called by:** CLI only.

## State
`01_json/`, `02_output/`, `02b_data/`, `03_data/`, `04_json/`, `smoke_output/` — all pipeline-stage intermediate outputs, gitignored. `md/` — 2 historical run-analysis reports (coindesk_scrape_2026-05-27[_freshctx].md), tracked.

## Gotchas
`02_coindesk_scrape.py` writes no report file — console-only progress; the two `md/coindesk_scrape_2026-05-27*.md` reports were produced by a separate historical run-analysis pass, not by the script itself.
