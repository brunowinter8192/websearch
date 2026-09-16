# dev/lane_choice/

## Role
Calibration data collection for a coming lane-choice metrics feature: fires BOTH acquisition
lanes (chromium, camoufox) fresh against every distinct URL in the production scrape log, so a
future feature can compare them on equal, current footing (historical single-lane records are
config/site-drift stale). Also the focus-steal verification harness for both lanes: an automated
gate wrapped around the backfill subprocess (`02_`), and a live HUMAN probe for one or more ad-hoc
URLs (`03_`) — the human watches/types live while a frontmost-app instrument records independently,
since a human judgment call ("did my focus actually get stolen") is not something an automated
tally alone settles. As of 2026-08-27, a second (AXMain/key-window) instrument that used to run
alongside the frontmost-app one was removed from both scripts — live human-judged runs, including
against 5 real URLs sequentially under sustained load, found that signal fires constantly with ZERO
perceived focus loss, a phantom signal carrying no information about real focus (see
`process-docs/camoufox_lane/`). Also the content/boilerplate metrics report (`04_`) over EVERY
both-lanes-ok paired scrape currently in the production log (not a fixed batch) — a mechanical
Kohlschuetter Algorithm 2 classifier plus the jusText heading rescue, plus a block-level PROSE test
(CONTENT + a corpus-derived length cap + a sentence-ending mark) that catches a single long
markdown line of embedded JSON/CSS/markup passing the CONTENT tree with an unbounded word count —
reporting per-lane content-word/block/PROSE counts with no verdict on which lane is better. Touch
this directory when extending the backfill's own resume/report shape, the
focus-steal instrumentation, or the content-metrics classifier/report shape; not the lane
implementations themselves — those are `src/scraper/chromium_scrape.py`/`camoufox_scrape.py`.

