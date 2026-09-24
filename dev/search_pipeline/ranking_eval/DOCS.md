# dev/search_pipeline/ranking_eval/

## Role
Ranking-method evaluation harness: pool fetch, method runs (BM25, BM25-capped, overlap, reranker, SPLADE, LLM), Jaccard aggregation against oracle selections, plus BM25 variant smokes. Touch to rerun or extend pooling investigations; not production ranking.

## Public Interface
No `__init__.py`. Entry scripts run as `./venv/bin/python dev/search_pipeline/ranking_eval/<script>.py`. They import the shared bases `bm25_sweep_smoke.py` and `rerank_probe_smoke.py` from the parent directory via a `sys.path` insert of that directory.

## Flow
`stage1_pool_fetch` (or `value_eval_probe`) writes per-pair pool JSON under `../runs/<ts>/`; `stage3_method_run*` applies the methods; `stage4_aggregate*` and `value_eval_aggregate` score them against oracle JSON and write eval Markdown next to the data.

## Modules

### stage1_pool_fetch.py (189 LOC)

**Purpose:** Pool fetch (v3 schema): four modes by four queries, per-pair pool JSON plus engine report and global engine summary.
**Reads:** imports pool builders from the parent bases.
**Writes:** `../runs/value_eval_v3_<ts>/` pool JSON, engine reports, `engine_report_summary.md`.
**Called by:** CLI only (`--smoke`, `--ts-dir`).
**Calls out:** parent bases `bm25_sweep_smoke.py`, `rerank_probe_smoke.py`; config and report siblings.

### _stage1_pool_fetch_config.py (2 LOC)

**Purpose:** Shared mode list for the stage-1 entry and its report.
**Reads:** none.
**Writes:** none.
**Called by:** `stage1_pool_fetch.py`, report sibling.
**Calls out:** stdlib only.

### _stage1_pool_fetch_report.py (184 LOC)

**Purpose:** Engine report Markdown and cross-pair engine summary for stage 1.
**Reads:** none (arguments only).
**Writes:** `<ts_dir>/<mode>_<slug>_engine_report.md`, `engine_report_summary.md`.
**Called by:** `stage1_pool_fetch.py`.
**Calls out:** config sibling.

### stage3_method_run.py (179 LOC)

**Purpose:** Method run v2: applies overlap, BM25, BM25-capped and cross-encoder to each pool, writes methods JSON.
**Reads:** `<ts_dir>/*_pool.json`.
**Writes:** `<ts_dir>/<mode>_<slug>_methods.json`.
**Called by:** CLI only (`--ts-dir`, `--smoke`).
**Calls out:** `httpx`, RAG `server_manager`, parent bases.

### stage3_method_run_v3.py (193 LOC)

**Purpose:** Method run v3: filters engines via `clean_pool`, then runs twelve methods M1-M12 per pool and writes methods JSON.
**Reads:** `<pool_dir>/*_pool.json`.
**Writes:** `<pool_dir>/<mode>_<slug>_methods_v3.json`.
**Called by:** CLI only (`--pool-dir`, `--smoke`).
**Calls out:** `clean_pool.py`, RAG `server_manager`, parent bases, cheap and gpu siblings.

### _stage3_method_run_v3_cheap.py (69 LOC)

**Purpose:** CPU-only methods M1-M5: overlap, RRF, structural URL penalty, BM25, BM25-capped.
**Reads:** none (arguments only).
**Writes:** none.
**Called by:** `stage3_method_run_v3.py`.
**Calls out:** parent base `rerank_probe_smoke.py`, config sibling.

### _stage3_method_run_v3_config.py (2 LOC)

**Purpose:** Shared top-N constant for the v3 method modules.
**Reads:** none.
**Writes:** none.
**Called by:** cheap and gpu siblings.
**Calls out:** stdlib only.

### _stage3_method_run_v3_gpu.py (188 LOC)

**Purpose:** GPU-service methods M6-M12: cross-encoder, instruction prefix, hybrids, SPLADE, LLM filter and selector.
**Reads:** none (service URLs passed in).
**Writes:** none.
**Called by:** `stage3_method_run_v3.py`.
**Calls out:** `httpx`, parent base `bm25_sweep_smoke.py`, config sibling.

### clean_pool.py (215 LOC)

**Purpose:** Pool filter helper and oracle cleanup: drops named engines from pools and rebuilds v3clean oracle files.
**Reads:** `../runs/<v2 ts_dir>/*_oracle.json`.
**Writes:** `<pair>_oracle_v3clean.json`, `oracle_v3clean_summary.md` in the v2 dir.
**Called by:** CLI (`--v2-dir`); `filter_pool` imported by `stage3_method_run_v3.py`.
**Calls out:** stdlib only.

### stage4_aggregate.py (336 LOC)

