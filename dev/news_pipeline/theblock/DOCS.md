# dev/news_pipeline/theblock/

## Role
Discovery + proxy-pool infrastructure for scraping theblock.co past Cloudflare. Own-level modules cover proxy source aggregation, liveness/CF-pass checking, sitemap discovery, and per-source quality tracking. `acquire_pipe/` (own DOCS.md) is the production-candidate fetch pipeline built on top of this infrastructure. `jhao104/` (vendored, undocumented) is a self-maintaining pool probe used as a comparison baseline.

## Modules

### curated_sources.py (262 LOC)

**Purpose:** Unified proxy source hub. Two production loaders + 13 standalone eval loaders + shared fetch/dedup helpers. `load_curated_proxies()` — monosans + proxifly (~3.5k unique), used by existing sitemap dev-runs. `load_backfill_pool()` — all 13 Top-Repo sources merged + deduped → 22,723 unique, used by `acquire_pipe.py --pool backfill` (proxifly excluded — rank 15, below survey cutoff per `probe_repo_cf_survey.py`). 13 standalone eval loaders: monosans (via `monosans_loader`), roosterkid, databay-labs, TheSpeedX, themiralay, r00tee, iplocate, sunny9577, ALIILAPRO, dpangestuw, Zaeem20, zloi-user, hookzof. Universal fetch helper `_fetch_roosterkid(proto, url)` applies `_IP_PORT_RE` (`\d{1,3}(?:\.\d{1,3}){3}:\d+`) to every line — handles bare, scheme-prefixed, and decorated (`host:port:Country`) formats; `_fetch_bare_txt` retained for existing callers.
**Reads:** 13 public proxy-list source URLs.
**Writes:** returns proxy lists (in-memory).
**Called by:** `acquire_pipe/acquire_pipe.py`, `probe_liveness.py` (`--source curated`), `pipe_theblock.py`.
**Calls out:** `monosans_loader`.

### monosans_loader.py (39 LOC)

**Purpose:** Fetch `monosans/proxy-list` live JSON (`proxies.json`) and return `[(protocol, host:port)]` — same tuple shape as `load_frozen_pool()`. Single synchronous `httpx.get`. Handles optional auth fields (currently always null in monosans).
**Reads:** monosans/proxy-list live JSON endpoint.
**Writes:** returns proxy tuple list.
**Called by:** `probe_liveness.py` (`--source monosans`), `curated_sources.load_curated_proxies()`.
**Calls out:** `httpx`.

### proxy_status_log.py (102 LOC)

**Purpose:** Cumulative proxy-status log — keyed by `"protocol://host:port"`, bounded by unique proxy count (not run count). `record_run(results, source_label)` loads `logs/proxy_status_log.json`, upserts every result (alive + dead), writes back. Per-entry schema: `{protocol, host, port, checks, alive, dead, last_status, first_seen, last_seen, cooled_at?}`. `proxy_key(proto, host_port)` — public canonical key builder (auth-stripped `proto://host:port`); shared by `record_run`, `partition_fresh`, and `curated_sources._merge_dedup` — single source of truth for the entire keyspace. `partition_fresh(entries, window_s)` — called by `probe_liveness.py` on the monosans and curated paths — partitions `[(proto, host_port)]` into `(to_check, skipped_fresh)` using the log's `last_seen` field; age comparison is timezone-aware.
**Reads:** `logs/proxy_status_log.json`.
**Writes:** `logs/proxy_status_log.json` (upserted).
**Called by:** `probe_liveness.py`, `curated_sources.py`, `acquire_pipe/p2_cooldown.py`, `acquire_pipe/p5_logger.py`.
**Gotcha:** `load_cooled_at`/`mark_cooled_batch`/`_parse_proxy_key` functions were added then removed in a later iteration when cooldown reverted to in-memory; a `cooled_at` field may still appear in legacy log entries — `probe_liveness.py` never reads it.

### probe_discovery.py (457 LOC)

