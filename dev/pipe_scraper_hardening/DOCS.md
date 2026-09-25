# dev/pipe_scraper_hardening/

## Role
Probe comparing the crawl4ai pipe scraper with and without stealth at per-domain concurrency 8, to see whether stealth changes WAF or error outcomes. Touch it to repeat that comparison; not for production scraper changes.

## Public Interface
No `__init__.py` — not a package. The numbered probe is the entry point, run from the repo root via `./venv/bin/python`.

## Flow
URL list in -> baseline run, a fixed gap, stealth run, each with the same pacing and concurrency -> per-run JSON in `json/` -> comparison report in `md/`.

## Modules

### 01_stealth_concurrency_probe.py (250 LOC)

**Purpose:** Runs the same URL list without and with crawl4ai stealth and reports outcome counts, crash signatures and byte deltas.
**Reads:** the discovered-URL list produced by the explore_pipeline area (the file is not tracked); live sites.
**Writes:** `json/01_<variant>_results.json`, `md/01_stealth_concurrency_probe_<date>.md`, scraped markdown under `/tmp/pipe_scraper_hardening_<variant>/`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

---

## State
No shared state. Results live in `json/` and `md/`.
