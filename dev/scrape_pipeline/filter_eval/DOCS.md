# dev/scrape_pipeline/filter_eval/

## Role
Crawl4AI content-filter configuration exploration — compares filter strategies (PruningFilter thresholds, BM25ContentFilter, raw), `content_source` parameter variants, and step-by-step pipeline instrumentation to find the best markdown extraction for downstream cleanup/RAG indexing.

## Modules

### 04_filtering.py (149 LOC)

**Purpose:** Tests multiple Crawl4AI content filter configurations (PruningFilter at various thresholds, BM25ContentFilter, raw) against test URLs. Saves raw and fit markdown for each config. Includes code block integrity check. URLs processed in parallel (PARALLEL_URLS=5, Semaphore); the 5 configs per URL run serially.
**Reads:** `domains.txt` (pipeline root) or a URL CLI arg.
**Writes:** `04_reports/<domain>_<config>_raw.md` / `_fit.md`.
**Called by:** CLI only.

### 05_filter_debug.py (393 LOC)

**Purpose:** Instruments the scraping pipeline step-by-step to show what each filter removes at each stage — node counts, character counts, percentage deltas, markdown previews of removed content. Used during active profile development.
**Reads:** `domains.txt` (pipeline root) or a URL CLI arg; `--profile`.
**Writes:** `md/<profile>/05_<domain>_<timestamp>.txt`.
**Called by:** CLI only. `--all` runs against all domains.
**Gotcha:** this module cannot be executed at all. Its top-level imports
`from src.scraper.routing import resolve_profile, load_config, match_url_to_profile`,
`from src.scraper.html_parser import parse_html`,
`from src.scraper.content_filter import remove_skip_tags, extract_main_content,
remove_navigation_attributes, remove_skip_tables, remove_noise_links, remove_noise_text`, and
`from src.scraper.chromium_scrape import init_browser, fetch_url_content, cleanup_browser` are all
dead — confirmed by attempting the import directly: `src/scraper/` currently holds only
`camoufox_scrape.py`, `chromium_process.py`, `chromium_scrape.py`, `scrape_logger.py`; the four
modules above and the three `chromium_scrape` names do not exist there. No process-docs record of
when this happened was found; treat "since when" as undocumented, not as "never broken until now".
Because the module cannot import, `run_pipeline_debug`'s 2026-09-16 split into
`run_node_level_filter_steps`/`run_markdown_cleanup_steps` could not be verified by running it —
verification was structural only: an AST-based line-for-line diff of the pre-split function body
against the concatenated post-split bodies, confirming every non-glue statement is byte-identical
and in the same order. That is a proof of mechanical relocation, not a proof of runtime behavior —
this script's actual behavior remains unverified and unverifiable until its imports are fixed or
the module they used to serve is confirmed gone for good and the script is retired instead.

### 06_content_source.py (187 LOC)

**Purpose:** Tests Crawl4AI's `content_source` parameter across many URLs per domain. Scrapes each URL with 6 configurations in parallel (5 URLs concurrent, 6 configs per URL concurrent). Max 20 URLs per domain. Configs: `cleaned_html`/`cleaned_html_pruning`/`raw_html`/`raw_html_pruning`/`fit_html`/`fit_html_pruning` (PruningFilter 0.48 where `_pruning`; `fit_markdown` field for pruning configs, `raw_markdown` otherwise).
**Reads:** `dev/explore_pipeline/md/` JSON reports (created via `dev/explore_pipeline/01_discovery.py --all`).
**Writes:** `05_content_source/<domain>/<config>/<NN>_<slug>.md` — raw markdown output per URL for manual inspection.
**Called by:** CLI only. `--all` / `--domain <name>` / `--url <url>`.

## Gotchas
Workflow: 04 gives broad filter comparison, 05 gives step-by-step pipeline transparency for one profile at a time. 06 is a large-scale content_source × filter comparison, requires `dev/explore_pipeline/01_discovery.py --all` to have run first.
