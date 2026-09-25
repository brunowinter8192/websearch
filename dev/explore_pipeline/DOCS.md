# dev/explore_pipeline/

## Role
URL discovery and traversal testing for Crawl4AI's BFS deep crawl: recall benchmarks against gold-standard URL sets, filter comparison, and strategy tuning. Touch it for discovery-recall experiments, not for production crawling.

## Public Interface
No `__init__.py` — not a package. Each numbered script is its own CLI entry point, run via `./venv/bin/python`.

## Flow
Seed URL or `domains.txt` (or a gold-standard URL list) -> BFS or nav-tree discovery variant -> recall and metric computation -> markdown or JSON report in `md/`; the nextdata probe also writes its URL set to `txt/`.

## Modules

### 01_discovery.py (176 LOC)

**Purpose:** BFS crawl of one or all seed domains with domain filtering, reporting discovery metrics.
**Reads:** `domains.txt` or a CLI URL.
**Writes:** `md/01_<label>_<ts>.json`, consumed by `dev/scrape_pipeline/filter_eval/06_content_source.py`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 02_url_filters.py (170 LOC)

**Purpose:** Compares a baseline crawl against a filtered crawl and lists the URLs removed by the filters.
**Reads:** CLI URL and exclude patterns.
**Writes:** `md/02_<label>_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 03_strategies.py (184 LOC)

**Purpose:** Benchmarks crawl strategies (baseline versus prefetch variants) on time, pages discovered, and speedup.
**Reads:** Optional CLI URL.
**Writes:** `md/03_explore_strategies_<domain>_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 04_render_recall.py (305 LOC)

**Purpose:** Measures HTTP-BFS discovery recall against the gold standard across three strategies to isolate the JS-rendering effect.
**Reads:** `goldstandard/docs_github_rest.txt`.
**Writes:** `md/04_docs_github_rest_<date>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 05_playwright_bfs.py (386 LOC)

**Purpose:** Manual per-page browser BFS with pattern-matched link following, measuring recall against the gold standard.
**Reads:** `goldstandard/docs_github_rest.txt`.
**Writes:** `md/05_docs_github_rest_<date>.md`, including a failed-fetch list.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

### 06_nextdata_probe.py (352 LOC)

**Purpose:** Agentic discovery via nav-tree extraction from Next.js SSR data over plain HTTP, scored against the gold standard.
**Reads:** `goldstandard/docs_github_rest.txt`.
**Writes:** `md/06_gh_live_discovery_<ts>.md`; discovered URL set to `txt/06_discovered_urls.txt`.
**Called by:** `dev/scrape_pipeline/_pipe_scrape_eval_common.py` (reads the URL set).
**Calls out:** none (stdlib urllib).

---

## State
`domains.txt` is the hand-maintained batch seed list. `goldstandard/` holds the recall reference for scripts 04 to 06. `txt/` holds the last discovered URL set, overwritten per run. `md/` reports are historical run outputs. Results and structural ceilings: process-docs area explore_pipeline.
