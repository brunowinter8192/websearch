# src/search/

## Role

pydoll-based parallel web-search pipeline behind the `search_web` and `search_engine_drilldown` CLI subcommands. Fans a single query out across 7 engines concurrently, dedups URLs into per-engine pools, caches the pools to disk, and returns an engine-breakdown table; the drilldown subcommand re-reads the cache to emit one engine's URLs. As of 2026-08-05, the drilldown path is ALSO logged (`record_type: "drilldown"` in `query_log.jsonl`, `cli.py`) — closing the "a scraped URL cannot be traced back to which engine(s) offered it" gap; see query_logger.py's module entry. Touch this package when changing engine fan-out, dedup/pool-building, the disk cache, or rate-limiting. Individual engine parsers live one level down in `engines/`.

## Public Interface

`__init__.py` is empty — modules are imported by path:

- `search_web_workflow(query, language="en", time_range=None, engines=None, …, query_modifier_map=None)` (search_web.py) — the `search_web` subcommand entry (`cli.py`). Returns `list[TextContent]` (one breakdown table).
- `fetch_search_results(...)` (search_web.py) — sync wrapper for dev scripts; returns the raw result list, no pool-building.
- `cache_key`, `cache_read`, `format_engine_pool` (cache.py) — the `search_engine_drilldown` subcommand path (`cli.py`).
- `log_query(record)` (query_logger.py) — called directly by `cli.py` (drilldown logging, as of 2026-08-05) in addition to `search_web.py`.
- `kill_own_chrome_atexit()` (browser.py) — registered `atexit` in `cli.py`; PID-scoped last-resort backstop, see browser.py's module entry.

## Flow

`search_web_workflow` selects engines → if any needs the browser, `_prewarm_browser` blocks (outside any watchdog) until this run's Chrome is up → `asyncio.gather` of `_engine_with_timing` tasks (each acquires a rate-limiter token, then runs the engine) → `finally: kill_own_chrome()` tears the browser down and releases the cross-process lock → flat `raw_results` → `build_engine_pools` dedups by URL owner → post-dedup pool cap to Google's pool size (fallback 10) → `_format_breakdown` table → `cache_write` to `~/.cache/websearch/<key>.json`. `search_engine_drilldown` skips all of this: `cache_read` the per-engine pool → `format_engine_pool` numbers + cleans snippets.

## Modules

### search_web.py (349 LOC)

