# dev/lane_choice/

## Role
Historical lane-choice calibration package. The camoufox lane was removed from the ad-hoc CLI on
2026-08-27 by user decision (`scrape_url_camoufox` no longer exists in `cli.py`), so the
chromium-vs-camoufox comparison this directory was built for is HISTORICAL: it stays as a record of
how the lanes were compared, with the reasoning in `process-docs/lane_choice/` and
`process-docs/camoufox_lane/`. Two things still run: the live HUMAN focus-steal probe (`03_`,
chromium lane only) and the content/boilerplate metrics report (`04_`), which reads whatever
chromium and camoufox records are currently in the production `scrape_log.jsonl` (camoufox records
are historical data; no new ones are produced). The backfill that fired both lanes fresh per URL and
its focus-steal wrapper were deleted with the camoufox subcommand; their outputs under `md/` and
`jsonl/` are kept. Touch this directory for the focus-steal probe or the content-metrics
classifier/report shape; the lane implementations are `src/scraper/chromium_scrape.py` (and the
still-present `camoufox_scrape.py`).

## Public Interface
No `__init__.py` — both scripts are standalone CLI entry points, run directly:
`./venv/bin/python dev/lane_choice/03_live_focus_probe.py [--url URL ...]` (`--url` may repeat; one
countdown up front, then one fresh-browser `scrape_url_chromium` per URL back-to-back via THIS
worktree's own `cli.py`, for a human to watch live) and
`./venv/bin/python dev/lane_choice/04_lane_metrics.py` (no flags; builds its own pair list from the
production log, see Gotchas).

## Flow
`03_live_focus_probe.py`: one countdown (human switches app + starts typing) → for each `--url` in
order, one real `cli.py scrape_url_chromium` call directly (never the `websearch` PATH wrapper),
each URL its own fresh browser, back-to-back, launch span recorded per URL → a macOS frontmost-app
instrument polls continuously across the whole sequence → overall + per-URL verdict printed to the
terminal + full sample series to md/.
`04_lane_metrics.py`: freshest (url, engine) pairs with no `acquisition_error` and real
`bytes_returned` (see Gotchas — the log no longer computes an "ok" verdict of its own) built from
the production `scrape_log.jsonl` → every chromium file's blocks read once, pooled into a
corpus-wide word-count distribution → a PROSE length cap derived from that distribution (p99) → per
URL, per lane, block classification (Algorithm 2 tree + heading rescue) + the PROSE test → per-lane
metrics → per-URL lines + one all-pairs table + aggregate win/disagreement/cap-exclusion counts +
the chromium-zero-CONTENT / camoufox-PROSE-rescue breakdown, written to md/.

## Modules

### 03_live_focus_probe.py (312 LOC)

**Purpose:** Live HUMAN focus-steal verification for the chromium lane for one or more ad-hoc URLs —
one visible countdown so the human can switch away and start typing, then a real
`scrape_url_chromium` per `--url` (repeatable) via this worktree's own `cli.py` directly (bypasses
the `websearch` PATH wrapper, see Gotchas), each URL its own fresh browser, back-to-back, no
countdown between them. The frontmost-app instrument polls continuously across the WHOLE sequence,
so `run_urls_in_sequence` records each URL's own launch span and `compute_per_url_verdicts` slices
the one continuous sample series back down per URL afterwards. The verdict (pooled and per-URL)
reports the instrument's own OBSERVED sampling resolution alongside its deviation count — the real
`osascript`-round-trip-bound cadence runs slower and less evenly than the nominal
`POLL_INTERVAL_S=0.25s` (a live run measured mean intervals of 0.4-1.0s and gaps up to ~5s), so
`longest_continuous_run` derives any open-run dwell estimate from the samples' own observed gaps.
The former camoufox lane switch (`--chromium` flag, `scrape_url_camoufox`) was removed with the
camoufox subcommand.
**Reads:** nothing of its own; launches this worktree's own `cli.py` as a subprocess, once per URL.
**Writes:** `md/03_live_focus_probe_report_<ts>.md` (per-URL launch spans, overall + per-URL
verdict, full sample series).
**Called by:** run directly, ad hoc, whenever a human needs to eyeball the chromium lane's live
focus posture.
**Calls out:** this worktree's own `venv/bin/python cli.py` (subprocess, real production entry
point, one call per URL); macOS `osascript`/System Events.

