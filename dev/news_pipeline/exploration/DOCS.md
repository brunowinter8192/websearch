# dev/news_pipeline/exploration/

## Role
Manual UI exploration probes for CoinDesk. Goal: learn page structure (button selectors, DOM shape, load-more mechanics, network patterns) before building production-grade discovery scripts. NOT a production pipeline. `01_coindesk_ui_probe.py` runs headed (`headless=False` default); `02_coindesk_pagination_probe.py` runs headless-only (Playwright, HAR capture).

## Modules

### 01_coindesk_ui_probe.py (222 LOC)

**Purpose:** Pydoll-driven playthrough of `https://www.coindesk.com/latest-crypto-news`. Learns the "More stories" button selector, click mechanics, article URL pattern, and how many clicks cover a 24h window. Outputs per-batch article URLs + time labels + button descriptor.
**Reads:** live CoinDesk site.
**Writes:** `01_output/probe_<UTC-timestamp>.json` (per-batch breakdown + button descriptor + summary), `~/tmp/coindesk_button_pos.png` (screenshot for selector debugging).
**Called by:** CLI only. `--headless` to run headless.
**Calls out:** `_01_dom.py` (this directory) for the pydoll/CDP DOM-scripting layer.

### _01_dom.py (215 LOC)

**Purpose:** pydoll/CDP DOM-scripting layer for `01_coindesk_ui_probe.py` — Chromium launch options and the JS snippets + async wrappers that inspect, extract, count, find and click against the live page.
**Reads:** nothing — takes a pydoll `tab` handle from `01_coindesk_ui_probe.py`.
**Writes:** nothing directly — returns data to `01_coindesk_ui_probe.py`.
**Called by:** `01_coindesk_ui_probe.py` only.
**Calls out:** `pydoll`.

### 02_coindesk_pagination_probe.py (24 LOC)

**Purpose:** CLI entry point — parses `--depth` and dispatches to quick mode or depth mode.
**Reads:** nothing.
**Writes:** nothing directly.
**Called by:** CLI only. `--depth` for ceiling-finder mode.
**Calls out:** `_02_quick.py`, `_02_depth.py` (this directory).

### _02_dom.py (131 LOC)

**Purpose:** Shared Playwright page-scripting layer for both `02` modes — JS snippets + wrappers for article extraction, feed-count polling, and oldest-date computation.
**Reads:** nothing — takes a Playwright `page` handle from the caller.
**Writes:** nothing.
**Called by:** `_02_quick.py`, `_02_depth.py`.
**Calls out:** none.

### _02_quick.py (205 LOC)

**Purpose:** Quick-mode probe (`probe_workflow`) — Playwright system Chrome (headless) against `/latest-crypto-news`, 5 clicks + full HAR capture, live network-response logging keyed by click number. Finding: first ~5 clicks reveal pre-embedded SSR articles (Next.js RSC payload, no network); after that, each click fires a cursor-based timeline API (`GET /api/v1/articles/timeline?size=16&lastId=<UUID>&lastDisplayDate=<ISO>`).
**Reads:** live CoinDesk site.
**Writes:** `02_output/session.har` (~19MB), `02_output/report_<UTC-timestamp>.md`.
**Called by:** `02_coindesk_pagination_probe.py` only.
**Calls out:** `playwright`; `_02_dom.py`, `_02_report.py` (this directory).

### _02_depth.py (164 LOC)

**Purpose:** Depth-mode probe (`depth_workflow`) — click until disabled/plateau/150-cap, lightweight coindesk-only network log (no HAR). Finding: 150 clicks → 2414 unique URLs, oldest 2026-01-23 (~5 months), no ceiling hit. API returns 403 to plain curl and curl_cffi-chrome (needs exact browser header/cookie/token set).
**Reads:** live CoinDesk site.
**Writes:** `02_output/depth_report_<UTC-timestamp>.md`.
**Called by:** `02_coindesk_pagination_probe.py` only.
**Calls out:** `playwright`; `_02_dom.py`, `_02_report.py` (this directory).