**Purpose:** Measures discovery coverage + URL taxonomy. Fetches the 64-sub sitemap union, news sitemap, RSS, and bounded UI crawl. Resume-safe via per-sub checkpoint files in `cache/`. CF behaviour: IP-level 403/429 fires after ~21 sequential sub-sitemap fetches.
**Reads:** theblock.co sitemap index, news sitemap, RSS feed.
**Writes:** `discover_coverage_report.md`; per-sub checkpoints in `cache/`.
**Called by:** CLI only.

### probe_pool_size.py (357 LOC)

**Purpose:** Measures raw proxy pool size from 68 public source URLs — pure fetch+parse+count, NO liveness checking, NO proxy contacted. Fetches all sources concurrently (`httpx.AsyncClient`, `Semaphore(20)`, 15s timeout), parses `host:port` entries from bare/`proto://`/`proto://user:pass@` formats. Exports `HTTP_SOURCES`, `SOCKS4_SOURCES`, `SOCKS5_SOURCES` (reused by `probe_repo_cf_survey.py`).
**Reads:** 68 public proxy-list source URLs.
**Writes:** `probe_pool_size_reports/` — per-source counts + per-protocol bucket breakdown + global unique dedup vs baseline. Gitignored.
**Called by:** CLI; `probe_repo_cf_survey.py` (imports source lists).

### probe_repo_cf_survey.py (303 LOC)

**Purpose:** Ranks the source repos from `probe_pool_size.py` by CF-pass rate against theblock.co — samples `SAMPLE_SIZE=1250` per repo at `CONCURRENCY=50`, checks via curl_cffi chrome impersonation against the sitemap index. Produced the rank ordering `curated_sources.py` uses to decide the 13-repo backfill set (proxifly excluded at rank 15).
**Reads:** proxy lists from `probe_pool_size.HTTP_SOURCES`/`SOCKS4_SOURCES`/`SOCKS5_SOURCES`.
**Writes:** `probe_repo_cf_survey_reports/repo_cf_survey_<ts>.md`. Gitignored.
**Called by:** CLI only.

### probe_liveness.py (410 LOC)

**Purpose:** Instrumented async liveness checker + concurrency sweep. Imports the 68 source URL lists from `probe_pool_size.py` (no re-typing). Modes: `--freeze` (fetch sources → write sorted, deduped `frozen_pool/{http,socks4,socks5}.txt`); `--sample N`/`--full` (check frozen pool via `curl_cffi.AsyncSession`); `--source monosans` (fetch live monosans JSON via `monosans_loader`, apply staleness filter, check without freeze); `--source curated` (fetch monosans+proxifly unified list via `curated_sources`, apply staleness filter, check without freeze). Classifies every dead proxy into a reason bucket, appends structured entry to `sweep_log.md`. After every run (all modes except `--freeze`), folds results into cumulative `logs/proxy_status_log.json` via `proxy_status_log.record_run()`. socks5 uses `socks5h://` (remote DNS through proxy). Timeout split: elapsed-time primary + libcurl message fallback + unknown on mismatch (version-drift signal). Staleness filter (`--source monosans`/`--source curated`): calls `proxy_status_log.partition_fresh(entries, window_s)`; `--recheck-window S` (default 3600) controls freshness threshold.
**Reads:** `probe_pool_size` source lists; monosans/curated live sources; `frozen_pool/` (sample/full modes).
**Writes:** `probe_liveness_logs/sweep_log.md` (tracked), `logs/proxy_status_log.json` (tracked, cumulative), `frozen_pool/` (gitignored, `--freeze`), `probe_liveness_logs/unknown_errors_*.log` (gitignored).
**Called by:** CLI only.

### source_tracker.py (283 LOC)

