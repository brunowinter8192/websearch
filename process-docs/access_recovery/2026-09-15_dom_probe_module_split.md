# access_recovery — DOM probe module split, 2026-09-15

Worker session. Task: bring `dev/access_recovery/` under the two dev-area size thresholds —
`01_google_dom_probe.py` was 528 LOC (over the 400 module cap), and three functions were at or
over 50 LOC (`01::write_report` 119 LOC HARD, `01::run_navigation` 53 LOC, `02::write_report` 88
LOC). Pure LOC-shrinking was explicitly out of scope — the ask was a concern split plus real
helper extraction.

## Concern boundaries chosen for `01_google_dom_probe.py`

Three concerns were separable from the entry script and became their own files:

- `_browser.py` — Chrome tab lifecycle (`_build_options`, `new_tab`, `kill_tab`, `close_browser`),
  a thin wrapper around `dev/_lib/browser_launch.py`. Owns the module-level `_handle` global.
- `_dom.py` — everything that is "how do you read a Google results page": the `_JS_*` constants,
  consent detection/handling, result wait/parse, the `/sorry/` block-path check, the diagnostic JS
  pass. No state, pure functions over a `tab` argument.
- `_report.py` — markdown assembly. `write_report`'s 119 LOC became one `_build_*_section` helper
  per report section (8 helpers), each returning `list[str]`; `write_report` itself dropped to 18
  LOC composing them in original order.

`01_google_dom_probe.py` stayed the entry point: `run_probe` (orchestrator, untouched shape),
`_load_queries`, `_slugify`, and three new private helpers extracted from `run_navigation`
(`_navigate_with_consent`, `_classify_navigation`, `_save_navigation_artifacts`) — `run_navigation`
itself dropped from 53 to 22 LOC.

`02_google_wml_probe.py` was NOT split into modules — it was already 293 LOC (under the 400 cap)
and had exactly one oversized function. Only `write_report` there got helper-extracted (same
section-builder pattern, `_compute_verdict` + 6 section helpers), no new files.

## Precedent followed for the new files

This project already has two examples of area-local helper files living flat next to numbered
entry scripts, not in a package: `dev/browser_posture/_lib.py` and
`dev/url_discovery/_fixture_site.py`. Both use bare `from _module import name` imports, relying on
the script's own directory landing on `sys.path[0]` when run directly — no `sys.path.insert` boot-
strapping needed on the importing side. The three new `access_recovery` files follow this exact
pattern, NOT the `dev/search_pipeline/_lib/` package pattern (that one has its own `__init__.py`
and is imported as `from _lib.parse import ...` — a subfolder, not a sibling file). Do not add an
`__init__.py` to `dev/access_recovery/` on the assumption it's missing; it is missing on purpose.

`# INFRASTRUCTURE` + `# FUNCTIONS` only (no `# ORCHESTRATOR`) on all three new files mirrors
`dev/_lib/browser_launch.py` exactly — that file is the reference example of the "Helper module"
exception in the code standard (pure primitives, no workflow function of its own).

## Constant/parameter ownership across the split — where it got fiddly

Splitting `write_report` out of the entry script meant `NUM_VARIANTS`, `NAV_DELAY_S`, and
`REPORT_DIR` were no longer in the same module as the function that needed them for report text
(pacing sentence, num-variant grouping, output path). Two options were on the table: duplicate the
literal constants in `_report.py`, or pass them as explicit arguments from `run_probe` (which
already has them in scope). Argument-passing was chosen — single source of truth stays in the
entry script, no risk of the two copies drifting. This is why `write_report`'s signature grew from
3 params to 5 (`records, run_ts, report_dir, num_variants, nav_delay_s`) even though nothing about
its *behavior* changed. A later split of this shape should default to this same choice.

## The one defect that slipped through the first pass

The original (pre-split) `write_report(records, run_ts, html_run_dir)` never actually read
`html_run_dir` inside its body — confirmed by grepping the pre-refactor source for the name inside
the function; it only appears in the signature. This dead parameter got mechanically carried
through the split into `_report.py`'s new 5-arg signature instead of being dropped, because the
refactor's own rule ("behaviour must not change") was read as "forward every original argument"
rather than "reproduce every original *effect*". Main caught it on review. Fix: drop the parameter
from `_report.py::write_report` and from the one call site in `01_google_dom_probe.py`. Lesson for
next time: when a function crosses a module boundary during a split, audit every one of its
parameters for actual use before deciding whether it travels with the function — a split is exactly
the moment dead parameters would otherwise get relocated instead of removed, because relocating
"looks like" preserving behavior.

## Verification method — reusable for future report-generator splits

Function-level `ast`-based LOC counts and `python3 -m ast` syntax checks proved the mechanical
things (no function over 50, no syntax breakage), but the thing that actually proves "behaviour did
not change" for a markdown-report split is a byte-identical text comparison: pull the pre-split
`write_report` (`git show HEAD:<path>` into a scratch file), feed it and the new post-split
`write_report` the exact same synthetic `records` list (built to cover all outcome states —
OK/EMPTY_PARSED/NO_CONTAINERS/BLOCKED/ERROR — since each drives a different conditional section),
and diff the two `.md` outputs. Both `01` and `02` came back `IDENTICAL: True` on the first pass,
and again after the `html_run_dir` fix. This scratch harness lived under `/tmp/ar_verify/` per the
dev/-area staging rule (one-off verification scripts don't belong in the repo) — it is gone now,
not committed anywhere; rebuilding it for a similar future check is ~30 lines: strip the target
`write_report` + its `_count_outcomes`/helpers out of the old file with a `str.index` slice on
`\ndef write_report` / `\nif __name__`, stub the module-level constants it references, build one
record dict per outcome value, call both versions, `==` the `.read_text()` results.

## Final module LOC (this session's end state)

```
48  dev/access_recovery/_browser.py
190 dev/access_recovery/_dom.py
171 dev/access_recovery/_report.py
192 dev/access_recovery/01_google_dom_probe.py
327 dev/access_recovery/02_google_wml_probe.py
```

All five functions that were originally flagged are now under 50 LOC; the largest post-split
function in the whole area is `02::run_query` at 35 LOC.

## What this session did NOT touch

`dev/access_recovery/queries.json`, the `md/`, `html/`, `wml/` output directories, and the
module-level docstrings in `01`/`02` (left exactly as they were, per instruction — they still
describe the probes' design at the level the docstrings were originally written, not the new
file layout underneath them). `process-docs/access_recovery/2026-09-15_sprint_opening_state.md`
was read for context only and was not edited — see that file for the actual research question
this area exists to answer (why Google search fails in production); this session was pure
mechanical refactor, no new measurement was taken.
