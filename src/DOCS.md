# src/

## Role

Root of the source tree. config.py, cdp_value.py, code_version.py, host_load.py, log_janitor.py, death_pipe.py and watchdog_spawn.py are the modules directly at this level: shared, domain-agnostic utilities and constants used by the packages below. All functional packages (search, scraper, crawler, news, pdf) live one level down, each with its own DOCS.md.

## Public Interface

`__init__.py` is empty. Modules are imported by path; death_pipe.py runs itself as a detached helper process, started by watchdog_spawn.py.

## Flow

code_version.py: the three log writers stamp its result into every record they write. host_load.py: the search and the chromium scrape take a snapshot at the start and ask for the facts at the end of their window. log_janitor.py: a log writer calls it after appending; it prunes old records or files at most once per hour. watchdog_spawn.py: a browser lane hands it PIDs; it starts death_pipe.py as a detached helper that waits on a pipe and cleans up when the caller dies.

## Modules

### config.py (40 LOC)

**Purpose:** Constants shared by two or more modules with identical meaning; single-module constants stay in their module.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** cli.py, src/search, src/scraper, src/news and src/pdf modules.
**Calls out:** none.

---

### cdp_value.py (3 LOC)

**Purpose:** Unwraps the value field of a CDP script-evaluation result; the one shared copy for all engines and the CoinDesk browser module.
**Reads:** the CDP result handed in.
**Writes:** none.
**Called by:** src/search/engines/ modules, src/news/platforms/coindesk/browser.py.
**Calls out:** none.

---

### code_version.py (41 LOC)

**Purpose:** Provides the git commit of the running code as the `code_version` stamp; marks tracked local changes, ignores untracked files.
**Reads:** the git state of the project root.
**Writes:** none.
**Called by:** src/search/query_logger.py, src/scraper/scrape_logger.py, src/crawler/pipe_scrape_logger.py.
**Calls out:** git (subprocess).

---

### host_load.py (113 LOC)

**Purpose:** Measures machine saturation over a workflow window: load average, system CPU busy share and the top CPU consumers; measuring errors are returned as facts, never raised.
**Reads:** the process table via `ps`, system CPU times via psutil, the load average.
**Writes:** none.
**Called by:** src/search/search_web.py, src/scraper/chromium_scrape.py.
**Calls out:** psutil, `ps` (subprocess).

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