**Purpose:** Per-source attribution, cumulative scoreboard, and freshness tracking. Called once per pipe run via `update_and_flush()`. Reads `source_results` + `hp_to_sources` from `pipe_theblock.fetch_fresh_pool()`, computes per-source `checked`/`alive`/`cf_checked`/`cf_passed`/`unique_latest` counters. Merges run stats into `source_scoreboard.json`, re-renders `source_scoreboard.md`, diffs against `source_snapshots/` for freshness, appends to `freshness_log.md`.
**Reads:** `pipe_theblock.fetch_fresh_pool()` output, `source_scoreboard.json`, `source_snapshots/`.
**Writes:** `source_scoreboard.json` (tracked), `source_scoreboard.md` (tracked, rendered ranking), `freshness_log.md` (tracked, appended), `source_snapshots/` (gitignored).
**Called by:** `pipe_theblock.py`. Not run standalone.

### pipe_theblock.py (339 LOC)

**Purpose:** Full proxy pipeline — Stage 1 (neutral liveness, 5k sample @ conc 128) → Stage 2 (CF-pass check via curl_cffi chrome impersonation vs `sitemap_tbco_post_type_post_0.xml`, 200+valid-XML=pass) → Stage 3 (sitemap sub-URL discovery with sequential-exhaustion B-capture: drains ONE proxy until it 403/429s to record real B observations, then rotates — vs round-robin which never exhausts). Appends one funnel entry to `pipe_log.md` per run. Resume-safe: per-sub checkpoint JSONs in `cache/`.
**Reads:** `curated_sources` fresh 68-source pool.
**Writes:** `pipe_log.md` (tracked, appended), `cache/sub_*.json` (gitignored, per-sub checkpoint).
**Called by:** CLI only. `./venv/bin/python dev/news_pipeline/theblock/pipe_theblock.py`.

### probe_curated_theblock_cf.py (151 LOC)

**Purpose:** Standalone direct CF-pass probe on the monosans+proxifly curated list (no alive pre-filter; curl_cffi chrome impersonation; same gate as jhao104 Stage 2). Finding: 52/3477 = 1.496% overall CF-pass (http 0.944%, socks4 3.567% — leads 3.8×, socks5 0.698%); curated list 17.6× better than jhao104 scraped sources. Home-IP direct check: CF-reputation-clear (200 + XML).
**Reads:** `curated_sources` monosans+proxifly list.
**Writes:** `probe_curated_theblock_cf_reports/`. Gitignored.
**Called by:** CLI only.

### probe_curl_cffi_discriminator.py (261 LOC)

