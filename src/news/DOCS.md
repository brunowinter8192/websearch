# src/news/

## Role

Multi-platform news ingestion pipeline, run as `python -m src.news --source <platform>`. Discovers articles, dedups against the raw corpus, scrapes raw markdown/HTML into `data/news/{name}/raw/`. For The Block (proxy_pool engine) the pipeline also runs an in-pipe clean-pass that writes cleaned articles into the RAG collection dir. Indexing stays fully decoupled — no `rag-cli index` call in any pipe path. Touch this package to add a news source or change pipeline orchestration; the generic scrape engines live in `engine/`, platform implementations in `platforms/`. Do NOT import from `src/crawler/` or `src/scraper/` — this package is self-contained.

## Public Interface

`__init__.py` is empty; the package runs as a module (`python -m src.news` → `__main__.py`). Direct async entry: `run_pipeline(platform)`, `run_discover_only(platform)`, `run_scrape_only(platform, year=…, limit=…)` in pipeline.py — import path unchanged across the 2026-08-20 module split (pipeline.py stays the entry module; `pipeline_support.py`/`clean_pass.py` are internal-only, no external caller imports from them except `dev/tests/test_theblock_clean_pass.py` → `clean_pass._run_clean_pass`).

## Flow

`__main__` parses args, imports the platform module (side-effect registers it), looks it up via `registry.get`, and calls one of pipeline's three entries. `run_pipeline`: discover → dedup(raw) → scrape → raw persist (+ clean-pass for proxy_pool/TheBlock). `run_scrape_only`: date-filtered backfill, discover-free, dispatched on `platform.scrape_engine`. `run_discover_only`: discover + persist only. Scrape dispatch key is `platform.scrape_engine` ∈ {browser, proxy_pool, proxy_riding}.

## Modules

### pipeline.py (381 LOC)

**Purpose:** Entry module — the 3 CLI-facing async orchestrators (`run_pipeline`, `run_scrape_only`, `run_discover_only`) plus their per-engine arm helpers, dispatching on `platform.scrape_engine`. `run_scrape_only` and `_run_pipeline_proxy_pool` were each split into single-responsibility helpers to stay under the 50-LOC function threshold (pure extraction, same behavior/log output — see Gotchas): `run_scrape_only` → `_scrape_only_preamble` (logging setup, `job_id`/`filter_desc`, internet + `load_scrape_entries`-capability precondition checks, both `sys.exit(1)` on failure); `_run_pipeline_proxy_pool` → one helper per STAGE block (`_stage_discover_proxy_pool`, `_stage_dedup_proxy_pool`, `_stage_scrape_proxy_pool`), with the discover stage returning `None` to signal "abort, already logged+marked" and the dedup stage returning the plain (possibly empty) `new_entries` list so the caller's own `if not new_entries: ...; return False` and the surrounding `try/finally`'s `len(new_entries)` read stay exactly as before.
**Reads:** `data/news/{name}/raw/`, `discover/` (dead_urls.txt, failed_urls.txt, per-year shards, master_urls.txt).
**Writes:** `raw/{hash}.{md,html}`, `raw/manifest.jsonl`, `discover/` block-lists, `scrape_jobs/{job_id}/` reports (via reporters); delegates marker/snapshot/master-list writes to `pipeline_support.py`, clean-pass writes to `clean_pass.py`.
**Called by:** `__main__.py`.
**Calls out:** `platform` (Platform); `engine.dedup` (filter_new_entries); `engine.scrape` (scrape_entries, RegwallGuardError); `engine.proxy_pool` (box_lock, Janitor, AcquireLogger, scrape_entries_proxy); `engine.scrape_job` (scrape_chunks_raw, _append_to_raw_manifest, _update_blocked_urls); `engine.browser_reporter` (write_scrape_report); `engine.proxy_riding` (scrape_entries_riding, RidingScrapeConfig, write_riding_report); `pipeline_support.py` (run bookkeeping + `PROJECT_ROOT`/`LOG_DIR`); `clean_pass.py` (`_run_clean_pass`).

### pipeline_support.py (88 LOC)

**Purpose:** Generic run bookkeeping shared by all 3 `pipeline.py` orchestrators — logging setup, connectivity precondition, and the 3 state-writer helpers (master URL list, discover JSON snapshot, last-run marker); owns `PROJECT_ROOT`/`LOG_DIR`.
**Reads:** `platform.precondition_url` (via `urllib`); existing `master_urls.txt` (set-union merge).
**Writes:** `LOG_DIR/news_{name}_{date}.log`, `LOG_DIR/news_{name}_last_run.txt`, `discover/master_urls.txt`, `discover/discover_{ts}.json`.
**Called by:** `pipeline.py` (all 3 orchestrators + `_run_pipeline_proxy_pool`/`_run_pipeline_browser`).
**Calls out:** none (stdlib `logging`, `urllib.request`, `json`).

### clean_pass.py (65 LOC)

**Purpose:** The proxy_pool/TheBlock clean-pass stage (`_run_clean_pass`) — reads `raw/{hash}.md`, calls `platform.cleanup()`, writes cleaned articles into the RAG collection dir.
**Reads:** `raw_dir/{hash}.md` for each ok entry; existing `clean/bodyless_urls.txt` (set-union merge).
**Writes:** `collection_dir/theblock__{pubdate}__{hash}.md` per cleaned entry; `raw_dir.parent/clean/bodyless_urls.txt` (body-less URLs, set-union, sorted); progress logged every 200 entries.
**Called by:** `pipeline.py:_persist_proxy_pool_results` (proxy_pool arm, only when `n_ok > 0`).
**Calls out:** none (stdlib `re` only).

### __main__.py (160 LOC)

**Purpose:** argparse entry point. Flags: `--source`, `--skip-index` (no-op, CLI compat), `--timeframe`, `--discover-only`, `--scrape-only` (+ `--year/--from/--to/--limit/--browsers/--slots/--cooldown-policy/--page-timeout`). Imports the platform modules for side-effect registration, resolves via `registry.get`, dispatches to the matching pipeline entry. When `--timeframe` is not `delta` and not `--discover-only`, auto-forces `skip_index=True` and prints the manual index reminder. `_add_core_args` was split into `_add_run_mode_args` (`--source`/`--skip-index`/`--timeframe`/`--discover-only`/`--scrape-only`) and `_add_date_filter_args` (`--year`/`--from`/`--to`/`--limit`), called in that order from `_add_core_args` — `add_argument` call order (and therefore `--help` output) is unchanged; verified byte-identical against the pre-split output.
**Reads:** CLI args.
**Writes:** stdout.
**Called by:** the `python -m src.news` entry point.
**Calls out:** `platforms.coindesk`, `platforms.theblock` (side-effect register); `registry` (get); `pipeline` (run_pipeline, run_discover_only, run_scrape_only).

### platform.py (35 LOC)

**Purpose:** The extension seam. Defines the `Platform` Protocol (name, collection, precondition_url, regwall_signals, scrape_engine, scrape_config, proxy_scrape_config; `discover()` + `cleanup()`), plus the `ScrapeConfig` and `ProxyScrapeConfig` dataclasses. `scrape_engine` ∈ {browser, proxy_pool, proxy_riding} is the pipeline dispatch key. Optional attrs (`riding_scrape_config`, `timeframe`, `uses_master_list`) are consumed via `getattr` in pipeline.py, deliberately NOT in the Protocol.
**Called by:** `pipeline.py`, `registry.py`, `platforms/*`, `engine/*`.
**Calls out:** none (stdlib `typing`, `dataclasses`).

### registry.py (19 LOC)

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
