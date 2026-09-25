# src/

## Role

Root of the source tree. config.py, cdp_value.py, log_janitor.py, death_pipe.py and watchdog_spawn.py are the modules directly at this level: shared, domain-agnostic utilities and constants used by the packages below. All functional packages (search, scraper, crawler, news) live one level down, each with its own DOCS.md.

## Public Interface

`__init__.py` is empty. Modules are imported by path; death_pipe.py runs itself as a detached helper process, started by watchdog_spawn.py.

## Flow

log_janitor.py: a log writer calls it after appending; it prunes old records or files at most once per hour. watchdog_spawn.py: a browser lane hands it PIDs; it starts death_pipe.py as a detached helper that waits on a pipe and cleans up when the caller dies.

## Modules

### config.py (35 LOC)

**Purpose:** Constants shared by two or more modules with identical meaning; single-module constants stay in their module.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** cli.py, src/search, src/scraper and src/news modules.
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

### death_pipe.py (83 LOC)

**Purpose:** Crash backstop for browser lanes: a detached helper kills leftover PIDs and removes a throwaway directory once the parent process ends for any reason.
**Reads:** the log-path environment variable, only when it must log an intervention.
**Writes:** one line to the CLI log, only when it actually kills or removes something.
**Called by:** src/watchdog_spawn.py (as a script); src/search/browser.py and src/scraper/chromium_process.py (`terminate_then_kill`).
**Calls out:** psutil.

### watchdog_spawn.py (22 LOC)

**Purpose:** Starts the detached death_pipe helper for a set of PIDs and a throwaway directory and returns the pipe end that keeps it waiting.
**Reads:** none.
**Writes:** a subprocess and a pipe.
**Called by:** src/search/browser.py, src/scraper/chromium_scrape.py.
**Calls out:** none (stdlib only).

## State

None in memory. The only persistent effects are the pruned log files and the intervention log line.
