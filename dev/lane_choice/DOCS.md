# dev/lane_choice/

## Role
Historical lane-choice calibration package: the chromium-versus-camoufox comparison is closed because the camoufox lane was removed from the ad-hoc CLI. Two scripts still run: a live human focus-steal probe (chromium lane) and a content-metrics report over the production scrape log. Touch it for those two.

## Public Interface
No `__init__.py` — not a package. Both numbered scripts are CLI entry points run via `./venv/bin/python`; the underscore modules are helpers of the metrics report.

## Flow
Focus probe: countdown -> real CLI scrape per URL against a frontmost-app poll -> verdict and sample series in `md/`.
Metrics: production scrape log -> URL pairs -> block reading -> classification -> aggregate -> per-URL and all-pairs report in `md/`.

## Modules

### 03_live_focus_probe.py (312 LOC)

**Purpose:** Live human focus-steal verification of the chromium lane over one or more URLs, with per-URL and pooled verdicts.
**Reads:** nothing of its own; launches this worktree's CLI as a subprocess per URL.
**Writes:** `md/03_live_focus_probe_report_<ts>.md`.
**Called by:** CLI only.
**Calls out:** the worktree's own `cli.py`, macOS `osascript`.

### 04_lane_metrics.py (50 LOC)

**Purpose:** Orchestrates pair collection, prose cap, classification, aggregation, and report; purely descriptive, never names a better lane.
**Reads:** nothing directly.
**Writes:** nothing directly.
**Called by:** CLI only.
**Calls out:** the `_lane_metrics_*` modules.

### _lane_metrics_pairing.py (55 LOC)

**Purpose:** Builds the URL pair list from the production scrape log, one freshest usable record per URL and lane.
**Reads:** The main repo's production scrape log.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none.

### _lane_metrics_blocks.py (68 LOC)

**Purpose:** Reads a scraped markdown file into blocks carrying word count, link density, heading and sentence-end flags.
**Reads:** Scrape content markdown files.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`, `_lane_metrics_prose.py`.
**Calls out:** none.

### _lane_metrics_classify.py (59 LOC)

**Purpose:** Content versus boilerplate decision tree (Kohlschuetter et al.) adapted to markdown, plus a short-heading rescue.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_lane_metrics_prose.py`.
**Calls out:** none.

### _lane_metrics_prose.py (79 LOC)

**Purpose:** Prose test on top of the content verdict, using a length cap derived at runtime from the corpus.
**Reads:** nothing directly.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** `_lane_metrics_blocks.py`, `_lane_metrics_classify.py`.

### _lane_metrics_aggregate.py (52 LOC)

**Purpose:** Cross-pair aggregates: content wins, cap exclusions, and prose rescues of chromium-zero-content pairs.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `04_lane_metrics.py`.
**Calls out:** none.

### _lane_metrics_report.py (128 LOC)

**Purpose:** Renders per-URL, all-pairs, cap, and aggregate sections into one markdown report.
**Reads:** nothing.
**Writes:** `md/04_lane_metrics_report_<ts>.md`.
**Called by:** `04_lane_metrics.py`.
**Calls out:** `_lane_metrics_aggregate.py`, `_lane_metrics_prose.py`.

---

## State
`md/` holds every timestamped report ever produced, including those of deleted scripts. `jsonl/` holds the resume state of the deleted backfill, read by nothing. Gotchas (PATH wrapper pinning, hardcoded log path, corpus-derived cap, comment-line definition): process-docs area refactor_sweep.
