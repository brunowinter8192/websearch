# engine_reduction — openalex_pdf_probe.py report helper extraction, 2026-09-15

Worker session. Task: bring `dev/engine_reduction/` under the sweep's function-size threshold. This
is the smallest area in the ongoing refactor sweep (same sweep as `dev/access_recovery/`,
`dev/agentic_discovery/`, `dev/browser_posture/`, all already merged) — a single module,
`openalex_pdf_probe.py`, 226 LOC pre-refactor, well under the 400-LOC module cap, so no split was in
scope. One function was flagged: `write_report` at 65 LOC (line 158), over the 50-LOC-or-extract
threshold.

## What was extracted

`write_report` built three independent markdown sections in one function body: the per-query counts
table (with running totals across 8 counters), the type-breakdown section, and the eyeball section
(title/type/chosen-URL/pdf_url per query, only for the 2 queries flagged in `EYEBALL_QUERY_NUMS`).
These three sections do not share any computation with each other — each reads only from `records`
and appends independently to the output `lines` list. Extracted each into its own
`_build_*_section`-style helper (`_build_per_query_table`, `_build_type_breakdown_section`,
`_build_eyeball_section`), each returning `list[str]`, in the same order they originally appeared.
`write_report` itself dropped from 65 LOC to 20 LOC: header/error-line construction stays inline (it
is a handful of lines with no independent responsibility of its own, not worth a fourth helper), then
three lines composing the extracted sections, then the file write. This is the same section-builder
pattern already established across the sweep (`dev/access_recovery/_report.py`,
`dev/browser_posture/_headed_chromium_report.py`, `dev/browser_posture/_fingerprint_report.py`,
`dev/browser_posture/_cdp_report.py`) — no new pattern invented here, applied in-file since the
module itself stays under 400 LOC (a `_report.py` split-out file was not warranted for one function).

Final per-function LOC in the file (`ast`-based walk, `FunctionDef`/`AsyncFunctionDef`):
`run_probe` 27, `fetch_works` 7, `_pick_url` 9, `classify` 7, `build_record` 21,
`build_eyeball_rows` 11, `_build_per_query_table` 29, `_build_type_breakdown_section` 9,
`_build_eyeball_section` 14, `write_report` 20. Largest is `_build_per_query_table` at 29 — well
clear of the 50 threshold. File grew from 226 to 239 LOC (function-def lines + blank separators for
three new top-level functions), still far under the 400-LOC module cap.

## Verification method used

Same core method as the two prior worker sessions in this sweep (`access_recovery`,
`agentic_discovery`): pulled the pre-refactor `write_report` via `git show HEAD~1:<path>` into a
scratch module (`/tmp/er_verify/old_full.py`, gone now — not committed, per the dev/-staging rule for
one-off verification scripts), loaded both old and new modules via `importlib.util.spec_from_file_
location`, built one synthetic `records` list covering every conditional branch `write_report`
exercises (a record with a non-empty `type_breakdown` and `eyeball=None`, a record with an empty
`type_breakdown` Counter and populated `eyeball` rows including a title containing a literal `|` to
exercise the escape path, and a single-result record), and called both versions with `REPORT_DIR`
monkeypatched to separate temp dirs, once with `error=None` and once with a synthetic 429 error
string (the "stopped early" branch). Compared the two output files after normalizing the
`YYYYMMDD_HHMMSS` timestamp substring (present in both the header line and the filename, generated a
render apart) to a fixed placeholder via regex — `IDENTICAL: True` on both branches on the first
attempt, no diff needed.

`./venv/bin/python3 -m py_compile` passed; script still imports cleanly via `runpy.run_path` with a
non-`__main__` run name (the `if __name__ == "__main__": asyncio.run(run_probe())` guard never fires
under that run name, so importing does not attempt a live network call against the OpenAlex API).

## Salvage from dev/engine_reduction/DOCS.md

The old DOCS.md's `## Gotchas` section is not part of the project's DOCS.md format (Role / Public
Interface / Flow / Modules / State only). Reproduced verbatim below, unparaphrased, per instruction —
this is real operational knowledge about running this probe (budget ceiling, what counts as "has
PDF") that must not be lost just because it doesn't fit the module-map format:

---

OpenAlex's keyless budget is $0.10/day at $0.001/search call — 7 queries per run is trivial, but a
429 means budget or per-minute rate exceeded; the script stops immediately on 429 and reports the
partial results rather than retrying. `open_access.oa_url` is NOT used as a PDF signal here (it may
be a landing page) — only `best_oa_location.pdf_url` counts as "has PDF".

---

The old DOCS.md also had no `## Public Interface` or `## Flow` section at all (both required by the
current format) — these were newly written for this recap, not salvaged from anything, since there
was nothing there to salvage for those two headings.

## What this session did NOT touch

`dev/engine_reduction/01_reports/` (existing report outputs) and every file under
`process-docs/engine_reduction/` predating this session — read in full for context (all five: the
query-log analysis that produced the keep-openalex decision, the milestone-1 pdf-url-availability
finding this very probe produced, the milestone-2 six-engine deletion, the milestone-3 API-migration
writeup, and the later mojeek removal) but none needed a correction filed against them. The
probe's own measurement logic, output content, `QUERIES` list, and module-level docstring were left
byte-for-byte as they were — this was a pure function-extraction task, no new measurement, no
rewording of existing prose.
