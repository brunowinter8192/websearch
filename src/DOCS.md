# src/

## Role

Root of the source tree. config.py, cdp_value.py, log_janitor.py and death_pipe.py are the modules directly at this level: shared, domain-agnostic utilities and constants used by the packages below. All functional packages (search, scraper, crawler, news) live one level down, each with its own DOCS.md.

## Public Interface

`__init__.py` is empty. Modules are imported by path; death_pipe.py also runs itself as a detached helper process.

## Flow

log_janitor.py: a log writer calls it after appending; it prunes old records or files at most once per hour. death_pipe.py: a browser lane hands it PIDs; a detached helper waits on a pipe and cleans up when the caller dies.

## Modules

### config.py (24 LOC)

**Purpose:** Constants shared by two or more modules with identical meaning; single-module constants stay in their module.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** src/search/browser.py, src/scraper/chromium_process.py, src/scraper/chromium_scrape.py, src/news/pipeline.py, src/news/pipeline_support.py, src/news/engine and src/news/platforms modules.
**Calls out:** none.

---

### cdp_value.py (3 LOC)

**Purpose:** Unwraps the value field of a CDP script-evaluation result; the one shared copy for all engines and the CoinDesk browser module.
**Reads:** the CDP result handed in.
**Writes:** none.
**Called by:** src/search/engines/ modules, src/news/platforms/coindesk/browser.py.
**Calls out:** none.

---

### log_janitor.py (80 LOC)

**Purpose:** Retention janitor for JSONL logs and sidecar directories, triggered on write and throttled by a marker file.
**Reads:** JSONL log files, sidecar directories, the retention environment variable.
**Writes:** atomically rewritten JSONL files; deletes stale sidecar files.
**Called by:** src/search/query_logger.py, src/scraper/scrape_logger.py, src/crawler/pipe_scrape_logger.py, cli.py.
**Calls out:** none (stdlib only).

### death_pipe.py (99 LOC)

**Purpose:** Crash backstop for browser lanes: a detached helper kills leftover PIDs and removes a throwaway directory once the parent process ends for any reason.
**Reads:** the log-path environment variable, only when it must log an intervention.
**Writes:** one line to the CLI log, only when it actually kills or removes something.
**Called by:** src/search/browser.py, src/scraper/chromium_scrape.py, src/scraper/chromium_process.py.
**Calls out:** psutil.

## State

None in memory. The only persistent effects are the pruned log files and the intervention log line.