**Purpose:** Search orchestrator — fans out across the 7 active engines via `asyncio.gather`, then builds pools, caps each to Google's pool size, formats a breakdown table, and caches the result. As of the browser-lifecycle milestone (2026-08-25), also owns deterministic own-browser teardown: `_prewarm_browser` launches the shared Chrome ONCE, outside any per-engine watchdog, before fanout (only when `selected` includes a browser engine); `kill_own_chrome` runs in a `finally` around the fanout regardless of outcome. As of the diagnosis-snapshot milestone, `_engine_with_timing` unpacks `engine.search_with_reason(...)`'s uniform `(results, empty_reason, diagnosis)` 3-tuple and threads `diagnosis` into `engine_stats[name]["diagnosis"]`, next to `"status"` — read by both `engine_run` and `workflow_summary` log records (they share the same `engine_stats` dict).
**Reads:** query + params; per-engine caps in `ENGINE_MAX_RESULTS`; default set via `_DEFAULT_ENGINES`; `_BROWSER_ENGINES` (which of the 7 need `browser.py`'s Chrome).
**Writes:** disk cache `~/.cache/websearch/<key>.json` (via cache_write); query log (via log_query).
**Called by:** `cli.py` (search_web_workflow); dev scripts (fetch_search_results).
**Calls out:** `httpx`, `pydoll.exceptions`, `websockets.exceptions`, `mcp.types.TextContent`; `engines/` (all 7 engine classes); `browser` (get_tab, kill_own_chrome); `cache` (cache_key, cache_write), `rate_limiter` (get_limiter), `merge` (build_engine_pools), `result` (SearchResult), `status`, `status_timeout`, `status_error`, `query_logger` (log_query).

### merge.py (32 LOC)

**Purpose:** Cross-engine URL dedup + per-engine pool builder — groups results by URL, assigns each to its lowest-position owner engine, and returns a per-engine pool dict sorted by native position. The fresh `SearchResult` built per winner names fields explicitly, so a new field (`date`, `pdf_url`) must be added here explicitly too or it silently drops.
**Reads:** flat `list[SearchResult]` from fan-out.
**Writes:** none (returns the pool dict).
**Called by:** `search_web.py`.
**Calls out:** `result` (SearchResult).

### cache.py (115 LOC)

**Purpose:** Disk cache for per-engine pools, backing `search_engine_drilldown` — atomic-write JSON keyed by a query/language/engines/time_range hash, 1h TTL, plus `format_engine_pool` for numbered-list rendering with snippet cleanup. Renders an optional `PDF: <url>` line directly after `URL:` when the cached entry carries a `pdf_url` (currently only `openalex`).
**Reads:** cache files under `~/.cache/websearch/`.
**Writes:** `~/.cache/websearch/<key>.json`.
**Called by:** `cli.py` (cache_key, cache_read, format_engine_pool); `search_web.py` (cache_key, cache_write).
**Calls out:** `result` (SearchResult), `snippet` (_strip_bloat, _truncate, MAX_SNIPPET_LEN).

### snippet.py (57 LOC)

**Purpose:** Snippet text utilities for drilldown display — HTML-unescape + bloat-pattern stripping, plus sentence-aware truncation.
**Reads:** raw snippet string.
**Called by:** `cache.py` (format_engine_pool).
**Calls out:** none (stdlib `html`, `re`).

### query_logger.py (25 LOC)

**Purpose:** Append-only JSONL query log (`log_query(record)`) — three record types (`engine_run`, `workflow_summary`, `drilldown`), correlated via a shared `search_key`.
**Reads:** `WEBSEARCH_QUERY_LOG_PATH` env (fallback `src/logs/query_log.jsonl`).
**Writes:** `src/logs/query_log.jsonl`.
**Called by:** `search_web.py` (engine_run, workflow_summary); `cli.py` (drilldown, as of 2026-08-05).
**Calls out:** `src/log_janitor.py` (maybe_prune_jsonl).

### browser.py (187 LOC)

**Purpose:** pydoll Chrome lifecycle — one shared, headed, backgrounded (macOS `open -g -n`) Chrome, one tab per engine for isolation, no JS fingerprint patches or UA override. `get_tab()`'s first-launch path blocks on a cross-process lock (`browser_lock.py`) scoped to the shared session profile, reaps any orphaned survivor of a crashed prior run (net 3), snapshots the real Chrome PID(s) it launched, then spawns a `death_pipe` watchdog (net 2 — no `cleanup_dir`, the session profile is persistent by design). `kill_own_chrome()` is the deterministic own-run teardown (net 1 — graceful CDP close + PID-scoped psutil safety net + lock release, `close_browser()`'s own raise caught so net 1 can't itself skip the lock release), replacing profile-pattern `pkill` as the primary teardown path.
**Reads:** nothing (singleton browser on first access).
**Writes:** Chrome session dir under the user-data-dir; the cross-process lock file + JSON sidecar at `LOCK_PATH` (`~/.websearch/browser-session.lock[.json]`).
**Called by:** `cli.py` (kill_own_chrome_atexit, atexit); `search_web.py` (get_tab via `_prewarm_browser`, kill_own_chrome); `engines/` (new_tab, kill_tab — google, duckduckgo, yandex, bing, brave, startpage); 40+ `dev/search_pipeline/*.py` probes (new_tab, close_browser — direct callers, bypass search_web.py's lock/prewarm entirely).
**Calls out:** `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager, TargetCommands); `psutil` (own-PID terminate/kill); `browser_lock` (acquire); `death_pipe` (spawn_watchdog); `open`/`pgrep` (macOS process control).

### browser_lock.py (65 LOC)

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

### document_status.py (39 LOC)

**Purpose:** Shared CDP Network-domain mechanism backing the diagnosis snapshot's `document_status_chain`/`http_status` facts, one copy for all 7 browser engines in `engines/` (these already share this package's `browser.py` tab lifecycle, unlike the scraper package's deliberately-duplicated chromium/camoufox lanes — see `src/scraper/DOCS.md`). `start_document_status_capture(tab)` arms a `Network.responseReceived` listener BEFORE an engine's first navigation (so it also catches that navigation's own response), filtering to `type == "Document"` and `frameId == tab._target_id` — the CDP convention (already relied on by `browser.py`'s `kill_tab`) that a target's own top-level frame ID equals its target ID — and returns the list that accumulates the ordered chain of observed statuses. `attach_document_status(diag, status_chain)` is a pure, after-the-fact merge (`document_status_chain`: the list; `http_status`: `chain[-1]`, `None` if empty, never a fabricated default) called at each engine's own `return` site — `_classify_diagnosis` never sees it. Same "fact, not verdict" principle and field name as `src/scraper/chromium_scrape.py`'s `document_status_chain`; CDP directly instead of a Playwright `page.on` hook. `start_document_status_capture`'s own setup is wrapped in try/except and degrades to an empty list on failure — a CDP hiccup here cannot turn an ordinary search into a new engine error.
**Reads:** nothing (pure functions + one CDP call).
**Writes:** nothing (returns values; no I/O).
**Called by:** `engines/google.py`, `duckduckgo.py`, `brave.py`, `bing.py`, `yandex.py`, `startpage.py`.
**Calls out:** `pydoll.protocol.network.events` (`NetworkEvent`), `pydoll.protocol.network.types` (`ResourceType`).

## State

Two module-owned states. `rate_limiter._limiters` — the per-engine token-bucket registry, populated at engine import, read/mutated via `get_limiter().acquire()`. The disk cache (`~/.cache/websearch/`) — written by `cache.cache_write` (from search_web), read by `cache.cache_read` (from the drilldown path); 1h TTL, atomic writes. No cross-request in-memory search state — each `search_web_workflow` call is independent.

## Gotchas

- Active engines (7, as of the 2026-09 engine-reduction milestone): google, duckduckgo, startpage, brave, bing, yandex (pydoll); openalex (HTTP). Google Scholar (`engines/scholar.py`) is decoupled from the default pool. crossref, semantic_scholar, stack_exchange, open_library, lobsters, marginalia, and mojeek were removed entirely (not parked) — see `process-docs/engine_expansion/` for their history.
- Two-call architecture: `search_web` returns counts only (no URLs); URLs come from `search_engine_drilldown` reading the cache. The drilldown query MUST match the prior `search_web` call or the cache key misses.
- Post-dedup pool cap keys off Google's pool size — if Google was CAPTCHA'd or excluded, K falls back to 10.
- Stealth config lives in `browser.py` (headed-backgrounded launch, `--disable-blink-features=AutomationControlled`, `BACKGROUNDING_FLAGS`, browser preferences) + per-engine files (SOCS cookie for Google) — no config file, no JS fingerprint patches or UA override (removed — see `browser.py`'s module history via `process-docs/browser_posture/`).
- pydoll tab cleanup uses `kill_tab` (browser-level close), NOT `tab.close()` — the latter hung 65s on non-cooperative renderers.
- CLI dispatch hardcodes `language="en"`, `time_range=None`, `engines=None`; the full `search_web_workflow` signature is retained only for dev-script callers.
- `pdf_url` (currently `openalex` only, from `best_oa_location.pdf_url`) is passed through as-is from the vendor with no validation — a live sample showed one `pdf_url` pointing at a `.jpg` figure asset rather than the paper's full text (see `process-docs/engine_reduction/`). Treat it as "OpenAlex's best guess at a direct full-text link", not a guaranteed PDF.
- **A URL can NEVER be attributed to exactly one engine** — engines overlap heavily; the same URL routinely appears in 3+ drilled engines' pools. Any log record or downstream tooling claiming "this URL came from engine X" is wrong by construction. What IS answerable (as of 2026-08-05, via `query_log.jsonl`'s `drilldown` records + `search_key`): "which engines offered this URL in this session" — possibly several, possibly none.
- `dev/tests/test_query_logger.py`'s engine mocks must expose `.search_with_reason(query, language, max_results) -> (results, empty_reason, diagnosis)` — `_engine_with_timing` calls that, not `.search()`. Fixed 2026-08-20 (the file's one shared mock helper, `_make_mock_engine`, set `.search` and was removed along with the drift it caused — see `_make_mock_engine_with_reason`, now the file's only engine-mock helper). Extended to a 3-tuple as of the diagnosis-snapshot milestone — `diagnosis` defaults to `None`. As of the guessed-verdict-removal milestone, every real engine's `search_with_reason` always returns `empty_reason=None` (there is no longer any non-`None` value any engine produces from inside that method) — a mock is free to pass any string for `empty_reason` purely to exercise the plumbing, it does not need to resemble a real status.
- **`engine_stats[name]` (both `engine_run` and `workflow_summary` records) carries a `"diagnosis"` key alongside `"status"`.** For `openalex`/`scholar`, the attachment rule is "whenever the engine returns WITHOUT results" — `diagnosis` is `None` on a real success, `{"http_status": int}` (`scholar` also adds `captcha_form`) otherwise. For the 6 browser engines, `diagnosis` is attached on EVERY branch including success, but the two halves are gated independently: the CDP-observed NETWORK facts (`document_status_chain`/`http_status`, `document_status.py`) are always attached — `attach_document_status({}, status_chain)` costs nothing extra on success, since `status_chain` is a list the listener already filled during navigation — while the DOM/JS facts (`marker`/`title`/`url`/`ready_state`/`containers_found` plus engine-specific extras, each engine's own `_diagnose(tab)`) stay empty-only, since a `_diagnose(tab)` call is a real JS round trip a successful search has no reason to pay for. This is why a success record for `brave`/`yandex` (the challenged engines) can still show whether a challenge resolved first, via `document_status_chain`'s length, without an unneeded DOM read — see `engines/DOCS.md`'s Gotchas for the exact field contract. **As of the guessed-verdict-removal milestone, `status` itself no longer carries the 5 EMPTY_* sub-statuses (`EMPTY_BLOCK`/`EMPTY_NO_CONTAINER`/`EMPTY_CONCURRENT_RACE`/`EMPTY_CONSENT`/`EMPTY_NO_RESULTS`) — every empty result now logs bare `"EMPTY"`, and the fact each removed sub-status used to encode lives entirely in `diagnosis` instead** (see `engines/DOCS.md`'s Gotchas for the full per-verdict mapping). `_classify_diagnosis` and its per-engine equivalents were deleted along with the statuses they produced.
- `search_web_workflow` writes TWO log records per call, not one: `"engine_run"` (from `_query_engines_concurrent`) then `"workflow_summary"` (from `_build_query_log_entry`) — a test asserting exactly one JSONL line after a workflow call is checking the wrong invariant; filter by `record_type` instead (see `test_search_web_workflow_writes_log`).
- `query_logger.py` has no `LOG_PATH` module attribute — the log path is read fresh from `WEBSEARCH_QUERY_LOG_PATH` (env var) inside `log_query()` on every call. Tests must `monkeypatch.setenv("WEBSEARCH_QUERY_LOG_PATH", ...)`, not `patch.object(query_logger, "LOG_PATH", ...)`.
- `log_janitor.maybe_prune_jsonl` (called at the end of every `log_query()`) drops any JSONL line whose `"ts"` field is older than the 14-day retention window — a test writing a record with a hardcoded past-dated `ts` literal (or no `ts` at all — a missing key is treated as unparseable and also dropped) will see its own line silently pruned away as real time passes. Always use a freshly-computed current timestamp in test payloads that include `ts`.
- **`get_tab()`'s cross-process lock wait MUST happen outside any per-engine watchdog — never call it lazily from within an `asyncio.wait_for(...)`-guarded task.** The per-engine watchdog (`ENGINE_WATCHDOG_TIMEOUT`, uniform `6.0s` across all engines as of 2026-08-25) is far shorter than a legitimate second-run lock wait (observed ~7s for one full sweep, budgeted up to `LOCK_HARD_BUDGET_S`=81s before stale-takeover). `asyncio.wait_for` cancelling a task mid-`await get_tab()` releases `get_tab`'s asyncio-level `_init_lock` (context-manager exit still runs under cancellation) but does NOT stop the underlying `asyncio.to_thread(browser_lock.acquire, ...)` call — a real OS thread, uncancellable — which keeps polling in the background, orphaned; the next queued engine then re-enters `get_tab()` and spawns ANOTHER competing thread. Caught live via a two-parallel-CLI-run test that showed repeated "Acquiring cross-process browser-session lock" log lines within a single process and a run that silently gave up without ever launching its own Chrome. Fixed by `search_web_workflow` calling `_prewarm_browser` (bare `await get_tab()`, no timeout) once, before the fanout, whenever `_BROWSER_ENGINES` intersects the selected set — by the time engines run, `_browser` is already set and their own `new_tab()` calls return near-instantly.
- **`get_tab()`'s launch body (from `browser_lock.acquire` through `_record_own_pids`) is wrapped in try/except that resets `_browser`/`_tab` to `None` and releases `_lock_handle` before re-raising.** Without this, a real Chrome-launch failure (missing binary, etc.) would leave the cross-process lock held forever by a process that never got a working browser — `close_browser()`'s own `_browser.stop()` would itself raise `BrowserNotRunning` on a half-initialized `Chrome` object, so `kill_own_chrome`'s `finally` can't be relied on alone to clean this up.
- **`_reap_session_profile()` (profile-pattern `pkill`-equivalent) is legitimate ONLY while the cross-process lock is held** — either right after acquiring it (before this run's own launch, reaping a crashed prior run's `open -g`-launched Chrome, which survives its own short-lived wrapper process dying) or as `browser_lock.acquire`'s `on_stale` callback during a takeover. Calling it unlocked would resurrect the original cross-run-kill bug this milestone fixed.
- **`kill_own_chrome`'s `close_browser()` call is wrapped in try/except, not bare.** Chrome dying mid-sweep (crash, manual close) makes `_browser.stop()` raise on the dead websocket BEFORE `close_browser`'s own `_browser = None` reset line runs — a bare call would then skip the PID-scoped psutil safety net and the lock release that follow it in `kill_own_chrome`, leaking the cross-process lock until the 81s stale-takeover. Caught by review, not live reproduction; regression-guarded (`test_kill_own_chrome_runs_safety_net_and_release_when_close_browser_raises`).
- `kill_own_chrome_atexit()` is a sync wrapper because `atexit` callbacks cannot be coroutines; it is safe only because `atexit` fires after `asyncio.run()` in `cli.py`'s `main()` has returned, so no loop is running at that point. If `cli.py` ever keeps a loop alive past `main()`, this wrapper must change.
- **Three independent nets, not one mechanism doing everything.** Net 1 (`kill_own_chrome`, this file) is the fast, deterministic common case. Net 2 (`death_pipe.spawn_watchdog`, called once right after `_record_own_pids`) is the crash backstop — proven live (2026-08-25): a real `search_web` run `kill -9`'d mid-sweep left its Chrome killed within the same second by the watchdog (`src/logs/cli.log`: `"parent died without tearing down its own browser — killed pids=[...]"`), never waiting for a subsequent run's reap. Net 3 (`_reap_session_profile`, pre-launch) only ever catches what net 2 could not — e.g. a leak from before this milestone shipped, or the vanishingly rare case where the watchdog itself never got to spawn. Do not remove net 3 on the reasoning that net 2 "already covers this" — they cover different failure windows.