**Purpose:** Discriminates an ambiguous 0/17202 monosans-pool result: re-tests the neutral pool with `curl_cffi impersonate=chrome` (correct browser JA3 vs monosans' rustls) against a real `/post/` sub-sitemap. Identifies which failure mode dominates: CF signature block, CF IP-reputation block, or stale pool. Finding: 80/425 (18.8%) pass → rustls was the blocker; curl_cffi-chrome passes CF; free-proxy loop viable for the discovery gap. Correct sub-URL pattern: `sitemap_tbco_post_type_post_N.xml` (not `post_N.xml`).
**Reads:** neutral proxy pool, `sitemap_tbco_post_type_post_0.xml`.
**Writes:** `probe_curl_cffi_discriminator_reports/`. Gitignored.
**Called by:** CLI only.

### probe_48h_article_fetch.py (172 LOC)

**Purpose:** 48h article delta probe — parallel wave-fetch design: shuffles full pool, fires in 128-proxy waves until first success (exhausts whole pool if needed), no sequential rotation, no cooldown. Flow: load backfill pool (22k) → index direct httpx, on fail `_fetch_parallel(INDEX_URL, pool, "xml")` → filter on `post_type_post`, pick highest trailing-number → `_fetch_parallel(sub_url, pool, "xml")` → parse `<url>` blocks (`<loc>` + `<lastmod>`) → filter `lastmod >= now − hours`; if `≥2` hits take 2, else take 2 newest by lastmod → `_fetch_parallel(url, pool, "html")` per article. `_fetch_parallel`: `pool[:]` shuffle → iterate 128-proxy waves → each wave `ThreadPoolExecutor` + `as_completed` early-return on first `ok=True` + `shutdown(wait=False, cancel_futures=True)`; returns `False, b""` only after all waves exhausted. Reuses `fetch_url`/`XML_MARKERS` from `acquire_pipe/p1_fetch.py`, `load_backfill_pool` from `curated_sources`.
**Reads:** `curated_sources.load_backfill_pool()`, theblock sitemap.
**Writes:** `probe_48h_output/article_0.html`, `article_1.html`. Gitignored.
**Called by:** CLI only. `--hours` (float, default 48; `<2` hits fallback to 2 newest).
**Calls out:** `acquire_pipe.p1_fetch`, `curated_sources`.

### probe_monosans.sh + monosans_cfg_neutral.toml + monosans_cfg_theblock.toml

**Purpose:** Evidence probe for `monosans/proxy-scraper-checker` proxy pool yield against theblock.co. Two runs: neutral `check_url` (icanhazip) and theblock.co sitemap `check_url`. Wrapper handles Docker invocation (native TUI binary requires TTY; Docker path works headless). Finding: neutral pool yields 494/17,202 proxies; theblock check_url yields 0/17,202 — conclusion: use neutral check_url only, theblock.co CF validation is the curl_cffi impersonate="chrome" fetch loop's responsibility.
**Configs:** `monosans_cfg_neutral.toml` (`check_url=https://ipv4.icanhazip.com`, concurrency 512), `monosans_cfg_theblock.toml` (`check_url=https://www.theblock.co/sitemap_tbco_news.xml`, concurrency 50).
**Reads:** monosans/proxy-scraper-checker Docker image.
**Writes:** `monosans_out_neutral/`, `monosans_out_theblock/` (ephemeral, gitignored).
**Called by:** CLI only. `bash probe_monosans.sh {neutral,theblock}`.

## State
`pipe_log.md` (tracked) — funnel log, one entry per `pipe_theblock.py` run: Stage 1 neutral-alive %, Stage 2 CF-pass rate, Stage 3 subs fetched + cache progress, per-IP budget B distribution, wall-clock per stage. `source_scoreboard.json`+`.md` (tracked) — cumulative per-source proxy quality; JSON canonical, MD rendered ranking table. Rank score: `cf_rate` if `cf_checked ≥ 30`, else `alive_rate × exclusivity`. `freshness_log.md` (tracked) — per-run new/dropped proxy diff per source. `probe_liveness_logs/sweep_log.md` (tracked) — liveness sweep log. `logs/proxy_status_log.json` (tracked) — cumulative proxy identity + alive/dead history across all `probe_liveness.py` runs.

Ephemeral/gitignored: `cache/` (sitemap checkpoint JSONs), `monosans_bin/`, `monosans_docker/`, `monosans_out_neutral/`, `monosans_out_theblock/`, `probe_curl_cffi_discriminator_reports/`, `probe_pool_size_reports/`, `probe_repo_cf_survey_reports/`, `probe_curated_theblock_cf_reports/`, `frozen_pool/`, `probe_liveness_logs/unknown_errors_*.log`, `source_snapshots/`, `probe_48h_output/`.

## Gotchas
As of the first pipe run, discovery coverage was 36/64 sub-sitemaps cached, CF-pass rate measured at 0.8% on the live pool (vs 18.8% on the curl_cffi discriminator probe — different sample/proxy source). Per-IP budget B distribution: min=4, max=20, mean=9.3 (3 exhausted proxies) at that measurement point. `jhao104/` (vendored, not documented per convention) — comparison baseline; `theblockValidator` (curl_cffi chrome impersonation vs `sitemap_tbco_index.xml`) measured ~0.085% CF-pass rate (1/1177 across 2 cycles) — see `jhao104/NOTES.md` for setup/findings (not indexed here, stays inside the vendored dir's own notes).
