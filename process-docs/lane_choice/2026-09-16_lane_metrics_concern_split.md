# 04_lane_metrics.py concern split, and the sys.path import hazard it exposed (2026-09-16)

Worker entry for the `dev/` refactor sweep orchestrated from `process-docs/refactor_sweep/`. This
area's hit list: `04_lane_metrics.py` at 520 LOC (module split) and `03_live_focus_probe.py
::write_report` at 57 LOC (function split, see below).

## The six-way split of 04_lane_metrics.py, and why these six boundaries

Read top to bottom, the module was six back-to-back concerns, each already separated by its own
comment block and already only calling into the concern before it:

1. `_lane_metrics_pairing.py` (68 LOC) — `_latest_ok_records_by_url_engine`,
   `_resolve_content_path`, `collect_pairs_from_scrape_log`, plus `PROD_SCRAPE_LOG_PATH`. Talks to
   the production JSONL log, nothing else in the module does.
2. `_lane_metrics_blocks.py` (77 LOC) — tokenizing one markdown file into blocks
   (`is_token`/`tokenize`/`is_comment_line`/`is_heading_line`/`contains_sentence_end`/
   `process_line`/`read_blocks`), plus the four regexes it needs.
3. `_lane_metrics_classify.py` (66 LOC) — the Kohlschuetter Algorithm 2 decision tree, verbatim
   from the paper, plus the jusText heading-rescue pass. Pure functions over an already-read block
   list, no I/O, no knowledge blocks even come from a file.
4. `_lane_metrics_prose.py` (90 LOC) — the project-specific PROSE test layered on top of (3): the
   corpus-derived length cap (`compute_prose_cap`, `PROSE_PERCENTILE = 99`) and the per-file
   metric aggregation that combines classification + PROSE into one metrics dict. Chosen as its own
   file rather than folded into (3) because it is explicitly a LOCAL, project-specific addition on
   top of a literal paper implementation — DOCS.md and the module's own original docstring already
   drew this exact line ("On top of that, a block-level PROSE test").
5. `_lane_metrics_aggregate.py` (55 LOC) — cross-pair stats (`winning_lane`, `compute_aggregate`),
   plus `LANES`. Operates over a list of already-computed per-URL metric dicts; never reads a file.
6. `_lane_metrics_report.py` (136 LOC) — every `format_*` function plus `write_report`. Imports
   `LANES` from (5) and `PROSE_PERCENTILE` from (4) — the two constants report formatting actually
   needs display values from.

`04_lane_metrics.py` itself is now 62 LOC: imports + `lane_metrics_workflow` (the orchestrator,
unchanged logic, just now calling into six modules instead of forty functions in one file) + `main`.

## The import hazard: dev/ has no package root, and this bit immediately

First attempt used `from dev.lane_choice._lane_metrics_aggregate import ...` (the code standard's
literal "absolute import" form). It parses fine and even works under `pytest` (which inserts the
project root for `dev.url_discovery._fixture_site`-style imports already used by
`dev/tests/test_discovery.py`). It does NOT work for direct script invocation:
`./venv/bin/python dev/lane_choice/04_lane_metrics.py` sets `sys.path[0]` to the script's own
directory (`dev/lane_choice/`), never the project root — confirmed empirically, not assumed:
`ModuleNotFoundError: No module named 'dev'`.

The fix, and the one to reuse: this project already has a working precedent for exactly this,
`dev/url_discovery/02_fixture_site_server.py`:
```python
sys.path.insert(0, str(Path(__file__).parent))
from _fixture_site import start_fixture_server, stop_fixture_server, ground_truth, seed_url  # noqa: E402
```
`04_lane_metrics.py` now does the same `sys.path.insert` + plain top-level import
(`from _lane_metrics_aggregate import compute_aggregate`, no `dev.lane_choice.` prefix). Each of
the six new `_lane_metrics_*.py` files cross-imports the same way (plain, no package prefix) —
they never need their own `sys.path.insert` because whichever script imports them first
(`04_lane_metrics.py`) already did it, and `sys.path` is process-global.

**If a successor adds another multi-file dev/ split that needs to run as a direct script, do the
`sys.path.insert(0, str(Path(__file__).parent))` + plain-import dance, not the `dev.<area>.` form.**
The `dev.<area>.` form only works from `pytest` (or anything else that puts the repo root on
`sys.path` itself), never from a bare `./venv/bin/python dev/<area>/<script>.py` invocation.

## Verification

Full pipeline run against a synthetic 2-URL-pair fixture (fake `scrape_log.jsonl` + 4 fake `.md`
files with CONTENT/BOILERPLATE/heading-rescue/PROSE-cap-exclusion cases) through both the
pre-refactor single file (`git show`'d to `/tmp`) and the new six-module split, both writing a
report: `report.read_text()` byte-identical, `cap`/`distribution`/`aggregate` dicts identical.
Comment multiset diff (old file vs. union of all seven new files, section markers and the new
`noqa: E402` pragmas excluded) came back empty. No `try`/`except`/`finally`/`with` exists anywhere
in this module — nothing to check on the control-flow front.

## 03_live_focus_probe.py::write_report

Split the same way as every other `write_report` in this sweep: one helper per `##` report
section (`_format_report_header`, `_format_url_spans`, `_format_verdict_sections`,
`_format_per_url_verdict_sections`, `_format_sample_series`). 364 -> 386 LOC, no other function in
this file was touched. Verified byte-identical against synthetic `url_runs`/`frontmost_samples`/
`verdict`/`per_url_verdicts` fixtures, including an empty-samples edge case
(`fm_total=0`, empty `frontmost_samples` list) — `WORKTREE_ROOT` was monkeypatched to a fixed
sentinel on both old and new before comparing, since it is a real filesystem path that differs
between where `git show`'d code lands (`/tmp`) and the actual worktree.

## Numbers after this pass

`04_lane_metrics.py`: 520 -> 62 LOC (+6 new files, largest 136, largest function 38). No module in
this area is over 400 LOC. No function is at or above 50 LOC (`compute_aggregate` at 38 is the
largest survivor).