**Purpose:** Aggregate v2: Jaccard of each method against the oracle, per-pair eval Markdown plus summary.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `<ts_dir>/<mode>_<slug>_eval.md`, `eval_summary.md`.
**Called by:** CLI only (`--ts-dir`, `--no-oracle`).
**Calls out:** stdlib only.

### stage4_aggregate_v3.py (299 LOC)

**Purpose:** Aggregate v3: Jaccard, per-method latency statistics and Pareto table across twelve methods.
**Reads:** `<pool_dir>/*_pool.json`, `*_methods_v3.json`; `<oracle_dir>/*_oracle_v3clean.json`.
**Writes:** `<pool_dir>/<mode>_<slug>_eval_v3.md`, `eval_summary_v3.md`.
**Called by:** CLI only (`--pool-dir`, `--oracle-dir`, `--no-oracle`).
**Calls out:** stdlib only.

### value_eval_probe.py (336 LOC)

**Purpose:** Historical stage 1+2 (v1): fetches pools per mode and query, applies four C-methods, writes oracle-input pool and methods JSON.
**Reads:** hardcoded mode-by-query matrix; live engine fetch.
**Writes:** `../runs/value_eval_<ts>/<mode>_<slug>_pool.json`, `_methods.json`.
**Called by:** CLI only (`--smoke`, `--ts-dir`).
**Calls out:** `httpx`, reranker GPU service, parent bases, `value_eval_aggregate.py`.

### value_eval_aggregate.py (342 LOC)

**Purpose:** Historical stage 4 (v1): Jaccard per pair with per-query and summary Markdown, superseded by the stage4 scripts.
**Reads:** `<ts_dir>/*_pool.json`, `*_methods.json`, `*_oracle.json`.
**Writes:** `../md/value_eval_<mode>_<slug>_<ts>.md`, `value_eval_summary_<ts>.md`.
**Called by:** CLI (`--ts-dir`, `--ts-out`, `--no-oracle`); imported by `value_eval_probe.py`.
**Calls out:** stdlib only.

### pool_diff_v2_v3.py (242 LOC)

**Purpose:** Pool diff: URL overlap and per-engine reliability between a v2 reference dir and a v3 run across sixteen pairs.
**Reads:** `../runs/value_eval_v2_<ts>/` (hardcoded), v3 dir via `--v3-dir` or newest.
**Writes:** `../md/pool_diff_v2_vs_v3.md`.
**Called by:** CLI only.
**Calls out:** stdlib only.

### single_query_pool_dump.py (179 LOC)

**Purpose:** Single-query capped-pool dump comparing four configs side by side with a comparison matrix.
**Reads:** imports pool builders and GPU helpers from the parent bases.
**Writes:** `../md/single_query_pool_<slug>_<ts>.md` (or `--output`).
**Called by:** CLI only (`--query`, `--output`).
**Calls out:** parent bases, report sibling, GPU services.

### _single_query_pool_dump_report.py (203 LOC)

**Purpose:** Section renderers and report writer for the single-query pool dump.
**Reads:** none (arguments only).
**Writes:** report file via `_write_report(path)`.
**Called by:** `single_query_pool_dump.py`.
**Calls out:** stdlib only.

### pooling_probe.py (355 LOC)

**Purpose:** Capped-pool strategy comparison: overlap, BM25, cross-encoder and embedding-cosine on the same pool, hard-stop when google_count is zero.
**Reads:** imports helpers and the 20-query set from the parent bases.
**Writes:** `../md/pooling_probe_<ts>.md`, `../jsonl/pooling_probe_<ts>.queries.jsonl`.
**Called by:** CLI only.
**Calls out:** parent bases, GPU services (embedding, reranker).

### bm25_capped_smoke.py (212 LOC)

**Purpose:** Per-engine top-K capped BM25 variant compared with hard-slot and uncapped BM25.
**Reads:** imports pool and BM25 helpers from the parent base.
**Writes:** `../md/bm25_capped_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py`, `rank_bm25`, `src.search.{browser,merge,search_web}`.

### bm25_compare_smoke.py (157 LOC)

**Purpose:** Five-config visual compare: hard-slot, vanilla BM25, b=0, b=1, title triple-weight.
**Reads:** imports helpers from the parent base.
**Writes:** `../md/bm25_compare_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py`, `src.search.{browser,merge,search_web}`.

### bm25_idf_engine_smoke.py (231 LOC)

**Purpose:** IDF and engine-inverse-weighting compare across five configs on the same pool.
**Reads:** imports helpers from the parent base.
**Writes:** `../md/bm25_idf_engine_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `bm25_sweep_smoke.py`, `rank_bm25`, `src.search.{browser,merge,search_web}`.

---

## State
Run data lives in `../runs/<ts_dir>/`; eval Markdown from the stage4 scripts is co-located with it by design. GPU-backed scripts need the RAG reranker, embedding, SPLADE or generator servers running.
