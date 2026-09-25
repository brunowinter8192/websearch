# dev/search_pipeline/ranking_eval/

## Role
Offline evaluation of stored ranking-method runs: Jaccard aggregation against oracle selections, pool diffs and oracle cleanup. The scripts that fetched pools and ran the methods were removed. Touch to re-score existing run data; not production ranking.

## Public Interface
No `__init__.py`. Entry scripts run as `./venv/bin/python dev/search_pipeline/ranking_eval/<script>.py`; each script runs standalone.

## Flow
Per-pair pool, methods and oracle JSON under `../runs/<ts>/` in; `stage4_aggregate*` and `value_eval_aggregate` score the methods against the oracle and write eval Markdown next to the data; `pool_diff_v2_v3` compares two runs; `clean_pool` rewrites oracle files.

## Modules

### clean_pool.py (223 LOC)

**Purpose:** Pool filter helper and oracle cleanup: drops named engines from pools and rebuilds v3clean oracle files.
**Reads:** `../runs/<v2 ts_dir>/*_oracle.json`.
**Writes:** `<pair>_oracle_v3clean.json`, `oracle_v3clean_summary.md` in the v2 dir.
**Called by:** CLI only (`--v2-dir`).
**Calls out:** stdlib only.

### stage4_aggregate.py (343 LOC)

**Purpose:** Aggregate v2: Jaccard of each method against the oracle, per-pair eval Markdown plus summary.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `<ts_dir>/<mode>_<slug>_eval.md`, `eval_summary.md`.
**Called by:** CLI only (`--ts-dir`, `--no-oracle`).
**Calls out:** stdlib only.

### stage4_aggregate_v3.py (306 LOC)

**Purpose:** Aggregate v3: Jaccard, per-method latency statistics and Pareto table across twelve methods.
**Reads:** `<pool_dir>/*_pool.json`, `*_methods_v3.json`; `<oracle_dir>/*_oracle_v3clean.json`.
**Writes:** `<pool_dir>/<mode>_<slug>_eval_v3.md`, `eval_summary_v3.md`.
**Called by:** CLI only (`--pool-dir`, `--oracle-dir`, `--no-oracle`).
**Calls out:** stdlib only.

### value_eval_aggregate.py (354 LOC)

**Purpose:** Historical stage 4 (v1): Jaccard per pair with per-query and summary Markdown, superseded by the stage4 scripts.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `../md/value_eval_<mode>_<slug>_<ts>.md`, `value_eval_summary_<ts>.md`.
**Called by:** CLI (`--ts-dir`, `--ts-out`, `--no-oracle`).
**Calls out:** stdlib only.

### pool_diff_v2_v3.py (245 LOC)

**Purpose:** Pool diff: URL overlap and per-engine reliability between a v2 reference dir and a v3 run across sixteen pairs.
**Reads:** `../runs/value_eval_v2_<ts>/` (hardcoded), v3 dir via `--v3-dir` or newest.
**Writes:** `../md/pool_diff_v2_vs_v3.md`.
**Called by:** CLI only.
**Calls out:** stdlib only.

---

## State
Run data lives in `../runs/<ts_dir>/`; eval Markdown from the stage4 scripts is co-located with it by design.