### _02_report.py (185 LOC)

**Purpose:** Markdown report assembly for both quick mode (`write_report`, including the click-1-vs-click-2 request diff) and depth mode (`write_depth_report`).
**Reads:** nothing — takes each mode's result data as arguments.
**Writes:** nothing directly — the `write_*` functions perform the file writes to paths given by the caller.
**Called by:** `_02_quick.py`, `_02_depth.py`.
**Calls out:** none.

### 03_coindesk_backfill_traversal.py (336 LOC)

**Purpose:** Uncapped browser-driven backfill of `/latest-crypto-news`. Reuses production `discover.py` Chrome machinery (pydoll headed Chrome via `open -gna`, CDP). Clicks "More stories" until button GONE / persistently DISABLED (3 retries, 2s wait + scroll nudge each) / plateau (3 consecutive no-growth clicks). Live-blog URLs (slug starts with `live-`) filtered from output. Known issue: `timeLabel` DOM walk in `_JS_EXTRACT` causes +3.23s/160-click slowdown — fix required before uncapped Stage B run.
**Reads:** live CoinDesk site.
**Writes:** `03_output/urls_<ts>.json` (final, production `build_entries()` shape `{url, lastmod, publication_date, title, section}`), `03_output/checkpoint_urls.json` (crash-safe, overwritten every 50 clicks + on exit).
**Called by:** CLI only. No flag: bounded run cap=`STAGE_A_CAP`(400); `--cap N` override; `--full` uncapped Stage B.
**Calls out:** `_03_capture.py`, `_03_log.py`, `_03_report.py` (this directory).

### _03_capture.py (216 LOC)

**Purpose:** pydoll/CDP browser launch + click/extract/button-state JS wrappers for `03`, including the disabled-button retry-with-scroll-nudge mechanism.
**Reads:** nothing — takes a pydoll `tab` handle from the caller.
**Writes:** nothing.
**Called by:** `03_coindesk_backfill_traversal.py` only.
**Calls out:** `pydoll`.

### _03_log.py (23 LOC)

**Purpose:** Live-tailable progress log writer (header + per-click line) for `03_coindesk_backfill_traversal.py`.
**Reads:** nothing — writes to the log file handle given by the caller.
**Writes:** `03_output/progress_<ts>.log` (flush per click).
**Called by:** `03_coindesk_backfill_traversal.py` only.
**Calls out:** none.

### _03_report.py (140 LOC)

**Purpose:** Stage A sanity report assembly — timing stats, DOM growth trend, and the Stage B click/time projection to CoinDesk's founding date.
**Reads:** nothing — takes `03`'s result values as arguments.
**Writes:** nothing directly — `write_run_report` performs the file write to the path given by `03_coindesk_backfill_traversal.py`. Produces `03_output/report_stage_a_<ts>.md`.
**Called by:** `03_coindesk_backfill_traversal.py` only.
**Calls out:** none.

### 04_coindesk_timeline_replay_probe.py (148 LOC)

**Purpose:** Orchestrates the capture → replay → cursor-loop → report pipeline for the Timeline API probe. Finding: HTTP replay works — cursor loop of 7 calls returns 200 at ~0.27s each. Endpoint: `GET /api/v1/articles/timeline?size=16&lastId=<UUID>&lastDisplayDate=<ISO>&lang=en`; cursor = last article's `_id` (lastId) + `articleDates.displayDate` (lastDisplayDate).
**Reads:** live CoinDesk site + timeline API.
**Writes:** `04_output/report_<ts>.md`.
**Called by:** CLI only. `--loop N` (default 3, cursor-loop calls after initial capture), `--delay S` (default 0.3), `--rate-test` (rerun loop with 2s delay).
**Calls out:** `_04_capture.py`, `_04_replay.py`, `_04_report.py` (this directory).

### _04_capture.py (118 LOC)

