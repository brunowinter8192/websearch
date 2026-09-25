# src/scraper/

## Role

Ad-hoc single-URL scraping behind the scrape and index subcommands of cli.py. Turns one URL into noise-filtered markdown via a stealth crawl4ai browser call and logs all facts. It reports facts and never judges content. Not the batch crawler; that is src/crawler.

## Public Interface

`__init__.py` is empty; modules are imported by path.

- chromium_scrape.py: the scrape entry used by cli.py (content only, never truncated).
- scrape_logger.py: log record and content sidecar writers, used by both acquisition lanes.
- index_scrapes.py: the indexing entry used by cli.py.
- camoufox_scrape.py: the Camoufox lane; not wired to any CLI subcommand, still used by src/crawler.

## Flow

URL in, one stealth browser call on a self-launched, dynamically resolved Chromium over CDP. Content, status chain and diagnostic facts are logged as one JSONL record plus a full-content sidecar. Only the content is returned to the caller. The index step later reads a URL's sidecar and writes it into an external RAG collection. Browser watchdog and log retention come from `src/death_pipe.py` and `src/log_janitor.py`.

## Modules

### chromium_scrape.py (267 LOC)

**Purpose:** Scrape orchestrator: one crawl4ai call through the self-launched Chromium, returns fit markdown, logs facts, and runs three independent process-hygiene nets.
**Reads:** the url argument.
**Writes:** log record and sidecar via scrape_logger.py; a throwaway browser profile directory removed by teardown.
**Called by:** cli.py, camoufox_scrape.py, src/crawler/pipe_scraper.py, src/crawler/pipe_scraper_acquisition.py.
**Calls out:** crawl4ai, mcp types.

### chromium_process.py (173 LOC)

**Purpose:** Self-launched Chrome process lifecycle for the chromium lane: bundle resolution, launch, port wait, focus-steal watchdog, teardown and orphan reaping.
**Reads:** nothing of its own; callers pass all inputs.
**Writes:** the Chrome process and its throwaway profile directory (removal).
**Called by:** chromium_scrape.py.
**Calls out:** crawl4ai browser manager, patchright, psutil, macOS open, pgrep and osascript.

### scrape_logger.py (51 LOC)

**Purpose:** Per-URL structured logging shared by both lanes: one JSONL record and one full-content sidecar per call.
**Reads:** the scrape-log path environment variable; the sidecar directory.
**Writes:** the scrape JSONL log and per-call sidecar files under src/logs (gitignored).
**Called by:** chromium_scrape.py, camoufox_scrape.py, index_scrapes.py.
**Calls out:** none.

### index_scrapes.py (92 LOC)

**Purpose:** Bridge from ad-hoc scrapes to an external RAG collection: resolves each URL's sidecar, rewrites it in collection format and triggers indexing.
**Reads:** the sidecar directory and the external collection directory.
**Writes:** one markdown file per URL into the collection directory; invokes the external rag-cli binary.
**Called by:** cli.py.
**Calls out:** rag-cli (subprocess).

### camoufox_scrape.py (219 LOC)

**Purpose:** Calibrated Firefox/Camoufox acquisition lane with the same facts-only contract; reactivatable but currently without a CLI subcommand.
**Reads:** the url and image-blocking arguments; the macOS system locale.
**Writes:** log record and sidecar via scrape_logger.py when its workflow entry is used.
**Called by:** src/crawler/pipe_scraper_acquisition.py; dev tests. No CLI caller since the subcommand was removed.
**Calls out:** camoufox, crawl4ai, mcp types.

## State

None in memory; every call is independent. Persistence is the scrape JSONL log and content sidecars, pruned by src/log_janitor.py.

Details, decisions and observed evidence: process-docs/scrape_pipeline, process-docs/camoufox_lane, process-docs/browser_posture and process-docs/refactor_sweep.
