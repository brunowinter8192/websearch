# dev/news_pipeline/theblock/acquire_pipe/

## Role
Production-candidate acquire pipeline for theblock.co: fetches a set of URLs through a rotating proxy pool using browser-impersonating requests, every request a productive fetch. Self-contained dev implementation with no `src/` imports; runs a sustained loop until every URL is done or dead.

## Public Interface
No `__init__.py` — not a package. `acquire_pipe.py` is the CLI entry point; the other modules are helpers imported by flat name, with the parent directory's modules put on the import path.

## Flow
Job orchestrator loads the backfill proxy pool and builds the sitemap target -> takes the global job lock -> sustained rotation loop fetches with cooldown and buffer management, streaming events to a log -> janitor derives a persistent job record and wipes transient artifacts.

## Modules

### p1_fetch.py (37 LOC)

**Purpose:** Browser-impersonating fetch primitive with XML and HTML content validators and a three-way status.
**Reads:** Remote URLs.
**Writes:** Returns status and content bytes.
**Called by:** `p3_target.py`, `p4_loop.py`, `p4_race.py`, `../probe_48h_article_fetch.py`.
**Calls out:** `curl_cffi`.

### p2_cooldown.py (42 LOC)

**Purpose:** In-memory per-job cooldown tracking of burned proxies with eligibility filtering.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `p3_target.py`, `p4_loop.py`, `p6_buffer.py`, `acquire_pipe.py`.
**Calls out:** `../proxy_status_log.py`.

### p3_target.py (53 LOC)

**Purpose:** Sitemap target builder: fetches the theblock index and parses sub-sitemap URLs, direct first with proxy fallback.
**Reads:** The theblock sitemap index.
**Writes:** Returns the sub-sitemap URL list.
**Called by:** `acquire_pipe.py`.
**Calls out:** `httpx`, `p1_fetch.py`, `p2_cooldown.py`.

### p4_loop.py (309 LOC)

**Purpose:** Sustained concurrent rotation loop with periodic pool refresh, exhaustion wait, tail race, and a two-strike burn lifecycle.
**Reads:** A pool provider callback and the target URL list.
**Writes:** Delegates state to the logger and cooldown manager; returns done, dead, and gap lists.
**Called by:** `acquire_pipe.py`.
**Calls out:** `p1_fetch.py`, `p2_cooldown.py`, `p5_logger.py`, `p6_buffer.py`.

### p4_race.py (119 LOC)

**Purpose:** One-shot race loop variant with workers pulling URL and proxy pairs, no cooldown or refresh.
**Reads:** Caller-supplied proxy pool and URL list.
**Writes:** Returns done and gap lists.
**Called by:** none. DEAD CODE, not wired into the orchestrator.
**Calls out:** `p1_fetch.py`, `p5_logger.py`, `p6_buffer.py`.

### p5_logger.py (41 LOC)

**Purpose:** Streams fetch events to a line-buffered JSONL file, kill-safe, with no in-memory counters.
**Reads:** Events pushed by the loops.
**Writes:** `acquire_pipe_logs/` event stream.
**Called by:** `p4_loop.py`, `p4_race.py`, `acquire_pipe.py`.
**Calls out:** `../proxy_status_log.py`.

### box_lock.py (97 LOC)

**Purpose:** Global single-job file lock so only one acquire job runs system-wide, with a JSON sidecar and stale recovery.
**Reads:** The lock sidecar.
**Writes:** Lock and sidecar files in `~/.websearch-locks/`.
**Called by:** `acquire_pipe.py`.
**Calls out:** none.

### p6_buffer.py (39 LOC)

**Purpose:** Active-buffer helpers for the loop: build and refill the eligible proxy buffer; holds buffer and concurrency defaults.
**Reads:** Proxy pool and cooldown eligibility.
**Writes:** Returns new buffer lists.
**Called by:** `p4_loop.py`, `p4_race.py`, `acquire_pipe.py`.
**Calls out:** `p2_cooldown.py`, `../proxy_status_log.py`.

### p7_janitor.py (140 LOC)

**Purpose:** Job lifecycle: wipes transient artifacts at start, derives the persistent job record and plot at end.
**Reads:** The streamed event log.
**Writes:** `acquire_pipe_jobs/<job_id>/` job summary and plot.
**Called by:** `acquire_pipe.py`.
**Calls out:** `matplotlib` (lazy).

### acquire_pipe.py (142 LOC)

**Purpose:** Job orchestrator wiring pool load, target build, lock, cooldown, sustained loop, content persistence, and janitor.
**Reads:** The backfill pool and the theblock sitemap index.
**Writes:** `acquire_pipe_output/` raw sub-sitemaps and the article URL list; job record via the janitor.
**Called by:** CLI only.
**Calls out:** `box_lock.py`, `p2_cooldown.py` to `p7_janitor.py`, `../curated_sources.py`.

---

## State
`acquire_pipe_jobs/` is the only persistent output; the log and report folders are wiped at job start and end. Cooldown state is in-memory per job. Loop semantics and gotchas: process-docs area news_pipeline.