**Purpose:** Captures CoinDesk timeline API requests via background Chrome + pydoll HAR recorder (full wire headers incl. `sec-ch-ua*`). Establishes minimum header set for replay (Referer, User-Agent, `sec-ch-ua*` — no cookie/auth required).
**Reads:** live CoinDesk site.
**Writes:** nothing directly — returns the captured HAR entry to the caller.
**Called by:** `04_coindesk_timeline_replay_probe.py` only.
**Calls out:** `pydoll`.

### _04_replay.py (325 LOC)

**Purpose:** Dual-client HTTP replay (`httpx` + `curl_cffi` Chrome impersonation) of the captured timeline URL, cursor-chained pagination, and 403 diagnostics (header signals, recoverability retest at +10s/+40s).
**Reads:** live CoinDesk timeline API.
**Writes:** nothing directly.
**Called by:** `04_coindesk_timeline_replay_probe.py` only.
**Calls out:** `httpx`, `curl_cffi`.

### _04_report.py (172 LOC)

**Purpose:** Markdown report assembly — captured headers, dual-client replay results, cursor-loop results with 403 diagnostics, and rate-test comparison.
**Reads:** nothing — takes `04`'s result data as arguments.
**Writes:** nothing directly — `write_report` performs the file write to the path given by `04_coindesk_timeline_replay_probe.py`.
**Called by:** `04_coindesk_timeline_replay_probe.py` only.
**Calls out:** none.

### 05_coindesk_cursor_probe.py (241 LOC)

**Purpose:** Investigates cursor validity and storyType distribution across paginated timeline calls. Walk mode: pages through N calls logging all article `_id`/`storyType`/`pathname`/`displayDate`, producing storyType distribution. Fixed mode: chains cursor calls with optional storyType filtering (retry-fallback on 403: falls back to N-1/N-2 cursor article). Findings: storyType distribution (128 articles) News 91.4% / live_news 5.5% / Opinion 3.1%; a deterministic 403 cursor turned out to be a standard "News" article (storyType hypothesis disproved) — the 403 was transient article unavailability, not a storyType rule (confirmed 200 on fresh session); valid anchor rule: any article can be a cursor anchor, fall back to N-1 on 403.
**Reads:** live CoinDesk timeline API.
**Writes:** `05_data/walk_<ts>.md`, `05_data/walk_<ts>_articles.json`, `05_data/fixed_<ts>.md`, `05_data/deep_<ts>.md`.
**Called by:** CLI only. `--mode walk|fixed`, `--n N` (default 25), `--invalid-types T1,T2` (fixed mode), `--delay S` (default 0.3).
**Calls out:** `_05_capture.py`, `_05_parse.py`, `_05_fixed.py`, `_05_report.py` (this directory).

### _05_capture.py (122 LOC)

**Purpose:** pydoll/CDP browser launch + timeline-request capture layer for `05_coindesk_cursor_probe.py`.
**Reads:** nothing — takes a pydoll `tab` handle and a `mode` label from the caller.
**Writes:** nothing directly — returns captured headers/URL/body to the caller.
**Called by:** `05_coindesk_cursor_probe.py` only.
**Calls out:** `pydoll`.

### _05_parse.py (43 LOC)

**Purpose:** Shared article-body parsing and standard-cursor/URL-building utilities used by both walk and fixed modes; a non-JSON body raises.
**Reads:** nothing — pure functions over the caller's response bodies/article lists.
**Writes:** nothing.
**Called by:** `05_coindesk_cursor_probe.py`, `_05_fixed.py`.
**Calls out:** none.

### _05_fixed.py (123 LOC)

**Purpose:** Fixed-cursor mode algorithm — skips invalid-storyType anchors, chains cursor calls, and builds the per-call result rows.
**Reads:** nothing — takes headers/body from the caller.
**Writes:** nothing.
**Called by:** `05_coindesk_cursor_probe.py` only.
**Calls out:** `httpx`; `_05_parse.py` (this directory).

### _05_report.py (156 LOC)