## Public Interface
No `__init__.py` — all four scripts are standalone CLI entry points, run directly:
`./venv/bin/python dev/lane_choice/01_backfill_pairs.py [--limit N]`,
`./venv/bin/python dev/lane_choice/02_focus_poll_smoke.py [--limit N]` (wraps the former as a
subprocess), `./venv/bin/python dev/lane_choice/03_live_focus_probe.py [--url URL ...] [--chromium]`
(`--url` may repeat; one countdown up front, then one fresh-browser scrape per URL back-to-back via
THIS worktree's own `cli.py`, for a human to watch live), and
`./venv/bin/python dev/lane_choice/04_lane_metrics.py` (no flags; builds its own pair list from the
production log, see Gotchas).

## Flow
`01_backfill_pairs.py`: distinct URLs from the production `scrape_log.jsonl` → skip already-done
(url, engine) pairs in this dir's own resume-state JSONL → fire each remaining pair via the
production `websearch` CLI → read back its fresh log record → append to resume-state → md/ report.
`02_focus_poll_smoke.py`: launches `01_backfill_pairs.py` as a subprocess while polling a macOS
frontmost-app instrument on a background thread → md/ report with its tally and any violation
samples.
`03_live_focus_probe.py`: one countdown (human switches app + starts typing) → for each `--url` in
order, one real `cli.py scrape_url_camoufox`/`scrape_url_chromium` call directly (never the
`websearch` PATH wrapper), each URL its own fresh browser, back-to-back, launch span recorded per
URL → the same frontmost-app instrument polls continuously across the whole sequence → overall +
per-URL verdict printed to the terminal + full sample series to md/.
`04_lane_metrics.py`: freshest (url, engine) pairs with no `acquisition_error` and real
`bytes_returned` (see Gotchas — the log no longer computes an "ok" verdict of its own) built from
the production `scrape_log.jsonl` → every chromium file's blocks read once, pooled into a
corpus-wide word-count distribution → a
PROSE length cap derived from that distribution (p99) → per URL, per lane, block classification
(Algorithm 2 tree + heading rescue) + the PROSE test → per-lane metrics → per-URL lines + one
all-pairs table + aggregate win/disagreement/cap-exclusion counts + the chromium-zero-CONTENT /
camoufox-PROSE-rescue breakdown, written to md/.

## Modules

### 01_backfill_pairs.py (285 LOC)

**Purpose:** Orchestration only — fires the production `websearch scrape_url_chromium`/
`scrape_url_camoufox` CLI per distinct URL, resumable via its own state file; never writes scrape
content itself (the CLI's own `scrape_log.jsonl`/sidecars do that).
**Reads:** production `scrape_log.jsonl` (hardcoded absolute path to the MAIN repo, never a
worktree copy — see Gotchas); this dir's own `jsonl/backfill_pairs_state.jsonl`.
**Writes:** `jsonl/backfill_pairs_state.jsonl` (appended per fired pair, resumable); `md/01_backfill_pairs_report_<ts>.md`.
**Called by:** `02_focus_poll_smoke.py` (as a subprocess); run directly for a bare backfill with no
focus-steal instrumentation.
**Calls out:** the `websearch` PATH command (subprocess) — see Gotchas.

### 02_focus_poll_smoke.py (127 LOC)

**Purpose:** Focus-steal verification gate for the backfill — a macOS frontmost-app poll (catches a
regular/non-accessory app's steal). REMOVED 2026-08-27: a second, LSUIElement/accessory-process
key-window instrument that used to run alongside it — proven a phantom signal by live human-judged
runs against the original complaint's own sustained-load, multi-URL workload shape (see
`process-docs/camoufox_lane/`), not just the launch-time-only signal it looked like on the smaller
`example.com` runs that motivated it.
**Reads:** nothing of its own; launches `01_backfill_pairs.py` and reads its stdout/exit code.
**Writes:** `md/02_focus_poll_smoke_report_<ts>.md`.
**Called by:** run directly, ad hoc, whenever a lane's focus-steal posture needs re-verifying.
**Calls out:** the `websearch` PATH command indirectly (via `01_backfill_pairs.py`); macOS
`osascript`/System Events for the poll.

### 03_live_focus_probe.py (386 LOC)

**Purpose:** Live HUMAN focus-steal verification for one or more ad-hoc URLs — one visible countdown
so the human can switch away and start typing, then a real scrape per `--url` (repeatable) via this
worktree's own `cli.py` directly (bypasses the `websearch` PATH wrapper Gotcha below on purpose, the
whole reason this script exists), each URL its own fresh browser, back-to-back, no countdown between
them — the workload shape of the original sustained-load complaint (one fresh Camoufox per scraped
URL across a backfill), not just an isolated single launch. The frontmost-app instrument (reused
from `02_`) polls continuously across the WHOLE sequence, not per URL, so `run_urls_in_sequence`
records each URL's own launch span (elapsed seconds since the countdown ended) and
`compute_per_url_verdicts` slices the one continuous sample series back down per URL afterwards. The
verdict (both the pooled whole-sequence one and each per-URL one) reports the instrument's own
OBSERVED sampling resolution (mean inter-sample interval, largest gap, effective rate) alongside its
deviation count — the real `osascript`-round-trip-bound cadence runs slower and less evenly than the
nominal `POLL_INTERVAL_S=0.25s` sleep alone would suggest (a live run measured mean intervals of
0.4-1.0s and gaps up to ~5s), so `longest_continuous_run` derives any open-run dwell estimate from
the samples' own observed gaps, never from the nominal constant, and both the terminal verdict and
the report say so explicitly. A single `--url` behaves the same as before, just as a one-entry
sequence. REMOVED 2026-08-27: a second (AXMain/key-window) instrument and its target-app-name
resolution (`resolve_target_app_name`/`_resolve_chromium_app_name`) — the live 5-URL sustained-load
check this script itself enabled found that signal fires constantly with zero perceived focus loss
(see `process-docs/camoufox_lane/`).
**Reads:** nothing of its own; imports `02_focus_poll_smoke.py`'s `get_frontmost_app` via
`importlib.util.spec_from_file_location` (filename starts with a digit, not `import`-able
directly); launches this worktree's own `cli.py` as a subprocess, once per URL.
**Writes:** `md/03_live_focus_probe_report_<ts>.md` (per-URL launch spans, overall + per-URL
verdict, full sample series).
**Called by:** run directly, ad hoc, whenever a human needs to eyeball a lane's live focus posture
(as opposed to `02_`'s automated tally over the backfill).
**Calls out:** this worktree's own `venv/bin/python cli.py` (subprocess, real production entry
point, one call per URL); macOS `osascript`/System Events (via the imported `02_` function).

### 04_lane_metrics.py (62 LOC)

**Purpose:** Orchestrates the pair-collection → PROSE-cap → per-URL classification → aggregate →
report pipeline, importing each step from its own sibling module below. Neither the script nor its
report ever states which lane is "better" — purely descriptive.
**Reads:** nothing directly — delegates to `_lane_metrics_pairing.py`.
**Writes:** nothing directly — delegates to `_lane_metrics_report.py`.
**Called by:** run directly, ad hoc, whenever the full paired corpus needs a fresh content-density
measurement.
**Calls out:** none — stdlib only (`sys`, `time`).

### _lane_metrics_pairing.py (68 LOC)

**Purpose:** Builds the URL pair list from the production log — freshest no-`acquisition_error`,
real-`bytes_returned`, `content_path`-bearing record per `(url, engine)`, paired across both lanes.
**Reads:** the production `scrape_log.jsonl` (hardcoded absolute path to the MAIN repo, never a
worktree copy — same convention as `01_backfill_pairs.py`, see Gotchas).
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none — stdlib only (`json`).

### _lane_metrics_blocks.py (77 LOC)

**Purpose:** Reads one scrape_content `.md` file into blocks (non-comment, non-empty lines with
>=1 token), each carrying its own word count, link density, heading flag and sentence-end flag.
**Reads:** the scrape_content `.md` file passed to `read_blocks`, line-by-line (several camoufox
files run past 1MB, the largest so far ~52MB).
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`, `_lane_metrics_prose.py`.
**Calls out:** none — stdlib only (`re`).

### _lane_metrics_classify.py (66 LOC)

**Purpose:** Kohlschuetter/Fankhauser/Nejdl (WSDM 2010) Algorithm 2's decision tree over
`numWords`/`linkDensity`, adapted to markdown image/link syntax, plus the jusText-style
short-heading rescue rule applied once afterwards.
**Reads:** nothing — pure functions over an already-read block list.
**Writes:** nothing.
**Called by:** `_lane_metrics_prose.py`.
**Calls out:** none — stdlib only.

### _lane_metrics_prose.py (90 LOC)

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

### _lane_metrics_aggregate.py (55 LOC)

**Purpose:** Cross-pair aggregate over every URL's per-lane metrics — CONTENT-word/percentage
wins, cap-exclusion totals per lane, and how many chromium-zero-CONTENT pairs camoufox rescues
with a PROSE block.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none — stdlib only.

### _lane_metrics_report.py (136 LOC)

**Purpose:** Renders the per-URL sections, the all-pairs table, the PROSE-cap section and the
aggregate/rescue sections into one markdown report and writes it.
**Reads:** nothing.
**Writes:** `md/04_lane_metrics_report_<ts>.md` only; never touches the production log, the source
`scrape_content` files, or `01_`'s resume state.
**Called by:** `04_lane_metrics.py`.
**Calls out:** `_lane_metrics_aggregate.py` (for `LANES`), `_lane_metrics_prose.py` (for
`PROSE_PERCENTILE`).

---

## State
`jsonl/backfill_pairs_state.jsonl` is the backfill's own resume state — one line per fired
(url, engine) pair, owned and appended-to exclusively by `01_backfill_pairs.py`; read (never
mutated) by nothing else in this package. `md/` holds every report ever produced by any of the
four scripts, timestamped, never overwritten.

## Gotchas
- **The `websearch` command on PATH is pinned to the MAIN repo's `cli.py`, never a worktree.**
  `01_backfill_pairs.py`'s `WEBSEARCH_CMD = "websearch"` resolves via the shell PATH wrapper at
  `~/.local/bin/websearch`, which is a fixed shell script (`exec .../websearch/cli.py "$@"` against
  the main repo's own absolute path) — confirmed by reading the wrapper directly. This means
  **neither script in this directory can ever exercise an unmerged worktree's own `src/scraper/`
  changes** — every real launch runs the main repo's currently-merged code, regardless of which
  worktree these scripts themselves are edited/run from. Discovered concretely 2026-08-25: a
  2-URL `02_focus_poll_smoke.py` smoke run intended to verify a worktree-only camoufox focus-steal
  fix instead showed the OLD pre-fix behavior (sustained multi-second key-window steals) — traced
  to this wrapper, not a defect in the fix itself; direct verification required invoking the
  worktree's own `venv/bin/python cli.py <subcommand> <url>` in place of the `websearch` PATH
  command (see `process-docs/camoufox_lane/`). Do not treat an all-green
  `02_focus_poll_smoke.py` run as evidence about an unmerged worktree change — it only proves
  something about whatever is currently in the main repo. `03_live_focus_probe.py` builds this
  worktree-direct invocation in from the start (`WORKTREE_ROOT = Path(__file__).resolve().parents[2]`,
  never `WEBSEARCH_CMD`) — it is the one script here safe to use for verifying an unmerged change.
- `PROD_SCRAPE_LOG_PATH` (`01_backfill_pairs.py`) is a hardcoded absolute path into the main repo's
  `src/logs/scrape_log.jsonl`, deliberately — worktrees have their own, separate, gitignored
  `src/logs/` tree, and the backfill's whole premise is enumerating URLs the MAIN repo has actually
  seen in production. Do not "fix" this to a relative/worktree-local path without re-deriving that
  premise first.
- `--limit N` selects the first N URLs of the FULL distinct-URL list, not "the next N unprocessed"
  — with M pairs already resumed/skipped, a smoke run needs `--limit (M/2 + desired_new_urls)` to
  actually fire new pairs rather than skip-looping through already-done ones (skips are near-instant,
  so a too-low limit just produces an empty-feeling report, not a hang).
- **`03_live_focus_probe.py` has no CLI flag or env var to disable any part of the camoufox lane's
  no-focus-steal fix for an A/B measurement, and must never get one — that would be a permanent
  surface for a temporary question.** The one-line-throwaway-branch-edit technique this Gotcha used
  to require for the (now-removed) watchdog is recorded historically in `process-docs/lane_choice/`
  and `process-docs/camoufox_lane/` — the same pattern (edit on a never-merged branch, run, revert in
  the same session, verify an empty `git diff integration -- src/`) applies to any future throwaway
  A/B question against this lane, but nothing here should be built to support it permanently.
- **`_lane_metrics_pairing.py`'s `PROD_SCRAPE_LOG_PATH` is the same hardcoded-absolute-path-into-the-MAIN-repo
  convention as `01_backfill_pairs.py`'s constant of the same name, and for the same reason** —
  worktrees have their own separate, gitignored `src/logs/` tree, so a worktree-relative path would
  silently see nothing. As of 2026-08-27 this REPLACED the earlier fixed `/tmp/lane_pairs_20.json`
  20-URL file (still referenced by `process-docs/lane_choice/2026-08-27_metric_vs_judgment_no_edge.md`
  as the source of one specific historical report, `04_lane_metrics_report_20260827T171744Z.md`,
  kept on disk for that reason — do not delete it). `collect_pairs_from_scrape_log()` takes the
  FRESHEST record with no `acquisition_error` and real `bytes_returned`, plus a `content_path`,
  per `(url, engine)` — the production log's own `"outcome"` field was REMOVED (see
  `src/scraper/DOCS.md`'s Gotchas: `acquisition_error` is logged as its own fact instead of being
  collapsed into a computed `ok`/`empty` verdict); `_latest_ok_records_by_url_engine` reconstructs
  the identical "ok" meaning off those two facts, which reads the same way on both a pre-removal
  record (real `"outcome": "ok"`, `acquisition_error` absent, real bytes) and a post-removal one (no
  `"outcome"` key at all). The log accumulates across sessions (some URLs have both a 2026-08-13
  general-use record and a later 2026-08-25/27 paired-backfill record for the same engine) — and
  pairs every URL with a freshest record on BOTH lanes. The pair count is therefore NOT fixed at
  111; it tracks whatever the production log currently contains.
- **The PROSE cap (`PROSE_PERCENTILE = 99`) is recomputed from the corpus on every run, never a
  hardcoded word count.** `compute_prose_cap` pools `num_words` across every block of every
  chromium file in the CURRENT pair set and takes the 99th percentile
  (`statistics.quantiles(..., n=100, method="inclusive")`) — a run against a future, larger corpus
  will derive its own cap, which may differ from any value quoted in an existing report or
  process-docs entry. See `process-docs/lane_choice/2026-08-27_prose_cap_and_corpus_wide_run.md` for
  the distribution that produced the first cap value (72 words) and why p99 was chosen over other
  percentiles.
- **A "comment line" for `_lane_metrics_blocks.py`'s block filter means the ENTIRE line is one or more
  HTML comments** (`COMMENT_LINE_RE = ^<!--.*-->$`), matching the sidecar header exactly. A line
  with a comment mixed into other content (e.g. `</div><!-- #page -->`, seen in real camoufox
  `mode: markdown` output) is NOT stripped and becomes a normal block, tag text and all — this is
  the spec's literal definition, not an oversight, so camoufox files with leftover raw HTML/script
  fragments can inflate `blocks_total`/`words_total` well beyond what a human would call "content".