### 04_lane_metrics.py (50 LOC)

**Purpose:** Orchestrates the pair-collection → PROSE-cap → per-URL classification → aggregate →
report pipeline, importing each step from its own sibling module below. Neither the script nor its
report ever states which lane is "better" — purely descriptive.
**Reads:** nothing directly — delegates to `_lane_metrics_pairing.py`.
**Writes:** nothing directly — delegates to `_lane_metrics_report.py`.
**Called by:** run directly, ad hoc, whenever the full paired corpus needs a fresh content-density
measurement.
**Calls out:** none — stdlib only (`sys`, `time`).

### _lane_metrics_pairing.py (55 LOC)

**Purpose:** Builds the URL pair list from the production log — freshest no-`acquisition_error`,
real-`bytes_returned`, `content_path`-bearing record per `(url, engine)`, paired across both lanes.
**Reads:** the production `scrape_log.jsonl` (hardcoded absolute path to the MAIN repo, never a
worktree copy — see Gotchas).
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none — stdlib only (`json`).

### _lane_metrics_blocks.py (68 LOC)

**Purpose:** Reads one scrape_content `.md` file into blocks (non-comment, non-empty lines with
>=1 token), each carrying its own word count, link density, heading flag and sentence-end flag.
**Reads:** the scrape_content `.md` file passed to `read_blocks`, line-by-line (several camoufox
files run past 1MB, the largest so far ~52MB).
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`, `_lane_metrics_prose.py`.
**Calls out:** none — stdlib only (`re`).

### _lane_metrics_classify.py (59 LOC)

**Purpose:** Kohlschuetter/Fankhauser/Nejdl (WSDM 2010) Algorithm 2's decision tree over
`numWords`/`linkDensity`, adapted to markdown image/link syntax, plus the jusText-style
short-heading rescue rule applied once afterwards.
**Reads:** nothing — pure functions over an already-read block list.
**Writes:** nothing.
**Called by:** `_lane_metrics_prose.py`.
**Calls out:** none — stdlib only.

### _lane_metrics_prose.py (79 LOC)

**Purpose:** The PROSE test layered on top of Algorithm 2's CONTENT/BOILERPLATE verdict — CONTENT,
word count at or under a corpus-derived length cap, and containing a sentence-ending mark
(`.`/`!`/`?`) — added because a single very long markdown line (embedded JSON/CSS/markup) can pass
the CONTENT tree with a huge word count no real prose block has (real corpus evidence: a 404 page
scoring 91% CONTENT off a 5,521-word "block"). The cap itself is derived at runtime, never
hardcoded: the 99th percentile of the pooled block-word-count distribution across every chromium
file in the corpus (chromium output is post-`PruningContentFilter`, the best available proxy for
prose length in this project) — see
`process-docs/lane_choice/2026-08-27_prose_cap_and_corpus_wide_run.md` for the full distribution
and the reasoning.
**Reads:** nothing directly — takes already-read block lists, or a path via `compute_file_metrics`.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** `_lane_metrics_blocks.py`, `_lane_metrics_classify.py`; stdlib `statistics`.

### _lane_metrics_aggregate.py (52 LOC)

**Purpose:** Cross-pair aggregate over every URL's per-lane metrics — CONTENT-word/percentage
wins, cap-exclusion totals per lane, and how many chromium-zero-CONTENT pairs camoufox rescues
with a PROSE block.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none — stdlib only.

### _lane_metrics_report.py (128 LOC)

**Purpose:** Renders the per-URL sections, the all-pairs table, the PROSE-cap section and the
aggregate/rescue sections into one markdown report and writes it.
**Reads:** nothing.
**Writes:** `md/04_lane_metrics_report_<ts>.md` only; never touches the production log or the source
`scrape_content` files.
**Called by:** `04_lane_metrics.py`.
**Calls out:** `_lane_metrics_aggregate.py` (for `LANES`), `_lane_metrics_prose.py` (for
`PROSE_PERCENTILE`).

---

## State
`md/` holds every report ever produced by any of the scripts, timestamped, never overwritten,
including the reports of the deleted backfill and focus-poll wrapper (`01_backfill_pairs_report_*`,
`02_focus_poll_smoke_report_*`). `jsonl/backfill_pairs_state.jsonl` is the resume state of the
deleted backfill: historical, read by nothing.

## Gotchas
- **Historical status of everything camoufox here.** The chromium-vs-camoufox comparison
  (`04_`'s per-lane columns, the `md/` reports, the backfill state) documents a decision that is
  closed: the camoufox subcommand was removed on purpose. Do not re-add a camoufox path here to make
  the historical scripts run again; see `process-docs/lane_choice/` and `process-docs/camoufox_lane/`.
- **The `websearch` command on PATH is pinned to the MAIN repo's `cli.py`, never a worktree.** The
  wrapper at `~/.local/bin/websearch` is a fixed shell script against the main repo's absolute path.
  That is why `03_live_focus_probe.py` invokes `WORKTREE_ROOT/cli.py` directly
  (`WORKTREE_ROOT = Path(__file__).resolve().parents[2]`): it is the one script here safe to use for
  verifying an unmerged worktree change. Background: `process-docs/camoufox_lane/`.
- **`_lane_metrics_pairing.py`'s `PROD_SCRAPE_LOG_PATH` is a hardcoded absolute path into the MAIN
  repo's `src/logs/scrape_log.jsonl`, deliberately** — worktrees have their own separate, gitignored
  `src/logs/` tree, so a worktree-relative path would silently see nothing. `collect_pairs_from_scrape_log()`
  takes the FRESHEST record with no `acquisition_error` and real `bytes_returned`, plus a
  `content_path`, per `(url, engine)` — the production log's own `"outcome"` field was REMOVED (see
  `src/scraper/DOCS.md`'s Gotchas); `_latest_ok_records_by_url_engine` reconstructs the identical "ok"
  meaning off those two facts, which reads the same way on a pre-removal and a post-removal record.
  Pairs need a freshest record on BOTH lanes, so the pair count tracks whatever the production log
  still contains (the log janitor prunes old records) and can only shrink now that no new camoufox
  records are produced. `md/04_lane_metrics_report_20260827T171744Z.md` is kept on disk because
  `process-docs/lane_choice/2026-08-27_metric_vs_judgment_no_edge.md` cites it (that report was built
  from a fixed 20-URL file that no longer exists).
- **The PROSE cap (`PROSE_PERCENTILE = 99`) is recomputed from the corpus on every run, never a
  hardcoded word count.** `compute_prose_cap` pools `num_words` across every block of every chromium
  file in the CURRENT pair set and takes the 99th percentile
  (`statistics.quantiles(..., n=100, method="inclusive")`) — a later run derives its own cap, which
  may differ from any value in an existing report or process-docs entry. See
  `process-docs/lane_choice/2026-08-27_prose_cap_and_corpus_wide_run.md` for the distribution behind
  the first value (72 words) and why p99 was chosen.
- **A "comment line" for `_lane_metrics_blocks.py`'s block filter means the ENTIRE line is one or more
  HTML comments** (`COMMENT_LINE_RE = ^<!--.*-->$`), matching the sidecar header exactly. A line with
  a comment mixed into other content (e.g. `</div><!-- #page -->`, seen in real camoufox
  `mode: markdown` output) is NOT stripped and becomes a normal block, tag text and all — this is the
  spec's literal definition, not an oversight, so camoufox files with leftover raw HTML/script
  fragments can inflate `blocks_total`/`words_total` well beyond what a human would call "content".
