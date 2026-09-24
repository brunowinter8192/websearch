# refactor-scan Phase 4 - DOCS.md structure for the root and src/ (2026-09-25)

## What was done

Every DOCS.md in scope (root DOCS.md and all 12 DOCS.md under src/) was rewritten to the format template: Role (max 50 words), Public Interface, Flow (3-5 lines), Modules (Purpose max 25 words, Reads, Writes, Called by, Calls out) and State. No function, method, class or constant name remains in these files. Function-level detail, constants, thresholds, removal decisions and observed evidence were removed from the DOCS.md files.

Nothing was lost: the complete pre-rewrite text of each file is archived below (section "Archive of the pre-rewrite DOCS.md text"), verbatim, per directory. It also lives in git at commit 3dbada3 (`git show 3dbada3:<dir>/DOCS.md`). The archive is a snapshot as of 2026-09-24/25; its line numbers, LOC values and file names describe that date, not later states. Where the archive and the code disagree, the code wins.

The DOCS.md files in dev/ were not part of this task (handled by a separate worker).

## Where the important details live (index into the archive)

Successor guide: which archived Gotchas matter most, per directory. Read the named section in the archive before touching the named behavior.

- root (cli.py): discover_urls deliberately writes no file and exits 1 when the discovery result is not ok, so a script is never handed a valid-looking empty file. The ad-hoc Camoufox subcommand was removed on 2026-08-27 by decision, not by accident; the module stays importable and reactivation means re-adding the import and the subparser/dispatch branch only. Help output is deliberately disabled (fixed sentence naming three skills, exit 2). Logging setup must run before any src import.
- src/ (log_janitor, death_pipe): the retention-days env var raises on an unparsable value (2026-09-09 decision); death_pipe is the crash backstop that must stay free of project imports; it kills own PIDs and removes a throwaway dir on EOF of a pipe.
- src/scraper: the module reports facts and never judges content (2026-08-05). Status code is the LAST main-frame document response, not the redirect-chain-first value (2026-09-03), example: skeptics.stackexchange.com chain [403, 302, 200]. Three independent process-hygiene nets (finally, death_pipe watchdog, orphan reap); do not collapse them. The self-launched Chrome bundle path is resolved dynamically every call. index_scrapes picks the lexically latest sidecar per URL on purpose (example: a 364-byte mojeek block page beats an 8912-byte real one, by design). Camoufox is decoupled from the CLI but reused by the batch crawler.
- src/crawler: no browser traversal in discovery anymore (removed after 3571 URLs took 2 s in feeders and over 12 minutes in the traversal). Fallback paths via curl_cffi were removed 2026-09-09. The outcome verdict field was removed from the batch scraper (13 nav-chrome-only pages had been indexed as ok). The onward-links file collects links at zero extra fetch cost; link identity drops query strings (example: 50 login variants collapsed to one). Feeders return not-ok for an unfetchable seed; only 404/410 mean absent.
- src/search: two-call architecture (search then drilldown reading the cache); pool cap and shared-URL handling; the lock wait must happen outside per-engine watchdogs (prewarm); three independent Chrome-hygiene nets; verdict statuses were replaced by observed facts in a diagnosis dict; corrupt cache raises instead of being swallowed.
- src/search/engines: Mojeek must never gain a block-detection early exit (boilerplate is on screen from the first poll); no page literals are matched, only structure. Diagnosis field names are uniform across the seven browser engines. Partial diagnosis with elapsed time is only written on cancelled or crashed engines. Google resolves goto redirects with a non-followed request per result.
- src/news: platform seam via registry, three scrape engines dispatched on one attribute, start-job ordering before logger construction, riding and browser reporters are not interchangeable.
- src/news/engine/proxy_pool and proxy_riding: several tests patch names on the DEFINING module, so certain helpers must stay in their module; the riding abort paths hard-exit and write reports into the job directory; the riding output directory must be the platform directory, not the raw directory.
- src/news/platforms: registration by side-effect import; regwall signal strings must stay precise; The Block cleanup strips the sponsor block to end of string (verified on 22,995 files).

## Process notes for a successor

- The docs-drift-check tool flags any backticked name followed by parentheses, dotted lowercase pairs such as module.attribute, and any all-caps token that matches a constant defined in the code. Writing prose at module level with only file names avoids all three.
- Path-drift findings in the report for src/scraper and src/news/engine/proxy_riding referenced dev paths that no longer exist; they vanished with the rewrite because the references now live only in this archive.
- Files at or above 400 lines after the rewrite: none in scope.

## Archive of the pre-rewrite DOCS.md text

Verbatim copies as of commit 3dbada3, one per directory.

### Archive: DOCS.md

~~~~markdown
# websearch/

## Role

CLI-driven web research toolkit for Claude Code. `cli.py` is the sole root-level `.py` file — a thin argparse dispatcher wiring the search, drilldown, scrape, discovery, and indexing workflows into 5 CLI subcommands. Touch this file when adding/removing a CLI subcommand or changing global logging setup; workflow logic itself lives in `src/search/`, `src/scraper/`, and `src/crawler/`.

## Modules

### cli.py (219 LOC)

