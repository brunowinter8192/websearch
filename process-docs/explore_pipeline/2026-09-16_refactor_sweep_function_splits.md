# explore_pipeline refactor sweep: function splits (2026-09-16)

Worker entry for the `dev/` refactor sweep orchestrated from `process-docs/refactor_sweep/`. This
area's hit list had zero modules over 400 LOC — only functions at or above 50 LOC. No module split
was needed or done here.

## What changed, and why each split is a real concern, not a cosmetic LOC cut

`04_render_recall.py::format_report` (was 70 LOC) — split into `_format_main_results_table`,
`_format_key_url_check`, `_format_recovery_analysis`, `_format_best_strategy_missing`,
`_format_regression_check`. Each maps 1:1 onto one `##`-heading section of the rendered report; the
original already had three inline comments marking these same boundaries
(`# Key URL check`, `# Recovery analysis...`, `# Best strategy missing sample`) — that is strong
evidence the boundaries were already conceptually separate report sections, not an invented cut.

`05_playwright_bfs.py::bfs_crawl` (was 85 LOC) — split into `_build_batch` (frontier -> batch),
`_fetch_batch` (the `asyncio.gather` call), `_handle_429_batch` (429 accounting + backoff,
`async` because it awaits `asyncio.sleep`), `_process_batch_results` (record latency, append to
`found`, enqueue new links), `_build_bfs_stats` (final stats dict). Same pattern: the original had
one inline comment per block (`# Build batch...`, `# Fetch batch...`, `# 429 batch accounting...`,
`# Per-page:...`) and each became the new function's leading comment, moved verbatim, not
reworded.

`05_playwright_bfs.py::format_report` (was 59 LOC) and `04_render_recall.py`'s sibling above use
the same section-per-helper pattern.

`lane_choice/03_live_focus_probe.py::write_report` and `url_discovery/01_resume_state_probe.py
::write_report` (covered under their own areas' entries, listed here only because they're the same
"one helper per `##` section" pattern applied consistently across the whole batch).

`06_nextdata_probe.py::nextdata_discovery_workflow` (was 158 LOC) — this one is different in kind:
it wasn't sections of a report, it was 9 numbered, commented pipeline steps
(`# Step 1: ...` through `# Step 9: ...`) already laid out linearly with `log.append(...)` calls
threaded through. Each step became its own function (`fetch_root_nextdata`, `parse_fpt_sidebar`,
`detect_versions`, `fetch_ghec_sidebar`, `normalize_ghec_urls`, `fetch_ghes_sidebars`,
`union_discovered_urls`, `save_discovered_urls`, `score_against_gold`, `save_full_report`), each
taking the mutable `log: list` and mutating it in place via `.append()` — chosen deliberately over
returning new log-line lists, because it is a strict, verified-byte-identical transcription of what
the orchestrator body already did line-by-line; no re-ordering, no re-computation.

## A pre-existing bug this split surfaced, NOT introduced, NOT fixed

Running the split under a synthetic `--no-ghes` fixture, both the pre-refactor and post-refactor
code raise the identical `UnboundLocalError: ghes_normalized` — reproduced with `git show`'d
pre-refactor code first, confirming it is not a regression. The cause: `ghes_normalized` is only
ever assigned inside `if include_ghes:` (both before and after the split), so
`nextdata_discovery_workflow`'s Step 6 (`union_discovered_urls` in the new code) crashes with
`include_ghes=False`. This is control-flow work — out of this sweep's scope by the task's own
"do not touch except handlers/fallbacks" boundary — and was left exactly as found. A successor who
wants to fix it: the trivial fix is initializing `ghes_normalized: list = []` alongside
`ghes_rest = []` at the top of `fetch_ghes_sidebars`/the old inline block, before the
`if include_ghes:` guard.

## Verification method actually used, and what it cannot see

For every split function: pulled the pre-refactor body via `git show HEAD:<path>` into `/tmp`,
loaded both old and new via `importlib.util.spec_from_file_location` in the same process, fed both
identical synthetic fixtures (fake `fetch_html`/`fetch_page`/`AsyncWebCrawler` — no network),
diffed output. All byte-identical except the `--no-ghes` case above, which was verified to raise
the *same* exception class on both sides instead.

Comment multiset diff (`grep '^\s*#'` old file vs. union of new files, sorted, `diff`) was run and
came back empty for every split file in this area, confirming no comment was reworded, invented, or
dropped while relocating it to sit above its new home function.

No `try`/`except`/`finally`/`with` body was moved across a function boundary anywhere in this area
— `bfs_crawl`'s `async with AsyncWebCrawler(**kw) as crawler:` still wraps the entire while-loop,
unchanged; the extracted helpers are called from inside it. `fetch_page`'s own `try/except` and the
GHES loop's `try/except Exception as exc` both stayed fully inside their one function, nothing
extracted out of either.

## What was declined and why

Did not merge the five near-identical `write_report`/`format_report` functions across this area,
`lane_choice`, and `url_discovery` into one shared reporter, even though they share a surface shape
(timestamp header, markdown sections, table rows). This mirrors a decision already recorded in
`process-docs/refactor_sweep/2026-09-15_dev_sweep_orchestrator_and_phase4_scan.md` for
`browser_posture`'s five `write_report`s: each report body carries genuinely different data and
section logic, so a shared helper would need a parameterization nobody asked for.

## Numbers after this pass

`04_render_recall.py`: 299 -> 321 LOC (largest function now 27). `05_playwright_bfs.py`: 328 -> 382
LOC (largest function now 39, `bfs_crawl` itself). `06_nextdata_probe.py`: 339 -> 389 LOC (largest
function now 45, pre-existing `build_report` which was already under 50 and untouched). All three
stayed well under the 400-LOC module threshold; no module split was needed in this area.
