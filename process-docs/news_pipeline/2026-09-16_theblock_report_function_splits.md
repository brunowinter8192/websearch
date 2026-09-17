# theblock probe report splits — orchestrator-written recap (2026-09-16)

The session that produced these two commits was cut off before the worker could write its own
recap. This entry was written by the orchestrator from the merged diff, not from the worker's
report. Treat it as a record of what landed, not as a record of what the worker considered.

## What landed

Two commits in `dev/news_pipeline/theblock/`, both pure report-assembly splits driven by the
`iterative-dev-refactor` Phase 1 function threshold (50 LOC extracts, 100 LOC is a hard target).

- `5f87ec3` — `probe_pool_size.py::build_report_md` was one long list-append body. It became six
  section renderers (`_render_header`, `_render_headline`, `_render_bucket_summary`,
  `_render_source_detail`, `_render_failed_sources`, `_render_baseline_comparison`), each returning
  its own list of lines, with `build_report_md` reduced to concatenation. The module stayed at one
  file, 357 LOC.
- `0c1ab9b` — `probe_discovery.py::build_report` moved out into a new `_probe_discovery_report.py`
  (228 LOC). The entry module dropped from 457 to 308 LOC. The new module carries the cross-method
  comparison, the gap-candidate detection and the `url_type` / `post_id` taxonomy helpers. It reads
  nothing and writes nothing, it takes each method's result data as arguments and returns markdown.

`dev/news_pipeline/theblock/DOCS.md` was updated in both commits, including the LOC numbers and a
correction: `probe_discovery.py` is not CLI-only, `pipe_theblock.py` imports `load_sub_cache`,
`save_sub_cache`, `extract_locs`, `normalize_url` and `CACHE_DIR` from it.

## The one defect a successor must not copy

`5f87ec3` did not delete the inline comments, it promoted them. The original body carried
`# Headline`, `# Per-bucket summary`, `# Per-source detail — one table per bucket`,
`# Failed sources` and `# Baseline comparison` as in-body section labels. The split left each of
them sitting directly above the new `def` line.

That is exactly the heading-over-a-`def` form the code standard names as forbidden. A comment that
was a violation inside a function is still a violation above a function. The only three comment
lines permitted anywhere are `# INFRASTRUCTURE`, `# ORCHESTRATOR` and `# FUNCTIONS`.

The generalised rule for any function split: the comment that marked a block inside the old body
is answered by the new helper's name, and it goes away. If the name cannot carry it, the
explanation belongs in a process-docs entry, never above the `def`.

Both files remain in the Phase 2 backlog for this reason, alongside the rest of `dev/`.

## State of the area as of 2026-09-16

A scan of `dev/news_pipeline/` against the Phase 1 thresholds after these two commits:

- 1 module still over 400 LOC: `theblock/probe_liveness.py` at 410.
- 11 functions still at or above 50 LOC, the largest being `theblock/acquire_pipe/p4_loop.py::run_loop`
  at 111 and `theblock/probe_curl_cffi_discriminator.py::build_report` at 106.

The area entered the sweep with 11 oversized modules and 47 oversized functions, so what is listed
above is the remainder, not the starting point. See `process-docs/refactor_sweep/` for the
orchestrator record of the whole run and the per-area starting numbers.