**Purpose:** Markdown report assembly for both walk mode and fixed mode — one section-builder helper per report section per mode.
**Reads:** nothing — takes each mode's result data as arguments.
**Writes:** nothing directly — `write_walk_report`/`write_fixed_report` perform the file writes to paths given by `05_coindesk_cursor_probe.py`.
**Called by:** `05_coindesk_cursor_probe.py` only.
**Calls out:** none.

### 05b_coindesk_warmth_probe.py (332 LOC)

**Purpose:** Measures IP warmth duration after a browser session closes. Captures the first timeline API URL + headers via Chrome (same mechanism as 04), saves to `state.json`, closes Chrome, replays the SAME URL at cumulative intervals (T=0,10,20,30,60,120,180,300s). At first 403: tests httpx feedpage GET re-warm + subprocess cold call. Findings: warmth lasts ≥300s for repeated-URL replays after browser close; warmth is IP-level (fresh subprocess with no prior coindesk connection returns 200 when IP warm); Phase C (rewarm/cold path) not triggered in first run — warmth outlasted the 300s ladder; a deep loop of 350 cursor advances (~4-5min) also fully succeeded.
**Reads:** live CoinDesk site + timeline API.
**Writes:** `05b_output/warmth_<ts>.md`, `05b_output/state.json`.
**Called by:** CLI only.
**Calls out:** `_05b_report.py` (this directory) for the markdown report renderer.

### _05b_report.py (106 LOC)

**Purpose:** Markdown report assembly for `05b_coindesk_warmth_probe.py` — one section-builder helper per report section (header, timing ladder, feedpage rewarm test, subprocess cold test).
**Reads:** nothing — takes `05b`'s result values as arguments.
**Writes:** nothing directly — returns rendered lines; `write_warmth_report` performs the actual file write to the path given by `05b_coindesk_warmth_probe.py`.
**Called by:** `05b_coindesk_warmth_probe.py` only.
**Calls out:** none.

### 06_coindesk_full_discovery.py (348 LOC)

**Purpose:** Combines the browser-capture (04-style timeline URL/header capture) and cursor-loop (05-style pagination) techniques into one full discovery run — captures initial timeline request via background Chrome, then chains cursor calls to exhaustion, writing articles per-year with checkpoint-based resume and rewarm fallback on 403.
**Reads:** live CoinDesk site + timeline API.
**Writes:** `06_output/urls/` (per-year article files), `06_output/progress_<ts>.log`, `06_output/discovery_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `_06_capture.py`, `_06_progress.py`, `_06_report.py` (this directory).

### _06_capture.py (167 LOC)

**Purpose:** pydoll/CDP browser launch + timeline-request capture layer for `06_coindesk_full_discovery.py` — same background-Chrome mechanism as `05b`, reused for this probe's warmup/rewarm cycles.
**Reads:** nothing — takes an `n_clicks` count and an optional log handle.
**Writes:** nothing directly — returns captured headers/URL/body to the caller.
**Called by:** `06_coindesk_full_discovery.py` only.
**Calls out:** `pydoll`, `httpx`.

### _06_progress.py (42 LOC)

**Purpose:** Progress logging and crash-safe checkpoint persistence for `06_coindesk_full_discovery.py`'s cursor loop.
**Reads:** nothing.
**Writes:** `06_output/checkpoint.json`, and (via the caller's open log handle) `06_output/progress_<ts>.log`.
**Called by:** `06_coindesk_full_discovery.py` only.
**Calls out:** none.

### _06_report.py (35 LOC)

**Purpose:** Markdown report assembly for `06_coindesk_full_discovery.py`'s final discovery summary.
**Reads:** nothing — takes `06`'s result dict as an argument.
**Writes:** nothing directly — `write_report` performs the file write to the path given by `06_coindesk_full_discovery.py`.
**Called by:** `06_coindesk_full_discovery.py` only.
**Calls out:** none.

## State
`01_output/` through `06_output/` — all probe run outputs, gitignored. `06_output/checkpoint.json` — crash-safe resume state for `06_coindesk_full_discovery.py`.