**Purpose:** CLI entry-point. Configures daily-rotating file logging (no stderr handler) before any `src.*` import, then dispatches 5 argparse subcommands: `search_web` (query → `search_web_workflow`), `search_engine_drilldown` (query + required `--engine` → cache-read-or-rerun, then `format_engine_pool`), `scrape_url_chromium` (url → `scrape_url_chromium_workflow`, the crawl4ai/chromium lane; rejects `.pdf` paths, tells the user to download manually), `discover_urls` (seed_url + `--url-file` → `discover_urls_workflow`, then `_write_discovery_output` — see Gotchas for its file-vs-exit-status contract on failure), `index_scrapes` (collection + one-or-more URLs → `index_scrapes_workflow`, then `_dispatch_index_scrapes` prints one terse outcome line per URL — see `src/scraper/DOCS.md` for the workflow itself).
**Reads:** CLI args (argparse), disk cache via `cache_read` (drilldown cache-miss path).
**Writes:** `src/logs/cli.log` (rotating log), stdout (result text/summary), and — `discover_urls` only, on success — the `--url-file` path (one URL per line, `pipe_scraper.py`'s own `--url-file` contract).
**Called by:** invoked directly as the CLI entry-point (`python cli.py <subcommand>`), not imported elsewhere.
**Calls out:** `src.search.search_web.search_web_workflow`, `src.search.browser.kill_own_chrome_atexit`, `src.search.cache.{cache_key,cache_read,format_engine_pool}`, `src.scraper.chromium_scrape.scrape_url_chromium_workflow`, `src.scraper.index_scrapes.index_scrapes_workflow`, `src.crawler.discovery.discover_urls_workflow`, `src.log_janitor.get_retention_days`.

## Gotchas

- 5 subcommands exist (`search_web`, `search_engine_drilldown`, `scrape_url_chromium`, `discover_urls`, `index_scrapes`); the scrape subcommand rejects `.pdf` URLs — PDF download is delegated to the user. There is exactly ONE ad-hoc acquisition lane, so there is no lane choice, no auto-selection and no fallback on this path.
- **`discover_urls` writes NO file at all and exits 1 when `DiscoveryResult.ok` is `False` (e.g. an unusable `seed_url`) — deliberately, not an oversight.** A caller/script must never be handed a file that looks like a valid, if empty, result and silently have `pipe_scraper` "successfully" scrape zero pages — the exact silent-loss failure mode the whole `url_discovery` area exists to prevent, arriving one step later in the pipeline. A degraded-but-`ok=True` run (a failed feeder) is NOT treated as an error and DOES write the file — `ok`/`failed_feeders` print first, unconditionally, even at zero/empty, specifically so a thin result cannot be mistaken for a complete one just because that fact would otherwise sit below the fold. The tooling reports the facts; the agent judges whether the run looks trustworthy.
- **`discover_urls` has no `--max-pages`/`--max-depth` flags, and no fetch-confirmation concept on its output.** `discover_urls_workflow` runs the three feeders and merges their output with the literal seed URL — it never fetches a page itself (a prior version additionally traversed the resulting URL set with a headless browser purely to read its links; removed as a duplicate fetch of every page in the run, see `src/crawler/DOCS.md`'s Gotchas), so there is no page budget to override and no fetched/failed/alias status left to report. `--url-file` is simply every `DiscoveredURL.url` from the result, one per line.
- **`scrape_url_camoufox` was REMOVED here on 2026-08-27 — do not re-add it as a "missing" subcommand.** The Camoufox module, its calibrated config and its tests are all still present and untouched, which makes the absent subcommand look like an oversight; it is a decision (see `process-docs/lane_choice/`). Reactivation means re-adding the import plus the subparser/dispatch branch, and nothing else. The batch pipeline's own `--engine camoufox` (`src/crawler/`) is a different consumer and was never part of this removal.
- `cli.py` inserts its own directory at the front of `sys.path` as its first statement so `src.*` imports resolve regardless of the working directory the CLI is invoked from.
- Logging setup MUST run before any `src.*` import — module-load-time log calls from those imports would otherwise route to Python's default stderr `lastResort` handler instead of the file handler.
- `atexit.register(kill_own_chrome_atexit)` — PID-scoped last-resort backstop (never a profile-pattern kill) for interpreter exit paths that skip `search_web_workflow`'s own `finally: kill_own_chrome()` (e.g. an uncaught exception before that point).
- Help/usage output is deliberately disabled. `main()` uses a `NoHelpParser(argparse.ArgumentParser)` subclass overriding `error()` and `print_help()`; both print a fixed sentence naming all three websearch skills (`websearch-web-research`, `websearch-capture-and-index`, `websearch-pdf`) and exit 2, never argparse's usage/flag listing. `add_subparsers()` propagates `parser_class=type(self)` automatically, so all subcommands (and any future one) inherit the same behavior with no per-subcommand wiring.
- **`index_scrapes` (M2, 2026-09-20) reuses `src.crawler.pipe_scraper_acquisition._url_to_filename` for the collection filename convention — confirmed against the real `websearch-reference` collection directory to match on ~40 sampled files, with one known exception, not fixed.** `api_semanticscholar_org_graph_v1_swagger.md` (source `https://api.semanticscholar.org/graph/v1/swagger.json`) is the one real file whose name does NOT match what `_url_to_filename` actually produces for that URL (`..._swagger_json.md` — the `.json` in the path becomes `_json`, not dropped). That file predates this milestone and was not produced by this function; every other sampled file (all `api.stackexchange.com/docs/...` URLs with no extension in the path) matches `_url_to_filename`'s output exactly. `index_scrapes` follows the function as written, not the one outlier — see `src/scraper/DOCS.md`'s own Gotcha on this module for the full reasoning.

~~~~

### Archive: src/DOCS.md

~~~~markdown
# src/

## Role

Root of the source tree. `log_janitor.py` and `death_pipe.py` are the two `.py` modules directly at this level — shared, domain-agnostic utilities used by the sub-packages below. All functional packages (`search/`, `scraper/`, `crawler/`, `news/`) live one level down, each with its own `DOCS.md`.

## Modules

### log_janitor.py (80 LOC)

**Purpose:** 90-day log retention janitor. On-write trigger with 1h marker-throttled slow path. Three public functions: `get_retention_days()` (env override — as of 2026-09-09 raises on an unparsable value instead of swallowing it, see Gotchas), `maybe_prune_jsonl(log_path)` (timestamp-based JSONL filter + atomic rewrite), `maybe_prune_sidecars(sidecar_dir)` (mtime-based `.md` unlink). `maybe_prune_jsonl`/`maybe_prune_sidecars` still log every failure as WARNING and swallow it, including one raised by `get_retention_days()` reached through them — only `cli.py`'s own direct call site is a real, uncaught tripwire.
**Reads:** JSONL log files, sidecar `.md` directories, `WEBSEARCH_LOG_RETENTION_DAYS` env var.
**Writes:** rewrites pruned JSONL atomically, unlinks stale sidecar files.
**Called by:** `src/search/query_logger.py`, `src/scraper/scrape_logger.py`, `cli.py` (imports `get_retention_days` for `TimedRotatingFileHandler` backupCount).
**Calls out:** none (stdlib only).

### death_pipe.py (82 LOC)

**Purpose:** Process-hygiene "net 2" — a crash backstop for any browser lane. `spawn_watchdog(pids, cleanup_dir=None)` forks a detached, minimal helper (this same file, re-invoked as `__main__`) connected to the caller only via a pipe; the helper blocks reading it and only wakes on EOF, which the OS delivers the instant the caller ends for ANY reason (clean exit, uncaught exception, or `SIGKILL` — a hard kill closes every fd the process held, no cooperation required). On wake, the helper kills any of `pids` still alive and removes `cleanup_dir` if given, then exits — a no-op (and completely silent, no log line) if the caller's own normal teardown already did that first. Reused by `chromium_process.py`'s own `_kill_by_profile` and pre-launch orphan reap for the identical terminate/kill primitive (`_terminate_then_kill`), not just for net 2 itself.
**Reads:** nothing at import time; `WEBSEARCH_DEATH_PIPE_LOG_PATH` env (fallback `src/logs/cli.log`) only when it actually has to log an intervention.
**Writes:** one line to `src/logs/cli.log` ONLY when it actually kills a PID or removes a dir (silent otherwise); no other state.
**Called by:** `src/search/browser.py` (`get_tab`, after `_record_own_pids`); `src/scraper/chromium_scrape.py` (`_acquire_cdp_headed`, after the cdp port resolves, via `spawn_watchdog`); `src/scraper/chromium_process.py` (`_kill_by_profile`/`_reap_orphaned_scrapes`, via `_terminate_then_kill`).
**Calls out:** `psutil` (terminate/wait/kill); no project-internal imports (deliberately — this module must start and run correctly even if something else in the codebase is broken).

## Gotchas

- **REMOVED 2026-09-09: `get_retention_days`'s silent fallback to 14 on an unparsable `WEBSEARCH_LOG_RETENTION_DAYS` — user decision, Phase 4 control-flow review.** No supporting observation existed: the env var is set nowhere in the repo (`cli.py`, skills, configs). An invalid value now raises `ValueError` at first use. `cli.py`'s own call (`backupCount=get_retention_days()`, module-load time, outside any try/except) is the real, uncaught tripwire — a typo now fails CLI startup immediately. The two internal call sites (`_prune_jsonl`/`_prune_sidecars`) are UNCHANGED and stay out of scope: both are reached only through `maybe_prune_jsonl`/`maybe_prune_sidecars`, which wrap their own call in a pre-existing, deliberate `except Exception as e: logger.warning(...)` — a `ValueError` surfacing through that path is still caught and merely logged, not a crash. This is a separate, already-documented fail-soft design (see this module's own Purpose line above), not touched by this removal.
- 2026-09-24 Phase 5: `log_janitor._prune_jsonl` keeps an unparseable line (with a warning) instead of dropping it in the rewrite. `death_pipe._log_intervention` no longer swallows `OSError` (in the detached child, a failing log path ends the helper), and `removed_dir` in the intervention line is true only when the directory is actually gone. the unused tmux spawn shell helper was deleted (no caller anywhere) together with its `.drift-whitelist.txt` names.

~~~~

### Archive: src/scraper/DOCS.md

~~~~markdown
# src/scraper/

## Role

URL scraping for the `scrape_url_chromium` CLI subcommand. Turns a single URL into clean, noise-filtered markdown via one stealth crawl4ai browser call (Crawl4AI v0.8.6). Touch this package when changing scrape extraction or cookie/consent handling. Not the batch crawler itself — that is `src/crawler/`.

**Contract (as of the 2026-08-05 removal of content judgment):** this module reports facts, it does not judge content. `scrape_url_chromium_workflow` returns whatever content crawl4ai produced — unconditionally, full length, no status-code gate, no keyword-based rejection. As of the M2 acquisition-facts-removal milestone (2026-09-15), the returned text carries content ONLY — the facts (HTTP status, the document status chain, byte counts, crawl4ai's own anti-bot diagnosis) are still captured and still logged to `scrape_log.jsonl` in full, they are simply no longer printed alongside the content; see Gotchas. The caller (an agent, with a user to report to) judges; this module used to judge content itself and no longer does. `is_garbage_content` (automatic verdict) no longer exists anywhere in this project: content judgment was removed from this module on 2026-08-05 and relocated to `garbage_filter.py` in `src/crawler/`, and that module — the last automatic-verdict consumer, via its only caller `crawl_site.py` (also `src/crawler/`) — was retired 2026-09-09 (zero callers of its own; `discovery.py`/`pipe_scraper.py` carry the whole discovery/batch-scrape function; user decision in the Phase 4 control-flow review). Do not reintroduce a content-judgment call from this module's own `try_scrape`/`scrape_url_chromium_workflow`.

## Public Interface

`__init__.py` is empty — modules are imported by path:

- `scrape_url_chromium_workflow(url)` (chromium_scrape.py) — imported by `cli.py` as the `scrape_url_chromium` subcommand entry. Returns `list[TextContent]`, one item: full content, never truncated, no acquisition-facts preamble (see Gotchas — the facts are logged, not printed).
- `log_scrape(record)`, `write_sidecar(url, ts, content, mode, engine)` (scrape_logger.py) — called by chromium_scrape.py and camoufox_scrape.py. No `outcome` parameter — see Gotchas.
- `index_scrapes_workflow(collection, urls)` (index_scrapes.py) — imported by `cli.py` as the `index_scrapes` subcommand entry. Reads each URL's own sidecar off disk (written by `write_sidecar` above) and indexes it into an external `rag-cli` collection — see Gotchas.
- `try_scrape_camoufox(url, block_images=False) -> tuple[str, dict]` (camoufox_scrape.py) — the calibrated acquisition primitive; called by `scrape_url_camoufox_workflow` below, and by `src/crawler/pipe_scraper_acquisition.py`'s `_scrape_one_camoufox` (the batch capture-pipeline's camoufox engine, a separate consumer, unaffected by anything below).
- `scrape_url_camoufox_workflow(url, block_images=False)` (camoufox_scrape.py) — **as of 2026-08-27, no longer imported by `cli.py`; the ad-hoc `scrape_url_camoufox` subcommand was REMOVED (see Gotchas).** The function itself, its calibrated config, and its tests are UNCHANGED — kept deliberately reactivatable, not deleted, importable and callable directly (`python -c "from src.scraper.camoufox_scrape import scrape_url_camoufox_workflow"`). Same `list[TextContent]` shape as `scrape_url_chromium_workflow` for whichever future caller re-wires it.

## Flow

`scrape_url_chromium_workflow` → `try_scrape(url)` runs one stealth crawl4ai call, with a `before_goto` hook (`_make_document_status_listener`) arming a `page.on("response")` listener before navigation starts, collecting the ordered chain of main-frame document response statuses (see Gotchas) → `og_published_time` is read straight off crawl4ai's own already-parsed `result.metadata` (the page's own `og:published_time` <head> tag, if it declared one — never a third-party guess, see Gotchas) → content is `fit_markdown` unconditionally (PruningContentFilter's output, no fit/raw selection — removed 2026-08-22, see Gotchas) → result + metadata logged via scrape_logger (JSONL record + content sidecar, full content, no truncation; `landed_url` raw as its own field, no computed verdict alongside it) → `_format_scrape_output` renders the `# Content from: <url>` heading followed by the full content, always in that order, returned as-is — no acquisition-facts block (removed 2026-09-15, see Gotchas; the facts themselves are unchanged, only the print of them is gone). No code in this module computes or stores a same/different verdict on the two URLs (removed 2026-08, see Gotchas) — an agent reading the log has both URLs and compares them itself.

## Modules

### chromium_scrape.py (265 LOC)

**Purpose:** Scrape orchestrator — single crawl4ai browser call via a self-launched, dynamically-resolved chromium bundle connected over CDP (`_acquire_cdp_headed`, stealth + consent-removal, self-launch/port-wait/teardown mechanics delegated to `chromium_process.py` below), returns `fit_markdown` unconditionally as the sole printed output (HTTP status, document status chain, byte counts, and crawl4ai's own anti-bot diagnosis are captured and logged but no longer printed — M2 milestone, 2026-09-15, see Gotchas) — no content judgment. Three independent process-hygiene nets, all implemented in `chromium_process.py`: net 1 is `_acquire_cdp_headed`'s own `finally` (`_kill_by_profile` + `shutil.rmtree`, fires on every normal exit path including budget exhaustion); net 2 is a `death_pipe` watchdog spawned once the cdp port resolves (crash backstop — kills this call's own PIDs and removes its throwaway dir if the CLI process itself dies before net 1 runs); net 3 is `_reap_orphaned_scrapes`, called at the start of every `try_scrape`, which kills only `scrape-url-cdp-*` processes OLDER than `TOTAL_SCRAPE_BUDGET_S` (never a live parallel scrape — each call's profile dir is unique, concurrency is legitimate) and sweeps any `scrape-url-cdp-*` dir with zero live processes at all.
**Reads:** `url` arg (no other parameters — `max_content_length` removed 2026-08-05).
**Writes:** result content + metadata via scrape_logger (no direct file writes); a throwaway `--user-data-dir` under the OS temp dir on the cdp path, created here and removed by `chromium_process.py`'s teardown (within one `try_scrape` call, or by net 2/net 3 if that removal itself never ran).
**Called by:** `cli.py` (scrape_url_chromium_workflow); `src/crawler/pipe_scraper.py` (hash_config); `src/crawler/pipe_scraper_acquisition.py` (extract_crawl4ai_diagnosis — reused as-is, not path-specific).
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, UndetectedAdapter, AsyncPlaywrightCrawlerStrategy, PruningContentFilter, DefaultMarkdownGenerator); `death_pipe` (spawn_watchdog, called directly here once the cdp port resolves); `mcp.types.TextContent`; `scrape_logger` (log_scrape, write_sidecar); `src.scraper.chromium_process` (CDP_PORT_WAIT_TIMEOUT_S, TOTAL_SCRAPE_BUDGET_S, and the self-launch/port-wait/kill/reap functions — see below). No longer calls out to `htmldate` — see Gotchas.

### chromium_process.py (175 LOC)

**Purpose:** The self-launched Chrome process lifecycle for the cdp-headed lane — split out of chromium_scrape.py (pure relocation, same behavior): dynamic bundle-path resolution (`_resolve_chromium_bundle_path`/`_find_app_bundle`), self-launch flag construction (`_build_self_launch_flags`, live `ManagedBrowser.build_browser_flags` call), the macOS focus-steal watchdog (`_get_frontmost_app`/`_activate_app`/`_focus_steal_watchdog`), the `open -g` self-launch itself (`_self_launch_chrome`), the DevToolsActivePort wait (`_wait_for_devtools_port`), and process/dir teardown (`_pids_on_profile`, `_kill_by_profile`, `_reap_orphaned_scrapes`, `_pids_matching_scrape_profiles`, `_live_scrape_profile_dirs` — nets 1 and 3, see chromium_scrape.py's own entry). Also owns `CDP_PORT_WAIT_TIMEOUT_S`, `FOCUS_STEAL_POLL_INTERVAL_S`, and `TOTAL_SCRAPE_BUDGET_S` (the outer wall-clock guard — kept here rather than in chromium_scrape.py to keep the dependency one-directional: chromium_scrape.py imports from this module, not the reverse).
**Reads:** nothing of its own — every function takes its inputs as parameters (`user_data_dir`, `bundle_path`, `browser_config`, etc.) from its caller in chromium_scrape.py.
**Writes:** the self-launched Chrome process itself (via `open -g`) and its throwaway `--user-data-dir`'s removal; no files of its own.
**Called by:** `src/scraper/chromium_scrape.py` (`_acquire_cdp_headed`, `try_scrape`) — the only caller.
**Calls out:** `crawl4ai.browser_manager.ManagedBrowser` (build_browser_flags, live call); `patchright.async_api` (async_playwright, for bundle-path resolution only); `psutil` (age checks in `_reap_orphaned_scrapes`, cmdline reads in `_live_scrape_profile_dirs`); `death_pipe` (`_terminate_then_kill`, used by `_kill_by_profile`/`_reap_orphaned_scrapes` — `spawn_watchdog` itself stays a chromium_scrape.py call, not here); macOS `open`/`pgrep`/`osascript` (self-launch, teardown, and focus-steal detection).

### scrape_logger.py (51 LOC)

**Purpose:** Per-URL structured logging for scrape_url_chromium — one JSONL record + one full-content `.md` sidecar per call, shared by both the chromium and Camoufox acquisition lanes (`"engine"` field discriminates both the JSONL record and, as of 2026-08-25, the sidecar's own HTML-comment header).
**Reads:** `WEBSEARCH_SCRAPE_LOG_PATH` env var (fallback `src/logs/scrape_log.jsonl`); sidecar dir `<log_dir>/scrape_content/`.
**Writes:** `src/logs/scrape_log.jsonl` (one line per call); `<log_dir>/scrape_content/<ts>_<slug>.md` (per-call sidecar). Both gitignored.
**Called by:** `chromium_scrape.py` (end of scrape_url_chromium_workflow); `camoufox_scrape.py` (end of scrape_url_camoufox_workflow) — same log file, both lanes, see the engine-discriminator note above.
**Calls out:** `src/log_janitor.py` (maybe_prune_jsonl, maybe_prune_sidecars).

### index_scrapes.py (92 LOC)

**Purpose:** `index_scrapes_workflow(collection, urls)` (M2, 2026-09-20) — the ad-hoc-scrape-to-RAG bridge: for each URL, resolves its own sidecar (see Gotchas for the multi-scrape tie-break), strips the sidecar's own `url`/`ts`/`bytes`/`mode`/`engine` header, rewrites it in the external `rag-cli` collection convention (`<!-- source: url -->` + blank line + content, filename via the reused `_url_to_filename`), writes it into the collection directory, then shells out to `rag-cli index --collection <collection> --document <filename>`. Aborts the whole run, before touching any URL, if the collection directory does not exist — never creates one. Per-URL failures (no sidecar, a non-zero `rag-cli` exit, any unexpected exception) are caught individually and reported as their own outcome; one URL's failure never stops the rest.
**Reads:** the sidecar dir resolved the same way `scrape_logger.py` does (`WEBSEARCH_SCRAPE_LOG_PATH` env override, else `DEFAULT_LOG_PATH`'s sibling `scrape_content/`); the real collection directory under `RAG_CLI_COLLECTIONS_ROOT` (hardcoded, a separate project's data directory — see Gotchas).
**Writes:** one `.md` file per successfully-resolved URL into the collection directory; no writes back to the sidecar itself (read-only).
**Called by:** `cli.py` (`index_scrapes` subcommand).
**Calls out:** `src.scraper.scrape_logger` (`DEFAULT_LOG_PATH`, `_url_slug`); `src.crawler.pipe_scraper_acquisition` (`_url_to_filename`); the external `rag-cli` binary, via `subprocess.run` — no Python import, `rag-cli` is a separate project reached only as a CLI call.

### camoufox_scrape.py (218 LOC)

**Purpose:** Calibrated core acquisition module for the Camoufox/Firefox lane — a second, parallel (not fallback) acquisition path: launches headed Camoufox, navigates, converts captured HTML to markdown via crawl4ai's `raw:` pipeline, same fact-only contract as chromium_scrape.py. As of 2026-09-03, `status_code` is the LAST main-frame document response observed before `page.content()`, not the (possibly stale) `page.goto` Response — see Gotchas, the M2 sibling of chromium_scrape.py's M1 fix. As of 2026-08-25, launch is guarded by a no-focus-steal fix (see Gotchas): `_ensure_no_focus_steal` (`LSUIElement=true`, passive default-activation suppression) plus `ignore_default_args=["-foreground"]` (drops Playwright's own explicit launch-time Cocoa activation call). REMOVED 2026-08-27: the in-process AXMain-keyed `_key_window_steal_watchdog` — five live human-judged runs found no measurable effect from it either way, because AXMain=true on this LSUIElement accessory process never implied real activation. Also as of 2026-08-27, launch passes an explicit `locale` kwarg — `_resolve_system_locale()`, resolved fresh on every call — so this lane requests the same language Chromium already gets for free from the OS (see Gotchas). **REMOVED from the AD-HOC CLI, separately, later the same day (see Gotchas):** this module itself, `scrape_url_camoufox_workflow`, its calibrated config, and its tests are all UNCHANGED — only `cli.py`'s import and subcommand were removed.
**Reads:** `url` arg, `block_images` arg.
**Writes:** `scrape_log.jsonl` + sidecar via scrape_logger.py, IF `scrape_url_camoufox_workflow` is invoked (`try_scrape_camoufox` itself still writes nothing) — as of 2026-08-27 that only happens via a direct Python call or a test, never via any CLI.
**Called by:** nothing in the ad-hoc CLI as of 2026-08-27 (see Gotchas) — `cli.py` no longer imports this module. `src/crawler/pipe_scraper_acquisition.py`'s `_scrape_one_camoufox` still calls `try_scrape_camoufox` directly (the batch capture-pipeline's own camoufox engine, a separate, unaffected consumer — see `src/crawler/DOCS.md`). `dev/tests/test_camoufox_scrape.py` still exercises `scrape_url_camoufox_workflow` directly.
**Calls out:** `camoufox` (launch_options, AsyncCamoufox, CamoufoxNotInstalled); `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, DefaultMarkdownGenerator) for the markdown-conversion step only; `src.scraper.chromium_scrape` (hash_config); `src.scraper.scrape_logger` (log_scrape, write_sidecar); `mcp.types.TextContent`; macOS `defaults read -g AppleLocale` (system-locale resolution, darwin only — see Gotchas).

## State

No shared in-memory state — each `scrape_url_chromium_workflow` call is independent. The only persistence is the JSONL log + content sidecars written by scrape_logger and pruned by log_janitor.

## Gotchas

- `TOTAL_SCRAPE_BUDGET_S=242.8` (down from 245.8 — see the Gotcha below on the removed `HTMLDATE_TIMEOUT_S=3.0` summand; renamed from `TOTAL_SCRAPE_BUDGET_CDP_S` — the escape hatch's own `TOTAL_SCRAPE_BUDGET_HEADLESS_S` was removed, no second budget remains to distinguish it from) — the one outer wall-clock guard (see `process-docs/browser_posture/`/`process-docs/scrape_pipeline/` for the sessions that derived/re-derived it) — `page_timeout=30000` bounds only `page.goto`; `delay_before_return_html=5.0` bounds only the render wait before HTML capture. Two things the outer guard does NOT cover: (1) `asyncio.wait_for` cancels only at await points — markdown generation + `PruningContentFilter` run as synchronous CPU inside crawl4ai's `arun()`, so a pathological synchronous parse can overrun the budget before the guard gets a chance to fire; not fixed (no thread offload/executor), documented as a known limit. (2) The guarded span is ACQUISITION only (`_acquire_scrape()`: browser call/connect + content selection) — post-acquisition local work (`write_sidecar`, `log_scrape`, output formatting) runs outside it so a budget-exhausted record stays writable; `timings_ms.total_wall` in the log can therefore exceed the budget by that post-processing cost.
- `CDP_PORT_WAIT_TIMEOUT_S=10.0` (`chromium_process.py`) is a self-owned, deterministic deadline-checked loop — not an unbounded event wait. Value proven in `dev/browser_posture/05_cdp_headed_probe.py`.
- `FOCUS_STEAL_POLL_INTERVAL_S=0.25` (`chromium_process.py`) bounds any focus steal to a sub-second flicker — the self-launched Chrome is a regular, non-accessory app (`LSUIElement` crashes this bundle, see `dev/browser_posture/DOCS.md`), so Camoufox's own accessory-app lever is unavailable on this lane. Same 0.25s granularity `dev/browser_posture/_lib.py`'s own focus-poll probes already use.
- **The cdp path's self-launched chromium bundle is resolved DYNAMICALLY every call, never hardcoded to a revision number.** `dev/browser_posture/04_headed_chromium_probe.py`/`05_cdp_headed_probe.py` hardcoded "chromium-1228" with a runtime safety check (fine for a manually-run dev probe); production instead asks patchright itself (`patchright.async_api`'s `BrowserType.executable_path`, ~0.15-0.25s per call, not cached — this module has no shared in-memory state by design) so a future patchright upgrade that moves to a different revision directory is followed automatically, not silently broken.
- **`_kill_by_profile` MUST wait for actual process death (via `psutil.wait_procs`) before the caller's `shutil.rmtree` runs.** A plain `pkill` returns once the signal is SENT, not once Chrome actually exits — this raced against the immediately-following directory removal and left a real, non-empty leftover profile dir under the OS temp dir, caught via a real live `cli.py scrape_url_chromium` run (not caught by any mock-based test, since the race is a real-process-timing issue). If this function is ever simplified back to a bare `pkill`, the leak returns.
- **`build_browser_flags()`-derived self-launch flags will never reach "full" parity with patchright's own RPC-launched headed cmdline (`dev/browser_posture/05_cdp_headed_probe.py`'s measured 34-flag delta) — this is a structural fact, not a maintenance gap.** Those flags are constructed by patchright's internal Node driver specifically for a `browserType.launch()`/`connectOverCDP` RPC call; confirmed by reading `ManagedBrowser.start()` (crawl4ai's own raw-`subprocess.Popen`-based self-launch mechanism, the same class of mechanism as our `open -g`) that NO raw-subprocess launcher can ever produce them, regardless of sourcing mechanism. Do not attempt to close this gap with a bigger pinned list — it cannot be closed short of launching via patchright's own RPC, which would defeat self-launching for no-focus-steal in the first place.
- `remove_overlay_elements` is NOT used — it misclassifies legitimate DOM (e.g. Wikipedia content) as overlays and destroys content. Cookie/consent handling is `remove_consent_popups=True` alone (see below).
- **REMOVED 2026-08-22: the hand-maintained `COOKIE_CONSENT_SELECTOR` (`excluded_selector` kwarg, ~19-entry CSS list, including the `cky-modal` entry this Gotcha used to require).** Verified redundant: crawl4ai's own vendor-maintained `remove_consent_popups.js` (301 selectors, market-share ordered, 5 phases) is a strict SUPERSET, including the exact CookieYes case this list was added for — it CLICKS `.cky-btn-accept` (phase 1), removes `.cky-consent-container`/`.cky-overlay` (phase 3), and clears `cky-modal-open` on body (phase 5), stronger than the old hide-only `excluded_selector` approach. `remove_consent_popups=True` now carries consent handling alone; `extract_config_stamp` no longer has an `excluded_selector_hash` field (another stamp-shape change, same accepted kind as the `min_content_threshold`/`max_content_length` drops).
- **As of 2026-08-05, this module's own `try_scrape`/`scrape_url_chromium_workflow` never calls a content classifier** — the whole point of the change was that content judgment moved to the caller (an agent). `is_garbage_content` itself was relocated to `garbage_filter.py` in `src/crawler/` and, as of 2026-09-09, no longer exists anywhere: that module was retired along with its only caller, `crawl_site.py` (also `src/crawler/`) (zero callers of its own; `discovery.py`/`pipe_scraper.py` carry the whole discovery/batch-scrape function; user decision in the Phase 4 control-flow review). The regression test that used to guard against this module reintroducing that call (`dev/tests/test_chromium_scrape.py::test_try_scrape_does_not_call_is_garbage_content`) was removed with it — `try_scrape` has no reference to a content classifier at all anymore, nothing left to patch against.
- **REMOVED 2026-08-22: the fit->raw fallback (`MIN_CONTENT_THRESHOLD=200`, `meta["fallback_to_raw"]`).** Content is `fit_markdown` unconditionally now. An operational-log analysis over 69 production chromium scrapes found the fallback fired exactly once, on a degenerate page where both fit and raw were ~1 byte (useless either way); zero records otherwise sat in the 1-199 fit-byte band; the one near-threshold case (fit=321, raw=2537) never fired, and its raw excess was category-page link-chrome — exactly what `PruningContentFilter` exists to remove. The mechanism's original 2026-03 anecdotal motivation (over-filtered short API docs) is separately covered by `preserve_tags=["pre","code"]`. `meta["raw_markdown_bytes"]`/log's `bytes_raw_markdown` were KEPT as a pure reported fact (crawl4ai's raw markdown size, independent of the now-gone selection) — real diagnostic value confirmed live: a filter-ratio signal against `bytes_returned` (e.g. a real rfc-editor.org scrape: 540416 raw -> 511762 filtered).
- **`http_status` is a fact, not a verdict, as of 2026-08-05** — a status code no longer gates content on its own. Real evidence both directions: `de.trustpilot.com/review/entega.de` returns HTTP 403 WITH the real 42707-byte review page (a status>=400 gate would have discarded all of it); `idealo.de`'s `OffersOfProduct` page returns HTTP 200 with 401 bytes of "Sorry! Something has gone wrong" (a content classifier let it through as clean).
- **As of 2026-09-03, `status_code`/`http_status` is the LAST main-frame document response received before HTML capture, not crawl4ai's own `result.status_code`** (which walks `request.redirected_from` backwards from the `page.goto` response and keeps the EARLIEST hop's status, then never updates it — confirmed by reading `async_crawler_strategy.py`'s "Walk the redirect chain" block). A self-resolving Cloudflare challenge answers `goto` with 403, then its own JS navigates the main frame again during `delay_before_return_html` — the real page lands at 200 and IS what this module returns, but crawl4ai's `status_code` stayed 403, and its own `is_blocked()` flags any 403-with-HTML as blocked (`success=False`, "Blocked by anti-bot protection: HTTP 403 with HTML content"), a false negative on a fully present page. Fixed by `_make_document_status_listener`, a `before_goto`-hook-armed `page.on("response")` listener (main-frame document responses only: `request.resource_type == "document"` AND `request.frame is page.main_frame`, with `request.frame` access guarded — it raises for a navigation request issued before its own frame exists) that collects the ORDERED chain into `meta["document_status_chain"]`/log field (printed as its own "Document status chain" line until the M2 milestone removed the whole acquisition-facts block, 2026-09-15 — see the Gotcha below; the log field itself is unaffected), a FACT never used to derive "challenge solved"/"blocked" anywhere. The last entry overrides `status_code`; an empty chain (e.g. a `raw:` input, which never calls `page.goto` at all) falls back to crawl4ai's own value unchanged, never inventing a status. Live-confirmed: `skeptics.stackexchange.com/questions/2566/...` — chain `[403, 302, 200]`, `status_code` now 200, crawl4ai's own diagnosis STILL reports the 403 block (unchanged, still surfaced as an observation in the log, not acted on) — matching this project's own standing caveat below that crawl4ai's diagnosis has documented false positives.
- **As of 2026-09-03, the Camoufox lane's `status_code` is ALSO the last main-frame document response (M2, the sibling of chromium_scrape.py's M1 fix directly above), driven through plain Playwright rather than a crawl4ai hook — this lane had no hook system to attach through.** `_acquire_camoufox` used to read `status_code = response.status` straight off the `page.goto` Response, the same staleness M1 fixed: a self-resolving challenge answers goto with a stale status, then navigates the main frame again during `CAMOUFOX_RENDER_WAIT_S`. `_make_document_status_listener(page, status_chain)` (duplicated from chromium_scrape.py's version, not imported — same lane-independence precedent as `_find_app_bundle`) is registered via `page.on("response", ...)` BEFORE `page.goto` so the goto response itself is the chain's first entry; same main-frame-document filter and guarded `request.frame` access. The last entry overrides `status_code`; an empty chain falls back to the goto Response's own status unchanged. `document_status_chain` is carried in `meta`, `scrape_url_camoufox_workflow`'s log record, and `pipe_scraper_records.py`'s `_log_pipe_camoufox_record` — same fact-not-verdict framing as M1 (as of the M2 acquisition-facts-block removal, 2026-09-15, `_format_camoufox_output` no longer has a line for this field at all — printed text dropped it, the log record did not, see the Gotcha below). Live-confirmed on the SAME repro URL as M1 (`skeptics.stackexchange.com/questions/2566/...`): chain `[403, 302, 200]`, `status_code` 200 — Camoufox saw the identical challenge shape chromium did on this host. Downstream effect proven at `src/crawler/pipe_scraper_acquisition.py`'s `_scrape_one_camoufox`: it already only ever reads `meta['status_code']` for its own `>=400` -> `http_error` mapping, so a resolved-challenge page now yields `ok` there with no code change to that function — only a test proving the wiring (`dev/tests/test_pipe_scraper.py::test_scrape_all_camoufox_resolved_challenge_status_yields_ok`).
- **`landed_url` identical to the requested URL does NOT prove no redirect happened.** Real CLI run against `idealo.de`'s `OffersOfProduct` page came back with `landed_url` IDENTICAL to the requested URL, HTTP 200, the 367-byte "Sorry! Something has gone wrong" block page. The most plausible reading is that the block page is served directly at the requested URL with no browser-level redirect at all, but a redirect BACK to the same URL is equally consistent with this same observation and cannot be distinguished from it using `landed_url` alone — recorded as a candidate explanation, not a settled mechanism. Do not read a matching `landed_url` next to a thin/blocked-looking page as proof the URL was never redirected.
- **No comparison function exists in this module anymore, and no verdict is stored in the log or rendered conditionally.** `is_same_target` (the requested-vs-landed comparison primitive) and the `same_target` field it fed were both ADDED then REMOVED within the same body of work (`process-docs/scrape_pipeline/`, the `landed_url_*` entries) — not a partial rollback, a deliberate reversal after review: the log is read only by an agent, after the fact, with both `url` and `landed_url` already in the same record, so a stored verdict was a re-derivable conclusion kept as data; the conditional render in `_format_scrape_output` (as it existed at the time, before the M2 milestone removed the whole block — see the Gotcha below) was the one place this module decided which facts the agent gets to see, which is the exact contract the 2026-08-05 removal inverted. The comparison rule itself did not disappear — it moved to the calling agent (`skills/websearch-web-research/SKILL.md`, updated separately, outside this module, to compare the two URLs itself and flag a real target difference to the user). Do not reintroduce `is_same_target`/`same_target` here; if a comparison is ever needed again in code, treat that as a new decision, not a revival of the old one — both raw URLs are on disk (the log record) either way.
- crawl4ai captures stdout — write debug to files, never `print()`.
- **`crawl4ai_error_message`/`crawl4ai_success`/etc. must be presented as an OBSERVATION, not a verdict, wherever they're surfaced — as of the M2 milestone (2026-09-15, see the Gotcha below) that means the log record only, `_format_scrape_output`'s rendered text no longer surfaces this field (or any acquisition field) at all.** crawl4ai's own anti-bot detector has documented false positives: `guenstiger.de` reports `"Blocked by anti-bot protection: Cloudflare JS challenge"` from crawl4ai's own detector on a render at `delay_before_return_html=6.0` that returns the full 38691-byte product page — the reasoning behind this framing lives in `the process-docs area scrape_pipeline/` (the render-time question that surfaces the real page is a separate, not-yet-done milestone — untouched here).
- Missing/failed patchright chromium binary looks IDENTICAL to a genuinely empty page unless caught: launch fails in ~300ms with `http_status:null`, `bytes_raw_markdown:null` — exactly the same shape as a blocked/empty scrape. `is_browser_launch_error` guards against this by matching launch-exception substrings (`executable doesn't exist`, `playwright install`, `browsertype.launch`); on match `meta["acquisition_error"]` is `"browser_missing"` (logged at ERROR, not WARNING) with a message naming the fix: `./venv/bin/python -m patchright install chromium`.
- **`outcome` (`"ok"`/`"empty"`, computed as `acquisition_error or ("ok" if content else "empty")`) was REMOVED from both engines' log records and the sidecar header — this module now reports facts and decides nothing, matching the precedent `src/crawler/pipe_scraper_records.py` set the same day.** `ok`/`empty` were a pure re-derivation of `bytes_returned` (already logged), so the branch was deleted outright, no new field needed. `budget_exhausted`/`browser_missing`/`exception` were DIFFERENT: real facts about what this module's own code did, previously visible ONLY through the collapsed `outcome` string (chromium's log never had a bare `acquisition_error` field of its own before this) — that fact is now logged directly as `"acquisition_error"` on both engines' records, added FIRST, before the `outcome` branch was deleted, per the "add the fact, then remove the verdict" order. The sidecar header's own `outcome` line was worse than a redundant fact: `write_sidecar` only ever runs when `content` is truthy (its own guard), so `acquisition_error` is structurally always `None` whenever a sidecar is written at all — EVERY sidecar's `outcome` line read `"ok"`, carrying zero information regardless of what actually happened on that call. Removed with no replacement line: there is no fact to put there that isn't already guaranteed constant in this exact context. `write_sidecar`'s signature dropped the `outcome` parameter entirely (`write_sidecar(url, ts, content, mode, engine)`, five params, not six).
- **`published_date`/`date` (`htmldate.find_date` guessing a publication date from the raw HTML) was REMOVED along with the `htmldate` dependency itself (`requirements.txt`), `HTMLDATE_TIMEOUT_S`, and `extract_date` — a third-party guess about the remote page, the same class of guess this project's own line already rejects elsewhere.** A real observed failure: a Trustpilot review page (a page class with no publication date at all) was given today's date. Replaced with `og_published_time` — read directly off `result.metadata["og:published_time"]`, a field crawl4ai's own `content_scraping_strategy.py` already populates for every non-prefetch scrape via `extract_metadata_using_lxml` (collects every `og:`-prefixed `<head>` meta tag) — a real fact already sitting on the SAME result object this module already has in hand, at zero extra acquisition cost, verified live (not assumed) by reading `content_scraping_strategy.py`'s `meta = extract_metadata_using_lxml("", doc)` call directly. Null whenever the page declares no such tag — never a guess, never derived from any other page text (e.g. a "Last updated on" footer, htmldate's own documented false-positive shape on reference/docs pages with no real publication-date candidate — the exact failure class this removal closes, not just the one Trustpilot instance). `TOTAL_SCRAPE_BUDGET_S` dropped by exactly `HTMLDATE_TIMEOUT_S`'s own 3.0s summand (245.8 → 242.8, see the Gotcha above) since no separate date-extraction step runs anymore. `_format_scrape_output`'s old top-level, presence-conditional `"Published: {date}"` line (omitted entirely when absent) was replaced by an unconditional `"- og:published_time (...): {value}"` bullet inside "## Acquisition facts" — the same unconditional-fact treatment `landed_url`/HTTP status already get in that block. That whole block, including this bullet, was removed 2026-09-15 (M2 milestone, see the Gotcha below) — `og_published_time` itself is unaffected and stays a plain logged fact, `meta.get("og_published_time")` in `scrape_url_chromium_workflow`.
- **`dev/lane_choice/01_backfill_pairs.py` and `04_lane_metrics.py` both read `outcome` off this exact log and were fixed the same day, locally, not by reintroducing the field.** `01_backfill_pairs.py`'s own `_derive_outcome` reconstructs the identical three-way label (`acquisition_error`, or `"ok"`/`"empty"` from `bytes_returned`) for its own reporting — a local, dev-only derivation, not a revival of the production verdict. `04_lane_metrics.py`'s `_latest_ok_records_by_url_engine` used to filter on `record.get("outcome") != "ok"`, which would have silently excluded EVERY record written after this removal (no `"outcome"` key at all, so the check is always true) rather than raising — fixed to check `acquisition_error`/`bytes_returned` directly, which reads identically on records from before and after this removal. See `dev/lane_choice/DOCS.md`'s own Gotchas for the fix in place.
- `PruningContentFilter` WITHOUT `preserve_tags=["pre","code"]` corrupts syntax-highlighted code: `_prune_tree` (crawl4ai's own `content_filter_strategy.py`) recurses into any node it keeps and decomposes children scoring below `threshold`; a highlighter's whitespace-only `<span>` between tokens scores near-zero and gets removed, collapsing `FROM golang:1.22-alpine AS builder` to `FROMgolang:1.22-alpineASbuilder` — confirmed via real CLI scrape of a live dev.to Docker post and the kubernetes.io Service page (crawl4ai issue #2110, open as of 0.9.2, this project's exact version). `preserve_tags` short-circuits `_prune_tree` before it recurses into a matched node, so the WHOLE subtree survives untouched — confirmed on both real repros; `preserve_classes` was evaluated and NOT added, since in both cases the `<pre>` tag itself (not a wrapping div/figure) is what the top-down recursion evaluates directly, so `preserve_tags` alone was sufficient without guessing highlighter-specific wrapper class names (Rouge/Prism/highlight.js all differ). `threshold` stays at 0.48 (empirically calibrated, see `the process-docs area scrape_pipeline/`) — this is a guard on that calibration, not a revision of it. NOT verified against MDN (the third page named in #2110): its interactive code examples never appear in `result.markdown` at all through this scrape path (likely cross-origin `<iframe>` content not captured by `wait_until="load"`) — genuinely untestable here, independent of this fix.
- `avoid_ads` (a `BrowserConfig` param, NOT `CrawlerRunConfig`) is deliberately NOT set. `browser_manager.py`'s `create_browser_context` registers `context.route(pattern, ...abort())` for a fixed, non-configurable list of 21 domain glob patterns (`ad_tracker_patterns`, `browser_manager.py:1302`) — Google Analytics/GTM/doubleclick/Hotjar/Mixpanel/etc. Two decisive negative findings: (1) `etracker.com`/`etracker.de` — the tracker behind this project's own recorded 61s-networkidle cost (`phase_escalation_networkidle_cost_2026-05-24.md`) — are absent from the list; confirmed live on the same BfN.de page, 0/16 requests blocked either way. (2) the glob patterns themselves (`**/google-analytics.com/**`) require a literal `/` immediately before the domain, so they match a bare `https://google-analytics.com/x` but NOT `https://www.google-analytics.com/x` — confirmed with a real Playwright `context.route()` probe (3 URLs, only the bare-domain one triggered the handler); real tracker scripts are served from subdomains almost universally, so this list is largely inert against real traffic even for domains nominally on it. Not revisited unless the list becomes configurable upstream.
- **No-focus-steal launch, as of 2026-08-27, is `_ensure_no_focus_steal` (`LSUIElement=true`) plus `ignore_default_args=["-foreground"]` — no watchdog, no third layer. Do not attempt to port the chrome lane's `open -g` mechanism here, it structurally cannot apply.** `_ensure_no_focus_steal` suppresses the OS's PASSIVE default activation-on-launch policy; `ignore_default_args=["-foreground"]` in `_build_camoufox_kwargs` drops an EXPLICIT Cocoa activation call Playwright's own Firefox launcher injects unconditionally whenever `headless=False` — playwright#41306 documents this as launch-time-only, with `ignoreDefaultArgs:['-foreground']` as the stated opt-out; the issue is also explicit that no juggler (Firefox) equivalent of Chromium's `background:true` launch option exists. A THIRD layer (`_key_window_steal_watchdog`, an in-process AXMain poll-and-reclaim loop) existed 2026-08-25 through 2026-08-27, added against a suspected window-creation-time residual (daijro/camoufox#739). REMOVED 2026-08-27: five live human-judged runs (watchdog enabled and disabled) showed zero perceived focus loss either way — AXMain=true on this LSUIElement accessory process does not imply the app was ever actually activated, so the signal the watchdog was reclaiming against was a phantom, not a real steal. See `process-docs/camoufox_lane/` for the full mechanism, external grounding (Gecko source read directly, upstream Playwright/Firefox issue search), and the live-verification writeup that overturned the original reading. If a future Playwright/Camoufox version ever exposes a process-launch hook, `open -g` becomes an option again, but nothing in the currently installed stack offers one.
- **SETTLED: `block_images` defaults `False` on BOTH Camoufox call sites — do not reintroduce a split.** The two lanes (`scrape_url_camoufox_workflow` here, `src/crawler/pipe_scraper.py`'s pipe engine) previously disagreed: the ad-hoc lane defaulted `False`, the pipe engine defaulted `True` (raw mass capture for the capture skill's Cleanup-step LLM never consumes images — camoufox's own docs frame `block_images` as bandwidth-saving, relevant at pipe volume). A REAL pipe run surfaced Camoufox's own `LeakWarning` on every URL: `"Blocking image requests has been reported to cause detection issues on major WAFs. If this is intentional, pass i_know_what_im_doing=True."` — the library's own documented anti-bot-signal risk, surfacing at exactly the volume (many URLs, one run) where a WAF is likeliest to notice a pattern. Decided by design, not measurement: stealth wins over bandwidth — this lane exists precisely for hard anti-bot targets, and images never reach the output either way (both lanes produce markdown text, not images). An explicit `block_images=True` still overrides the default for a caller who deliberately wants the bandwidth saving.
- **The `raw://` urlparse bug (see `process-docs/camoufox_lane/`) was fixed 2026-08-06 by switching to `raw:`.** `crawler.arun(url=f"raw://{html}", ...)` crashed on any HTML with a bare `[` before the first `/`; `_html_to_markdown` now uses `crawler.arun(url=f"raw:{html}", ...)` (`raw:` carries no netloc, so crawl4ai's own `urlsplit()` never attempts the parsing that raised `Invalid IPv6 URL`). The second call site that shared the bug, `src/crawler/`'s `_own_fallback_rescue`, was removed on 2026-09-09 together with the rest of the pipe_scraper fallback paths, so this lane's `_html_to_markdown` is the only `raw:` conversion left. Regression coverage in `dev/tests/test_camoufox_scrape.py` feeds a fake crawler that performs the REAL `urllib.parse.urlsplit(url)` call crawl4ai makes internally, on HTML containing a JS array literal before the first `/`.
- **REMOVED 2026-09-09: the raw-HTML-as-content fallback on markdown-conversion failure — user decision in the Phase 4 control-flow review (output by a second method is a fallback).** `_convert_camoufox_html` used to return the captured HTML as `content` with `content_is_raw_html=True` when crawl4ai's `raw:` conversion failed. No supporting observation existed for it: the only real trigger was the `raw://` urlsplit bug directly above, fixed 2026-08-07 by the switch to `raw:`, and the production log has carried 112 camoufox records since with zero `content_is_raw_html=True` occurrences. Conversion failure now surfaces as empty content (`""`) plus `markdown_conversion_error` — nothing else; the `content_is_raw_html` meta key, the `_format_camoufox_output` "Content format: RAW HTML" line, and the log-record field (`pipe_scraper_records.py::_log_pipe_camoufox_record`) are all gone. `_convert_camoufox_html`'s own outer `try/except` around `_html_to_markdown` was ALSO removed as unreachable: `_html_to_markdown` already catches its own exceptions and returns `("", error_text)`, so nothing could ever reach that outer handler — confirmed by reading `_html_to_markdown` in full, not assumed. With both removed, `_convert_camoufox_html` was a two-line function and was inlined into `_acquire_camoufox`, which stays well under the 50-LOC split threshold.
- `remove_consent_popups=True` runs `remove_consent_popups.js` on the LIVE page (click "Accept All" across ~100+ CMP-specific selectors incl. CookieYes, then CMP JS APIs, then removes ~140 known CMP container selectors, then CMP iframes, then restores body scroll) BEFORE `page.content()` captures HTML (`async_crawler_strategy.py:1044-1046`, ahead of the capture at line 1085) — unaffected by the 2026-08-05 removal of post-hoc content judgment (`strip_consent_prefix`, which acted AFTER capture based on a garbage verdict, is what was removed, not this). As of 2026-08-22 this is the SOLE consent-handling mechanism — the hand-maintained `excluded_selector=COOKIE_CONSENT_SELECTOR` (a second, hide-only layer that used to run later on the captured HTML string) was removed as redundant: `remove_consent_popups.js` verified a strict superset, including the exact CookieYes case that list existed for (see above). Real recovered content on azubiyo.de, from when both layers still coexisted: `excluded_selector` ALONE let ~3400 chars of German CMP banner text through into `raw_markdown`; `remove_consent_popups=True` removed it cleanly (confirmed via real CLI, `bytes_raw_markdown` 41583→37988) — the historical evidence that `remove_consent_popups` was already doing the real work even before `excluded_selector`'s removal. Unconditional cost on EVERY page regardless of whether a popup exists: two separate 500ms sleeps — one inside `remove_consent_popups.js` itself (`await new Promise(r => setTimeout(r, 500))`, unconditional "wait for CMP animations" step) and one in Python after the JS eval returns (`page.wait_for_timeout(500)`, `async_crawler_strategy.py:1581`) — measured end-to-end on `rfc-editor.org` (no consent layer): +0.96s wall time (1.93s→2.89s). That same ~1s extra wait also produced a 126-byte `raw_markdown` diff on the RFC page even though no CMP action ever fired there — root-caused (not just observed): the RFC page is a Nuxt.js SPA; a visually-hidden (CSS `clip-rect`, not `display:none`) accessibility `<span>` duplicating the page title finishes client-side hydrating within that extra ~1s window and gets swept into the captured HTML — reproduced identically by adding `delay_before_return_html=1.1` alone with `remove_consent_popups=False`, proving it's a generic "waited longer before capture on a still-hydrating page" artifact, not a DOM mutation from the consent-removal JS itself. One 60.32s timeout with zero content was observed once against `stepstone.de` with this switch on; NOT reproduced across 3 immediate retries (including the exact production config) — logged as an unresolved, non-reproduced anomaly, not blocking. `avoid_ads` was rejected on the same investigation pass — see above. With `remove_consent_popups=True` and the then-explicit `delay_before_return_html=2.0` (since raised to 5.0, see the module entry above), a differential CLI run on rfc-editor.org (`delay_before_return_html` 0.1 vs 2.0, both otherwise identical) showed IDENTICAL `bytes_raw_markdown` (11218 both) — the consent-popup's own forced ~1s wait already crossed this page's hydration window even at the 0.1s library default, so rfc-editor.org did not exercise `delay_before_return_html` under that config; it remains valid evidence only that raising it to 2.0 caused no regression there, not that the 2.0s wait did observable work on this specific page.
- **Three independent process-hygiene nets on the chromium lane, not one mechanism doing everything** — net 1 (`_acquire_cdp_headed`'s `finally`) is the fast common case; net 2 (`death_pipe` watchdog, spawned once the cdp port resolves) is the crash backstop, proven live (2026-08-25): a real `scrape_url_chromium` run `kill -9`'d mid-scrape had its Chrome killed AND its throwaway profile dir removed within the same second (`src/logs/cli.log`: `"parent died without tearing down its own browser — killed pids=[...], removed_dir=/var/.../scrape-url-cdp-..."`), traced back to a real 2026-08-24 incident (a `cli.py scrape_url` subprocess killed mid-flight — `cylex.de`, 10:56:44 — left a Chrome-for-Testing instance on `scrape-url-cdp-vjre0993` running 28+ hours, confirmed via the log's total silence after that one "Scraping:" line: no completion log, no `scrape_log.jsonl` record, ruling out every code path inside `try_scrape`'s own try/except, all of which log before returning). Net 3 (`_reap_orphaned_scrapes`, start of every `try_scrape`) only ever catches what net 2 could not (e.g. a pre-death_pipe-milestone leak) — it NEVER kills a live process under `TOTAL_SCRAPE_BUDGET_S` age, since parallel scrapes on distinct throwaway profiles are legitimate, not contention to resolve.
- **Camoufox (the sibling `camoufox_scrape.py` lane) needed NO death_pipe treatment — verified live, not assumed.** Two independent `kill -9`-mid-scrape trials (`cli.py scrape_url_camoufox`, killed ~1.2-1.5s into a real Wikipedia scrape, well inside the unconditional `CAMOUFOX_RENDER_WAIT_S=5.0` window) both left zero surviving `Library/Caches/camoufox/` processes, confirmed via `ps aux` (not `pgrep -f`, which produced misleading transient/shifting-PID noise unrelated to camoufox during this investigation). Consistent with `the process-docs area camoufox_lane/`'s finding that Firefox is spawned from inside Playwright's own Node.js driver, never a detached `open -g` process — that driver evidently self-terminates its child when its own connection to the (now-dead) Python process breaks, unlike the two Chrome lanes' detached `open -g` launches, which have no such built-in death-detection and needed the explicit death_pipe mechanism instead.
- **The two lanes used to request different languages from the same URL, because the Camoufox launch set no `locale` — per the vendor's own docs, an unset `locale` falls back to `en-US` regardless of the host OS.** Real evidence: `olat.server.uni-frankfurt.de`, scraped 12s apart, returned `# Willkommen in OLAT` on chromium (which sets nothing and inherits the macOS system locale for free) and `# Welcome to OLAT` on camoufox. Fixed 2026-08-27 by resolving the machine's own system locale at runtime (`_resolve_system_locale()`) and passing it as an explicit `locale` kwarg into `_build_camoufox_kwargs`, landing in the config stamp (`config.locale`, e.g. `"de-DE"`) so a later log reader can see which language a scrape asked for. **`_resolve_system_locale()` deliberately reads `defaults read -g AppleLocale`, NOT the shell's `LANG` env var or Python's `locale.getlocale()` (used only as an off-macOS/command-failure fallback) — the two can disagree.** Confirmed live on this machine: `LANG=en_US.UTF-8` (the shell/Python view) vs. `AppleLocale=de_DE` (the real macOS System Settings language, what Chromium actually renders against) — using the Python-locale value alone would have reproduced the exact mismatch this fix closes. The chromium lane was deliberately left untouched (it already gets the OS locale for free with zero config); do not add an explicit `locale`/`--lang` there without first proving live that its current OS-inherited behavior actually diverges from Camoufox's new explicit one.
- **`_resolve_system_locale` no longer swallows a failing `defaults read -g AppleLocale` (2026-09-24 Phase 4 pass).** The `locale.getlocale()`/`en-US` tail stays for the non-darwin and empty-output cases; a failed or timed-out command now propagates and surfaces as `acquisition_error="exception"` instead of silently requesting a different language than chromium.
- **The Camoufox lane was REMOVED from the ad-hoc CLI on 2026-08-27, by user decision — the module, its calibrated config, and its tests were deliberately NOT touched, so the lane can be reactivated later without redoing any of that work.** `cli.py` no longer imports `scrape_url_camoufox_workflow` or offers `scrape_url_camoufox` as a subcommand; that is the entire change (`git diff` on this removal touches only `cli.py`). The evidence behind the decision: across the whole production `scrape_log.jsonl` at the time (198 chromium records, 115 camoufox records), there is not one URL where chromium failed and camoufox succeeded — the lane's founding justification (passing anti-bot protection chromium cannot pass) has zero supporting instances in this corpus. The one double-failure (`tedi-shop.com`'s search URL) failed on BOTH lanes. The direction found was the reverse: camoufox drew 5 HTTP 403 responses against chromium's 2, and on 3 of those URLs (`frankfurt.de` twice, `anwalt.de`) chromium got a normal HTTP 200 while camoufox was blocked on the exact same target. `src/crawler/pipe_scraper.py`/`pipe_scraper_acquisition.py`'s OWN camoufox engine (a different consumer, its own `_scrape_one_camoufox` call site) is UNCHANGED and out of scope for this decision — this removal is about the ad-hoc single-URL CLI path only. To reactivate: re-add the import and the `scrape_url_camoufox` subparser/dispatch branch to `cli.py`; nothing else needs rebuilding.
- **REMOVED 2026-09-15 (M2 milestone): the printed `## Acquisition facts` block, from both `_format_scrape_output` (chromium_scrape.py) and `_format_camoufox_output` (camoufox_scrape.py).** Project owner decision, following an operational-log audit of the ad-hoc lane's own output — see `process-docs/scrape_pipeline/` for the audit and this milestone's own writeup. The facts themselves are UNCHANGED and stay fully logged to `scrape_log.jsonl`; only the print stopped. Two helper symbols existed solely to feed the removed block and were removed with it: `_ACQUISITION_ERROR_MESSAGES`/`_acquisition_error_message` (chromium_scrape.py), `_CAMOUFOX_ACQUISITION_ERROR_MESSAGES` (camoufox_scrape.py) — the raw `acquisition_error` string they turned into prose is already a logged fact on its own, with no other consumer. Both format functions dropped their now-unused `meta`/`og_published_time` parameters, trimmed to `(url, content)`. `cli.py`'s `scrape_url_chromium` help text was updated to stop promising printed output that no longer exists. `skills/websearch-web-research/SKILL.md`'s matching scrape-lane instruction line was REMOVED outright, not reworded — skill files are out of scope for edits driven from this module, full stop; see `process-docs/scrape_pipeline/` for why that line went through a reword before the removal.
- **FIXED 2026-09-15 (M0 milestone): `content_type` was read off `result.headers`, an attribute `CrawlResult` (`crawl4ai/models.py`) does not have at all — the real field is `response_headers`.** `hasattr(result, "headers")` was `False` on every single call, so the branch reading it never once executed on any real scrape; 91/91 null in the operational log was a defect, not an empty field. Confirmed against the installed crawl4ai 0.9.2 source and against a live, no-browser `CrawlResult(...)` construction (`process-docs/scrape_pipeline/` has the exact check). Fixed to read `result.response_headers.get("content-type")`; the old `.get("Content-Type")` fallback was also dropped — Playwright's own `RawHeaders.headers()` always lowercases keys (`playwright/_impl/_network.py`), so that fallback could never have matched either. Regression-guarded (`dev/tests/test_chromium_scrape.py::test_try_scrape_extracts_content_type_from_response_headers`), but the fix's effect on a REAL scrape has not yet been independently confirmed live as of this writing — see `process-docs/scrape_pipeline/` for the outstanding live check.
- **VERIFIED 2026-09-15 (M0 milestone): `og_published_time`'s null-on-null-window reading is legitimate, not a defect — do not "fix" it without a fresh live counter-example.** Traced end to end against the installed crawl4ai 0.9.2 source: `extract_metadata_using_lxml` (`crawl4ai/utils.py`) collects every `<meta property="og:...">` tag keyed by its exact declared property name, called from `LXMLWebScrapingStrategy._scrap` (`content_scraping_strategy.py`) — the DEFAULT `scraping_strategy` `CrawlerRunConfig` falls back to when none is set (`async_configs.py`), which `chromium_scrape.py::_build_run_config` never overrides — flowing unconditionally through `ScrapingResult.metadata` into the final `CrawlResult.metadata` on every non-`raw:` scrape. The mechanism is correctly wired; 91/91 null across the operational-log window means the sampled pages mostly don't declare this specific OpenGraph extension, not that the code fails to read it. See `process-docs/scrape_pipeline/` for the full trace.
- **`index_scrapes.py` (M2, 2026-09-20) resolves a URL to its sidecar by recomputing `scrape_logger._url_slug(url)` and taking the LEXICALLY-LATEST filename matching `*_<slug>.md` — deliberately, even though this can pick a tiny block-page sidecar over a real one written minutes earlier.** Real example found in the production `scrape_content/` directory while building this: `https://www.mojeek.com/search?q=python+asyncio+tutorial` has seven sidecars, mostly 364-byte "Verification required" pages; the literal latest-by-timestamp one for that exact URL IS a 364-byte block page, with an 8912-byte real-content sidecar sitting one scrape earlier. Picking by recency never inspects content — it is the only tie-break available that does not reintroduce the content judgment this project has repeatedly removed from the scrape path (see `process-docs/scrape_pipeline/`). The M2 milestone's own added requirement — the `indexed:` output line reports the written byte count — exists specifically so a small number is visible in the CLI output without anyone needing to open the file; nothing in this module acts on that number.
- **`_url_to_filename` (reused from `src.crawler.pipe_scraper_acquisition`, not reimplemented) does not match one pre-existing file in the real `websearch-reference` collection.** `api_semanticscholar_org_graph_v1_swagger.md` (source `https://api.semanticscholar.org/graph/v1/swagger.json`) has no `_json` suffix; `_url_to_filename` on that same URL produces `..._swagger_json.md` (the `.json` in the path is slugged like any other non-alphanumeric run, not dropped as a file extension) — confirmed live against the installed function, not assumed. Sampled ~40 other real files in that same collection (all `api.stackexchange.com/docs/...` URLs, none with a path extension) and every one matches `_url_to_filename`'s output exactly. Read as: that one file predates this function/milestone and was produced some other way, not evidence that today's convention drops extensions. `index_scrapes.py` follows `_url_to_filename` as written; do not add extension-stripping to chase that one outlier without a fresh, separately-motivated reason to touch the shared function (`pipe_scraper_acquisition.py`'s own batch lane would inherit any change made there).
- **REMOVED 2026-09-15 (M0 milestone): `crawl4ai_fallback_fetch_used` from the AD-HOC lane's own logged record only.** The only code path that ever sets `crawl_stats["fallback_fetch_used"] = True` (`crawl4ai/async_webcrawler.py`) is gated on `config.fallback_fetch_function` being set — this project's own `_build_run_config`/`BrowserConfig` never set it, so the field was structurally always `False` for every scrape this lane can produce, carrying zero information (the same class of dead field as the already-removed `outcome`/`EMPTY_*` sub-statuses). **`extract_crawl4ai_diagnosis` itself is UNCHANGED** — still computes and returns this key — because `src/crawler/pipe_scraper_records.py::_log_pipe_record` reads the identical shared function's output for the BATCH lane's own log; only `scrape_url_chromium_workflow`'s final `log_scrape({...})` dict stopped surfacing the key. **The batch lane carries the identical dead-field condition** (`pipe_scraper_config.py::_build_configs` also never sets `fallback_fetch_function`, confirmed) — this is a stated fact from this milestone's own investigation, not something this milestone changed; touching the batch lane's own log was explicitly out of scope. See `process-docs/scrape_pipeline/` for the source trace.
- 2026-09-24 Phase 5: `_resolve_system_locale` has no `getlocale`/`en-US` tail (empty AppleLocale or a failing `defaults` call raises); `_ensure_no_focus_steal` no longer swallows plist errors; `chromium_process._get_frontmost_app`/`_activate_app` log a warning once per process when osascript exits non-zero or returns nothing; `scrape_logger.log_scrape`/`write_sidecar` no longer catch write failures (`write_sidecar` returns `None` only for empty content).

~~~~

### Archive: src/crawler/DOCS.md

~~~~markdown
# src/crawler/

## Role

Full-site discovery + capture-pipeline scrape step for offline documentation indexing (the capture-and-index workflow). Standalone entry modules — none is a `cli.py` subcommand except `discovery.py`, which backs `cli.py`'s `discover_urls`. Touch this package to change discovery (seed-feeder-based URL enumeration) or the raw batch-scrape step; single-URL in-chat scraping lives in `src/scraper/`. Also the `seed_feeders*.py` group (robots.txt, sitemaps, a site's own frontend-framework navigation tree) and `discovery.py`, the URL-discovery entry point: it runs all three feeders over plain HTTP and merges their output with the literal seed URL — no page is ever fetched in a browser here. A prior version additionally traversed the resulting URL set with a headless `crawl4ai` browser purely to read each page's links, looking for pages no feeder had listed; that traversal was removed as a duplicate fetch of every page in the run (link-following moved to the scrape step, which already loads each page for its content — see discovery.py's own Gotchas and `process-docs/url_discovery/` for the removal's measurement and the traversal's prior history). **REMOVED 2026-09-09: `crawl_site.py` and `garbage_filter.py`** — zero callers (`crawl_site.py`'s only entry was its own `__main__` block; `garbage_filter.py`'s only caller was `crawl_site.py`), `discovery.py` (discovery) and `pipe_scraper.py` (batch scrape) already carried the whole function this package needs; user decision in the Phase 4 control-flow review.

## Public Interface

`__init__.py` is empty. Every entry module runs as `python -m src.crawler.<module>` and exposes importable entry functions:

- `scrape_urls_workflow(urls, output_dir, download_delay, concurrency_per_domain=None, engine="chromium", block_images=False, headed=False)` (pipe_scraper.py) — batch raw-markdown scrape of a URL list. `engine` is a per-RUN choice ("chromium" default/unchanged behavior, or "camoufox" — a deliberate second lane, never auto-selected); `concurrency_per_domain=None` resolves to the ENGINE'S OWN default. `headed` (M3, 2026-09-15) reaches only the chromium engine's `BrowserConfig` — see this file's Gotchas.
- `log_pipe_scrape(record)` (pipe_scrape_logger.py) — called by pipe_scraper.py.
- `robots_feeder_workflow(seed_url)`, `sitemap_feeder_workflow(seed_url)`, `navtree_feeder_workflow(seed_url)` (seed_feeders.py) — each returns a `FeederResult(urls, ok, error, source, version_keys, dropped)` (seed_feeders_scope.py). `source` is a short tag naming the extraction method ("robots", "sitemap_declared", "sitemap_conventional", "navtree_tree", "navtree_flat" — see seed_feeders_scope.py's own Gotcha) so a caller can tell an authoritative navigation-tree inventory from a flat href scrap without either being filtered here.
- `discover_urls_workflow(seed_url)` (discovery.py) — returns a `DiscoveryResult(urls, ok, wall_s, failed_feeders, dropped, error)`; `urls` is `list[DiscoveredURL(url, source)]`, `source` ∈ `{"seed", "robots", "sitemap_declared", "sitemap_conventional", "navtree_tree", "navtree_flat"}`. No page is ever fetched by this function itself (see discovery.py's own entry below).
- `host_key(host)` (seed_feeders_scope.py) — host-collapse (`www.`/apex) used internally by `scope_and_dedup`/`_dedup_key`; `require_host(seed_url)` — seed_url validation shared by all three feeders and by `discovery.py`.

## Flow

pipe_scraper: URL list in → per-domain paced raw crawl → one `.md` per URL + a `/tmp` scrape report (status/bytes/wall_ms per URL, no verdict) + a `/tmp` onward-links file (chromium engine only — every scraped page's own on-host outbound links, deduped, minus anything already in the input list) + a persistent per-URL JSONL log record (run/config-stamped, facts only). seed_feeders: seed URL in → `robots_feeder_workflow` (robots.txt Allow/Disallow paths), `sitemap_feeder_workflow` (robots-declared or conventional-path sitemaps, resolved recursively through any `<sitemapindex>` nesting), and/or `navtree_feeder_workflow` (the site's own frontend-framework navigation tree, detected + walked + unioned across every version the site exposes) → each independently host-scoped, normalized, deduped, and returned as a `FeederResult`. discovery: seed URL in → all three feeders run concurrently over plain HTTP → merged into one `{url: source}` seed set (literal `seed_url` first, then robots/sitemap/navtree, first-write-wins; a failed feeder's name+error land in `failed_feeders`, never silently treated as empty) → returned as a `DiscoveryResult`. No page is fetched by this step itself.

## Modules

### pipe_scraper.py (112 LOC) — entry point

**Purpose:** Entry point + orchestrator for the capture-pipeline scrape step — dispatches a URL list per-RUN (never per-URL, never auto-selected) to one of two acquisition engines (chromium: shared crawler; camoufox: fresh browser per URL). As of the M3 milestone (2026-09-15), a `-g`/`--headed` flag flips the chromium engine's `BrowserConfig` to visible (`headless=False`) — see `pipe_scraper_config.py`'s own entry and this file's Gotchas for what the flag does and does not defend against; structurally inert under `--engine camoufox`, which is already headed unconditionally (see Gotchas).
**Reads:** URL list from `--url-file` or caller-supplied list.
**Writes:** delegates all actual writing to sibling modules (see below); prints the console summary and writes the `/tmp` report + onward-links file itself via `pipe_scraper_report.py`.
**Called by:** capture-and-index skill Scrape step; importable as `scrape_urls_workflow()`.
**Calls out:** `crawl4ai` (AsyncWebCrawler); `src.scraper.chromium_scrape` (hash_config); `pipe_scraper_constants.py`, `pipe_scraper_config.py`, `pipe_scraper_acquisition.py`, `pipe_scraper_report.py` (all below).

### pipe_scraper_constants.py (7 LOC)

**Purpose:** Pacing/timeout constants shared by 3+ of pipe_scraper's sibling modules — full sourced rationale lives in this file's own Gotchas entries below, not restated per-constant. `EMPTY_THRESHOLD_BYTES` (the invented 100-byte "empty page" threshold) was REMOVED with the `outcome` classification it existed solely to compute — see this file's own Gotchas. `FALLBACK_FETCH_TIMEOUT_S` was REMOVED 2026-09-09 along with both curl_cffi fallback paths it timed — see `pipe_scraper_acquisition.py`'s own Gotchas.
**Called by:** `pipe_scraper.py`, `pipe_scraper_config.py`, `pipe_scraper_acquisition.py`.
**Calls out:** none.

### pipe_scraper_pacing.py (24 LOC)

**Purpose:** Per-domain Scrapy-style pacing gate (`_ensure_domain_state`, `_gate_domain`) — delay-gate + jitter + concurrency cap, engine-agnostic (used by both chromium and camoufox executors).
**Called by:** `pipe_scraper_acquisition.py`.
**Calls out:** none (stdlib only).

### pipe_scraper_config.py (48 LOC)

**Purpose:** `_build_configs(headed=False)` sets a fixed anti-bot posture for the chromium engine, optimized purely for reachability, not extraction quality (stealth + `magic=False` + `remove_consent_popups=True`); `headed` (M3, 2026-09-15) flips only `headless`, nothing else in the posture. No longer wires a `fallback_fetch_function` — the curl_cffi fallback it used to wire (path a) was REMOVED 2026-09-09, see `pipe_scraper_acquisition.py`'s own Gotchas.
**Called by:** `pipe_scraper.py` (`_scrape_all`).
**Calls out:** `crawl4ai` (BrowserConfig, CrawlerRunConfig, CacheMode, DefaultMarkdownGenerator); `pipe_scraper_constants.py`.

### pipe_scraper_acquisition.py (129 LOC)

**Purpose:** Per-URL engine executors for both acquisition engines (`_scrape_one` chromium, `_scrape_one_camoufox` camoufox). Neither executor classifies anything anymore — see this file's own Gotchas for the `outcome` removal. `_scrape_one`'s `except Exception` block records status=None/bytes=0 plus `error` (`Type: message`) in the JSONL record and the run continues; the batch itself no longer swallows executor exceptions (`return_exceptions` removed, a raising executor aborts the run) — see this file's own Gotchas for the two curl_cffi fallback paths it replaces. `_scrape_one`'s success path also collects the page's own onward links (`_extract_onward_links`/`_onward_link_identity`) off the SAME crawl4ai result it already has in hand — chromium engine only, see this file's own Gotchas.
**Reads:** URL list passed in from `pipe_scraper._scrape_all`.
**Writes:** per-URL `.md` to `--output-dir` (with source header, or camoufox-engine content — markdown, or empty on a conversion failure since the raw-HTML-as-content fallback was REMOVED 2026-09-09, see `src/scraper/DOCS.md`'s Gotchas); one JSONL record per URL via `pipe_scraper_records.py`.
**Called by:** `pipe_scraper.py` (`_scrape_all`); `pipe_scraper_report.py` imports `_onward_link_identity` directly, to normalize the run's own input URLs the identical way before excluding them from the onward-links file.
**Calls out:** `crawl4ai` (AsyncWebCrawler, CrawlerRunConfig); `src.scraper.chromium_scrape` (extract_crawl4ai_diagnosis); `src.scraper.camoufox_scrape` (try_scrape_camoufox); `src.crawler.seed_feeders_scope` (`host_key`); `pipe_scraper_pacing.py`; `pipe_scraper_records.py`; `pipe_scraper_constants.py`.

### pipe_scraper_records.py (39 LOC)

**Purpose:** Assembles and writes one JSONL record per URL via `pipe_scrape_logger.log_pipe_scrape` — a chromium-engine function and a sibling camoufox-engine function, kept separate since the two engines' own fact sets differ entirely (crawl4ai diagnosis dict vs `try_scrape_camoufox`'s own meta dict), not for any fallback-specific reason anymore — `pipe_fallback_used`/`pipe_fallback_resolved` were REMOVED 2026-09-09 along with both curl_cffi fallback paths, see `pipe_scraper_acquisition.py`'s own Gotchas. As of 2026-09-03, `_log_pipe_camoufox_record` also carries `document_status_chain` straight off `meta` (`try_scrape_camoufox`'s own fact field — see `src/scraper/DOCS.md`'s Gotchas); `_log_pipe_camoufox_record` also now carries `acquisition_error` straight off `meta` for the same reason (see this file's own Gotchas on the `outcome` removal — this fact previously fed the removed camoufox `outcome="error"` branch and would otherwise have been silently dropped by removing it). `_log_pipe_record` (chromium engine, `_scrape_one`) has no equivalent — that engine's own `status_code`/listener fix was out of scope for this milestone, see `pipe_scraper_acquisition.py`'s own entry.
**Called by:** `pipe_scraper_acquisition.py` (`_scrape_one`, `_scrape_one_camoufox`).
**Calls out:** `src.crawler.pipe_scrape_logger` (log_pipe_scrape).

### pipe_scraper_report.py (62 LOC)

**Purpose:** `/tmp/<domain>_scrape_report.md` per-URL status/bytes/wall_ms table + `/tmp/<domain>_scrape_links.txt` (the run's own onward links, see `_collect_onward_links`'s own Gotchas) + a one-line console status-code/zero-bytes/onward-link-count summary, all purely factual (no `outcome` verdict — see this file's own Gotchas), consumed only by `scrape_urls_workflow` at the end of a run.
**Called by:** `pipe_scraper.py` (`scrape_urls_workflow`).
**Calls out:** `pipe_scraper_acquisition.py` (`_onward_link_identity`).

### seed_feeders.py (60 LOC) — entry point

**Purpose:** Orchestrates all three feeders — `robots_feeder_workflow` (Allow/Disallow paths), `sitemap_feeder_workflow` (robots-declared `Sitemap:` locations, preferred, falling back to conventional paths only when robots declares none), and `navtree_feeder_workflow` (the site's own navigation tree, also passing through `FeederResult.version_keys` — see `seed_feeders_scope.py`; currently unconsumed outside this module, since `discovery.py`'s former link-graph traversal was its only external consumer and has been removed). All three validate `seed_url`, fetch, scope+dedup the result, tag `FeederResult.source`, and convert an unexpected orchestration failure (e.g. an unparseable `seed_url`) into `FeederResult(ok=False, error=...)` rather than raising — a normal per-fetch outcome (missing robots.txt, a 404 sitemap, no framework payload detected) stays `ok=True` with a possibly-empty `urls` list, never `ok=False`.
**Reads:** live HTTP (robots.txt, sitemap, and navigation-tree-bearing HTML pages) via `httpx.AsyncClient`, one fresh client per workflow call.
**Writes:** nothing — returns a `FeederResult`, no disk/log side effects.
**Called by:** `discovery.py` (`_run_feeders`), the only caller so far.
**Calls out:** `httpx`; `seed_feeders_constants.py`, `seed_feeders_scope.py`, `seed_feeders_robots.py`, `seed_feeders_sitemap.py`, `seed_feeders_navtree.py` (all below).

### seed_feeders_constants.py (8 LOC)

**Purpose:** Shared HTTP timeout, User-Agent, conventional sitemap fallback paths, sub-sitemap and nav-tree-version fetch concurrency caps.
**Called by:** `seed_feeders_robots.py`, `seed_feeders_sitemap.py`, `seed_feeders_navtree.py`, `seed_feeders.py`.
**Calls out:** none.

### seed_feeders_scope.py (71 LOC)

**Purpose:** `FeederResult` dataclass (including `version_keys`, populated only by the navtree feeder, `None` for a version-less site — see `seed_feeders_navtree.py`; surfaced originally for `discovery.py`'s former traversal to recognize an explicit-version duplicate of an already-known canonical page, now unconsumed since that traversal was removed); `normalize_url` (the merge-vs-keep-distinct boundary — see Gotchas); `scope_and_dedup` (host-only scope, `www.`/apex collapsed for comparison only, order-preserving dedup, malformed URLs dropped not raised); `host_key` — promoted from a `seed_feeders.py`-private helper, used internally by `scope_and_dedup`/`_dedup_key`; `require_host` — seed_url validation, shared by all three feeders and by `discovery.py`.
**Called by:** `seed_feeders.py` (all three workflows), `discovery.py` (`require_host` for seed_url validation).
**Calls out:** none (stdlib only).

### seed_feeders_robots.py (40 LOC)

**Purpose:** `fetch_robots_txt` (GET, `None` on any failure — normal outcome); `parse_robots_directives` (Allow/Disallow path values AND `Sitemap:` URLs, every `User-agent:` block collected together, not scoped to one).
**Called by:** `seed_feeders.py` (both workflows).
**Calls out:** `httpx`.

### seed_feeders_sitemap.py (69 LOC)

**Purpose:** `fetch_sitemap` (GET, gunzips `.gz`, `None` only on a non-200 status; network errors, corrupt gzip and non-XML bodies propagate to the feeder workflow, which returns `ok=False` with `error`); `parse_sitemap_xml` (namespace-agnostic `ElementTree`, distinguishes `<sitemapindex>` from `<urlset>`); `resolve_sitemap_urls` (recursive, bounded concurrency via a shared `asyncio.Semaphore`, cycle-guarded via a shared visited set, arbitrary nesting depth).
**Called by:** `seed_feeders.py` (`sitemap_feeder_workflow`).
**Calls out:** `httpx`.

### seed_feeders_navtree.py (264 LOC)

**Purpose:** `extract_payloads` (detection dispatch, extensible list of shape-extractors — as of 2026-09-24 the Next.js Pages Router `__NEXT_DATA__` blob and the App Router RSC `self.__next_f.push` stream); `find_navigation_tree` (tier 1: the largest dict subtree structurally shaped like a nav tree, found anywhere in the payload by shape, never a hardcoded key path; tier 2 fallback: a flat href/url scan, filtered, when tier 1 finds nothing); `resolve_navigation_tree` (orchestrates: fetch seed → detect → walk → find + fetch every OTHER version the same payload declares → canonicalize each version's URLs back to the default version's shape → union). `navtree_feeder_workflow` (seed_feeders.py) wraps this with the shared `FeederResult`/scope/dedup contract, tagging `source` "navtree_tree" or "navtree_flat" from whichever tier produced the DEFAULT tree, and passing through `version_keys`. `canonicalize_version_url` is PUBLIC (not `_`-prefixed); it was promoted for `discovery.py`'s former link-graph traversal to reuse for version-duplicate recognition (see that module's own Gotchas for the removal) — that traversal is gone, and this function is now only used internally by this module's own version union.
**Reads:** live HTTP (the seed page + each detected version's own root page) via `httpx.AsyncClient`, passed in by the caller (no client of its own).
**Writes:** nothing — pure fetch + parse, returns `(urls, tier, version_keys)`.
**Called by:** `seed_feeders.py` (`navtree_feeder_workflow`).
**Calls out:** `httpx`; `seed_feeders_constants.py`.

### discovery.py (70 LOC) — entry point

**Purpose:** The URL-discovery entry point: `discover_urls_workflow` runs all three feeders concurrently against `seed_url` over plain HTTP, then merges their output plus the literal `seed_url` into one `{url: source}` seed set (a failed feeder's name+error lands in `failed_feeders`, never silently treated as an empty result — see Gotchas). No page is ever fetched in a browser — a prior version of this module additionally traversed the resulting URL set with `crawl4ai`'s `BFSDeepCrawlStrategy` to read each page's links, looking for pages no feeder had listed; that traversal was removed as a duplicate fetch of every page in the run (measured: the feeders returned 3571 URLs in ~2s on a real site, the traversal over those same 3571 URLs was still running after 12 minutes — see Gotchas and `process-docs/url_discovery/` for the removal and the traversal's prior history). Every result URL is tagged only with what produced it ("seed" or a feeder's own `source`) — there is no fetch-confirmation or version-duplicate-canonicalization concept left, since both existed solely to make the removed traversal's own findings legible.
**Reads:** feeder output via `seed_feeders.py` (each feeder does its own live HTTP fetch; this module fetches nothing itself).
**Writes:** nothing — returns a `DiscoveryResult`, no disk/log side effects.
**Called by:** `cli.py`'s `discover_urls` subcommand (`discover_urls_workflow(seed_url)`).
**Calls out:** `seed_feeders.py` (all three workflows); `seed_feeders_scope.py` (`normalize_url`, `require_host`).

### pipe_scrape_logger.py (19 LOC)

**Purpose:** Per-URL JSONL log writer for pipe_scraper — one record per URL (`run_id`-grouped, `ts`=request start), shared by both acquisition engines (`"engine"` field discriminates), separate schema/file from `src/logs/scrape_log.jsonl`.
**Reads:** `WEBSEARCH_PIPE_SCRAPE_LOG_PATH` env var (fallback `src/logs/pipe_scrape_log.jsonl`).
**Writes:** `src/logs/pipe_scrape_log.jsonl` (one line per URL). Gitignored.
**Called by:** `pipe_scraper_records.py` (`_log_pipe_record` for the chromium engine, `_log_pipe_camoufox_record` for the camoufox engine).
**Calls out:** `src/log_janitor.py` (maybe_prune_jsonl).

## Gotchas

- pipe_scraper pacing is a Scrapy per-domain gate: `lastseen` dict + `asyncio.Lock` (serializes starts) + `asyncio.Semaphore(8)` cap, `DOWNLOAD_DELAY=1.0s`, jitter `uniform(0.5×,1.5×)` → ~1 req/s per domain. No batch loop, no inter-batch sleep, no retry/backoff.
- pipe_scraper's per-URL `ts` MUST be stamped after `_gate_domain`, not before the domain semaphore — `asyncio.gather` starts every `_scrape_one` coroutine at once, so a pre-gate `ts` collapses to one near-identical value across an entire run's records regardless of real pacing (a real bug, caught and fixed; regression-guarded by `dev/tests/test_pipe_scraper.py::test_scrape_one_ts_reflects_request_start_not_queue_time`).
- pipe_scraper's `_build_configs()` (`pipe_scraper_config.py`) anti-bot posture is ONE fixed calibration derived from external sources (crawl4ai/playwright-stealth source + issue trackers), not a set of tunable knobs — do not add CLI flags for it, do not tune it against sampled domains (a sweep's result holds for the domains sampled, not the next unknown one; `src/logs/pipe_scrape_log.jsonl` is where real weak spots surface over time). `magic=False` in particular is a deliberate rejection, not an unset default — see the `pipe_scraper_hardening` area for the full reasoning before turning it on.
- `_build_configs()`'s `enable_stealth=True` reachability depends on pipe_scraper passing NO custom `crawler_strategy`/adapter to `AsyncWebCrawler` — crawl4ai's `browser_manager.py` only builds the `StealthAdapter` when `enable_stealth and not use_undetected`, and `use_undetected` resolves from `isinstance(self.adapter, UndetectedAdapter)`. If this module ever starts passing a custom adapter, re-verify `use_undetected` still resolves False (`dev/tests/test_pipe_scraper.py::test_build_configs_produces_live_stealth_adapter` is the wiring test to re-run).
- `pipe_scraper.py`'s `--block-images`/`--no-block-images` share `dest='block_images'` — argparse resolves a shared dest's default from the FIRST `add_argument` call added that lacks a namespace value yet, so `--block-images`'s own `default=False` (not `--no-block-images`'s) governs omission. Do not reorder the two `add_argument` calls without re-verifying which default wins.
- `_build_configs()` takes no parameters on purpose — the browser/run config does not depend on `download_delay`/`concurrency_per_domain`. Only `_extract_pipe_config_stamp` needs those (to log the pacing values actually in effect). Do not thread pacing params back into `_build_configs()`'s signature — that was tried and reverted (signature asserted a dependency that did not exist).
- **REMOVED 2026-09-09: both curl_cffi fallback paths — user decision in the Phase 4 control-flow review (output by a second method is a fallback, and a fallback is eliminated).** Path (a) (crawl4ai's own `fallback_fetch_function`, wired to `_fallback_fetch`) and path (b) (`_own_fallback_rescue`, called from `_scrape_one`'s `except Exception` block) both re-fetched the URL a SECOND way (via `curl_cffi`) when the browser failed. Removed along with `_curl_cffi_get`, `_fallback_fetch`, `_own_fallback_rescue`, and `FALLBACK_FETCH_TIMEOUT_S` (`pipe_scraper_constants.py`); `_build_configs` no longer sets `fallback_fetch_function`; the `fallback_armed` config-stamp key and the `pipe_fallback_used`/`pipe_fallback_resolved` log fields are gone with the mechanism they described. `_scrape_one`'s `except Exception` block is now a tripwire: it logs `status=None, bytes=0` (nothing invented in the record shape — `diagnosis={}` and `landed_url` stay at their existing defaults) and returns the same dict shape as the success path minus `'links'`, and the run continues to the next URL — nothing is fetched by a second method. `_landed_url_from_result`'s `crawl4ai_fallback_fetch_used` short-circuit is gone with path (a) — it was a one-liner once the short-circuit was removed, so it was inlined at its one call site (`landed_url = getattr(result, "redirected_url", None)`) rather than kept as a wrapper. `crawl4ai_fallback_fetch_used` itself STAYS in the log — it is crawl4ai's OWN diagnosis field read off `crawl_stats`, an observation of the library, not of our own removed fallback. The bullets immediately below that described paths (a)/(b) in more detail are kept as short pointers back to this one, not deleted outright.
- **REMOVED 2026-09-09 — see the fallback-removal Gotcha above.** This bullet used to justify `max_retries` staying at 0 as protecting path (a)'s rescue opportunity from a wasted second browser attempt. `max_retries` still stays at 0 (crawl4ai's untouched library default, never set by this module) — just no longer for a fallback-protection reason.
- **As of 2026-09-03, `_scrape_one_camoufox`'s logged `http_status` reads a CORRECTED `meta['status_code']`** (`try_scrape_camoufox`'s own last-main-frame-document-response fix, see `src/scraper/DOCS.md`'s Gotchas) — no code changed in `_scrape_one_camoufox` itself, it already only ever read `meta['status_code']` and passed it straight through. A self-resolving challenge page that used to log a stale 4xx `goto` status now logs the real 200 that eventually loaded; this is the INTENDED effect, not a side effect to guard against. The chromium engine's `_scrape_one` has no equivalent fix (out of scope, still reads crawl4ai's own possibly-stale `result.status_code`). (Historical note: before the `outcome` removal below, this correction was described as changing a computed `http_error`→`ok` mapping — the mapping is gone, only the underlying `http_status` fact and this note about it remain.)
- **REMOVED 2026-09-09 — see the fallback-removal Gotcha above.** This bullet documented that a crawl4ai-own-fallback (path a) success ALWAYS logged `http_status=200` regardless of what actually happened, while pipe_scraper's own path (b) did not repeat that flaw (`http_status=200` there was only ever set on a genuine curl_cffi 200). Neither path exists anymore, so neither behavior is left to trust or distrust.
- **REMOVED 2026-09-09 — see the fallback-removal Gotcha above.** This bullet documented that `landed_url` was hardcoded null on path (a) (crawl4ai always reported `redirected_url=url`, never the real followed URL) but carried a genuine `response.url` on path (b) (via `_own_fallback_rescue`'s direct `_curl_cffi_get` call). Both routes are gone; `landed_url` on a normal success now reads `result.redirected_url` unconditionally, no route-dependent special-casing left.
- **No `same_target` verdict exists in this module anymore, and none is stored in the log.** `is_same_target` (`src/scraper/chromium_scrape.py`) and the `same_target` field it fed both existed for a period and were REMOVED — a deliberate reversal after review, not a partial rollback (see `src/scraper/DOCS.md`'s own Gotcha on the same reversal for the full reasoning: the log is read only by an agent, after the fact, with `url`/`landed_url`/`crawl4ai_fallback_fetch_used` already in the same record — everything needed to derive a verdict is already there, so storing one too was a re-derivable conclusion kept as data; `pipe_fallback_used` was part of that same record at the time this reasoning was written but was itself REMOVED 2026-09-09 along with both curl_cffi fallback paths — see this file's own Gotcha above). The comparison rule moved to the calling agent (`skills/websearch-web-research/SKILL.md`, updated separately outside this module) rather than disappearing. Do not reintroduce `is_same_target`/`same_target` here on the assumption it was simply forgotten.
- **`CAMOUFOX_CONCURRENCY_PER_DOMAIN=1` is NOT the same kind of number as `CONCURRENCY_PER_DOMAIN=8` — do not "fix" the apparent inconsistency by raising it to match.** The chromium default was measured/validated (`the process-docs area pipe_scraper_hardening/`, 0 crashes at 8) for N requests sharing ONE already-launched browser. The camoufox engine launches a FRESH, real, headed Firefox process per in-flight request — concurrency=8 there would mean up to 8 simultaneous heavy processes per domain, unmeasured, against field evidence that Camoufox's memory footprint is already heavier per-instance than patchright/undetected-chromium. 1 is the conservative default absent evidence, not a final number — raise it only with the same kind of measurement that earned chromium's 8, never by assumption.
- **The pipe-engine log's `"config"` shape is NOT comparable across `"engine"` values, ever — a config_hash collision across engines means nothing.** Chromium's `config` is the FULL pacing/stealth surface, computed once for the whole run off the real shared browser objects; camoufox's own `config` (headless/os/block_images/timeout/executable_path/total_budget_s) is computed PER URL, off that call's own `try_scrape_camoufox` meta, and has no pacing/stealth keys at all (there is no shared browser to read them off). Grouping/comparing records by `config_hash` only makes sense WITHIN one `"engine"` value.
- **REMOVED 2026-09-09 — see the fallback-removal Gotcha above.** This bullet recorded an open, never-chased-further question about how often path (b) (`_own_fallback_rescue`) was even reachable in this crawl4ai version, based on a milestone-4 verification attempt that failed to trigger it via a controlled `net::ERR_ABORTED` test (crawl4ai's own `_crawl_web` wrapper caught the browser exception internally before it ever reached `_scrape_one`'s `except Exception:` block). Moot now — path (b) no longer exists. (Historical detail preserved: `the process-docs area pipe_scraper_hardening/` reached path (b) originally via a different failure shape — a connection that never responds, forcing a timeout.)
- **The `outcome` field (`"ok"`/`"empty"`/`"http_error"`/`"waf_429"`/`"error"`) was REMOVED from every pipe_scraper return dict, the JSONL log schema, the `/tmp` report, and the console summary — this module now reports facts and decides nothing.** Measured motivation: 13 real pages came back at 9738 bytes of pure navigation chrome plus 51 lines of `Loading...`, were classified `outcome="ok"` on no evidence beyond a byte count, and went into the RAG index that way. Branch-by-branch disposition, per the same fact-vs-verdict method `the process-docs area search_pipeline/` used: `waf_429` (`status==429`) and `http_error` (`status>=400`) in both `_scrape_one` and `_scrape_one_camoufox`, plus `empty`/`ok` (`byte_count` vs. the invented `EMPTY_THRESHOLD_BYTES=100`) in `_scrape_one`/`_scrape_one_camoufox`/`_own_fallback_rescue` — all SIX of these were pure re-derivations of facts the record already carried (`http_status`, `bytes`), so the branches were deleted outright, no new field needed. The camoufox engine's `outcome="error"` (`meta.get("acquisition_error")` truthy) was DIFFERENT: `try_scrape_camoufox`'s own `acquisition_error` fact (`"budget_exhausted"`/`"browser_missing"`/`"exception"`) existed on `meta` already but was never logged, only collapsed into the string `"error"` — that fact was added to `_log_pipe_camoufox_record`'s JSONL output FIRST (`pipe_scraper_records.py`), then the branch was deleted, per the "add the fact, then remove the verdict" order. `EMPTY_THRESHOLD_BYTES` (`pipe_scraper_constants.py`) and its `"empty_threshold_bytes"` config-stamp key (`pipe_scraper_config.py`) were removed with the branches that were its only reason to exist. The console summary (`_print_summary`, `pipe_scraper_report.py`) no longer says "N ok, M errors" — it prints a raw HTTP-status histogram (a `no_status` bucket for a URL our own code never got a status for at all) plus a zero-byte count, both plain tallies of already-recorded facts. The `/tmp` report's `outcome` column is simply gone, `status`/`bytes`/`wall_ms`/`url` unchanged. `_own_fallback_rescue`'s return tuple dropped its leading `outcome` element (now `(status, byte_count, fb_used, fb_resolved, landed_url)`) — its two failure branches already returned `status=None`/`byte_count=0`, so nothing new was needed there either (`_own_fallback_rescue` itself, along with path (a), was REMOVED 2026-09-09 — see this file's own Gotcha above; this sentence is preserved as history of the `outcome` removal, not a description of current code). Not touched: `src/scraper/chromium_scrape.py`/`camoufox_scrape.py`'s own `outcome` field — a separate, deliberately deferred ad-hoc-path task.
- **`pipe_scraper` now collects every scraped page's own onward links, at zero extra fetch cost, into `/tmp/<domain>_scrape_links.txt` — the job a browser-driven link traversal used to do in `discovery.py` by re-fetching every page a SECOND time, before that traversal was removed entirely (`the process-docs area url_discovery/`).** `_scrape_one` reads `result.links` off the SAME crawl4ai result it already produced for the page's markdown — chromium engine only; `try_scrape_camoufox` returns content+metadata and no link set at all, so `_scrape_one_camoufox`'s return dict never carries a `'links'` key (absent, not an empty list — a caller checking `'links' in record` cannot mistake a camoufox run for a chromium run that looked and found nothing; `_collect_onward_links` returns `None`, not `[]`, for the same reason, and `_print_summary`/`_write_onward_links_file` both treat `None` as "not collected," never printing/writing a bare zero). `_extract_onward_links` unions crawl4ai's own `"internal"`/`"external"` link buckets rather than trusting either alone — that split is crawl4ai's own classification, already distrusted for scope once in this project (the now-removed traversal's `_ExactHostFilter` existed for the identical reason) — and applies this project's own `host_key` comparison (`seed_feeders_scope.py`) against the PAGE's own host (`urlparse(url).hostname`, not the pacing gate's `netloc`-with-port `domain` variable — the two are NOT interchangeable for this comparison, since `host_key` does not strip a port).
- **A link is normalized by `_onward_link_identity` to scheme/host-lowercased, query-string-and-fragment-DROPPED — deliberately NOT `seed_feeders_scope.normalize_url`, which keeps the query on purpose.** That module's own worst case for merging two URLs is a seed that is never fetched at all, so it protects the query string as a possibly-distinct resource. This file's worst case inverts: it is a supplementary, non-authoritative candidate list for a follow-up scrape round, never the sole record of a page's existence, and a real hand-checked 50-page `platform.claude.com` run measured exactly where reusing that reasoning would have failed — 224 distinct on-host links, 174 not in the 50-page input, 57 of those genuinely unknown against the domain's full 3571-URL discovery list, and 54 of those 57 worthless: 50 were the SAME `/login` page (one per scraped source page, each carrying a different `returnTo=` query string a plain string-dedup could not collapse), 3 were the SAME `/playground` page (differing only by a `model=` query), 1 was a `.gif`. Query-stripping collapses the 50 login variants and 3 playground variants to ONE entry each; `_NON_PAGE_EXTENSIONS` (a small evidence-based blocklist: image/style/script/font/document/media extensions) drops the `.gif` outright. Re-run against the SAME 50-page input after this milestone: 122 onward links collected, only 4 not already in the full discovery list — 3 real content pages (`prompt-engineering`, `release-notes/api`, `release-notes/system-prompts`) and exactly one collapsed `/login` (the honest, deduplicated survivor of the 50-variant noise source; `/playground`'s own collapsed form also appears in the 122 but was already a known discovery-list URL, so it drops out of that specific "not in discovery" count). Zero of the 54 original noisy URL strings survive verbatim — none of their exact query-bearing forms exist anymore, by construction.
- **`_collect_onward_links` excludes a discovered link only against the RUN'S OWN input `urls` list, never against any broader "already known" set — `discovery.py`'s full discovery list is not, and cannot be, passed into `pipe_scraper` at all.** The input-list exclusion is real and cheap (no extra fetch, the list is already in memory); a link that happens to already be on `discovery.py`'s own full list but NOT in this particular scrape batch's input still appears in the onward-links file (as `/playground` did in the verification run above) — this is correct, not a bug: `pipe_scraper` has no way to know that fact, and inventing a dependency on the discovery output just to suppress it was judged out of scope. Cross-referencing the onward-links file against a broader known-URL set, if wanted, is the calling agent's own job, done externally (exactly how the verification numbers above were produced: a plain `comm -23` between the two files).
- **REMOVED 2026-09-09 — see the fallback-removal Gotcha above.** This bullet documented that path (b)'s successful `raw:` conversion did not get its own onward links extracted, deliberately out of scope at the time. Moot now — `_own_fallback_rescue` no longer exists, and `_scrape_one`'s except block fetches nothing by a second method at all.
- **`seed_feeders_scope.normalize_url`'s merge boundary is deliberate, not arbitrary — a seed feeder's worst case for merging two URLs is a seed that is never fetched at all, so a differing query string (`?page=2`) or a real `/@user`/`/package/@scope/name` path segment can be a genuinely different document and must stay distinct.** The merge boundary this module actually uses: scheme/host casing, the scheme's own default port, an empty path vs `/`, and the fragment are collapsed (pure protocol-level identity — literally the same request or the same client-only annotation, not a heuristic); `www.` vs apex is collapsed for SCOPE/DEDUP COMPARISON only, via a separate `_host_key` helper — the output URL text keeps whatever host spelling the source actually declared, never rewritten, since rewriting risks producing a form the site doesn't actually serve. Query strings, `http` vs `https`, and any non-root trailing slash are all kept DISTINCT — none of the three is a protocol-level identity (unlike the merged set), only a common convention that does not hold universally, and this feeder's whole purpose is maximum coverage. See `the process-docs area scrape_pipeline/` for the same reasoning applied to a different (post-fetch, comparison-only) primitive, and why its own `www.`/`http`-vs-`https`/trailing-slash merges do not transfer here unmodified.
- **`sitemap_feeder_workflow` and `robots_feeder_workflow` each fetch `robots.txt` independently — calling both against the same seed fetches it twice.** Deliberate simplicity for this milestone (the two feeders are meant to be independently callable, and neither is wired into a shared caller yet); revisit if/when a frontier-wiring caller wants both from one seed.
- **Not using crawl4ai's `AsyncUrlSeeder`** (`venv/lib/python3.14/site-packages/crawl4ai/async_url_seeder.py`, `source="sitemap"`), on four grounds verified by reading its source: (1) `_from_sitemaps` tries the conventional paths BEFORE falling back to `robots.txt`'s `Sitemap:` lines — the opposite priority this milestone requires; (2) it has no Allow/Disallow extraction at all; (3) it writes an on-disk cache under `~/.crawl4ai/` as a side effect, unwanted for a stateless feeder; (4) its `urls()` returns a bare list with no empty-vs-failed signal, and its producer/worker/queue/BM25 machinery is far harder to unit-test with local fixtures than plain functions plus a mocked `httpx.AsyncClient` (this project's own established pattern). `filter_nonsense_urls` is therefore moot here, but its `True` default would have been rejected anyway even if the seeder had been used — it drops API paths and media files, wrong for a feeder whose stated goal is maximum coverage; content-type filtering is a downstream concern.
- **`seed_feeders_scope.py` uses `urlsplit`/`urlunsplit`, never `urlparse`/`urlunparse`, and this is deliberate, not a stylistic choice.** `urlparse`'s legacy 6-tuple splits a trailing `;params` path segment (e.g. `/a/b;jsessionid=ABC`) out of `path` into its own `.params` field — rebuilding a URL from `scheme`/`netloc`/`path`/`query` alone (as `normalize_url` and `_dedup_key` both do) then silently drops that segment with no decision ever made about it, exactly the kind of silent merge this module's own boundary table argues against (a `;params` segment is rare in practice but CAN denote a different resource, e.g. legacy Java session-tracking). `urlsplit` never performs this split — `;params` stays embedded in `.path` and survives the rebuild untouched — while still exposing the same `.hostname`/`.port` convenience properties `normalize_url` needs. Caught in post-commit review; regression risk if a future edit reintroduces `urlparse` here for path/query reconstruction.
- **`fetch_robots_txt`/`fetch_sitemap` return `None` on a non-200 response — this is a real return value, not a bug (a network error is not swallowed since the 2026-09-24 Phase 4 pass: it propagates, and so do a corrupt `.gz`, unparseable sitemap XML and malformed `__NEXT_DATA__` JSON; the feeder workflow turns each into `ok=False` with `error`, and one failing sub-sitemap therefore fails the whole sitemap feeder), and the type annotations (`str | None`/`bytes | None`) say so explicitly.** A bare `-> str`/`-> bytes` annotation was caught in post-commit review as describing only the success path while the function's own documented contract (a missing/404 resource is a normal outcome) requires the `None` path just as often. `_child_text` (`seed_feeders_sitemap.py`) and `FeederResult.error`/`resolve_sitemap_urls`'s `seen` parameter carry the same `X | None` treatment for the identical reason.
- **`FeederResult.source` exists because a caller cannot otherwise tell an authoritative result from a scrap.** `navtree_feeder_workflow`'s tier 1 (a real recursive tree, found by structural shape) and tier 2 (a flat href/url scan with no tree evidence behind it) can both return a plausible-looking non-empty URL list from the SAME function — live proof: tier 1 on `ui.shadcn.com/docs` returned 248 URLs from a real navigation tree, tier 2 on `nextjs.org/docs` returned 21 stray hrefs from a site with hundreds of real doc pages. Deliberately NOT expressed as filtering or a quality threshold (`urls` always carries everything either tier found, unfiltered) — `source` is a provenance label only, added as a field on the SHARED `FeederResult` contract (not a navtree-only bolt-on): `robots_feeder_workflow`/`sitemap_feeder_workflow` now also tag `source="robots"`/`"sitemap"` for the same reason, even though neither has a tier distinction of its own. A future frontier-wiring or coverage-check milestone decides what to DO with `"navtree_flat"` (trust it, weight it lower, re-verify it) — that decision is explicitly not made here.
- **The navtree tree-finder rejects a rendered React element as a false-positive tree by checking that "children" is a list of DICTS, not a list of LISTS.** A React Server Components element serializes as `["$", tagName, key, propsDict]` — a 4-item LIST — so a `<button>` with an icon + text renders as `{"href": "/prev", "children": [["$","svg",...], ["$","span",...]]}`, structurally matching "has href + a children list" but NOT "children is a list of dicts". Verified live against `ui.shadcn.com`'s real pagination button before this rule was added — an earlier looser version of the shape check (`isinstance(value, list)` alone) matched 11 rendered-DOM false positives on that exact page. `_child_key_of`'s `all(isinstance(c, dict) for c in value)` check is what makes the difference, and is not incidental — do not loosen it back to a bare list check.
- **`_find_version_list`'s "any key containing `version`, value a dict of 2+ dicts" heuristic is verified against exactly one real site (`docs.github.com`'s `allVersions`).** Labeled here the same way the original 2026-05-31 GitHub experiment (`the process-docs area agentic_discovery/`) labeled its own analogous move: "partially generic — heuristic, needs adaptation", not proven to transfer. The instruction that authorized shipping it anyway: a false version candidate is validated away for free by the fetch that follows — `_build_version_urls` constructing a wrong URL just means `_fetch_html` gets a 404/unexpected page and that "version" contributes nothing (see `_resolve_one_version`), never a crash or bad data. The failure mode is benign by construction, which is why this heuristic did not need the same multi-site verification the tree-shape/detection logic got.
- **A version-URL's language prefix MUST be derived from the version-list-site's OWN "path without language" field BEFORE that field's version segment is stripped, not after — a real bug, caught by a synthetic test, not by the live `docs.github.com` run.** `currentPathWithoutLanguage` is version-INCLUSIVE when the current page is already a non-default version (e.g. `/enterprise-cloud@latest/rest` on the GHEC page) and only happens to look version-free on the default page (`/rest`, since the default has no URL prefix at all). Deriving `lang_prefix` from the already-version-stripped `content_path` instead of the original field produced `/de/v2` instead of `/de` for a non-default seed — invisible against `docs.github.com/de/rest` itself (default page, no version segment to strip, so the bug's two code paths coincidentally produced the same prefix) but caught immediately by `test_build_version_urls_strips_version_prefix_when_seed_is_a_non_default_version`, which is exactly why that scenario has a dedicated synthetic test and not just live-run coverage.
- **A `seed_url` that cannot be fetched at all is `ok=False`, never an empty `"navtree_flat"` result — deliberately asymmetric with every other fetch failure in this module.** A version root's own fetch failure (`_resolve_one_version`), a missing robots.txt, and a 404 sitemap are ALL normal outcomes elsewhere in `seed_feeders*.py`, because the resource being fetched might legitimately not exist. The seed is different: it is not an optional resource, it is the target of the whole run, and its failure means the feeder never got to look at anything — indistinguishable from "genuinely no navigation tree" would be a real information loss for a caller. `resolve_navigation_tree` raises `RuntimeError` when `_fetch_html(client, seed_url)` returns `None`, caught by `navtree_feeder_workflow`'s existing `except Exception` — the same path an invalid `seed_url` already used, since both are preconditions for the feeder to do any work at all, not something the feeder discovered by doing the work. Verified live: `navtree_feeder_workflow` against a real, definitely-404 URL on a real reachable host (`docs.github.com/this-page-does-not-exist-...`) returns `ok=False, error="could not fetch seed_url: ..."`, not `ok=True, urls=[]`.
- **Return-type/parameter annotation audit, post-review: every function/parameter in `seed_feeders_navtree.py` that can carry `None` is now typed `X | None`.** `_child_key_of`, `_find_version_list`, `_find_current_version`, `_find_path_without_language`, `_fetch_html`, and `_find_tree_candidates`'s `out` parameter were all found mismatched (annotated as always returning/accepting the bare type, but `None` is a real, reachable value for each) — the same defect class M1 fixed on `fetch_robots_txt`/`fetch_sitemap`. `_build_version_urls`'s three parameters were fixed to match, since all three are fed directly from the now-correctly-annotated finder functions above.
- **`discovery.py`'s browser-driven link-graph traversal (the `BFSDeepCrawlStrategy`/`_ExactHostFilter`/resume-state/pacing machinery this section used to document at length) was REMOVED, not tuned further.** It existed to find pages no feeder had listed, by re-fetching every already-discovered URL in a real headless browser purely to read its links — a duplicate fetch of every page in the run. Measured on a real site: the three feeders returned 3571 URLs in ~2s; the traversal over those same 3571 URLs was still running after 12 minutes, projected well over an hour. Link-following now belongs to the scrape step, which already loads each page for its content anyway. Everything that existed solely to make that traversal's own findings legible — `DEFAULT_MAX_DEPTH`/`MIN_MAX_PAGES`/`MAX_PAGES_PER_SEED`/`TRAVERSAL_MEAN_DELAY_S`/`TRAVERSAL_MAX_RANGE_S`/`TRAVERSAL_CONCURRENCY`, `DiscoveryResult.stop_reason`/`pages_fetched`/`pages_failed`, `DiscoveredURL.fetched`/`canonical_url`, `_ExactHostFilter`, `_build_resume_state`/`_validate_resume_state`/`_traverse`/`_determine_stop_reason`/`_resolve_canonical_alias`/`_merge_results`, and `discover_urls_workflow`'s `max_depth`/`max_pages` parameters and `cli.py`'s `--max-pages` flag — went with it. `seed_feeders_navtree.py`'s `canonicalize_version_url` and `FeederResult.version_keys` were this traversal's only external consumer; both remain on the feeder contract (the navtree feeder still uses `canonicalize_version_url` internally for its own version union) but neither is consumed by anything outside `seed_feeders_navtree.py` anymore. The full prior history (frontier wiring, fetch-success/frontier-visibility, pacing measurement, the version-duplicate-recognition gap and its closure) is preserved in `process-docs/url_discovery/` — read there for context, not here, since none of it still describes current code.
- **`-g`/`--headed` (M3, 2026-09-15) flips only `BrowserConfig.headless` — it carries NO focus-defense mechanism, unlike the ad-hoc lane (`src/scraper/chromium_process.py`'s name-keyed `_focus_steal_watchdog`) or the search lane (`src/search/browser.py`'s PID-keyed watchdog).** A live-measured focus steal WAS observed on a real run: the headed browser (`"Google Chrome for Testing"`, crawl4ai's own `ManagedBrowser`, plain `playwright` — confirmed by reading `browser_manager.py` directly, not the `patchright` bundle the ad-hoc lane resolves) took focus once, at launch, for roughly 2 seconds, then released on its own with nothing reclaiming it — longer than either other lane's own sub-second, watchdog-bounded flicker. See `process-docs/pipe_scraper_hardening/` for the measurement (sample size, timing, and why a name-keyed watchdog is now a confirmed-workable follow-up, not attempted in this milestone).
- **`-g` is structurally inert under `--engine camoufox`.** That engine already launches headed, unconditionally, via the ad-hoc lane's own `try_scrape_camoufox` (`src/scraper/camoufox_scrape.py`), with its own no-focus-steal mechanism already in place (`_ensure_no_focus_steal`/`LSUIElement`). `-g`'s only effect is on `pipe_scraper_config._build_configs`, which the camoufox code path never calls — passing `-g` alongside `--engine camoufox` changes nothing, silently.
- 2026-09-24 Phase 5: `log_pipe_scrape` no longer catches write failures (a broken log path raises).

## Gotchas (2026-09-24 Phase 5 pass)

- Non-200 handling in the feeders: only 404/410 mean "absent" (`ABSENT_STATUSES`); any other non-200 raises, so the feeder is `ok=False` and `discovery` reports it in `failed_feeders`. A navtree version page that is absent is logged (`seed_feeders_navtree` logger) and skipped.
- `scope_and_dedup` returns `(urls, dropped)`; malformed URLs are counted into `FeederResult.dropped`, summed into `DiscoveryResult.dropped` and printed by `cli.py` as `dropped_malformed_urls`.

~~~~

### Archive: src/search/DOCS.md

~~~~markdown
# src/search/

## Role

pydoll-based parallel web-search pipeline behind the `search_web` and `search_engine_drilldown` CLI subcommands. Fans a single query out across 8 engines concurrently, dedups URLs into per-engine pools, caches the pools to disk, and returns an engine-breakdown table; the drilldown subcommand re-reads the cache to emit one engine's URLs. As of 2026-08-05, the drilldown path is ALSO logged (`record_type: "drilldown"` in `query_log.jsonl`, `cli.py`) — closing the "a scraped URL cannot be traced back to which engine(s) offered it" gap; see query_logger.py's module entry. Touch this package when changing engine fan-out, dedup/pool-building, the disk cache, or rate-limiting. Individual engine parsers live one level down in `engines/`.

## Public Interface

`__init__.py` is empty — modules are imported by path:

- `search_web_workflow(query, language="en", time_range=None, engines=None, …, query_modifier_map=None)` (search_web.py) — the `search_web` subcommand entry (`cli.py`). Returns `list[TextContent]` (one breakdown table).
- `fetch_search_results(...)` (search_web.py) — sync wrapper for dev scripts; returns the raw result list, no pool-building.
- `cache_key`, `cache_read`, `format_engine_pool` (cache.py) — the `search_engine_drilldown` subcommand path (`cli.py`).
- `log_query(record)` (query_logger.py) — called directly by `cli.py` (drilldown logging, as of 2026-08-05) in addition to `search_web.py`.
- `kill_own_chrome_atexit()` (browser.py) — registered `atexit` in `cli.py`; PID-scoped last-resort backstop, see browser.py's module entry.

## Flow

`search_web_workflow` selects engines → if any needs the browser, `_prewarm_browser` blocks (outside any watchdog) until this run's Chrome is up → `asyncio.gather` of `_engine_with_timing` tasks (each acquires a rate-limiter token, then runs the engine) → `finally: kill_own_chrome()` tears the browser down and releases the cross-process lock → flat `raw_results` → `build_engine_pools` groups by URL and keeps one entry per engine that returned it, each annotated with every engine's position for that URL → per-engine pool cap to a fixed 10 → `_format_breakdown` table → `_prepend_degraded_notice` (a no-op on a healthy run) → `cache_write` to `~/.cache/websearch/<key>.json`. `search_engine_drilldown` skips all of this: `cache_read` the per-engine pool → `format_engine_pool` numbers + cleans snippets.

## Modules

### search_web.py (355 LOC)

**Purpose:** Search orchestrator — fans out across 8 engines, builds and caps per-engine pools, formats a breakdown table (prefixed with the degraded-run notice from `degraded_notice.py`), and caches the result.
**Reads:** query + params; per-engine caps in `ENGINE_MAX_RESULTS`; default set via `_DEFAULT_ENGINES`; `_BROWSER_ENGINES` (which of the 8 need `browser.py`'s Chrome).
**Writes:** disk cache `~/.cache/websearch/<key>.json` (via cache_write); query log (via log_query).
**Called by:** `cli.py` (search_web_workflow); dev scripts (fetch_search_results).
**Calls out:** `httpx`, `pydoll.exceptions`, `websockets.exceptions`, `mcp.types.TextContent`; `engines/` (all 8 engine classes); `browser` (get_tab, kill_own_chrome); `cache` (cache_key, cache_write), `rate_limiter` (get_limiter), `merge` (build_engine_pools), `result` (SearchResult), `status`, `status_timeout`, `status_error`, `query_logger` (log_query), `degraded_notice` (_prepend_degraded_notice).

### degraded_notice.py (61 LOC)

**Purpose:** Builds the degraded-run notice prepended to the breakdown once the error/timeout share of selected engines crosses a fixed threshold; names each failing engine's shortened drop_reason and prints a repair line only for the observed browser-never-started signature.
**Reads:** the per-engine `engine_stats` dict handed in (`status`, `drop_reason`).
**Writes:** none (returns the text).
**Called by:** `search_web.py` (`_prepend_degraded_notice`); `dev/tests/test_search_web_degraded_notice.py`.
**Calls out:** `status_error`, `status_timeout`.

### merge.py (34 LOC)

**Purpose:** Groups results by URL and returns one per-engine pool per URL, each entry annotated with every engine's position, sorted by native position.
**Reads:** flat `list[SearchResult]` from fan-out.
**Writes:** none (returns the pool dict).
**Called by:** `search_web.py`.
**Calls out:** `result` (SearchResult).

### cache.py (112 LOC)

**Purpose:** Atomic-write JSON disk cache for per-engine pools (1h TTL), plus `format_engine_pool` for numbered-list drilldown rendering with snippet cleanup.
**Reads:** cache files under `~/.cache/websearch/`.
**Writes:** `~/.cache/websearch/<key>.json`.
**Called by:** `cli.py` (cache_key, cache_read, format_engine_pool); `search_web.py` (cache_key, cache_write).
**Calls out:** `result` (SearchResult), `snippet` (_strip_bloat, _truncate, MAX_SNIPPET_LEN).

### snippet.py (57 LOC)

**Purpose:** Snippet text utilities for drilldown display — HTML-unescape + bloat-pattern stripping, plus sentence-aware truncation.
**Reads:** raw snippet string.
**Called by:** `cache.py` (format_engine_pool).
**Calls out:** none (stdlib `html`, `re`).

### query_logger.py (19 LOC)

**Purpose:** Append-only JSONL query log (`log_query(record)`) — three record types (`engine_run`, `workflow_summary`, `drilldown`), correlated via a shared `search_key`.
**Reads:** `WEBSEARCH_QUERY_LOG_PATH` env (fallback `src/logs/query_log.jsonl`).
**Writes:** `src/logs/query_log.jsonl`.
**Called by:** `search_web.py` (engine_run, workflow_summary); `cli.py` (drilldown, as of 2026-08-05).
**Calls out:** `src/log_janitor.py` (maybe_prune_jsonl).

### browser.py (313 LOC)

**Purpose:** pydoll Chrome lifecycle — one shared, headed, backgrounded Chrome self-launched via a dynamically resolved bundle, one fresh profile directory per run, one tab per engine.
**Reads:** nothing (singleton browser on first access).
**Writes:** a fresh `tempfile.mkdtemp(prefix=SESSION_DIR_PREFIX)` profile directory per run, removed on this run's own clean exit and swept by the next run's `_reap_session_profile` otherwise (`process-docs/browser_posture/`); the cross-process lock file + JSON sidecar, at a fixed path independent of the profile directory.
**Called by:** `cli.py` (kill_own_chrome_atexit, atexit); `search_web.py` (get_tab via `_prewarm_browser`, kill_own_chrome); `engines/` (new_tab, kill_tab — google, duckduckgo, mojeek, yandex, bing, brave, startpage); 40+ `dev/search_pipeline/*.py` probes (new_tab, close_browser — direct callers, bypass search_web.py's lock/prewarm entirely).
**Calls out:** `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager, TargetCommands); `patchright.async_api` (async_playwright, bundle-path resolution only); `psutil` (own-PID terminate/kill); `browser_lock` (acquire); `death_pipe` (spawn_watchdog); `open`/`pgrep`/`osascript` (macOS process control and frontmost-app/window control).

### browser_lock.py (80 LOC)

**Purpose:** Generic, domain-agnostic blocking cross-process file lock (`fcntl.flock`-based) with a stale-takeover escape hatch — no Chrome/SESSION_DIR knowledge, takes an `on_stale` callback so the caller decides what "break it" means. Polls a non-blocking `flock`; a JSON sidecar (`{pid, started_at}`) older than `hard_budget_s` is presumed a stuck (not just slow) holder — `on_stale()` runs, then a fresh inode is opened at the same path (flock is inode-bound, so this bypasses the old holder's still-technically-held lock) and acquire retries.
**Reads:** the lock file + its `.json` sidecar.
**Writes:** the lock file (created on first acquire, persists across releases) + sidecar (written on acquire, unlinked on release).
**Called by:** `browser.py` (get_tab, with `_reap_session_profile` as `on_stale`).
**Calls out:** none (stdlib `fcntl`, `json`, `time`).

### rate_limiter.py (41 LOC)

**Purpose:** Per-engine token-bucket rate limiter — module-level `_limiters` registry populated at engine import, consumed via `get_limiter(name).acquire()` before engine work.
**Reads / Writes:** in-memory `_limiters` registry.
**Called by:** `search_web.py` (get_limiter); `engines/` (RateLimiter, _limiters).
**Calls out:** none (stdlib `asyncio`, `time`).

### result.py (17 LOC)

**Purpose:** `SearchResult` dataclass — `url, title, snippet, engine, position, preview, engines, snippets, engine_positions, date, pdf_url`. `date` populated only by API engines with native date metadata; `pdf_url` populated only by `openalex` (`best_oa_location.pdf_url`).
**Called by:** `search_web.py`, `merge.py`, `cache.py`, `engines/`.
**Calls out:** none (stdlib `dataclasses`).

### status.py (5 LOC)

**Purpose:** The 3 ungrouped engine-status string constants — `OK`, `EMPTY`, `RATE_SKIP` — facts about our own runtime for the query log + audit. The `TIMEOUT_*` and `ERROR_*` prefix clusters were split into their own sibling modules (`status_timeout.py`/`status_error.py`, below) once this file held two or more prefix clusters (this sweep's split rule); same constants, same string values, pure relocation. As of the guessed-verdict-removal milestone, the 5 EMPTY_* sub-statuses (`EMPTY_BLOCK`/`EMPTY_NO_CONTAINER`/`EMPTY_CONCURRENT_RACE`/`EMPTY_CONSENT`/`EMPTY_NO_RESULTS`) and the 2 unused bare `TIMEOUT`/`ERROR` constants (zero and one usage respectively, neither ever produced by `_classify_engine_exception`) were removed — see `engines/DOCS.md`'s Gotchas for what replaced the EMPTY_* distinctions in the diagnosis snapshot.
**Called by:** `search_web.py` (imported as `status as S`); `dev/search_pipeline/no_google_burst_smoke.py` (same alias).
**Calls out:** none.

### status_timeout.py (5 LOC)

**Purpose:** The `TIMEOUT_*` prefix cluster split out of `status.py` (pure relocation, same values): `TIMEOUT_WATCHDOG`, `TIMEOUT_NONCOOP`, `TIMEOUT_HTTPX`.
**Called by:** `search_web.py` (imported as `status_timeout as ST`, used in `_classify_engine_exception`); `dev/search_pipeline/no_google_burst_smoke.py` (same alias).
**Calls out:** none.

### status_error.py (6 LOC)

**Purpose:** The `ERROR_*` prefix cluster split out of `status.py` (pure relocation, same values): `ERROR_BROWSER`, `ERROR_HTTP`, `ERROR_PARSE`, `ERROR_OTHER`.
**Called by:** `search_web.py` (imported as `status_error as SE`, used in `_classify_engine_exception`); `dev/search_pipeline/no_google_burst_smoke.py` (same alias).
**Calls out:** none.

### selector_hits.py (13 LOC)

**Purpose:** Aggregates the per-item `sel` selector indexes returned by the engine parse scripts into `{field: {index: count}}` for the diagnosis.
**Called by:** `engines/google.py`, `engines/bing.py`, `engines/brave.py`, `engines/yandex.py` (`_parse_results`).
**Calls out:** none.

### document_status.py (43 LOC)

**Purpose:** Shared CDP Network-domain mechanism backing the diagnosis snapshot's `document_status_chain`/`http_status` facts, one copy for all 7 browser engines (google, duckduckgo, mojeek, startpage, brave, bing, yandex) in `engines/` (these already share this package's `browser.py` tab lifecycle, unlike the scraper package's deliberately-duplicated chromium/camoufox lanes — see `src/scraper/DOCS.md`). `start_document_status_capture(tab)` arms a `Network.responseReceived` listener BEFORE an engine's first navigation (so it also catches that navigation's own response), filtering to `type == "Document"` and `frameId == tab._target_id` — the CDP convention (already relied on by `browser.py`'s `kill_tab`) that a target's own top-level frame ID equals its target ID — and returns the list that accumulates the ordered chain of observed statuses. `attach_document_status(diag, status_chain)` is a pure, after-the-fact merge (`document_status_chain`: the list; `http_status`: `chain[-1]`, `None` if empty, never a fabricated default) called at each engine's own `return` site — `_classify_diagnosis` never sees it. Same "fact, not verdict" principle and field name as `src/scraper/chromium_scrape.py`'s `document_status_chain`; CDP directly instead of a Playwright `page.on` hook. `start_document_status_capture` has no handler of its own (removed 2026-09-24): a CDP failure while arming the listener propagates out of the engine and is recorded by `_engine_with_timing` as an error status. As of the partial-diagnosis-on-timeout milestone (`process-docs/search_pipeline/`), `update_partial(partial, status_chain, t0, facts)` reuses `attach_document_status` internally to merge a caller-supplied mutable dict with the same network facts plus `elapsed_ms` (`time.perf_counter() - t0`, the one thing `attach_document_status` itself has no notion of) — a no-op when `partial` is `None`, called by each of the 7 browser engines' own poll loop on every iteration, using facts already computed that same iteration.
**Reads:** nothing (pure functions + one CDP call).
**Writes:** nothing (returns values; no I/O).
**Called by:** `engines/google.py`, `duckduckgo.py`, `mojeek.py`, `brave.py`, `bing.py`, `yandex.py`, `startpage.py`.
**Calls out:** `pydoll.protocol.network.events` (`NetworkEvent`), `pydoll.protocol.network.types` (`ResourceType`).

## State

Two module-owned states. `rate_limiter._limiters` — the per-engine token-bucket registry, populated at engine import, read/mutated via `get_limiter().acquire()`. The disk cache (`~/.cache/websearch/`) — written by `cache.cache_write` (from search_web), read by `cache.cache_read` (from the drilldown path); 1h TTL, atomic writes. No cross-request in-memory search state — each `search_web_workflow` call is independent.

## Gotchas

- **Since the self-launch milestone, `get_tab()` skips the two pieces of pydoll's `Chrome.start()` that only fire through `.start()`/`.connect()`: proxy-credential configuration and the `--user-agent=` override (both browser-level and per-worker).** `build_options()` sets neither today, so this is currently a no-op gap, not an observed regression — but it means proxy support or a UA override cannot just be added to `build_options()` the way `webrtc_leak_protection`/`BACKGROUNDING_FLAGS` were; the equivalent pydoll-internal calls (`_configure_proxy`, `_apply_user_agent_override`, `_setup_worker_user_agent_override`) would need to be called explicitly from `get_tab()` too. Flagged here once so it isn't rediscovered as a mystery later.
- **`get_tab()`'s stale-`DevToolsActivePort`-file race no longer exists, and `_clear_stale_devtools_port()` is gone, not merely made unnecessary in one call path.** As of the fresh-profile-per-run milestone (`process-docs/browser_posture/`), every run's profile is a brand-new `tempfile.mkdtemp()` directory, same as `src/scraper/chromium_process.py` always was — a file left behind by a PRIOR run can no longer be read by THIS run, because this run's directory did not exist yet when that prior file was written. The race required a single directory shared across runs; that precondition is gone by construction, not guarded against.
- **`LOCK_PATH` is a fixed constant, deliberately NOT derived from `SESSION_DIR_PREFIX` or any per-run value.** It was briefly derived from the (then-persistent) profile directory's own name so it could not drift out of sync with a renamed directory — see `process-docs/browser_posture/` for that reasoning. Once the profile directory changes on every single run rather than occasionally, deriving the lock path the same way would give every run its own lock file, and two concurrent invocations would never see each other's lock at all. Do not re-derive `LOCK_PATH` from the profile directory again without re-reading that history first.
- Active engines (8): google, duckduckgo, mojeek, startpage, brave, bing, yandex (pydoll); openalex (HTTP). `mojeek` was removed in the 2026-09 engine-reduction milestone and returned on 2026-09-17 once its ALTCHA challenge was shown to be solvable unattended — see `process-docs/mojeek_return/`. Google Scholar (`engines/scholar.py`) is decoupled from the default pool. crossref, semantic_scholar, stack_exchange, open_library, lobsters, and marginalia were removed entirely (not parked) — see `process-docs/engine_expansion/` for their history.
- Two-call architecture: `search_web` returns counts only (no URLs); URLs come from `search_engine_drilldown` reading the cache. The drilldown query MUST match the prior `search_web` call or the cache key misses.
- **Post-dedup pool cap is a fixed 10 per engine (`POOL_CAP` in `search_web.py`), independent of any other engine's — including Google's — result count.** A URL shared by several engines consumes a cap slot in each of those engines' own top-10 independently. See `process-docs/search_pipeline/` for the reasoning and the prior google-anchored design it replaced.
- **`build_engine_pools` no longer reassigns a shared URL to one winning engine — every engine that returned it keeps its own pool entry, annotated with `engine_positions` for every engine that offered it.** `engine_positions` is persisted through `cache_write` but is NOT rendered in `format_engine_pool`'s text output. See `process-docs/search_pipeline/` for the measured impact and reasoning.
- Stealth config lives in `browser.py` (headed-backgrounded launch, `--disable-blink-features=AutomationControlled`, `BACKGROUNDING_FLAGS`, browser preferences) + per-engine files (SOCS cookie for Google) — no config file, no JS fingerprint patches or UA override (removed — see `browser.py`'s module history via `process-docs/browser_posture/`).
- pydoll tab cleanup uses `kill_tab` (browser-level close), NOT `tab.close()` — the latter hung 65s on non-cooperative renderers.
- CLI dispatch hardcodes `language="en"`, `time_range=None`, `engines=None`; the full `search_web_workflow` signature is retained only for dev-script callers.
- `pdf_url` (as of 2026-09-24 `openalex` only, from `best_oa_location.pdf_url`) is passed through as-is from the vendor with no validation — a live sample showed one `pdf_url` pointing at a `.jpg` figure asset rather than the paper's full text (see `process-docs/engine_reduction/`). Treat it as "OpenAlex's best guess at a direct full-text link", not a guaranteed PDF.
- **A URL can NEVER be attributed to exactly one engine** — engines overlap heavily; the same URL routinely appears in 3+ drilled engines' pools. Any log record or downstream tooling claiming "this URL came from engine X" is wrong by construction. What IS answerable (as of 2026-08-05, via `query_log.jsonl`'s `drilldown` records + `search_key`): "which engines offered this URL in this session" — possibly several, possibly none.
- `dev/tests/test_query_logger.py`'s engine mocks must expose `.search_with_reason(query, language, max_results, partial) -> (results, empty_reason, diagnosis)` — `_engine_with_timing` calls that, not `.search()`. Fixed 2026-08-20 (the file's one shared mock helper, `_make_mock_engine`, set `.search` and was removed along with the drift it caused — see `_make_mock_engine_with_reason`, now the file's only engine-mock helper). Extended to a 3-tuple as of the diagnosis-snapshot milestone — `diagnosis` defaults to `None`. Extended again, as of the partial-diagnosis-on-timeout milestone, to accept a 4th `partial` parameter (keyword-defaulted `None` on `BaseEngine` and all 9 real engines, so every pre-existing caller not passing it — `.search()`, every `dev/search_pipeline/*.py` script calling `search_with_reason` directly — is unaffected; confirmed live, not just read, by importing all 9 engine modules plus both dev scripts that call `search_with_reason` directly, and by a real 3-positional-arg `OpenAlexEngine().search_with_reason(...)` call against the live API). As of the guessed-verdict-removal milestone, every real engine's `search_with_reason` always returns `empty_reason=None` (there is no longer any non-`None` value any engine produces from inside that method) — a mock is free to pass any string for `empty_reason` purely to exercise the plumbing, it does not need to resemble a real status.
- **A cancelled engine's diagnosis no longer has to be `None`.** `_engine_with_timing` creates a plain `partial = {}` dict before `asyncio.wait_for(engine.search_with_reason(..., partial), timeout=...)` and hands it to the engine BY REFERENCE — the only channel that survives `asyncio.wait_for` cancelling the wrapped coroutine's own Task, since a `ContextVar` set inside that Task does not propagate back out (each `asyncio.Task` gets its own copied context) and nothing else the cancelled coroutine touches is visible from outside it. Each of the 7 browser engines' own poll loop writes into `partial` on every iteration, using facts it already computed that same iteration for its own control-flow decision — no new DOM round trip, the success path is unaffected either way since the loop already runs there too, just returns before ever needing the caught-exception branch. On ANY exception (not gated to `asyncio.TimeoutError` specifically — the same channel and the same "was anything actually observed" question apply to a genuine crash mid-poll too), `_engine_with_timing`'s `except` branch uses `{**partial, "diagnosis_partial": True}` if `partial` has anything in it, else `None` — the same "don't invent a fact that was never observed" rule the guessed-verdict-removal milestone settled, now extended to the case where the observation exists but the RETURN never happened. `diagnosis_partial` never appears on a normal return, from any engine, ever — see `engines/DOCS.md`'s Gotchas for the full field contract, including `elapsed_ms`, the one new field this adds to answer "how stale is this snapshot". See `process-docs/search_pipeline/` for what was and was not verified live — the mechanism is confirmed, a genuine Brave-challenge overrun of the 6.0s budget has not been observed even once, and the two must not be conflated.
- **`engine_stats[name]` (both `engine_run` and `workflow_summary` records) carries a `"diagnosis"` key alongside `"status"`.** For `openalex`/`scholar`, the attachment rule is "whenever the engine returns WITHOUT results" — `diagnosis` is `None` on a real success, `{"http_status": int}` (`scholar` also adds `captcha_form`) otherwise. For the 7 browser engines, `diagnosis` is attached on EVERY branch including success, but the two halves are gated independently: the CDP-observed NETWORK facts (`document_status_chain`/`http_status`, `document_status.py`) are always attached — `attach_document_status({}, status_chain)` costs nothing extra on success, since `status_chain` is a list the listener already filled during navigation — while the DOM/JS facts (`marker`/`title`/`url`/`ready_state`/`containers_found` plus engine-specific extras, each engine's own `_diagnose(tab)`) stay empty-only, since a `_diagnose(tab)` call is a real JS round trip a successful search has no reason to pay for. This is why a success record for `brave`/`yandex`/`mojeek` (the challenged engines) can still show whether a challenge resolved first, via `document_status_chain`'s length, without an unneeded DOM read — see `engines/DOCS.md`'s Gotchas for the exact field contract. **As of the guessed-verdict-removal milestone, `status` itself no longer carries the 5 EMPTY_* sub-statuses (`EMPTY_BLOCK`/`EMPTY_NO_CONTAINER`/`EMPTY_CONCURRENT_RACE`/`EMPTY_CONSENT`/`EMPTY_NO_RESULTS`) — every empty result now logs bare `"EMPTY"`, and the fact each removed sub-status used to encode lives entirely in `diagnosis` instead** (see `engines/DOCS.md`'s Gotchas for the full per-verdict mapping). `_classify_diagnosis` and its per-engine equivalents were deleted along with the statuses they produced.
- `search_web_workflow` writes TWO log records per call, not one: `"engine_run"` (from `_query_engines_concurrent`) then `"workflow_summary"` (from `_build_query_log_entry`) — a test asserting exactly one JSONL line after a workflow call is checking the wrong invariant; filter by `record_type` instead (see `test_search_web_workflow_writes_log`).
- `query_logger.py` has no `LOG_PATH` module attribute — the log path is read fresh from `WEBSEARCH_QUERY_LOG_PATH` (env var) inside `log_query()` on every call. Tests must `monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", ...)`, not `patch.object(query_logger, "LOG_PATH", ...)`.
- `log_janitor.maybe_prune_jsonl` (called at the end of every `log_query()`) drops any JSONL line whose `"ts"` field is older than the 90-day retention window — a test writing a record with a hardcoded past-dated `ts` literal (or no `ts` at all — a missing key is treated as unparseable and also dropped) will see its own line silently pruned away as real time passes. Always use a freshly-computed current timestamp in test payloads that include `ts`.
- **`get_tab()`'s cross-process lock wait MUST happen outside any per-engine watchdog — never call it lazily from within an `asyncio.wait_for(...)`-guarded task.** The per-engine watchdog (`ENGINE_WATCHDOG_TIMEOUT`, uniform `6.0s` across all engines as of 2026-08-25) is far shorter than a legitimate second-run lock wait (observed ~7s for one full sweep, budgeted up to `LOCK_HARD_BUDGET_S`=81s before stale-takeover). `asyncio.wait_for` cancelling a task mid-`await get_tab()` releases `get_tab`'s asyncio-level `_init_lock` (context-manager exit still runs under cancellation) but does NOT stop the underlying `asyncio.to_thread(browser_lock.acquire, ...)` call — a real OS thread, uncancellable — which keeps polling in the background, orphaned; the next queued engine then re-enters `get_tab()` and spawns ANOTHER competing thread. Caught live via a two-parallel-CLI-run test that showed repeated "Acquiring cross-process browser-session lock" log lines within a single process and a run that silently gave up without ever launching its own Chrome. Fixed by `search_web_workflow` calling `_prewarm_browser` (bare `await get_tab()`, no timeout) once, before the fanout, whenever `_BROWSER_ENGINES` intersects the selected set — by the time engines run, `_browser` is already set and their own `new_tab()` calls return near-instantly.
- **`get_tab()`'s launch body (from `browser_lock.acquire` through `_record_own_pids`) is wrapped in try/except that resets `_browser`/`_tab` to `None` and releases `_lock_handle` before re-raising.** Without this, a real Chrome-launch failure (missing binary, etc.) would leave the cross-process lock held forever by a process that never got a working browser — `close_browser()`'s own `_browser.stop()` would itself raise `BrowserNotRunning` on a half-initialized `Chrome` object, so `kill_own_chrome`'s `finally` can't be relied on alone to clean this up.
- **`_reap_session_profile()` (profile-pattern `pkill`-equivalent) is legitimate ONLY while the cross-process lock is held** — either right after acquiring it (before this run's own launch, reaping a crashed prior run's `open -g`-launched Chrome, which survives its own short-lived wrapper process dying) or as `browser_lock.acquire`'s `on_stale` callback during a takeover. Calling it unlocked would resurrect the original cross-run-kill bug this milestone fixed.
- **`kill_own_chrome`'s `close_browser()` call is wrapped in try/except, not bare.** Chrome dying mid-sweep (crash, manual close) makes `_browser.stop()` raise on the dead websocket BEFORE `close_browser`'s own `_browser = None` reset line runs — a bare call would then skip the PID-scoped psutil safety net and the lock release that follow it in `kill_own_chrome`, leaking the cross-process lock until the 81s stale-takeover. Caught by review, not live reproduction; regression-guarded (`test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises`).
- `kill_own_chrome_atexit()` is a sync wrapper because `atexit` callbacks cannot be coroutines; it is safe only because `atexit` fires after `asyncio.run()` in `cli.py`'s `main()` has returned, so no loop is running at that point. If `cli.py` ever keeps a loop alive past `main()`, this wrapper must change.
- **Three independent nets, not one mechanism doing everything.** Net 1 (`kill_own_chrome`, this file) is the fast, deterministic common case. Net 2 (`death_pipe.spawn_watchdog`, called once right after `_record_own_pids`) is the crash backstop — proven live (2026-08-25): a real `search_web` run `kill -9`'d mid-sweep left its Chrome killed within the same second by the watchdog (`src/logs/cli.log`: `"parent died without tearing down its own browser — killed pids=[...]"`), never waiting for a subsequent run's reap. Net 3 (`_reap_session_profile`, pre-launch) only ever catches what net 2 could not — e.g. a leak from before this milestone shipped, or the vanishingly rare case where the watchdog itself never got to spawn. Do not remove net 3 on the reasoning that net 2 "already covers this" — they cover different failure windows.
- The focus-steal watchdog is keyed on PID, not app name — a decision that predates the M2 bundle-path fix below and was kept even though the collision it originally guarded against no longer applies. See `process-docs/browser_posture/` for the reasoning.
- As of the M2 no-Spaces-drag milestone, this module launches a dynamically resolved, dedicated Chromium bundle under its own separate persistent profile, instead of the owner's real Chrome, to stop the launch from switching macOS Spaces. Two tradeoffs (profile identity, engine-facing browser identity) were accepted deliberately rather than solved in code — see `process-docs/browser_posture/` for the reasoning and how to verify them against a baseline.
- **The watchdog's "known-good app to restore" anchor is captured by `get_tab()` itself, before `Chrome(options)`/`_browser.start()` ever runs, and threaded into `_spawn_focus_watchdog`/`_focus_steal_watchdog_by_pid` as a parameter — the watchdog does not derive its own initial reading.** Capturing it inside the watchdog's own first read is a proven-live bug: the watchdog only starts after Chrome has already launched, which is exactly when Chrome is likeliest to already be frontmost, so a self-read can capture an OWNED pid as the anchor and silently disable reclaim. Regression-guarded by `test_focus_steal_watchdog_by_pid_reclaims_immediately_when_already_stolen_at_start` (`dev/tests/test_browser.py`). See `process-docs/browser_posture/` for the live probe that caught it and the post-fix verification.
- `close_browser()` cancels any live `_focus_watchdog_task` (`_cancel_focus_watchdog`) as the FIRST action, unconditionally, before touching `_browser.stop()` — not only in `kill_own_chrome()`'s teardown path. `close_browser()` is called directly by 40+ `dev/search_pipeline/*.py` probes that bypass `kill_own_chrome()` entirely (see this module's own `Called by` above); placing cancellation only in `kill_own_chrome()` would leak a live watchdog task for every one of those direct callers.
- **REMOVED 2026-09-24 (Phase 4 control-flow review, owner decision): `cache.cache_read`'s `except Exception -> None` and `document_status.start_document_status_capture`'s `except Exception -> warning`.** A corrupt cache file now raises `json.JSONDecodeError` out of `cache_read` (the drilldown command fails visibly instead of telling the user to rerun `search_web`; writes are atomic via `os.replace`, and `Cache read error` was never logged in the retained `cli.log` files 2026-08-31..2026-09-24). A CDP failure while arming the status listener now fails that engine with a recorded status instead of silently yielding an empty `document_status_chain`; `document-status capture setup failed` was never logged either. The engine-level handlers removed in the same review are in `engines/DOCS.md`. Guard: `dev/tests/test_search_control_flow_removals.py`, `dev/tests/test_document_status.py`.
- **`query_logger.log_query`'s `except Exception` stays, classified as best-effort telemetry (Phase 4 class D, owner decision 2026-09-24).** It logs a WARNING (`query_log write failed`) and drops the record; losing a log line does not change search results, and the posture is deliberate. Never observed in the retained logs.
- **`_prewarm_browser`'s handler stays (fallback observed 6 times on 2026-09-21: `DevToolsActivePort did not appear ... within 10.0s`), but its WARNING no longer claims the engines retry.** In all 6 observed cases the browser engines then failed individually (`Engine browser error: Failed to get browser ws address`, status `ERROR_BROWSER`) and only non-browser engines returned results, so the message now reads that browser engines are expected to fail individually and non-browser engines still run. The failure stays traceable through that WARNING plus the per-engine statuses and the degraded-run notice.
- 2026-09-24 Phase 5: `_select_engines` raises `ValueError` on an unknown engine name and returns only the selected dict; the always-empty `engines_excluded` field was removed from the `workflow_summary` query-log record. `browser_lock.acquire` logs a warning (holder pid, age, budget) before breaking a stale lock, an unreadable or corrupt sidecar raises (only a missing sidecar means "not stale"), and the sidecar is written atomically (tmp + `os.replace`). `browser._get_frontmost_pid`/`_activate_pid` log a warning once per process on a failing osascript. `query_logger.log_query` no longer catches write failures. New module `selector_hits.py` (aggregation of the per-item selector index).

~~~~

### Archive: src/search/engines/DOCS.md

~~~~markdown
# src/search/engines/

## Role

Per-engine search implementations. Each module (except `base.py`) exports one `BaseEngine` subclass implementing `search(query, language, max_results) -> list[SearchResult]`. Two implementation styles: pydoll Chrome-tab scraping (DOM parse via injected JS) for engines with no public API, and direct `httpx` calls for engines with a JSON/XML API. Touch this package to add/modify an engine's parsing logic or its rate-limit registration; touch `search_web.py` to change which engines are wired into the default pool.

## Public Interface

`__init__.py` is empty. Consumers import engine classes directly, e.g. `from src.search.engines.google import GoogleEngine`.

## Flow

Query string in → engine-specific fetch (pydoll tab navigation + JS extraction, or `httpx` GET/POST) → HTML/JSON parse → `list[SearchResult]` out. Each module registers a `RateLimiter` into the shared `_limiters` registry (`src/search/rate_limiter.py`) at import time; `search_web._engine_with_timing` acquires a token before invoking `search()`.

## Modules

### base.py (16 LOC)

**Purpose:** Abstract `BaseEngine` parent — as of 2026-09-09, `search_with_reason()` is the abstract method (every engine's real logic lives there, returning the uniform `(results, empty_reason, diagnosis)` 3-tuple) and `search()` is the one concrete base method, a plain delegation (`results, _, _ = await self.search_with_reason(...); return results`) with no try/except — an exception from any engine propagates through it unchanged. `empty_reason` is `None` for every real engine as of the guessed-verdict-removal milestone — no engine has a non-`None` value left to return from inside `search_with_reason`. As of the partial-diagnosis-on-timeout milestone, the abstract signature gained a 4th, keyword-defaulted `partial: dict | None = None` — `search()`'s own delegation does not pass it, matching every pre-existing caller.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** every engine module in this package (subclassed).
**Calls out:** `src.search.result.SearchResult` (type only).

---

### google.py (284 LOC)

**Purpose:** Google web search via pydoll Chrome tab — navigates to the search URL, sets the `SOCS` consent cookie, waits for `div.MjjYud` result containers, detects the `/sorry/` CAPTCHA path, and extracts results via an injected JS parse script. Every non-success branch (the `/sorry/` short-circuit, the post-wait-failure branch, the zero-parsed-results branch) returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`marker` always `None` here — Google's signal is the URL path, not a text marker — plus `title`/`url`/`ready_state`/`containers_found`), merged with `document_status.attach_document_status` for the `document_status_chain`/`http_status` facts. The success branch (non-empty results) attaches those same network facts too — `attach_document_status({}, status_chain)`, no DOM read — see `engines/DOCS.md`'s Gotchas for why. `_classify_diagnosis` was removed (the guessed-verdict-removal milestone) — its BLOCK/CONSENT/CONCURRENT_RACE/NO_CONTAINER outputs are all fully re-derivable from `url`/`ready_state`, already in the snapshot. As of the 2026-09-19 goto-redirect milestone: Google's organic-result href is a same-origin `/goto?url=<opaque blob>` redirector, not the destination — `_parse_results`/`_build_results` extract title/snippet/date/that href, then `_resolve_urls` resolves all of a page's hrefs concurrently via a single non-followed `curl_cffi` request each, dropping any result that doesn't resolve to a 302 with an absolute `http(s)` `Location` and collapsing duplicate destinations, and reporting every drop as a `goto_resolution` count in the diagnosis (see Gotchas); see `process-docs/search_pipeline/` for the investigation, the measurements and a second, independently found snippet-selector bug fixed in the same pass. As of the partial-diagnosis-on-timeout milestone, `_wait_for_results` calls `document_status.update_partial(partial, status_chain, t0, {"containers_found": False})` on every poll iteration — the one fact a raw-count loop actually has, no new round trip.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `pydoll` (NetworkCommands, CookieSameSite), `curl_cffi` (`AsyncSession`), `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### duckduckgo.py (163 LOC)

**Purpose:** DuckDuckGo HTML-endpoint search via pydoll Chrome tab (`html.duckduckgo.com/html/`) — waits for `#links > div.web-result` containers, detects the `form#challenge-form` CAPTCHA element, and populates `SearchResult.date` (day precision) from the optional dated `<span>` in `.result__extras__url` when present. Every non-success branch returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`title`/`url`/`ready_state`/`containers_found` plus its own `challenge_form: bool`, since the block signal is structural — an element count, not text — so `marker` stays `None`, never overloaded with a selector string). `document_status.attach_document_status` merges in `document_status_chain`/`http_status`. The success branch (non-empty results) attaches those same network facts too — `attach_document_status({}, status_chain)`, no DOM read. `_classify_diagnosis` was removed (the guessed-verdict-removal milestone) — its BLOCK/CONCURRENT_RACE/NO_CONTAINER outputs are fully re-derivable from `challenge_form`/`ready_state`, already in the snapshot. As of the partial-diagnosis-on-timeout milestone, `_wait_for_results` calls `update_partial(partial, status_chain, t0, {"containers_found": False})` on every poll iteration.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### startpage.py (152 LOC)

**Purpose:** Startpage (Google-index frontend) search via pydoll Chrome tab — two-step React-form flow (homepage load, native-setter query fill, real button click) to obtain a per-session `sc` token, then waits for `div.result` containers and detects block/captcha markers. Every non-success branch returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`marker`/`title`/`url`/`ready_state`/`containers_found` plus the engine-specific `iframe_challenge: bool`), merged with `document_status_chain`/`http_status` via `document_status.attach_document_status` — status capture is armed before `_submit_search`'s own homepage `go_to`, so the chain also covers the homepage load, not just the post-form-submit result page. The success branch attaches those same network facts too — `attach_document_status({}, status_chain)`, no DOM read. `_classify_diagnosis` was removed (the guessed-verdict-removal milestone) — its BLOCK/CONCURRENT_RACE/NO_CONTAINER outputs are fully re-derivable from `marker`/`iframe_challenge`/`ready_state`, already in the snapshot. As of the partial-diagnosis-on-timeout milestone, `_wait_for_results` calls `update_partial(partial, status_chain, t0, {"containers_found": False})` on every poll iteration — `t0` is captured at the very top of `search_with_reason`, before the homepage load, matching the network-fact capture window.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### brave.py (238 LOC)

**Purpose:** Brave Search via a pydoll Chrome tab, solving Brave's button challenge unattended when one is served.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

Three decisions here have each cost a milestone and are all recorded in
`process-docs/marker_reflection/`. The block check runs only after emptiness is established, never
before. The challenge button is clicked before anything else ends the wait, because the 429 page and
the challenge page are the same page. The click is gated on a narrow observed vocabulary rather than
on any button, and a separate unfiltered field records a button we saw but could not act on.
`challenge_triggered` rides on every branch including success; `button_present` only on the empty
ones. Read the area before changing any of the three.

---

### bing.py (182 LOC)

**Purpose:** Bing web search (direct path to the Bing index) via pydoll Chrome tab, headed — single GET, waits for `li.b_algo` containers, unwraps the `bing.com/ck/a?...&u=<base64>` tracking redirect on every href, and detects blocks via an EN+DE marker scan. Every non-success branch returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`marker`/`title`/`url`/`ready_state`/`containers_found`), merged with `document_status_chain`/`http_status` via `document_status.attach_document_status`. The success branch attaches those same network facts too — `attach_document_status({}, status_chain)`, no DOM read. `_classify_diagnosis` was removed (the guessed-verdict-removal milestone) — its BLOCK/CONCURRENT_RACE/NO_CONTAINER outputs are fully re-derivable from `marker`/`ready_state`, already in the snapshot. As of the partial-diagnosis-on-timeout milestone, `_wait_for_results` calls `update_partial(partial, status_chain, t0, {"containers_found": False})` on every poll iteration.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### yandex.py (161 LOC)

**Purpose:** Yandex Search (independent index) via pydoll Chrome tab, headed — waits for `li.serp-item` containers, extracts direct hrefs from `a.OrganicTitle-Link` (no unwrap needed), with fast CAPTCHA-redirect short-circuit and self-referential-result filtering. `_is_block_url` checks `urlparse(url).path` ONLY, as of the marker-reflection fix (see `process-docs/marker_reflection/`) — `SEARCH_URL` embeds the raw query into the `?text=` component of the very URL this check reads, so a query containing e.g. "showcaptcha" used to satisfy the marker via the query string alone, on the engine's own un-redirected results URL, with zero results ever attempted. Scoping to `path` cannot be perturbed by query content, since Yandex's own redirect target (`/showcaptcha`, live-confirmed) lives in the path, never the query string; a real redirect is still caught immediately, same as before. Every non-success branch returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`marker`/`title`/`url`/`ready_state`/`containers_found`, `None` on the redirect short-circuit — `_wait_for_results` was never called), including the CAPTCHA-redirect short-circuit (a fresh snapshot taken once the redirect is confirmed), merged with `document_status_chain`/`http_status` via `document_status.attach_document_status` — live-confirmed the SmartCaptcha redirect page itself serves HTTP 200, not a 3xx. The success branch attaches those same network facts too — `attach_document_status({}, status_chain)`, no DOM read. `_classify_diagnosis` was removed (the guessed-verdict-removal milestone) — its BLOCK/CONCURRENT_RACE/NO_CONTAINER outputs are fully re-derivable from `marker`/`url`/`ready_state`, already in the snapshot; `_is_block_url` stays, since it is also the early short-circuit optimization inside `search_with_reason`, independent of the removed verdict. As of the partial-diagnosis-on-timeout milestone, `_wait_for_results` calls `update_partial(partial, status_chain, t0, {"containers_found": False})` on every poll iteration — the redirect short-circuit itself is a single cheap property read, not a loop, so it carries no equivalent checkpoint.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### mojeek.py (204 LOC)

**Purpose:** Mojeek web search (independent index) via pydoll Chrome tab — navigates, and when Mojeek serves its self-hosted ALTCHA proof-of-work wall, dispatches the widget's own `verify()` from the main world and keeps polling until the solved page reloads with results. One wall-clock deadline (`MOJEEK_BUDGET_S`, 4.5s) anchored at the function's first line covers navigation and the poll together, leaving margin under the 6.0s watchdog for the diagnose and teardown that follow. Parsing waits for sufficiency-or-stability rather than first sight (`_is_ready_to_parse`): a full page parses immediately, a shorter list parses once it stops growing — the post-challenge reload was observed serving 1 link at the instant the poll first matched. Every non-success branch returns `reason=None` and attaches a `_diagnose(tab)` snapshot (`title`/`url`/`ready_state`/`containers_found` plus its own `challenge_widget`/`challenge_triggered`/`challenge_state`/`captcha_note`; `marker` stays `None` — the block signal is the presence of the `altcha-widget` element, not text), merged with `document_status_chain`/`http_status`. The success branch attaches those same network facts, no DOM read — a chain of length 2 is the solved-challenge trace. As of the partial-diagnosis-on-timeout milestone, `_await_results` calls `update_partial(partial, status_chain, t0, {"containers_found": trace["ready"], "challenge_triggered": trace["challenge_triggered"]})` on every iteration, right after updating `trace` — deliberately a NARROW subset of `trace`'s own internal keys (`link_count`/`poll_count` stay out), matching exactly the two field names already part of this engine's documented diagnosis contract rather than introducing new, undocumented ones through the partial path alone.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `src.search.browser` (`new_tab`, `kill_tab`), `src.search.document_status` (`update_partial`).

---

### openalex.py (123 LOC)

**Purpose:** OpenAlex academic graph search via `httpx` GET against `api.openalex.org/works` (JSON API, no browser) — iterative HTML-entity unescape on titles, `SearchResult.date` from `publication_date` (day-accurate) falling back to `publication_year` (year precision), `SearchResult.pdf_url` from `best_oa_location.pdf_url` (`_pick_url`'s arxiv > doi > id choice stays the canonical `url`). `per_page` clamped to the vendor's 100-max. `reason` is always `None` — the 429 branch used to surface a guessed `EMPTY_BLOCK` verdict, removed (the guessed-verdict-removal milestone) since it carried no information the observed `http_status` (already in diagnosis) didn't already carry; 403 (forbidden resource) was already `reason=None` beforehand, unchanged. `diagnosis` is `{"http_status": <the observed status_code>}` on every branch that returns WITHOUT results (429, 403, and a 200 that parsed to zero results), `None` only when results are non-empty — no DOM diagnosis mechanism (HTTP API, no browser to inspect), but the one fact this engine already holds (the real HTTP status) is no longer discarded. `partial` (the partial-diagnosis-on-timeout milestone's 4th `search_with_reason` parameter) is accepted for interface uniformity but never written to — a single `httpx` call has no intermediate poll-loop checkpoint to snapshot, and this engine's own internal timeout (3.6s) already sits comfortably under the 6.0s watchdog, so the outer cancellation this parameter exists for is not expected to fire here in practice.
**Reads:** `OPENALEX_API_KEY` env var (optional free API key, sent as `api_key` query param — raises the daily budget from $0.10 to $1; `mailto` is never sent, ignored by the API since 2026-02).
**Writes:** none (network only).
**Called by:** `src/search/search_web.py`.
**Calls out:** `httpx`.

---

### scholar.py (99 LOC)

**Purpose:** Google Scholar search via `httpx` GET (no browser, migrated off pydoll) — detects concurrent-CAPTCHA via 30x redirect to `/sorry/`; not wired into `search_web.py`'s production engine pool. `reason` is always `None` — the redirect and inline-captcha-form branches used to surface guessed `EMPTY_BLOCK`/`EMPTY_NO_RESULTS` verdicts, both removed (the guessed-verdict-removal milestone). The redirect's fact (the observed HTTP status) was already in diagnosis; the inline-captcha-form fact was NOT — `_parse_response` now returns `(results, captcha_form: bool)` instead of `(results, reason)`, and `captcha_form` moved into `diagnosis` alongside `http_status` before the verdict it fed was removed. `diagnosis` is `{"http_status": <the observed status_code>}` (redirect branch) or `{"http_status": ..., "captcha_form": bool}` (post-fetch branches) on every branch that returns WITHOUT results, `None` only when results are non-empty — same "one fact already in hand" treatment as `openalex.py`, extended by one field here since scholar had a second signal (`captcha_form`) that only ever fed a classification, never a snapshot, before this milestone. `partial` (the partial-diagnosis-on-timeout milestone's 4th `search_with_reason` parameter) is accepted for interface uniformity but never written to, same reasoning as `openalex.py` — one `httpx` call, no poll loop.
**Reads:** none (network only).
**Writes:** none (network only).
**Called by:** dev probe scripts only (`dev/search_pipeline/`) — NOT imported by `src/search/search_web.py`. Decoupled/parked from the production 7-engine pool.
**Calls out:** `httpx`, `lxml.html`.

## Gotchas

- **`mojeek.py` has NO block-detection early-exit branch, and must not grow one.** Its only decision is "are there result links yet" — a condition that is false at the start and becomes true. Mojeek's challenge page carries its boilerplate (`Verification required`, title `Captcha`) from the first poll and keeps it on screen for the entire verification sequence, clearing only when results replace the page, so any branch keyed on that text returns empty on iteration zero and the challenge is never solved. That exact defect produced two wrong live runs before it was caught in review (see `process-docs/engine_reduction/`); `dev/tests/test_mojeek_engine.py::test_block_boilerplate_from_first_poll_does_not_short_circuit` is the regression guard. The boilerplate is recorded as a fact in the diagnosis, never used as a verdict.
- **`mojeek.py` matches no page literal anywhere, deliberately.** The challenge copy was captured live on 2026-09-17 served in English (`Verification required`) on a page whose `html lang` is `de` and whose footer is German, so an English anchor is not a reliable locale-independent signal; and the results page's body would contain those same words for anyone who searched them — the same shape as the `roboter`/`robot` false positive recorded below. The engine keys on structure instead (`document.querySelector('altcha-widget')`, `typeof el.verify === 'function'`) and records `#captcha-note`'s text verbatim, whatever language it arrives in. Observed note sequence: `Waiting for verification.` -> `Checking verification with server...` -> `Verified successfully. Reloading...`. A solved challenge also appends a `chv=<hex>` parameter to the URL on the reload, visible in the diagnosis `url` field.

- All 8 production engines register a uniform `RateLimiter(max_requests=4, window_seconds=60)` into `_limiters` at module import time — adding a new engine requires this registration or `search_web._engine_with_timing` will KeyError on `get_limiter(name)`.
- `scholar.py` is fully wired (class, rate limiter, parse logic) but excluded from `search_web.py`'s imports — it is reachable code, not literally dead, but not part of any production call path. Re-enabling it means adding an import + entry to `_DEFAULT_ENGINES` in `filter_modes.py`.
- pydoll-based engines (`google`, `duckduckgo`, `mojeek`, `startpage`, `brave`, `bing`, `yandex`) all use `finally: await kill_tab(tab)` — NOT `tab.close()`, which caused 65s hangs on `TIMEOUT_NONCOOP` cases (`Page.close` via tab connection → hung renderer → 60s pydoll fallback).
- As of the engine-reduction milestone (2026-09), `openalex.py` is the only remaining HTTP (non-pydoll) engine — its `httpx.AsyncClient(timeout=3.6)` already matches the uniform `ENGINE_WATCHDOG_TIMEOUT`; no more hand-aligned per-engine timeout to track.
- **`search_with_reason` is a uniform 3-tuple return across all 9 engines: `(results, empty_reason, diagnosis)`, and a uniform 4-parameter signature as of the partial-diagnosis-on-timeout milestone: `(query, language, max_results, partial)`.** `diagnosis` is a `dict | None`. As of the guessed-verdict-removal milestone, `empty_reason` is `None` on EVERY branch of EVERY engine — there is no longer any code path that returns a non-`None` value from inside `search_with_reason` (the fact-based statuses — `TIMEOUT_*`/`ERROR_*`/`RATE_SKIP`/`OK` — are all assigned later, in `search_web._engine_with_timing`, never inside an engine). `diagnosis` is `None` only for `openalex.py`/`scholar.py` on a real success (non-empty `results`) — for the 7 browser engines, `diagnosis` is `None` only in `BaseEngine`'s default (never exercised in production); every real return from all 9 engines carries at least the network facts. See the "DOM vs. network facts" Gotcha below for the split that makes this true without paying for an unneeded DOM read. `partial: dict | None = None` is keyword-defaulted on `BaseEngine` and all 9 concrete engines — every pre-existing caller (`.search()`, every dev script calling `search_with_reason` directly) is unaffected, confirmed live. A new engine MUST implement this exact signature and return this exact 3-tuple shape or `search_web._engine_with_timing`'s call/unpack raises.
- **The diagnosis snapshot splits into two independently-gated halves, for the 7 browser engines: NETWORK facts (`document_status_chain`/`http_status`, from `document_status.py`) are attached on EVERY branch, success included — `attach_document_status({}, status_chain)` on success costs nothing extra (`status_chain` is a list the CDP listener already filled during navigation; no new CDP call, no JS eval). DOM facts (`marker`/`title`/`url`/`ready_state`/`containers_found`, from each engine's own `_diagnose(tab)`) stay empty-only — a `_diagnose(tab)` call is a real JS round trip, and a successful search has nothing to diagnose.** This is why `brave.py`/`yandex.py`/`mojeek.py` (the 3 engines that get proof-of-work/CAPTCHA-challenged) can show, on a SUCCESS record, whether a challenge resolved before the results arrived: `document_status_chain` length ≥ 2 means a reload happened first; length 1 means none did. An engine that was never challenged at all (e.g. a duckduckgo run with no `form#challenge-form` ever shown) looks the same either way on success: `{"document_status_chain": [200], "http_status": 200}` — a single entry, since only the one page load ever happened; the snapshot cannot itself say "no challenge was offered" vs. "a challenge was offered and this engine doesn't reload for it" — it can only say how many main-frame documents were observed.
- **Diagnosis snapshot field names are consistent across the 7 browser engines: `marker` (`str | None`, the matched block-keyword text, or `None` when the engine's own block signal isn't text-based — google's is a URL path, ddg's is an element count), `title` (`document.title`, raw casing), `url` (`window.location.href`), `ready_state` (`document.readyState`), `containers_found` (`bool | None` — `True` when `_wait_for_results` succeeded but parsing still produced zero items, `False` when it failed, `None` on a branch that short-circuits before ever calling `_wait_for_results` — never observed, never fabricated as `False`), `document_status_chain` (`list[int]`, ordered main-frame document response statuses observed via CDP — see `document_status.py`'s module entry in `src/search/DOCS.md`), `http_status` (`int | None`, `document_status_chain[-1]`, `None` — never a fabricated default — when nothing was observed).** Engine-specific extras keep their own names and never get folded into `marker`: `pow_link`/`button_present` (brave), `iframe_challenge` (startpage), `challenge_form` (duckduckgo), `captcha_form` (scholar), `challenge_widget`/`challenge_triggered`/`challenge_state`/`captcha_note` (mojeek) — `challenge_triggered` reuses mojeek's field name for brave too (same concept: did this run attempt to solve a served challenge), the one field name shared by two engines on purpose. This is what lets a later reader compare engines without a per-engine lookup table — do not add a new common-sounding key without adding it to every engine's `_diagnose`, and do not repurpose `marker` for a structural (non-text) signal. `openalex.py`/`scholar.py`'s diagnosis shape is deliberately narrower — no DOM fields at all (there is no DOM) — not a partial/broken implementation of the 7-engine shape.
- **Two fields exist ONLY on a diagnosis assembled by `search_web._engine_with_timing` from a cancelled/crashed engine, never on one an engine returns itself: `diagnosis_partial` (always `True` when present, never present otherwise — the one flag that tells a reader "every other field in this dict describes the state as of the last completed poll checkpoint, not a concluded outcome"; `containers_found: False` under a normal empty branch means the wait loop exhausted its own budget and never found anything, the SAME field under `diagnosis_partial: True` means only "not yet, as of the last checkpoint — the loop never got to finish, we do not know what the next cycle would have shown") and `elapsed_ms` (`int`, wall time in milliseconds from the top of that engine's own `search_with_reason` to the checkpoint that produced this snapshot — the answer to "how stale is this": a `containers_found: False` written at `elapsed_ms: 190` on a 6000ms-timeout run means something hung for the remaining ~5800ms with no further checkpoint reached, a `elapsed_ms: 5940` means the snapshot is close to current).** Both are populated by `document_status.py`'s `update_partial`, called from inside each of the 7 browser engines' own poll loop on every iteration — see that module's entry in `src/search/DOCS.md`. `diagnosis_partial`/`elapsed_ms` are never added to a normal return by any engine's own code; `_engine_with_timing` is the only writer of `diagnosis_partial`, `update_partial` is the only writer of `elapsed_ms`.
- Each browser engine's `_diagnose(tab)` (the DOM-fact half of the snapshot) is called fresh at each site that needs one (typically once per empty branch), no engine reuses a stale one — `brave.py` did until the marker-reflection fix (see `process-docs/marker_reflection/`): before that fix it took ONE `diag` snapshot immediately after navigation, before `_wait_for_results` ever ran, and reused it — potentially up to `MAX_WAIT_CYCLES × WAIT_INTERVAL` (6s) stale — for both the immediate PoW/CAPTCHA branch and the post-wait-failure branch. That immediate branch is gone: `_diagnose(tab)` now only ever runs after `_wait_for_results` has already resolved, exactly like every other browser engine in this package.
- **HTTP status (the real server response code) is captured via `document_status.py`, a CDP `Network.responseReceived` listener armed before each browser engine's first navigation — see that module's entry in `src/search/DOCS.md`.** It answers exactly the question the DOM-only snapshot (marker/title/url/readyState) cannot. Measured cost: `tab.enable_network_events()` (the one added CDP round trip, once per engine) averaged ~10ms across 8 fresh tabs (7-14ms range) — under 0.2% of the 6.0s per-engine watchdog, invisible against the hundreds-of-ms network jitter these engines already show call to call.
- **The EMPTY_* sub-statuses (`EMPTY_BLOCK`, `EMPTY_NO_CONTAINER`, `EMPTY_CONCURRENT_RACE`, `EMPTY_CONSENT`, `EMPTY_NO_RESULTS`) and every `_classify_diagnosis` (and scholar's inline captcha-form classification) were removed — they were verdicts guessed from a title/body keyword scan or a URL pattern-match, and the log now records the observation instead of the guess. A concrete case that motivated this: `roboter-bausatz.de Versandkosten versandkostenfrei ab` logged as `EMPTY_BLOCK` for mojeek purely because the query's substring `roboter` contains `robot`, one of mojeek's block keywords — indistinguishable from a genuine block by verdict alone, live-confirmed still true after the snapshot exists (`marker: "captcha"`) but now honestly labeled `status: "EMPTY"`.** Every engine now returns `reason=None` on every branch; `_engine_with_timing` maps that to the generic `EMPTY` status. Per-verdict mapping (the check performed branch by branch before deleting anything, per engine — all facts were already in the snapshot except two, added here): `EMPTY_BLOCK`/`EMPTY_CONSENT` (google) → `url`; `EMPTY_BLOCK` (duckduckgo) → `challenge_form`; `EMPTY_BLOCK` (mojeek/bing/startpage/brave/yandex) → `marker` (also `pow_link` for brave, `iframe_challenge` for startpage, `url` for yandex); `EMPTY_CONCURRENT_RACE` (all 7) → `ready_state`; `EMPTY_NO_CONTAINER` (all 7) → re-derivable as "none of the above", no field needed; `EMPTY_NO_RESULTS` (all 7) → **new field `containers_found`**, since neither `marker` nor `ready_state` could tell "wait succeeded, zero parsed" apart from "wait failed"; `EMPTY_BLOCK` (openalex, 429) → `http_status` (verified in code: `_fetch_results` returns the same `status_code` for 429 as diagnosis already carries); `EMPTY_BLOCK` (scholar, 30x redirect) → `http_status`; `EMPTY_BLOCK` (scholar, inline captcha form) → **new field `captcha_form`**, since that fact previously fed `_parse_response`'s verdict and nowhere else. `status.py` shrank from 17 to 10 constants — `OK`/`EMPTY`/`RATE_SKIP`/3×`TIMEOUT_*`/4×`ERROR_*` — the ones that describe our own runtime, never a guess about the remote side; the unused bare `TIMEOUT` (zero usages anywhere) and bare `ERROR` (one dev-script-only usage, never in `src/search/`) were dropped too, since `_classify_engine_exception` never produced either.
- **REMOVED 2026-09-09: every engine's own `search()` override, which wrapped `search_with_reason` in a `try`/`except Exception: logger.error(...); return []` — a code-standards violation (silently swallowing an error that affects business logic) per the Phase 4 control-flow review, user decision.** `search_web.py` never called `engine.search(...)` at all (only `search_with_reason`, both in `_run_engine_fanout`'s timed and untimed branches) — the only real callers were the offline dev scripts under `dev/search_pipeline/` and one test in `dev/tests/test_openalex_engine.py`. `search()` is now `BaseEngine`'s one concrete method (see `base.py`'s own entry above): a plain delegation to the now-abstract `search_with_reason`, no try/except. This is a dev-script/manual-testing convenience only — production code never needs it — and it must never grow a try/except again; an engine exception reaching a dev script via `search()` is the intended tripwire, not a regression to catch and hide.
- **REMOVED 2026-09-09: `_parse_results`'s `except (json.JSONDecodeError, TypeError): return []` handler in the six browser engines (`bing`/`brave`/`duckduckgo`/`google`/`startpage`/`yandex`) — user decision, Phase 4 control-flow review.** The handler dated from each engine's first commit (2026-04-07) with no supporting observation ever behind it: 0 `ERROR_PARSE` occurrences across 4566 logged engine records, and the value `json.loads` parses there is always this project's own `JSON.stringify` output from `_JS_PARSE`, never third-party data. A parse failure now propagates out of `_parse_results` through `search_with_reason` into `_engine_with_timing`, where `_classify_engine_exception` maps a `json.JSONDecodeError` to `ERROR_PARSE` (it is a `ValueError` subclass, already in that tuple) — a bare `TypeError` is NOT in `_classify_engine_exception`'s tuple and would fall to the generic `ERROR_OTHER` branch instead; this was left as-is, not extended, since no observed `TypeError` trigger exists either. Either way, a parse failure now surfaces as a real error status instead of silently masquerading as `EMPTY` (an empty results page). `_diagnose(tab)`'s own `json.loads(val)` try/except, left alone by that removal, was removed on 2026-09-24 (see the next entry).
- **REMOVED 2026-09-24: the `(KeyError, TypeError) -> None` handler in every browser engine's `_extract_value`, the `(json.JSONDecodeError, TypeError)` handler in every browser engine's `_diagnose`, and brave's two matching handlers in `_poll_state` and `_click_challenge_button` — Phase 4 control-flow review, owner decision, no replacement handler.** None of these triggers was ever observed: 0 `ERROR_PARSE` in 209 `engine_run` records, and `cli.log` never records CDP `Runtime.evaluate` responses, so a script that returned no value could not be seen either. Per the fallback/tripwire standard an unobserved condition goes to the tripwire: a CDP result without `value` (script threw, execution context destroyed) now raises `KeyError`, a non-dict result `TypeError`, unparseable engine JSON `json.JSONDecodeError`. All three leave `search_with_reason` and are turned into a visible status by `_engine_with_timing` (`KeyError`/`JSONDecodeError` -> `ERROR_PARSE`; a bare `TypeError` -> `ERROR_OTHER`, same caveat as the 2026-09-09 entries). Behaviour change to expect: a transient mid-navigation blip inside a poll loop (`_wait_for_results` and its siblings; startpage polls across its form-submit navigation) now ends the engine with `ERROR_PARSE` instead of silently polling on. If that shows up in `query_log.jsonl`, read its `drop_reason` before adding anything back. Guard: `dev/tests/test_search_control_flow_removals.py`.
- **REMOVED 2026-09-09: `bing.py::_clean_url`'s decode-failure passthrough of the raw tracking URL — user decision, Phase 4 control-flow review.** The `try/except Exception: return href` around `base64.urlsafe_b64decode(...).decode(...)` was added 2026-07-21 as a precaution when Bing was first wired, with no observation behind it since: 0 `bing.com/ck/a` URLs in the production query log, 0 in 400 cache files. A decode failure now propagates out of `_clean_url` through `_build_results` → `_parse_results` → `search_with_reason` into `_engine_with_timing`'s own `_classify_engine_exception` — both realistic exception types land on `ERROR_PARSE` already, no tuple extension needed: `binascii.Error` (malformed base64 padding/alphabet) and `UnicodeDecodeError` (bad UTF-8 after decode) are both `ValueError` subclasses. The `if not href: return ""` and `if not u: return href` branches immediately above stay — both are input-shape handling (a genuinely empty href, or a direct unwrapped href that's already the destination), not a fallback.
- **google's diagnosis carries `goto_resolution: {found, resolved, dropped, reasons}` on every branch that reaches `_resolve_urls` (success included), and one WARNING line in `cli.log` whenever `dropped > 0`.** `found` is the count of goto-href results parsed from the page after the `max_results` slice; containers `_JS_PARSE` skips for lacking an anchor/title are not counted. `reasons` keys: `timeout`, `request_error` (any other curl_cffi `RequestException`), `non_302_<status>`, `no_location`, `relative_location`, `duplicate_destination`. Status stays `OK` when results survive; read `goto_resolution` to tell a thinned page from a genuine one.
- 2026-09-24 Phase 5: (a) the google consent branch (`consent.google.com` redirect / inline consent text, `_JS_CONSENT`, `_has_inline_consent`, `_handle_consent`) was removed - the SOCS cookie is injected up front and 0 consent occurrences exist in `cli.log*`; a consent page now falls into the no-containers diagnosis (`url` shows it). (b) The selector alternatives in the `_JS_PARSE` scripts of google (anchor 0-4, snippet 0-2), bing (caption 0-1), brave (title 0-1, snippet 0-1) and yandex (snippet 0-1) now return `sel` per item; `_parse_results` returns `(results, selector_hits)` and the success branch puts `selector_hits` (`{field: {index: count}}`, see `src/search/selector_hits.py`) into the diagnosis. `sel` is stripped in `_build_results`, so `SearchResult` and CLI output are unchanged. Equivalence of old and new JS on fixture HTML: `dev/search_pipeline/selector_js_equivalence_check.py`.

~~~~

### Archive: src/news/DOCS.md

~~~~markdown
# src/news/

## Role

Multi-platform news ingestion pipeline, run as `python -m src.news --source <platform>`. Discovers articles, dedups against the raw corpus, scrapes raw markdown/HTML into `data/news/{name}/raw/`. For The Block (proxy_pool engine) the pipeline also runs an in-pipe clean-pass that writes cleaned articles into the RAG collection dir. Indexing stays fully decoupled — no `rag-cli index` call in any pipe path. Touch this package to add a news source or change pipeline orchestration; the generic scrape engines live in `engine/`, platform implementations in `platforms/`. Do NOT import from `src/crawler/` or `src/scraper/` — this package is self-contained.

## Public Interface

`__init__.py` is empty; the package runs as a module (`python -m src.news` → `__main__.py`). Direct async entry: `run_pipeline(platform)`, `run_discover_only(platform)`, `run_scrape_only(platform, year=…, limit=…)` in pipeline.py — import path unchanged across the 2026-08-20 module split (pipeline.py stays the entry module; `pipeline_support.py`/`clean_pass.py` are internal-only, no external caller imports from them except `dev/tests/test_theblock_clean_pass.py` → `clean_pass._run_clean_pass`).

## Flow

`__main__` parses args, imports the platform module (side-effect registers it), looks it up via `registry.get`, and calls one of pipeline's three entries. `run_pipeline`: discover → dedup(raw) → scrape → raw persist (+ clean-pass for proxy_pool/TheBlock). `run_scrape_only`: date-filtered backfill, discover-free, dispatched on `platform.scrape_engine`. `run_discover_only`: discover + persist only. Scrape dispatch key is `platform.scrape_engine` ∈ {browser, proxy_pool, proxy_riding}.

## Modules

### pipeline.py (364 LOC)

**Purpose:** Entry module — the 3 CLI-facing async orchestrators (`run_pipeline`, `run_scrape_only`, `run_discover_only`) plus their per-engine arm helpers, dispatching on `platform.scrape_engine`. `run_scrape_only` and `_run_pipeline_proxy_pool` were each split into single-responsibility helpers to stay under the 50-LOC function threshold (pure extraction, same behavior/log output — see Gotchas): `run_scrape_only` → `_scrape_only_preamble` (logging setup, `job_id`/`filter_desc`, internet + `load_scrape_entries`-capability precondition checks, both `sys.exit(1)` on failure); `_run_pipeline_proxy_pool` → one helper per STAGE block (`_stage_discover_proxy_pool`, `_stage_dedup_proxy_pool`, `_stage_scrape_proxy_pool`), with the discover stage returning `None` to signal "abort, already logged+marked" and the dedup stage returning the plain (possibly empty) `new_entries` list so the caller's own `if not new_entries: ...; return False` and the surrounding `try/finally`'s `len(new_entries)` read stay exactly as before.
**Reads:** `data/news/{name}/raw/`, `discover/` (dead_urls.txt, failed_urls.txt, per-year shards, master_urls.txt).
**Writes:** `raw/{hash}.{md,html}`, `raw/manifest.jsonl`, `discover/` block-lists, `scrape_jobs/{job_id}/` reports (via reporters); delegates marker/snapshot/master-list writes to `pipeline_support.py`, clean-pass writes to `clean_pass.py`.
**Called by:** `__main__.py`.
**Calls out:** `platform` (Platform); `engine.dedup` (filter_new_entries); `engine.scrape` (scrape_entries, RegwallGuardError); `engine.proxy_pool` (box_lock, Janitor, AcquireLogger, scrape_entries_proxy); `engine.scrape_job` (scrape_chunks_raw, _append_to_raw_manifest, _update_blocked_urls); `engine.browser_reporter` (write_scrape_report); `engine.proxy_riding` (scrape_entries_riding, RidingScrapeConfig, write_riding_report); `pipeline_support.py` (run bookkeeping + `PROJECT_ROOT`/`LOG_DIR`); `clean_pass.py` (`_run_clean_pass`).

### pipeline_support.py (83 LOC)

**Purpose:** Generic run bookkeeping shared by all 3 `pipeline.py` orchestrators — logging setup, connectivity precondition, and the 3 state-writer helpers (master URL list, discover JSON snapshot, last-run marker); owns `PROJECT_ROOT`/`LOG_DIR`.
**Reads:** `platform.precondition_url` (via `urllib`); existing `master_urls.txt` (set-union merge).
**Writes:** `LOG_DIR/news_{name}_{date}.log`, `LOG_DIR/news_{name}_last_run.txt`, `discover/master_urls.txt`, `discover/discover_{ts}.json`.
**Called by:** `pipeline.py` (all 3 orchestrators + `_run_pipeline_proxy_pool`/`_run_pipeline_browser`).
**Calls out:** none (stdlib `logging`, `urllib.request`, `json`).

### clean_pass.py (48 LOC)

**Purpose:** The proxy_pool/TheBlock clean-pass stage (`_run_clean_pass`) — reads `raw/{hash}.md`, calls `platform.cleanup()`, writes cleaned articles into the RAG collection dir. As of 2026-09-09, `pub_date_str` is no longer defined here — this module imports the single surviving copy from `src.news.engine.dedup` (see that module's own entry and Gotchas).
**Reads:** `raw_dir/{hash}.md` for each ok entry; existing `clean/bodyless_urls.txt` (set-union merge).
**Writes:** `collection_dir/theblock__{pubdate}__{hash}.md` per cleaned entry; `raw_dir.parent/clean/bodyless_urls.txt` (body-less URLs, set-union, sorted); progress logged every 200 entries.
**Called by:** `pipeline.py:_persist_proxy_pool_results` (proxy_pool arm, only when `n_ok > 0`).
**Calls out:** `src.news.engine.dedup` (`pub_date_str`).

### __main__.py (155 LOC)

**Purpose:** argparse entry point. Flags: `--source`, `--skip-index` (no-op, CLI compat), `--timeframe`, `--discover-only`, `--scrape-only` (+ `--year/--from/--to/--limit/--browsers/--slots/--cooldown-policy/--page-timeout`). Imports the platform modules for side-effect registration, resolves via `registry.get`, dispatches to the matching pipeline entry. When `--timeframe` is not `delta` and not `--discover-only`, auto-forces `skip_index=True` and prints the manual index reminder. `_add_core_args` was split into `_add_run_mode_args` (`--source`/`--skip-index`/`--timeframe`/`--discover-only`/`--scrape-only`) and `_add_date_filter_args` (`--year`/`--from`/`--to`/`--limit`), called in that order from `_add_core_args` — `add_argument` call order (and therefore `--help` output) is unchanged; verified byte-identical against the pre-split output.
**Reads:** CLI args.
**Writes:** stdout.
**Called by:** the `python -m src.news` entry point.
**Calls out:** `platforms.coindesk`, `platforms.theblock` (side-effect register); `registry` (get); `pipeline` (run_pipeline, run_discover_only, run_scrape_only).

### platform.py (35 LOC)

**Purpose:** The extension seam. Defines the `Platform` Protocol (name, collection, precondition_url, regwall_signals, scrape_engine, scrape_config, proxy_scrape_config; `discover()` + `cleanup()`), plus the `ScrapeConfig` and `ProxyScrapeConfig` dataclasses. `scrape_engine` ∈ {browser, proxy_pool, proxy_riding} is the pipeline dispatch key. Optional attrs (`riding_scrape_config`, `timeframe`, `uses_master_list`) are consumed via `getattr` in pipeline.py, deliberately NOT in the Protocol.
**Called by:** `pipeline.py`, `registry.py`, `platforms/*`, `engine/*`.
**Calls out:** none (stdlib `typing`, `dataclasses`).

### registry.py (17 LOC)

**Purpose:** Name → Platform registry. `register(instance)` (called at platform-module import) and `get(name)` (called by `__main__`).
**Reads / Writes:** in-memory registry dict.
**Called by:** `__main__.py` (get); `platforms/*/__init__.py` (register).
**Calls out:** `platform` (Platform).

## State

`registry`'s in-memory name→Platform dict — populated at platform-module import (side-effect), read by `__main__`. On disk, per-platform corpus under `data/news/{name}/` (raw/, discover/, clean/, scrape_jobs/) is the durable state; `raw/manifest.jsonl` + the discover block-lists (dead/failed/regwall/empty) drive dedup and make re-runs resumable.

## Gotchas

- To add a platform: create `platforms/<name>/__init__.py` defining a `Platform` class that calls `register(instance)` at import, then import that module in `__main__.py` for side-effect registration.
- `--skip-index` is accepted but a no-op — no path ever runs `rag-cli index`.
- `Platform.regwall_signals = []` disables the regwall guard entirely (`engine/scrape.py:_check_regwall_guard` short-circuits on falsy) — a deliberate opt-out, not "no signals configured yet".
- `_run_pipeline_proxy_pool`: `start_job` runs BEFORE `AcquireLogger` construction so `Janitor` wipes `log_dir` before the JSONL is opened — reordering truncates the run's own JSONL log.
- proxy_riding (CoinDesk current) writes raw `.html`; browser/proxy_pool write raw `.md`. `filter_new_entries` takes `raw_ext` accordingly.
- `run_scrape_only` reporters are engine-specific: `write_riding_report` for proxy_riding, `write_scrape_report` for browser. They are NOT interchangeable — the browser reporter needs `t_chunk_start`/`elapsed_s` fields absent from riding manifests and would crash.
- Both normal completion and the stall-abort path write the job report to the same `scrape_jobs/{job_id}/` dir; the platform root is never written to by the report step.
- `_run_pipeline_browser`'s `RegwallGuardError` recovery: `scrape_entries` raising mid-run means the
  guard tripped (too many regwalls) — the exception's `.manifest` (partial, already-persisted
  results) is used AS the final manifest, not discarded; the arm proceeds to persist it normally
  (not treated as a hard failure — `n_ok`/raw files up to the abort point are kept).
- 2026-09-24 Phase 5: `_run_clean_pass` raises `FileNotFoundError` when a manifest entry has no raw file (was: warning + skip, stats no longer added up).

~~~~

### Archive: src/news/engine/DOCS.md

~~~~markdown
# src/news/engine/

## Role

Generic, platform-agnostic pipeline engine modules. Called by `pipeline.py`; no platform-specific
logic lives here. All modules accept platform parameters explicitly (no hardcoded source names).

`pipeline.py` dispatches on `platform.scrape_engine`: `"browser"` → `scrape.py` (via
`scrape_chunks_raw` in `run_scrape_only`); `"proxy_pool"` → `proxy_pool/scrape.py` (via
`run_pipeline`); `"proxy_riding"` → `proxy_riding/scrape.py` (via `run_scrape_only`, CoinDesk
backfill path — chunk-bypass, full entry set, returns `(manifest, state)`). All three engines wired.
The two sub-engines live in their own subpackages with own-level DOCS.md: `proxy_pool/` (entry
`scrape_entries_proxy`) and `proxy_riding/` (entry `scrape_entries_riding`).

## Modules

### scrape.py (163 LOC)

**Purpose:** Browser-engine scraper — fresh `AsyncWebCrawler` per URL, Scrapy gate pacing, regwall guard. Active when `platform.scrape_engine == "browser"`.
**Reads:** entries list (in-memory), ScrapeConfig, regwall_signals list.
**Writes:** `{hash}.md` (BODY ONLY, no frontmatter) to output_dir (raw_dir in all call paths).
**Called by:** `pipeline.py:_run_pipeline_browser`, `scrape_job.py:_scrape_one_chunk`.
**Calls out:** `crawl4ai` (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig).

### dedup.py (54 LOC)

**Purpose:** Filter discover entries to those not yet in the raw corpus by checking file existence; optionally exclude known-failure URLs permanently. As of 2026-09-09, `pub_date_str` is the ONE surviving definition (see Gotchas) — used internally by `filter_new_entries`'s `mode="pubdate"` branch and imported directly by `clean_pass.py`; returns `"unknown"` when no date is found.
**Reads:** entries list (in-memory), dir (filesystem), source name, mode, optional exclusion set.
**Writes:** nothing (pure filter).
**Called by:** `pipeline.py:_run_pipeline_proxy_pool` / `_run_pipeline_browser` (mode=`"raw"`), `pipeline.py:run_scrape_only` (mode=`"raw"`); `clean_pass.py` (`pub_date_str` only).
**Calls out:** stdlib only.

### scrape_job.py (104 LOC)

**Purpose:** Raw-only chunked scrape orchestration for `run_scrape_only()` and shared raw-persist helpers.
**Reads:** chunks (list of entry lists), platform config.
**Writes:** `{hash}.md` into raw_dir per ok entry; appends to `raw/manifest.jsonl`; updates `regwall_urls.txt` / `empty_urls.txt`.
**Called by:** `pipeline.py:_run_scrape_only_browser` (`scrape_chunks_raw`); `pipeline.py:_persist_proxy_pool_results` / `_run_pipeline_browser` (`_append_to_raw_manifest`, `_update_blocked_urls`).
**Calls out:** `scrape.py:scrape_entries`.

### browser_reporter.py (196 LOC)

**Purpose:** Per-job report writer for browser-engine scrape jobs. Produces `job.md` + `cumulative.png` from `job_records`.
**Reads:** `job_records` (in-memory list from `scrape_chunks_raw`), `t_job_start`.
**Writes:** `{job_dir}/job.md` (counts, regwall rate, throughput, backfill projection, char-count percentiles p10–p95, failure table); `{job_dir}/cumulative.png` (step-plot of cumulative ok count vs elapsed seconds).
**Called by:** `pipeline.py:_run_scrape_only_browser`.
**Calls out:** `matplotlib` (lazy import inside `_write_plot`), `statistics` (stdlib).

## Gotchas

- `scrape.py` raises `RegwallGuardError` (not sys.exit) at regwall fraction ≥ `REGWALL_FAIL_THRESHOLD` (0.20); the exception's `.manifest` carries the full per-entry manifest including ok entries written before abort — callers persist aborted-run data from it.
- `dedup.py`'s `mode="raw"` takes `raw_ext` — `".html"` for the proxy_riding path, default `".md"` elsewhere.
- **2026-09-09: `pub_date_str` consolidated into `dedup.py` with the `unknown` fallback — user decision, Phase 4 control-flow review.** `clean_pass.py` used to define its own byte-identical copy, differing only in the final fallback (`"unknown"` vs `dedup.py`'s own `""`). `clean_pass.py` built its output filename as `theblock__{pubdate}__{h}.md` using its own `"unknown"`; `dedup.py`'s `mode="pubdate"` branch built its lookup filename the same way using its own `""` — for a date-less entry the two names differed (`theblock__unknown__{h}.md` vs `theblock____{h}.md`), so the pubdate-mode dedup lookup could never find what `clean_pass` actually wrote. `mode="pubdate"` is currently unreached in production (every `pipeline.py` call site passes `mode="raw"`), so this never manifested as an observed bug, but the divergence itself was real and would have surfaced the moment anything called `filter_new_entries` without an explicit `mode=`. `clean_pass.py` now imports `pub_date_str` from here; its own copy and `DATE_RE` are gone.
- 2026-09-24 Phase 5: `scrape.py` no longer uses `return_exceptions=True`; `_fetch_one` already turns every fetch exception into a `failed` manifest entry, the dead `_collect_manifest` branch was deleted.

~~~~

### Archive: src/news/engine/proxy_pool/DOCS.md

~~~~markdown
# src/news/engine/proxy_pool/

## Role

Generic proxy-rotation scrape engine. Called by `pipeline.py` via `scrape_entries_proxy()` when
`platform.scrape_engine == "proxy_pool"`. Manages a rotating pool of HTTP/SOCKS4/SOCKS5 proxies
with sustained concurrent fetching via curl_cffi chrome impersonation, 60-min pool refresh,
2-strikes lifecycle, per-job lock, and audit trail.

No platform-specific logic lives here — target URLs, content type, and pool provider are all
caller-supplied. Touch this package when changing rotation mechanics, pool loader sources, or
the job lifecycle (lock, janitor). Do NOT touch when adding a browser-engine platform.

## Public Interface

`__init__.py` is empty — callers import modules directly.

- `scrape_entries_proxy(entries, output_dir, proxy_cfg, logger)` in `scrape.py` — sole entry point for `pipeline.py`; `logger` is a caller-supplied `AcquireLogger`.
- `load_backfill_pool()` in `pool_loaders.py` — used by platform `ProxyScrapeConfig.pool_provider`; returns `(pool, sources)` where `sources` is `[{url, ok, count}, …]` per fetched URL.

## Flow

1. `pipeline.py:_run_pipeline_proxy_pool` acquires `box_lock`, instantiates `Janitor` + `AcquireLogger`; calls `start_job` (wipes log_dir) before opening the JSONL. The unified job spans discover + scrape: discovery proxy fetches in `theblock/discover.py:_fetch_xml` call `logger.record_attempt`; article scrape fetches call it via `run_loop`.
2. `scrape_entries_proxy` receives the caller-supplied `logger` + instantiates `PersistentCooldownManager`; delegates to `run_loop`.
3. `run_loop` sustains concurrent rotation: `pool_provider()` → `build_active_buffer` → batches of `(proxy, URL)` → `fetch_url` via `ThreadPoolExecutor`.
4. Per ok fetch: `content_handler` decodes bytes → writes `output_dir/{hash}.md`.
5. `logger` streams all events to JSONL (discovery + scrape combined); `pipeline.py:_run_pipeline_proxy_pool` calls `logger.close()` + `janitor.end_job` in `finally` — fires on all exit paths including 0-entries and 0-new-after-dedup early returns. `end_job` derives `job.md` + `cumulative_hits.png`.
6. `_build_manifest` maps `(done, dead, gap)` → `[{url, hash, status, file, char_count, error}]` matching the browser engine manifest contract.

## Modules

### scrape.py (81 LOC)

**Purpose:** Proxy-pool scrape entry point — wires `run_loop` with a caller-supplied `AcquireLogger`; returns pipeline manifest. Job lifecycle (box_lock, Janitor, AcquireLogger) is owned by `pipeline.py:_run_pipeline_proxy_pool`.
**Reads:** `entries` list (in-memory) + `proxy_cfg.pool_provider()`.
**Writes:** `output_dir/{url_hash}.md` per ok fetch.
**Called by:** `pipeline.py:_run_pipeline_proxy_pool`.
**Calls out:** `loop.py`, `cooldown.py`, `logger.py` (type reference only).

---

### loop.py (296 LOC)

**Purpose:** Sustained concurrent rotation loop — 60-min pool refresh, 2-strikes lifecycle, tail-race, wait-on-exhaustion, stall-terminate. `run_loop` and `_execute_batch` were each split into single-responsibility helpers to stay under the 50-LOC function threshold (pure extraction, same behavior/log output/`time.monotonic()` call count — see Gotchas): `run_loop` → `_check_stall` (stall-log + boolean signal), `_maybe_refresh_and_refill` (refresh-if-due + refill-if-under-buffer_size, returns rebound `pool`/`buf`/`last_refresh`), `_run_batch_cycle` (consume batch off queue → `_execute_batch` → requeue failures, returns rebound `buf`/`last_progress`); `_execute_batch` → `_apply_future_outcome` (the per-future ok/dead/other branch, returns rebound `buf`/`last_progress` since one is conditionally reassigned and the other conditionally rebound on proxy-burn).
**Reads:** `pool_provider()` callback (returns `(pool, sources)`) + target URL list (in-memory).
**Writes:** delegates state to `AcquireLogger` + `PersistentCooldownManager`; calls `content_handler` per ok fetch. Returns `(done, dead, gap)`. After each `pool_provider()` call: `record_pool_refresh(len(pool))` then `record_pool_source(url, ok, count)` per source.
**Called by:** `scrape.py:scrape_entries_proxy`.
**Calls out:** `fetch.py`, `cooldown.py`, `logger.py`, `buffer.py`.

---

### fetch.py (37 LOC)

**Purpose:** curl_cffi chrome-impersonating HTTP fetch primitive + content-type gate (`"html"` | `"xml"`).
**Reads:** remote URL via curl_cffi Session (routed through proxy).
**Writes:** nothing — returns `(status, content)`: `"ok"` — valid content fetched, `content` is raw
bytes; `"dead"` — origin returned 404/410 (proxy worked, URL is gone), `content` is `b""`; `"fail"` —
connection error, timeout, CF block, or wrong-format content, `content` is `b""`.
**Called by:** `loop.py:run_loop`; `theblock/discover.py:_fetch_xml` (proxy fallback during discovery).
**Calls out:** `curl_cffi`.

---

### cooldown.py (37 LOC)

**Purpose:** In-memory per-job cooldown tracking — clean slate per instantiation, 60-min burn window.
**Reads:** nothing (in-memory only).
**Writes:** nothing.
**Called by:** `buffer.py`, `loop.py`, `scrape.py`.
**Calls out:** `proxy_key.py:proxy_key`.

---

### buffer.py (32 LOC)

**Purpose:** Active-buffer helpers — `build_active_buffer`, `refill_buffer`; holds `BUFFER_SIZE = 1280`
(10× `DEFAULT_CONCURRENCY`), `DEFAULT_CONCURRENCY = 128` (concurrent `(proxy, URL)` pairs per batch —
also `ProxyScrapeConfig`'s `concurrency`/`buffer_size` defaults).
**Reads:** proxy pool + `PersistentCooldownManager` eligibility (in-memory).
**Writes:** returns new buffer lists (pure — no mutation of inputs).
**Called by:** `loop.py:run_loop`.
**Calls out:** `cooldown.py:PersistentCooldownManager`.

---

### logger.py (52 LOC)

**Purpose:** Streams per-fetch events to JSONL (line-buffered, kill-safe). Stats derived by `janitor.end_job`.
**Reads:** events pushed via `record_attempt` / `record_pool_refresh` / `record_pool_source`.
**Writes:** `{platform_dir}/proxy_pool_logs/acquire_events_{ts}.jsonl` (streamed, line-buffered). Event types: `{proxy_key, ts, url, result}` (attempt), `{event:"pool_refresh", size, ts}`, `{event:"pool_source", url, ok, count, ts}`.
**Called by:** `pipeline.py:_run_pipeline_proxy_pool` (instantiates + closes); `loop.py` (`record_attempt` + `record_pool_refresh` + `record_pool_source` per pool load); `theblock/discover.py:_fetch_xml` (`record_attempt` per discovery proxy fetch).
**Calls out:** `proxy_key.py:proxy_key`.

---

### janitor.py (264 LOC)

**Purpose:** Job lifecycle — `Janitor(jobs_dir, log_dir, report_dir)` wipes transient dirs at start and derives `job.md` (60-min window stats + pool source breakdown) + `cumulative_hits.png` from the JSONL at end.
**Reads:** JSONL at `jsonl_path` passed to `end_job`.
**Writes:** `{jobs_dir}/{job_id}/job.md`, `cumulative_hits.png`; wipes `log_dir` + `report_dir` at start and end.
**Called by:** `pipeline.py:_run_pipeline_proxy_pool`.
**Calls out:** `matplotlib.pyplot` (lazy import in `_write_plot`), `statistics` (stdlib).

---

### box_lock.py (97 LOC)

**Purpose:** System-wide single-job flock — `acquire(job, target, lock_name="proxy_pool")`; crash-safe (kernel releases flock on process death). Raises `LockBusyError` on contention.
**Reads:** `~/.websearch-locks/{lock_name}.lock` sidecar (in `cleanup_stale` + busy message).
**Writes:** `~/.websearch-locks/{lock_name}.{flock,lock}`.
**Called by:** `pipeline.py:_run_pipeline_proxy_pool`.
**Calls out:** `fcntl`, `os` (stdlib).

---

### proxy_key.py (14 LOC)

**Purpose:** Canonical proxy key — `proxy_key(proto, host_port) → "proto://host:port"` (auth stripped if present).
**Reads:** nothing.
**Writes:** nothing (pure).
**Called by:** `cooldown.py`, `logger.py`, `pool_loaders.py`.
**Calls out:** stdlib only.

---

### pool_retry.py (20 LOC)

**Purpose:** Bounded exponential-backoff retry for httpx fetches — `fetch_with_retry(fn)` calls `fn()` up to 5 times, sleeping 1/2/4/8s between attempts (~15s total backoff; ~90s worst-case combined with `FETCH_TIMEOUT=15` per attempt); re-raises last exception on final failure.
**Reads:** nothing.
**Writes:** nothing (pure control-flow wrapper).
**Called by:** `monosans_loader.py:_fetch_json`, `pool_loaders.py:_fetch_bare_txt` / `_fetch_roosterkid` / `_fetch_proxifly`.
**Calls out:** stdlib only.

---

### pool_loaders.py (184 LOC)

**Purpose:** 18 proxy-source loaders + `load_backfill_pool()` — fetches all sources per-URL with retry and per-source failure isolation; returns `(pool, sources)` where `pool` is deduped `[(protocol, host:port)]` (~32k unique) and `sources` is `[{url, ok, count}, …]` one entry per URL.
**Reads:** 44 GitHub raw proxy-list URLs via httpx (each wrapped in `fetch_with_retry`).
**Writes:** nothing.
**Called by:** `theblock/config.py` (via `ProxyScrapeConfig.pool_provider`); `theblock/discover.py:_fetch_xml` (fallback pool, unpacks `pool, _ = load_backfill_pool()`).
**Calls out:** `httpx`, `pool_retry.py:fetch_with_retry`, `monosans_loader.py:load_monosans_proxies`, `proxy_key.py:proxy_key`.

---

### monosans_loader.py (38 LOC)

**Purpose:** Fetch monosans/proxy-list JSON; return `[(protocol, host:port)]` in source order. `_fetch_json` is wrapped with `fetch_with_retry` — transient network errors ride out automatically.
**Reads:** monosans GitHub raw JSON URL via httpx.
**Writes:** nothing.
**Called by:** `pool_loaders.py:load_backfill_pool` (via `_try_source`).
**Calls out:** `httpx`, `pool_retry.py:fetch_with_retry`.

## Gotchas

- `pool_loaders.py` (190 LOC after the 2026-08-20 dead-code removal below) — no extractable concern exists in `load_backfill_pool` (flat list of `_try_source(...)` calls sharing one `_merge_dedup` utility). Do not split. `load_backfill_pool` itself (56 code lines) is a flat ordered sequence — the call ORDER affects `sources`' reported order (and, via `_merge_dedup`, which source's entry wins on a dup) — confirmed 2026-08-20, left un-extracted rather than risk that order under a data-driven loop.
- `pool_loaders.py`'s 17 per-source `load_X_proxies()` functions (`load_curated_proxies` through
  `load_murongpig_proxies`) were REMOVED 2026-08-20 — dead within `src/` (`load_backfill_pool` calls
  `_try_source` + lambdas directly, never these wrappers); confirmed via repo-wide grep including
  `dev/` before removal. The only surviving same-named functions are a separate, non-importing copy
  in `dev/news_pipeline/theblock/curated_sources.py` — untouched, out of scope.
- `janitor.end_job` calls `jsonl_path.unlink()` then wipes `log_dir`. Interrupt between these two orphans the JSONL in `log_dir`. Non-critical: `start_job` wipes `log_dir` at the next run.
- `box_lock`: SIGTERM kills Python before `finally` runs → sidecar stays; kernel releases flock. Next `acquire()` recovers via `cleanup_stale()` (dead-PID detection).
- `_sleep` in `loop.py` AND `pool_retry.py` are both module aliases (`_sleep = time.sleep`) — patch the alias in the target module in tests, not `time.sleep` directly. For retry tests patch `pool_retry._sleep`; for exhaustion-sleep tests patch `loop._sleep`.
- `loop.py:_apply_future_outcome`'s `last_progress` reassignment (called once per future from
  `_execute_batch`'s `as_completed` loop) MUST call `time.monotonic()` once per done/dead URL
  resolution (not once per batch) — `dev/tests/test_proxy_pool.py`'s `test_run_loop_refresh_*`
  tests patch `loop.time` wholesale and drive it with a pre-counted `side_effect` sequence keyed to
  the exact call count and ORDER, across every `time.monotonic()` call anywhere in `loop.py`
  (module-level patch, so `run_loop`'s own startup/per-iteration calls and `_maybe_refresh_and_refill`'s
  refresh-tick call share the same sequence). Collapsing to a single post-batch call, or moving a
  call earlier/later relative to any other `time.monotonic()` call in the file, desyncs that
  sequence. Don't "simplify" this without re-checking those tests — confirmed safe as of the
  2026-09-07 function-size split (the per-future call moved into `_apply_future_outcome` but fires
  at the exact same point in execution order; both `test_run_loop_refresh_*` tests still pass
  unchanged).
- 2026-09-24 Phase 5: `fetch_url` returns `(status, content, reason)` and catches only curl_cffi `RequestException` (reason = exception class name; `http_<code>`; `content_marker_missing`); any other exception propagates. `AcquireLogger.record_attempt` persists `reason`, `record_pool_source` persists `error` (exception class name from `_try_source`).

~~~~

### Archive: src/news/engine/proxy_riding/DOCS.md

~~~~markdown
# src/news/engine/proxy_riding/

## Role

Third scrape engine: browser + rotating proxies. Purpose: defeat CoinDesk's IP-rate regwall for the
61k article-body backfill. Each URL gets a fresh crawl4ai browser context bound to a distinct proxy;
the proxy is burned after `burn_threshold` regwall hits or `FAIL_THRESHOLD` (2) failed/empty strikes
and a new one is picked from the shuffled pool. A timer-based asyncio watchdog (`_watchdog`) runs
independently of the slot tasks and hard-aborts via `os._exit(1)` if no progress occurs for
`stall_timeout_s` seconds — immune to wedged Playwright I/O.

**Active as CoinDesk's `run_scrape_only` path.** `platform.scrape_engine == "proxy_riding"` dispatched
in `pipeline.py:run_scrape_only`; `RidingScrapeConfig` consumed via `getattr` (not in Protocol);
`filter_new_entries` raw_ext reconciliation done (`.html` for riding path).

Touch this package when changing proxy-riding engine behaviour. Do NOT touch `engine/scrape.py` or
`engine/proxy_pool/` — those engines are strictly independent.

## Public Interface

`__init__.py` is empty. Entry paths:

- `scrape_entries_riding(entries, output_dir, riding_cfg, job_dir)` in `scrape.py` — async; called by
  `pipeline.py:_run_scrape_only_riding`. Returns `tuple[list[dict], RiderState]`: manifest
  `[{url, hash, status, file, char_count, error}]` + full rider state (for `write_riding_report`).
  `job_dir` is threaded to the watchdog so stall-abort writes land in `scrape_jobs/{job_id}/` (same as
  normal completion), not the platform root.
- `RidingScrapeConfig` in `scrape.py` — dataclass with production defaults
  (`n_browsers=4, n_slots=64, stall_timeout_s=300.0, burn_threshold=2, page_timeout_ms=8_000`).
- `write_riding_report(state, job_dir, t_job_start)` in `reporter.py` — called by
  `pipeline.py:_run_scrape_only_riding` (normal completion) and by `abort.py`'s `_abort_stall` / `_abort_done` /
  `_abort_interrupted` (late import, abort paths).
- `run_riding_pool(url_queue, proxy_pool, cooldown_mgr, output_dir, job_dir, target_urls, …)` in
  `rider.py` — async; called by `scrape_entries_riding`. Stable entry point — this import path does
  not change even as the package's internals are split across modules.
- `RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`, `RAW_SUBDIR` defined in `state.py`;
  re-imported (not re-defined) into `rider.py` so `rider.RiderState` etc. still resolve for existing
  callers.

## Flow

1. `scrape_entries_riding` builds URL queue from entries, loads pool via `load_backfill_pool()`,
   filters to `{"http","socks5"}`, shuffles, constructs `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`.
2. `run_riding_pool` spawns B `AsyncWebCrawler` instances + N slot tasks + 1 watchdog task.
3. Each slot draws a proxy from the shuffled pool (cursor-atomic under `proxy_lock`), rides URLs
   until burn_threshold regwall or FAIL_THRESHOLD failed/empty, then rotates to the next proxy.
   **Tail-race:** when `url_queue` is empty (unresolved URLs < n_slots), slots immediately race an
   open URL (`sorted(target_urls − done_urls)[slot_id % len]`) with their current proxy — no 10 s
   wait. `asyncio.QueueEmpty` → race path; `asyncio.Queue.get_nowait()` replaces `wait_for(…, 10s)`.
4. Ok fetches write `raw/{hash}.html` guarded by first-writer check (`done_urls`); dup-race arrivals
   are discarded without write or n_ok increment. State accumulates `job_records` + `ride_records`.
5. Termination: `all_resolved = len(done_urls) >= len(target_urls)` (not queue-empty + in_flight==0).
   `state.termination` transitions from `"running"` → one of `"all-done"` | `"stall"` |
   `"pool-exhausted"` | `"interrupted"` (signal abort).
6. `scrape_entries_riding` maps `state.job_records` → manifest via `_build_manifest`.

## Modules

### cooldown.py (83 LOC)

**Purpose:** Riding-specific proxy cooldown manager (`RidingCooldownManager`, isolated from the theblock-shared `proxy_pool/cooldown.py`) with two per-run policies via `RidingScrapeConfig.cooldown_policy` — `"fixed"` (60-min flat) and `"exp"` (full-jitter backoff, reset on productive ride).
**Reads:** `_burned_at` / `_next_eligible` / `_failed_attempts` (in-memory dicts keyed by `proxy_key`).
**Writes:** same dicts on `mark_burned(proto, hp, ride_ok=0)`.
**Called by:** `rider.py:_finalize_ride` (via `state.cooldown_mgr.mark_burned`);
`rider.py:_next_proxy` (via `state.cooldown_mgr.eligible_candidates`);
`rider.py:_watchdog` (via `state.cooldown_mgr.eligible_candidates` + `cooldown_count`);
`scrape.py:scrape_entries_riding` (instantiation: `RidingCooldownManager(policy=riding_cfg.cooldown_policy)`);
`reporter.py:_write_md` (via `state.cooldown_mgr.policy`).
**Calls out:** `src.news.engine.proxy_pool.proxy_key.proxy_key`.

---

### state.py (87 LOC)

**Purpose:** Shared riding dataclasses (`RiderState`, `JobRecord`, `RideRecord`) + calibrated constants — the one canonical import source for every other module and the dev/ tests.
**Reads:** n/a (data-shape module).
**Writes:** n/a.
**Called by:** `rider.py` (imports all of it), `fetch.py` (`DELAY_BEFORE_HTML`, `RAW_SUBDIR`),
`abort.py` (`RiderState` type hint), `reporter.py` (`RiderState` type hint only), `metrics.py`
(`RiderState`, `FAIL_THRESHOLD`), `scrape.py` (`RiderState`), dev/ tests under
`dev/news_pipeline/coindesk_proxy_riding/`.
**Calls out:** `src.news.engine.proxy_riding.cooldown.RidingCooldownManager` (type hint on
`RiderState.cooldown_mgr`).

### fetch.py (101 LOC)

**Purpose:** Per-URL fetch + outcome classification — the crawl4ai call, regwall detection, connect-fail subtype classification, and raw-HTML persistence.
**Reads:** n/a (pure per-call).
**Writes:** `output_dir/raw/{url_hash}.html` (`_write_raw`, called from `rider.py:_apply_ok_result`
on first-writer OK).
**Called by:** `rider.py:_fetch_and_build_job` (`_fetch_one_url`, `_url_hash`), `rider.py:_apply_ok_result`
(`_write_raw`, `_url_hash`), `rider.py:_apply_connect_fail_result` (`_classify_connect_fail`).
**Calls out:** `crawl4ai` (`AsyncWebCrawler`, `CrawlerRunConfig`, `CacheMode`, `ProxyConfig`,
`DefaultMarkdownGenerator`).

### abort.py (54 LOC)

**Purpose:** The three watchdog/signal abort paths (`_abort_done`, `_abort_interrupted`, `_abort_stall`) plus their shared write-report-and-exit helper `_abort_write_report_and_exit`. `_abort_write_report_and_exit` is a tripwire on a reporter failure since 2026-09-09 — see this file's own Gotchas for the removed stub it replaces.
**Reads:** `RiderState` (in-memory, for the report).
**Writes:** `state.job_dir/job.md` (+ `cumulative.png`/histograms via `write_riding_report`) on
success; nothing on a `write_riding_report` failure — a missing `job.md` is the signal.
**Called by:** `rider.py:_watchdog` (`_abort_done`, `_abort_stall`); `rider.py:run_riding_pool`
(`_abort_interrupted`, registered as the SIGINT/SIGTERM handler).
**Calls out:** late import of `reporter.write_riding_report` inside `_abort_write_report_and_exit`
(avoids a circular top-level import — `reporter.py` imports from `state.py` (directly) and from
`metrics.py`/`plots.py` (which themselves import from `state.py`), not from `abort.py`, but the
cycle would still exist through `rider.py`).

### rider.py (349 LOC)

**Purpose:** Entry module — orchestrates B `AsyncWebCrawler` instances, N slot coroutines, per-URL proxy context, burn/fail rotation, 30-min pool refresh, and the watchdog (`run_riding_pool`); installs SIGINT/SIGTERM handlers so manual aborts also produce a report. `_run_slot` and `_apply_fetch_result` were each split into single-responsibility helpers to stay under the 50-LOC function threshold (pure extraction, same behavior/log output — see Gotchas): `_run_slot` → `_next_url_for_slot` (dequeue-or-tail-race, returns an explicit `"continue"|"break"|"proceed"` action so the caller's own loop control is preserved) → `_fetch_and_apply` (per-attempt orchestrator) → `_fetch_and_build_job` (fetch + `JobRecord` construction) and `_apply_fetch_result` (now a pure dispatcher) → one helper per status (`_apply_ok_result`, `_apply_regwall_result`, `_apply_connect_fail_result`, `_apply_generic_failure_result`) sharing `_maybe_requeue` for the repeated requeue-if-dequeued check.
**Reads:** URL queue (asyncio.Queue), proxy pool list, `RidingCooldownManager` (shared state).
**Writes:** `output_dir/raw/{hash}.html` for each ok URL (via `fetch.py:_write_raw`); triggers
`state.job_dir/job.md` + `cumulative.png` writes on abort (via `abort.py`).
**Called by:** `scrape.py:scrape_entries_riding` (via `run_riding_pool`).
**Calls out:** `crawl4ai` (`AsyncWebCrawler`, `BrowserConfig`); `state.py` (`RiderState`,
`RideRecord`, `JobRecord`, constants); `fetch.py` (`_fetch_one_url`, `_classify_connect_fail`,
`_write_raw`, `_url_hash`); `abort.py` (`_abort_done`, `_abort_interrupted`, `_abort_stall`).

### reporter.py (200 LOC)

**Purpose:** Orchestrator (`write_riding_report`) + the `job.md` markdown-rendering concern (counts, throughput, riding stats, regwall counts, connect-fail breakdown, load-time distribution, plot links) from a completed `RiderState`. Metric derivation and plot-file writing were split out into `metrics.py`/`plots.py` (below, pure relocation, same behavior) once this file crossed 400 LOC by mixing three concerns; this module is left as the orchestrator plus the one remaining concern (markdown rendering) since that alone keeps it well under any split threshold.
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** `{job_dir}/job.md`. Plot files (`cumulative.png`, `success_load_hist.png`, `connect_fail_hist.png`) are written by `plots.py`, called from this module's own orchestrator.
**Called by:** `pipeline.py:_run_scrape_only_riding` (normal completion, via `write_riding_report`);
`abort.py:_abort_stall` (late import, stall abort); `abort.py:_abort_done` (late import,
wedge-after-done); `abort.py:_abort_interrupted` (late import, SIGINT/SIGTERM abort).
**Calls out:** `src.news.engine.proxy_riding.state` (`RiderState`, type hints only); `src.news.engine.proxy_riding.metrics` (`_compute_stats`); `src.news.engine.proxy_riding.plots` (`_write_cumulative_plot`, `_write_load_hist`, `_write_cf_hist`).

### metrics.py (152 LOC)

**Purpose:** Metric derivation from `RiderState` — split out of `reporter.py` (pure relocation, same behavior): `_compute_stats` (the single entry point `write_riding_report` calls), `_compute_fetch_counts` (per-fetch counts/elapsed-time stats/completion times, extracted from `_compute_stats` itself to keep it under 50 LOC — see Gotchas), `_compute_retry_outcome`, `_compute_pool_windows`, `_compute_load_percentiles`, `_compute_connect_fail_stats`, `_distribution_stats`, and the `_BACKFILL_TOTAL = 61_000` constant.
**Reads:** `RiderState` (in-memory), `t_job_start` (datetime).
**Writes:** nothing — returns a plain `dict` (the `stats` shape `reporter.py`/`plots.py` both consume).
**Called by:** `reporter.py` (`write_riding_report` via `_compute_stats`) — the only caller.
**Calls out:** `statistics` (stdlib, incl. `statistics.quantiles` with `method='inclusive'` — bounds p-values within observed [min, max]); `src.news.engine.proxy_riding.state` (`RiderState`, `FAIL_THRESHOLD`).

### plots.py (74 LOC)

**Purpose:** Matplotlib plot-file writers — split out of `reporter.py` (pure relocation, same behavior): `_write_cumulative_plot`, `_write_load_hist`, `_write_cf_hist`. All histograms: 0.25 s bins, x-axis auto-ranges to data max, page_timeout_s red vertical line. Pure functions of `job_dir: Path` + the `stats` dict `metrics.py` produces — no `proxy_riding`-internal import at all.
**Reads:** nothing of its own — takes the `stats` dict as a parameter.
**Writes:** `{job_dir}/cumulative.png`; `{job_dir}/success_load_hist.png` (only when ≥2 OK `load_s` values, gated by the caller); `{job_dir}/connect_fail_hist.png` (only when ≥2 `connect_fail_records`, gated by the caller).
**Called by:** `reporter.py` (`write_riding_report`) — the only caller.
**Calls out:** `matplotlib` (lazy import inside each plot function); `math` (stdlib, bin count).

### scrape.py (107 LOC)

**Purpose:** Pipeline entry point + manifest adapter. Loads pool, shuffles, calls `run_riding_pool`,
maps `RiderState.job_records` → pipeline manifest.
**Reads:** entries list (in-memory), `RidingScrapeConfig`, proxy pool (network via `load_backfill_pool`).
**Writes:** delegates to `rider.py` (raw HTML writes to `output_dir/raw/{hash}.html`); writes nothing directly.
**Called by:** `pipeline.py:_run_scrape_only_riding` (proxy_riding dispatch arm).
**Calls out:** `src.news.engine.proxy_pool.pool_loaders.load_backfill_pool`;
`src.news.engine.proxy_riding.cooldown.RidingCooldownManager`;
`src.news.engine.proxy_riding.rider.run_riding_pool`;
`src.news.engine.proxy_riding.state.RiderState`.

## State

`RiderState` (defined in `state.py`, re-exported through `rider.py`) is the shared mutable state
across all slot coroutines and the watchdog. Owned and mutated by `rider.py:run_riding_pool`,
`rider.py:_run_slot` and its per-attempt/per-status helpers (`_fetch_and_apply`,
`_fetch_and_build_job`, `_apply_fetch_result` and its four status handlers), `rider.py:_finalize_ride`. Read by
`reporter.py:write_riding_report`, `metrics.py:_compute_stats` (called from `write_riding_report`),
and `scrape.py:_build_manifest` (read-only, after run completes).
`asyncio` single-threaded: `set.add/discard` on `in_flight_urls` and `int` increments on counters
are safe without explicit locking. `proxy_lock` (asyncio.Lock) guards `proxy_cursor` advancement.

## Gotchas

- `file` field in manifest points to `.html` (not `.md`). `dedup.py:filter_new_entries` mode `"raw"`
  now accepts `raw_ext` param — pass `".html"` for riding path (done in `pipeline.py:run_scrape_only`).
  `clean_pass.py:_run_clean_pass` still hardcodes `{h}.md` but is NOT on CoinDesk's path (proxy_pool /
  TheBlock only) — out of scope unless CoinDesk gains a clean-pass step.
- `output_dir` passed to `scrape_entries_riding` must be `platform_dir` (`data/news/{name}/`), NOT
  `raw_dir`. The rider writes to `output_dir/raw/{hash}.html`; passing `raw_dir` puts files at
  `raw/raw/` (wrong), breaking dedup.
- All three abort functions (`_abort_stall`, `_abort_done`, `_abort_interrupted`, in `abort.py`) call
  `os._exit` — no Python teardown, no atexit, no `browser.close()`. Raw files flushed before the call
  are durable; in-flight writes at the moment of abort are lost. All write to `state.job_dir`
  (= `scrape_jobs/{job_id}/`), NOT to `output_dir`; each creates the dir itself (`mkdir`) before
  the first write because the dir may not exist at abort time. Exit codes follow Unix signal-kill
  convention: 130 = 128+SIGINT(2), 143 = 128+SIGTERM(15); 0 = wedge-after-done (work complete), 1 = stall.
- **REMOVED 2026-09-09: the stub `job.md` written on a `write_riding_report` failure — user decision
  in the Phase 4 control-flow review (a branch producing the same artifact by a second method is a
  fallback, and a fallback is eliminated).** `_abort_write_report_and_exit`'s `except Exception`
  branch used to write a minimal hand-built `job.md` (title from a per-caller `fallback_title`,
  termination, the four counters, the reporter error) when the real reporter raised. That inner
  `try`/`except` is gone, along with the `fallback_title`/`extra_fields` parameters every caller
  (`_abort_done`, `_abort_interrupted`, `_abort_stall`) used to pass just to feed it —
  `_abort_stall`'s `idle_s` value that used to also go into `extra_fields` is unaffected, since it
  was already printed to stderr in `_abort_stall`'s own line. What stays is the tripwire: the WARN
  line naming the reporter exception on stderr, `sys.stderr.flush()`, and `os._exit(exit_code)` — a
  missing `job.md` after an abort is now the honest signal that the reporter itself failed, not a
  stub that could be mistaken for a real report.
- Late import of `reporter.write_riding_report` inside `abort.py`'s shared helper is intentional:
  `reporter.py` imports from `state.py` (directly, for the `RiderState` type hint) and from
  `metrics.py`/`plots.py` (which themselves import from `state.py`); importing `reporter` at
  `abort.py`'s top level would still create a cycle through `rider.py` (which imports both
  `state.py` and `abort.py`). Splitting `reporter.py` into `reporter.py`/`metrics.py`/`plots.py`
  did not change this — none of the three import `abort.py` or `rider.py`, so the late import
  remains necessary and sufficient.
- `metrics.py:_compute_stats` was 61 LOC before `_compute_fetch_counts` was extracted from it — the
  per-fetch-record block (`n_total_fetches`/`n_ok`/`n_regwall_fetches`/`n_failed`/`n_connect_fail`,
  elapsed-time `mean_s`/`median_s`, `wall_s`/`urls_per_min`, `ok_completion_s`), everything derivable
  from `jobs`/`t_job_start` alone before any ride/proxy/pool/load/connect-fail-specific computation
  begins. `_compute_stats` now spreads `**_compute_fetch_counts(...)` into its returned dict — same
  keys/values as before, dict-equal return shape, not a behavior change.
- Pool load (`load_backfill_pool`) is blocking network I/O, run via `run_in_executor` to avoid
  blocking the event loop during the async entry point.
- `_run_slot` and `_watchdog` MUST stay defined in `rider.py`: the dev/ tests patch
  `_fetch_one_url`/`_next_proxy`/`POOL_REFRESH_INTERVAL_S`/`os` via
  `unittest.mock.patch.object(rider_mod, ...)`, which only resolves through the DEFINING module's
  globals — moving these to `fetch.py`/`state.py` silently breaks the test suite. The helpers
  extracted from `_run_slot`/`_apply_fetch_result` (`_next_url_for_slot`, `_fetch_and_apply`,
  `_fetch_and_build_job`, `_apply_fetch_result` and its four status handlers, `_maybe_requeue`) all
  stay in `rider.py` too — none of `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`'s
  patches target these, so no patch target changed, but keeping them here preserves the same
  DEFINING-module-globals guarantee for any future patch.
- `_next_url_for_slot`'s three-way `("continue"|"break"|"proceed", ...)` return exists specifically
  because a bare `continue`/`break` inside an extracted helper does not affect the caller's own
  loop — the original inline block had one `continue` (stale dequeued dup) and two `break`s
  (all_resolved; no open URL left to race), and collapsing all three into a single sentinel (e.g.
  `None`) would have silently turned the `continue` case into a `break`. Verified live, not just by
  inspection: `dev/news_pipeline/coindesk_proxy_riding/test_tail_race.py`'s
  `test_3_no_spurious_requeue` sub-case A depends on exactly this distinction (a stale dequeued dup
  must retry the inner loop, not exit the ride) and passed unchanged (7/7) after the split.
- Regwall detection (`fetch.py:_is_regwall`) checks `result.markdown.raw_markdown` (browser-rendered
  visible text), NOT `result.html` — `REGWALL_SIGNALS` are embedded as hidden React components in the
  raw HTML of every CoinDesk page, so an html-based check would silently never fire.
- `state.py:STALL_TIMEOUT_S = 3600.0` is only the module-level fallback default (used when
  `run_riding_pool`/`RiderState` are constructed without an explicit `stall_timeout_s`). Production
  runs override it via `RidingScrapeConfig.stall_timeout_s = 300.0` — don't read the module constant
  as "the" production stall timeout.
- `plots.py:_write_load_hist`'s x-axis auto-ranges to data max rather than clamping at
  `page_timeout_s` — `load_s` (elapsed minus the fixed `DELAY_BEFORE_HTML`) can legitimately exceed
  `page_timeout_s` due to post-navigation processing time not covered by the nav timeout; the red
  vertical line marks the nav cap, it is not the axis bound.

~~~~

### Archive: src/news/platforms/DOCS.md

~~~~markdown
# src/news/platforms/

## Role

Namespace package holding one subdirectory per news source, each implementing the `Platform` Protocol (defined in `src/news/platform.py`). No logic lives directly at this level — this directory only groups platform packages. Touch this level only when adding a brand-new platform directory; touch the platform subdirectory itself to change that platform's discovery/cleanup behavior.

## Public Interface

`__init__.py` is empty (0 LOC). Entry is via `src.news.platforms.<name>` — each platform subpackage's own `__init__.py` registers its `Platform` implementation into the registry as a side effect of being imported by `src/news/__main__.py`.

## Flow

`__main__.py` imports a platform subpackage for its registration side-effect → subpackage's `__init__.py` instantiates its `Platform` class and calls `register(instance)` → `src/news/pipeline.py` looks up the platform by `--source` name via the registry and drives discover → dedup → scrape → (clean-pass, if `proxy_pool` engine) → publish.

~~~~

### Archive: src/news/platforms/coindesk/DOCS.md

~~~~markdown
# src/news/platforms/coindesk/

## Role

CoinDesk platform implementation. Imported for side-effects by `__main__.py` — the import
registers `CoinDeskPlatform()` into the registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `CoinDeskPlatform` (implements `Platform` Protocol).
Auto-registers via `register(CoinDeskPlatform())` at module end.

## Modules

### config.py (34 LOC)

**Purpose:** Platform constants — REGWALL_SIGNALS, SCRAPE_CONFIG (ScrapeConfig()), timeline-API
discovery params (TIMELINE_BASE, COINDESK_BASE, TARGET_URL, CALL_DELAY, REWARM_EVERY,
CLICKS_WARMUP, CLICKS_REWARM, MAX_CURSOR_FALLBACKS, CHECKPOINT_EVERY, DEFAULT_DELTA_DAYS,
FULL_MODE_FLOOR, DISCOVER_DIR, SKIP_HEADERS).
**Called by:** `browser.py`, `discover.py`, `timeline.py`, `__init__.py`.

### browser.py (158 LOC)

**Purpose:** Chrome browser launch + pydoll HAR-capture machinery for the initial feed warmup.
`browser_load_feed(n_clicks)` launches Chrome via `open -gna`, navigates to latest-crypto-news,
clicks "More stories" n times under HAR record, captures the first `/api/v1/articles/timeline`
request (URL + headers + first response body). Returns `(headers, api_url, body_bytes)`.
**Called by:** `discover.py:discover` (warmup); `timeline.py:try_rewarm` (re-warm fallback).
**Calls out:** `pydoll` (Chrome CDP), `httpx` (first response replay).

### discover.py (279 LOC)

**Purpose:** Discover orchestration + cursor paging — `discover(timeframe)` orchestrates warmup → load discover → `cursor_loop` (backward-paging, crash-safe per-article shard writes) → incremental discover write. Timeline-API access/re-warm and per-year shard storage were split out into `timeline.py`/`shards.py` (below, pure relocation, same behavior) once this file crossed 400 LOC by mixing three concerns.
**Called by:** `__init__.py:CoinDeskPlatform.discover` (via `discover`).
**Calls out:** `httpx` (`_fetch_next_page`'s own cursor GET); `browser.py:browser_load_feed` (warmup, in `discover` itself); `timeline.py` (`parse_articles`, `build_cursor_url`, `fetch_feedpage`, `try_rewarm`); `shards.py` (`_append_to_shard`, `load_discover`).

### timeline.py (73 LOC)

**Purpose:** Timeline-API access + session re-warm — split out of `discover.py` (pure relocation, same behavior): `parse_articles` (response-body → article dicts; as of 2026-09-09 raises on a non-JSON body instead of swallowing the parse failure, see Gotchas), `build_cursor_url` (pagination cursor URL), `fetch_feedpage` (plain-httpx feed-page GET, used both standalone and inside re-warm), `try_rewarm` (httpx feedpage re-warm first, browser re-warm fallback via `browser.py:browser_load_feed`).
**Called by:** `discover.py` — `cursor_loop` (`parse_articles`), `_fetch_next_page` (`build_cursor_url`), `_maybe_proactive_rewarm` (`fetch_feedpage`), `_handle_cursor_exhaustion` (`try_rewarm`) — the only caller module.
**Calls out:** `httpx`; `browser.py:browser_load_feed` (re-warm fallback).

### shards.py (63 LOC)

**Purpose:** Per-year discover shard storage — split out of `discover.py` (pure relocation, same behavior): `_append_to_shard` (streaming, line-buffered append to `coindesk_{year}.txt`), `load_discover` (read all shards → set of known URLs, used by `discover()`'s dedup seed), `load_discover_filtered` (read shards filtered by year/date-range/limit → `[{url, publication_date}]`, the `--scrape-only` interface).
**Called by:** `discover.py` (`_append_to_shard` via `_process_batch`, `load_discover` via `discover()`); `__init__.py:load_scrape_entries` (`load_discover_filtered`, imported directly — no re-export through `discover.py`).
**Calls out:** none (stdlib `pathlib` only).

### cleanup.py (120 LOC)

**Purpose:** Strip CoinDesk page chrome from raw crawl4ai markdown → pure article body (H1 start-anchor → first end-anchor → `clean_body` strip/normalize passes).
**Called by:** NOT called by any active pipeline path. Available to future cleanup skill.
**Calls out:** stdlib re only.

### __init__.py (40 LOC)

**Purpose:** `CoinDeskPlatform` class wrapping config + discover + cleanup + scrape-entry loading; auto-registers on import; `scrape_engine = "proxy_riding"`, raw output `.html`.
**Called by:** `__main__.py` (side-effect import); `pipeline.py:run_scrape_only` (via `platform.load_scrape_entries`, `platform.scrape_engine`); `pipeline.py:_run_scrape_only_riding` (via `platform.riding_scrape_config`).

## Gotchas

- **`_parse_stop_date` treats `"delta"` explicitly (2026-09-24 Phase 4 pass).** The CLI default `--timeframe` is `delta`, which resolved to `DEFAULT_DELTA_DAYS` only because `int("delta")` raised into a swallowing handler; the branch is now explicit and any other non-integer value raises.

- `REGWALL_SIGNALS` uses precise match strings deliberately — do NOT loosen to generic markers like "subscribe"/"register": those fire on ordinary article footers, producing false regwall positives.
- `cleanup(raw_markdown, entry)`'s `entry` param is unused but part of the platform-generic signature — do not remove as dead.
- At 60k+ article scale the fixed cleaner is fragile — articles occasionally retain the full site footer after cleanup; per-shape diagnosis against the full raw corpus is recommended before cleanup at scale.
- **REMOVED 2026-09-09: `timeline.py::parse_articles`'s parse-failure→`[]` handler — user decision, Phase 4 control-flow review.** `cursor_loop` (`discover.py`) used to log "Empty response — reached API bottom or parse failure. Stopping." on either a genuine API-exhaustion payload OR a non-JSON body, admitting it could not tell the two apart — no supporting observation existed for a real parse failure (no process-docs entry documents one). A non-JSON timeline body now raises `json.JSONDecodeError` straight out of `parse_articles`, propagating through `cursor_loop`'s own `try/finally` (year-shard files still close cleanly) and up through `discover()`, ending the run with a traceback instead of a silent stop. `cursor_loop`'s stop message was reworded to "Empty response — reached API bottom. Stopping." — an empty list from `parse_articles` now means exactly one thing.
- 2026-09-24 Phase 5: `parse_articles` reads only the recorded shape (`_id`, `pathname`, `articleDates.displayDate`) and raises `KeyError` otherwise (list-or-dict container detection stays); `_extract_value` no longer swallows KeyError/TypeError; `cleanup` returns `""` with a warning when there is no H1 and warns when no end anchor exists; `load_discover_filtered` raises `FileNotFoundError` for a missing directory or year shard. A missing recorded key now aborts discovery instead of dropping articles silently.

~~~~

### Archive: src/news/platforms/theblock/DOCS.md

~~~~markdown
# src/news/platforms/theblock/

## Role

The Block platform implementation. Uses the `proxy_pool` scrape engine (curl_cffi rotation,
no browser) and its own RAG collection `"theblock"`. Discovery is sitemap-based (not feed-scroll).
`dedup_mode` attribute is not used by `run_pipeline` (which always uses `mode="raw"` against
`data/news/theblock/raw/`). The Block has no `publication_date` at discover time — the date
comes from JSON-LD post-fetch and is mutated into `entry["publication_date"]` by `cleanup.py`.

Imported for side-effects by `__main__.py` — the import registers `TheBlockPlatform()` into the
registry. No other module should import from here directly.

## Public Interface

`__init__.py` exports `TheBlockPlatform` (implements `Platform` Protocol).
Auto-registers via `register(TheBlockPlatform())` at module end.

Extra platform attributes (not in Protocol):
- `timeframe: str` — discovery mode (`"delta"` default); overwritten by `__main__` from `--timeframe`.
- `dedup_mode: str = "hash_only"` — legacy attribute, not consumed by `run_pipeline` (which uses `mode="raw"`).
- `uses_master_list: bool = True` — signals `pipeline.py` to write a single `data/news/theblock/discover/master_urls.txt`
  instead of per-year shards. Consumed via `getattr(platform, "uses_master_list", False)` in both
  `run_discover_only()` and `run_pipeline()` proxy_pool path.

## Modules

### config.py (14 LOC)

**Purpose:** Platform constants — `SITEMAP_INDEX`, `DIRECT_TIMEOUT`, `DEFAULT_TIMEFRAME`,
`PROXY_SCRAPE_CONFIG` (`ProxyScrapeConfig(pool_provider=load_backfill_pool, content_type="html")`),
`SCRAPE_CONFIG` (default `ScrapeConfig()`, required by Protocol but ignored by proxy path).
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `__init__.py`, `discover.py`.
**Calls out:** `engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

---

### discover.py (161 LOC)

**Purpose:** Sitemap-based article discovery. Fetches theblock sitemap index (direct httpx →
proxy pool fallback), selects `post_type_post_*` sub-sitemaps by mode (`delta`/`full`/`sub:N`/`sub:A-B`),
parses `<url>/<loc>/<lastmod>` blocks — no date filtering. Returns `[{url, lastmod}]` — NO
`publication_date` (comes from JSON-LD post-fetch in cleanup). The proxy-pool fallback triggers on the observed direct-fetch outcome (HTTP status other than 200 or no XML marker); a direct-fetch exception and an unparseable `lastmod` propagate (2026-09-24 Phase 4 pass).
**Reads:** `https://www.theblock.co/sitemap_tbco_index.xml` + selected sub-sitemaps (network).
**Writes:** nothing.
**Called by:** `__init__.py:TheBlockPlatform.discover`.
**Calls out:** `httpx`, `engine/proxy_pool/fetch.py:fetch_url`,
`engine/proxy_pool/pool_loaders.py:load_backfill_pool`.

---

### cleanup.py (111 LOC)

**Purpose:** Parse JSON-LD `NewsArticle` block from raw HTML fetched by proxy engine →
extract `articleBody` (HTML) → convert to Markdown via `crawl4ai.html2text.HTML2Text` →
apply `_post_clean()` regex pass → mutate `entry["publication_date"] = datePublished`.
**Reads:** raw HTML string (proxy engine output), entry dict (scrape manifest).
**Writes:** mutates `entry["publication_date"]` in place.
**Called by:** `clean_pass.py:_run_clean_pass` (proxy_pool arm, dispatched from `pipeline.py:_run_pipeline_proxy_pool`).
**Calls out:** `crawl4ai.html2text` (bundled, no new dep).

---

### __init__.py (30 LOC)

**Purpose:** `TheBlockPlatform` class wrapping config + discover + cleanup; auto-registers on import; `scrape_engine="proxy_pool"`, `uses_master_list=True`.
**Called by:** `__main__.py` (side-effect import).

## Gotchas

- `precondition_url` is `https://www.google.com`, not theblock.co — theblock.co returns 403 on plain urllib.
- `_SPONSOR_BLOCK_RE` in `cleanup.py` strips from the sponsor-block header to END OF STRING (no closing anchor) — corpus-verified safe on the validated 22,995-file corpus, but re-check that assumption against new corpus shapes before trusting it on fresh scrapes.
- 2026-09-24 Phase 5: a failed direct sitemap fetch logs status and URL, each served sitemap logs its route (direct or proxy), and a sub-sitemap that fails direct + proxy raises `RuntimeError` like the index. `discover(timeframe, acquire_logger=None)` (the `AcquireLogger` parameter was renamed to free `logger` for the module logger).

~~~~
