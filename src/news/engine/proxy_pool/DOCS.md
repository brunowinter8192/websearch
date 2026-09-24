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
