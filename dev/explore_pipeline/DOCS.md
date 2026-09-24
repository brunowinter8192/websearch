# dev/explore_pipeline/

## Role
URL discovery and traversal testing for Crawl4AI's BFS deep crawl strategy — recall benchmarks against gold-standard URL sets, filter comparison, and strategy tuning (prefetch, render mode, agentic nav-tree extraction).

## Modules

### 01_discovery.py (162 LOC)

**Purpose:** Crawls a website using BFS strategy with domain filtering. Reports URL discovery metrics: total fetched, unique URLs, duplicates removed, content presence, character counts. `--all` crawls all domains from `domains.txt` in parallel (asyncio.gather, no semaphore — each domain gets its own browser context with independent BFS state).
**Reads:** `domains.txt` (seed URLs, format `label|url|depth|max_pages`) when `--all`; else CLI URL arg.
**Writes:** `md/01_<label>_<timestamp>.json` — JSON with summary (total fetched, unique URLs, duplicates, content/empty counts, total chars) and per-URL content status + char counts. Consumed by `dev/scrape_pipeline/filter_eval/06_content_source.py`.
**Called by:** CLI only. `./venv/bin/python dev/explore_pipeline/01_discovery.py <url> --depth 2 --max-pages 50` or `--all`.

### 02_url_filters.py (156 LOC)

**Purpose:** Compares crawl results with and without URL filters — baseline crawl (no filters) vs filtered crawl (`--exclude-patterns`), reports which URLs were removed. ContentTypeFilter (text/html) always active in both runs.
**Reads:** CLI URL arg, `--exclude-patterns`.
**Writes:** `md/02_<label>_<timestamp>.md` — summary table, removed URLs list, full baseline URL list with `[REMOVED]` markers.
**Called by:** CLI only. `./venv/bin/python dev/explore_pipeline/02_url_filters.py <url> --exclude-patterns "/genindex*,/py-modindex*"`.

### 03_strategies.py (175 LOC)

**Purpose:** Benchmarks explore_site crawl strategies — baseline (domcontentloaded + DefaultMarkdownGenerator), prefetch + domcontentloaded, prefetch without wait_until. Measures time per strategy, pages discovered, per-page latency, speedup vs baseline. Default test URL: docs.crawl4ai.com.
**Reads:** CLI URL arg (optional, defaults to docs.crawl4ai.com), `--depth`, `--max-pages`.
**Writes:** `md/03_explore_strategies_<domain>_<timestamp>.md` — strategy comparison table (pages, time, per-page ms, duplicates), speedup calc, depth distribution per strategy.
**Called by:** CLI only.

### 04_render_recall.py (295 LOC)

**Purpose:** Measures URL discovery recall on docs.github.com/de/rest against a 305-URL gold standard. Compares three BFS strategies (prefetch+dCL baseline, prefetch+NI, full-render NI) to isolate JS-rendering effect on discovered URL count. CLI flags: `--gold PATH`, `--max-pages INT`, `--depth INT`, `--no-regression`, `--strategies COMMA_LIST`, `--delay INT`.
**Reads:** `goldstandard/docs_github_rest.txt` (305 URLs, github/docs content/rest repo tree).
**Writes:** `md/04_docs_github_rest_<YYYYMMDD>.md`.
**Called by:** CLI only. Strategy C (prefetch=False) resilient to GitHub WAF rate-limiting; other strategies need `--delay`.

### 05_playwright_bfs.py (355 LOC)

**Purpose:** Manual Playwright-per-page BFS — renders each page via `AsyncWebCrawler.arun()` (real browser, post-JS DOM), extracts `result.links.internal`, follows matching `--include-pattern` URLs. Measures recall vs goldstandard. Contrasts with `04_render_recall.py` (HTTP BFS). CLI flags: `--gold PATH`, `--seed URL`, `--include-pattern STR`, `--max-pages INT`, `--max-depth INT`, `--delay N.N`, `--page-timeout INT`, `--concurrency {1,2,3}`, `--stealth`.
**Reads:** `goldstandard/docs_github_rest.txt`.
**Writes:** `md/05_docs_github_rest_<YYYYMMDD>.md` — recall table (found/matched/missing/noise/latency), baseline comparison, sample missing URLs.
**Called by:** CLI only.

### 06_nextdata_probe.py (343 LOC)

**Purpose:** Agentic discovery via `__NEXT_DATA__` nav-tree extraction — fetches seed HTML via plain HTTP (no browser), parses `sidebarTree` from the Next.js SSR blob, detects all versions via `allVersions`, fetches each version's REST root page, unions all sidebar trees normalized to canonical `/de/rest/…` form. Scores recall vs goldstandard. Generic to any Next.js SSR doc site. CLI flags: `--gold PATH`, `--no-ghec`, `--no-ghes`.
**Reads:** `goldstandard/docs_github_rest.txt`.
**Writes:** `md/06_gh_live_discovery_<date>_<time>.md` — recall table (found per version/net additions/matched/noise), baseline comparison, per-step discovery log. Discovered URL set → `txt/06_discovered_urls.txt`.
**Called by:** CLI only.

## State
`domains.txt` — batch-crawl seed list, hand-maintained, one domain per HTML generator/content type for broad test coverage. `goldstandard/docs_github_rest.txt` — 305-URL recall reference for scripts 04-06. `txt/06_discovered_urls.txt` — last discovered URL set from `06_nextdata_probe.py`, overwritten per run. All `md/*` reports are historical run outputs, not maintained.

## Gotchas
`BFSDeepCrawlStrategy` (used by `04_render_recall.py`) uses HTTP for link extraction regardless of `wait_until` — changing to `networkidle` has no recall effect (finding as of 2026-05-29 run, Strategy C 205/305=67.2%). Playwright-per-page BFS (`05_playwright_bfs.py`) reached 248/305=81.3% (2026-05-29) — ceiling is structural, GHEC/deprecated pages unlinked from any FPT sidebar page. `06_nextdata_probe.py` reached 305/305=100% recall in 1.6s (2026-05-31) via nav-tree union — no crawling needed for Next.js SSR doc sites with `__NEXT_DATA__`.
