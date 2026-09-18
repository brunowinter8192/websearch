# Splitting dev/search_pipeline/branch_probe.py by concern (2026-09-18)

`dev/search_pipeline/branch_probe.py` was 704 LOC, mixing five concerns in one file:
`RateLimiter.acquire()` monkeypatch instrumentation, a Pattern-B scheduling-latency canary,
per-query analysis (limiter snapshots, event reduction, branch classification), a timestamped
markdown report, and a fixed-path narrative findings doc — plus the CLI entry/orchestrator holding
all of it together. Three functions were over the 50-LOC function threshold, two of them
(`_write_findings` 161 LOC, `_write_report` 145 LOC) past the 100-LOC hard target;
`run_branch_probe` itself was 100 LOC.

## Module boundary

Five new area-local siblings, all named `_branch_probe_*.py` (this directory's own established
convention for split-out submodules of a single probe — see `_altcha_trigger_probe_*.py`, not the
generic `_browser.py`/`_dom.py`/`_report.py` shape used in `dev/access_recovery/`, which only has
two probes sharing its directory and no naming-collision pressure):

- `_branch_probe_instrument.py` (68 LOC) — the `RateLimiter.acquire()` monkeypatch, applied at
  import time. Owns `_acq_events`, `_pre_snapshots`, `_rl_mod`.
- `_branch_probe_canary.py` (76 LOC) — the Pattern-B canary task and its stats. Owns
  `_canary_samples`, `PROBE_START` (module-internal now, set via `_start_probe_clock()`).
- `_branch_probe_analysis.py` (107 LOC) — `_load_queries`, `_snapshot_limiters`,
  `_build_engine_detail`, `_query_discriminator`, `_dump_smoke`.
- `_branch_probe_report.py` (207 LOC) — `_overall_verdict` plus `_write_report`, split into one
  section-builder helper per report section (same shape `dev/access_recovery/_report.py` used for
  its own report).
- `_branch_probe_findings.py` (221 LOC) — `_write_findings`, split the same way (averages
  computation, verdict-text lookup, header/narrative/key-numbers/verdict/side-finding/next-steps
  section builders).

`branch_probe.py` itself dropped to 196 LOC: module docstring, imports, constants
(`SCRIPT_DIR`/`QUERIES_FILE`/`REPORT_DIR`/`FINDINGS_DIR`/`BACKOFF_IMMUNE`), the orchestrator, and
the orchestration-glue functions extracted out of the old 100-LOC `run_branch_probe` body
(`_execute_queries`, `_run_single_query`, `_cascade_result`, `_report_smoke_ok`,
`_write_stop_note`, `_write_outputs`). None of these six glue functions are a "concern" in their
own right — they are the orchestrator's own control flow, sliced into named, individually-callable
pieces so the orchestrator can stay a flat sequence of calls per the code standard. They stayed in
the entry file rather than moving to a sibling.

## Import ordering constraint (the actual hard part)

The whole file exists to monkeypatch `RateLimiter.acquire` **before** `src.search.browser` /
`src.search.search_web` get imported anywhere (those transitively import `rate_limiter` and would
bind the original `acquire`). The split preserves this by import-statement ordering in
`branch_probe.py`: `sys.path.insert(...)` first, then `from _branch_probe_instrument import
_acq_events, _pre_snapshots` (this one import line executes all of `_branch_probe_instrument.py`'s
top-level code, including the `RateLimiter.acquire = _replacement_acquire` assignment), and only
**after** that line do the `importlib.import_module("src.search.browser")` /
`"src.search.search_web"` calls happen. `_branch_probe_instrument.py` also does its own
`sys.path.insert(0, str(Path(__file__).parent.parent.parent))` so it stays independently importable
(needed for the clean-import check below) rather than relying on the caller having done it first.

## The repo-tooling `from src.` hook

This directory's DOCS.md gotcha ("New files in this directory cannot `from src....` import at
all — a repo-tooling hook blocks any Write/Edit that introduces a NEW such import line") governs
`_branch_probe_instrument.py`, which is the one new file that needs `src.search.rate_limiter`. It
uses the same `importlib.import_module("src.search.rate_limiter")` pattern the original
`branch_probe.py` already used (never the literal `from src....` text), so no new file trips the
hook. `branch_probe.py` kept the same `importlib.import_module` pattern for
`src.search.browser`/`src.search.search_web` rather than switching to `from src... import` even
though it's a pre-existing grandfathered file — matching what was already there is simpler than
finding out whether an edit to a grandfathered file's existing import lines counts as "new."

## Naming: kept every original identifier

Every moved name — `_acq_events`, `_pre_snapshots`, `_rl_mod`, `_canary_samples`, `PROBE_START`,
`_canary_stats`, `_overall_verdict`, `_write_report`, `_write_findings`, all of
`_branch_probe_analysis.py`'s functions — kept its original underscore-prefixed name even where it
is now imported across a sibling-module boundary (e.g. `_branch_probe_findings.py` does
`from _branch_probe_report import _overall_verdict`). Python does not restrict importing
underscore-prefixed names explicitly (only `import *` skips them), and this kept the diff to
genuinely "moved code, unchanged, plus new import lines" rather than also being a renaming pass.
The two exceptions are constants that used to be bare module globals read directly by multiple
functions and are now passed as explicit parameters instead: `BACKOFF_IMMUNE` (stayed the single
source of truth in `branch_probe.py`, passed into `_dump_smoke`, `_write_report`, `_write_findings`)
and `REPORT_DIR`/`FINDINGS_DIR` (same treatment, passed into `_write_report`/`_write_findings` as
`report_dir`/`findings_dir`) — this mirrors `dev/access_recovery/_report.py`'s own
`report_dir`-as-argument shape rather than each sibling module owning its own copy of the path
constant.

One genuine deviation from "moved code, byte-identical": the original file had a trailing
structural comment, `# End monkey-patch — src.search imports follow`, directly under the
`RateLimiter.acquire = _replacement_acquire` line. That comment described what came next in the
same file; after the split nothing follows it inside `_branch_probe_instrument.py` (the
`src.search` imports now live in `branch_probe.py`), so keeping it verbatim would have made it
false. It was dropped rather than edited or kept-but-wrong. Every other comment and docstring in
the original file moved with its code, untouched.

## Verification

All six modules import cleanly standalone (`python3 -c "import <module>"` from inside
`dev/search_pipeline/`, one at a time) with no live browser/network involved — `_branch_probe_
instrument.py` applies the real monkeypatch against `src.search.rate_limiter.RateLimiter` but never
calls `acquire()`. `git diff` against the original `branch_probe.py` shows every relocated block
line-for-line identical apart from indentation and the new `import`/parameter lines described
above. `./venv/bin/python3 -m pytest dev/tests/`: 431 passed before the split (confirmed via
`git stash`) and 431 passed after — expected, since nothing in that suite exercises this dev probe
directly. A synthetic end-to-end check (fake 4-record `query_records`, `REPORT_DIR`/`FINDINGS_DIR`
pointed at a scratch dir under `dev/search_pipeline/debug/`, deleted afterward — `debug/` is not
version-controlled) ran `_write_outputs` and `_write_stop_note` through the real split call chain
and confirmed both `md/branch_probe_<ts>.md` and `md/03_branch_probe.md` render with the same
section structure as the pre-split file, and that `_write_findings`'s
`report_path.relative_to(Path(__file__).parent.parent.parent)` still resolves to the project root
from its new file location (same directory depth as the original `branch_probe.py`). Every function
across all six files is ≤44 LOC (`_run_single_query`, the largest); see any future refactor of this
area for the exact per-function counts rather than trusting this number to stay current.

See `dev/search_pipeline/` (this DOCS.md) for the resulting module list and
`dev/access_recovery/` for the split precedent this one followed for shape (not content).

# Splitting dev/search_pipeline/14_download_classify_probe.py by concern (2026-09-18)

Same sweep, same rules, next unit in `dev/search_pipeline/`. This file was 605 LOC and mixed three
concerns: building the URL pool from two source reports (glob-discover, extract, domain-tier,
doi.org-sample, write `.txt` pool files), classifying each pooled URL over HTTP (Tier-1 transform,
GET, content-type/PDF-magic/citation_pdf_url/paywall sniffing), and assembling the markdown report
(one function per section already — that part was already well-shaped). An AST pass over every
function in the file (same technique as the `branch_probe.py` split) confirmed only one function was
at or over the 50-LOC threshold: `_classify_url` at 98 LOC. Every other function, including all six
report `_section_*` builders, was already under 50.

## Module boundary

Three new siblings, named off the entry script's own base name with its numeric prefix dropped
(`14_download_classify_probe.py` → `_download_classify_probe_*.py`), same naming rule as the
`_altcha_trigger_probe_*.py` / `_branch_probe_*.py` precedents:

- `_download_classify_probe_pool.py` (115 LOC) — `_latest_report`, `_extract_pool`,
  `_has_real_path`, `_url_tier`, `_base_domain`, `_filter_and_tier`, `_apply_doi_sampling`,
  `_write_pool_files`. Owns `TIER1_DOMAINS`…`TIER4_DOMAINS`, `RANDOM_SEED`, `DOI_SAMPLE_SIZE`.
- `_download_classify_probe_classify.py` (235 LOC) — `_classify_all`, `_classify_with_cap`,
  `_classify_url` (now 22 LOC) plus its four new extracted helpers (below), `_apply_transform`,
  `_extract_title`. Owns `GLOBAL_MAX_CONNECTIONS`, `GLOBAL_MAX_KEEPALIVE`,
  `DOMAIN_CONCURRENCY_CAP`, `DOMAIN_COURTESY_SLEEP`, `TIER1_TIMEOUT`, `DEFAULT_TIMEOUT`,
  `HTML_READ_BYTES`, `PDF_SNIFF_BYTES`, `PAYWALL_MARKERS`.
- `_download_classify_probe_report.py` (243 LOC) — `_write_report`, `_build_report`, and the six
  `_section_*` builders, unchanged in shape (they were already one-function-per-section).

`14_download_classify_probe.py` dropped to 56 LOC: docstring, imports, `SCRIPT_DIR`/`REPORT_DIR`/
`DATA_DIR`/`SMOKE_REPORTS_GLOB`/`FREE_WORD_REPORTS_GLOB`, and `run_probe` itself — already
orchestrator-shaped at 26 LOC before this split (it was already just a flat sequence of calls into
what are now the three siblings) and untouched beyond the directory-argument additions described
below. No orchestrator restructuring was needed here, unlike the `run_branch_probe` split, because
`run_probe` never had an oversized-function problem to begin with.

## Cutting `_classify_url` along its own stages

The four seams inside `_classify_url` are behavioural stages, in strict sequence, each gating
whether the next one runs: init record → dispatch on status code → read body → dispatch on
content-type → (if HTML) parse title/citation_pdf_url/paywall and pick an outcome. That sequence
survived the extraction unchanged:

1. `_init_classify_record(original_url, transformed_url, tier)` — the dict literal, unchanged.
2. `_classify_response(rec, resp)` — status/content-type capture, the `>= 400` early return, calls
   `_read_response_body`, the PDF-magic check, dispatches to `_classify_html_body` for
   `text/html`, falls through to `HTML_OK` for anything else. Same four branches, same order,
   same early-return points as the original inline code — verified by running all six original
   outcome branches (`HTTP_404`, `PDF_OK`, `HTML_HAS_PDF_LINK`, `HTML_PAYWALL`, `HTML_OK`,
   non-PDF/non-HTML `HTML_OK`) through the split functions against a fake `httpx.Response`-shaped
   object (no network), one `asyncio.run` per case — every case landed on the exact original
   outcome string.
3. `_read_response_body(resp)` — the single-pass accumulate-up-to-`HTML_READ_BYTES` loop, moved
   verbatim including its original comment (`# Single-pass read: accumulate up to HTML_READ_BYTES;
   check PDF magic on first bytes` — the PDF-magic check it refers to now lives one function up in
   `_classify_response`, not literally beside it anymore, but the comment is still accurate context
   for why the read is capped, so it was left as-is rather than treated as the one-exception case).
4. `_classify_html_body(rec, body)` — decode, `_extract_title`, the two-variant citation_pdf_url
   regex, the paywall-marker loop, the outcome trichotomy (`HTML_HAS_PDF_LINK` /
   `HTML_PAYWALL` / `HTML_OK`). Same order as original.

`_classify_url` itself is now just: compute `transformed_url`/`fetch_url`/`timeout`, call
`_init_classify_record`, `try`/`await _classify_response(rec, resp)`/`except` (the four `except`
clauses — `TimeoutException`, `ConnectError`, `RequestError`, bare `Exception` — untouched, same
order) — 22 LOC.

## Two pieces of pre-existing dead code, moved as-is (per the standing discipline from the
`branch_probe.py` split)

- `PDF_SNIFF_BYTES = 1024` was already declared and never referenced anywhere in the 605-LOC
  original. It moved into `_download_classify_probe_classify.py` (the thematically nearest module —
  it sits beside `HTML_READ_BYTES`, the constant that actually does the sniff-size job) unchanged
  and unused. Not this split's job to decide whether it should exist.
- `parse_qs` and `urlencode` were imported from `urllib.parse` in the original and never used
  anywhere in the file either — also pre-existing, also dead. They moved into
  `_download_classify_probe_classify.py`'s import line (alongside `urlparse`/`urlunparse`, which
  *are* used there) for the same reason: nearest thematic home, untouched, unused. Flagging this
  explicitly so a later reader doesn't mistake either the constant or these two imports for
  something this split introduced or overlooked — both predate it.

There is also a pre-existing dead local, `total_doi_in_pool` in `_section_metadata` (computed,
never read before the `return`) — moved unchanged into `_download_classify_probe_report.py` for the
same reason.

## Verification

All four modules import cleanly standalone (`python3 -c "import <module>"` from inside
`dev/search_pipeline/`). No CLI flags exist on this entry script (no `argparse`), so there is no
`--help` surface to diff — the `if __name__ == "__main__": asyncio.run(run_probe())` block is
untouched, confirmed by diff. `git diff` against the original reviewed concern by concern: every
relocated block is line-for-line identical apart from indentation and the new directory-argument
parameters (`report_dir` added to `_latest_report`/`_write_report`, `data_dir` added to
`_write_pool_files` — same "pass the directory in" treatment as `REPORT_DIR`/`FINDINGS_DIR` got in
the `branch_probe.py` split, for the same reason: the constant's owning module moved out from under
the functions that used to read it as a bare global). `./venv/bin/python3 -m pytest dev/tests/`:
431 passed before (via `git stash`) and 431 passed after — unchanged, no test exercises this dev
probe. A synthetic end-to-end run (fixture `pipeline_smoke_*.md` / `free_word_injection_probe_*.md`
files under a scratch `dev/search_pipeline/debug/` dir, deleted afterward) drove
`_latest_report` → `_extract_pool` → `_filter_and_tier` → `_apply_doi_sampling` →
`_write_pool_files` → (faked classify results, no network) → `_write_report` through the real
cross-module call chain and produced a correctly tiered pool (arxiv.org `/abs/` URL → T1,
dl.acm.org → T4, root-domain-only URL correctly dropped by `_has_real_path`) and a report with the
expected Section 1 table. Every function across all four files is ≤41 LOC
(`_section_tier1_transforms`, unchanged from the original, was already the largest report section).

See `dev/search_pipeline/` (this DOCS.md) for the resulting module list.

# Splitting dev/search_pipeline/acquire_probe.py by concern (2026-09-18)

Third unit in the same sweep. `acquire_probe.py` is the Phase-2 sibling of `branch_probe.py`
(Phase 3) — same investigation, one phase earlier, 588 LOC. The scan named the two dominant
functions (`_write_findings` 123 LOC, `_write_report` 100 LOC); an AST pass over every function in
the file (same technique used on the prior two units) found a third: `run_acquire_probe` itself at
83 LOC, not named in the scan line but over the 50-LOC threshold and therefore in scope — the scan
gives the dominant functions, the threshold is the rule, and reading the file is what catches the
rest. Everything else in the file (`_build_engine_summary` 26, `_discriminator` 19, `_canary_stats`
17, `_agg_ratios` 15, `_WatchedLock`'s methods 2–6 each) was already under 50.

## Module boundary, and where this split matches branch_probe.py's — and where it does not

Four new siblings, `_acquire_probe_*.py`, same naming rule as `_branch_probe_*.py`:

- `_acquire_probe_instrument.py` (80 LOC) — `_get_name`, `_WatchedLock`, `_orig_init`/
  `_patched_init`, `_orig_acquire`/`_patched_acquire`, the two patch assignments (this file patches
  **both** `RateLimiter.__init__` and `RateLimiter.acquire`; `branch_probe.py`'s instrument module
  patches only `acquire`, as a full byte-identical replacement rather than a wrapper — the two
  probes' instrumentation is a different shape, not just a renamed copy of each other). Owns
  `_acq_events`.
- `_acquire_probe_canary.py` (72 LOC) — matches `_branch_probe_canary.py` almost line-for-line:
  same constants, same `_canary_monitor`/`_sample_category`/`_pct`/`_canary_stats`, same
  `_start_probe_clock`/`_start_canary_monitor`/`_stop_canary_monitor` extraction.
- `_acquire_probe_analysis.py` (92 LOC) — `_load_queries`, `_build_engine_summary`,
  `_discriminator`, `_dump_smoke`, `_agg_ratios`. Matches `branch_probe.py`'s analysis concern in
  kind, not in content: this file has no `_snapshot_limiters` equivalent (no Layer-1 pre-call
  limiter introspection — `acquire_probe.py` is purely event-based) and, unlike anything in
  `branch_probe.py`, `_agg_ratios` (cross-record ratio aggregation) is called from *both* the report
  and the findings module. Keeping it centralized rather than inlining the ratio math into each
  report/findings section (which is what `branch_probe.py`'s equivalent sections do) preserves that
  asymmetry — see the dedicated note below.
- `_acquire_probe_report.py` (155 LOC) — `_overall_disc` + `_write_report`, split into one
  section-builder helper per report section, same shape as `_branch_probe_report.py`.
- `_acquire_probe_findings.py` (184 LOC) — `_write_findings`, split the same way (`_disc_text`
  lookup, header/narrative/key-numbers/verdict/next-steps builders), `_overall_disc` imported from
  the report sibling.

`acquire_probe.py` itself dropped to 170 LOC. `run_acquire_probe`'s 83 LOC came down to an 11-line
orchestrator plus six glue functions (`_execute_queries`, `_run_single_query`, `_cascade_result`,
`_report_smoke_ok`, `_report_cascade_warning`, `_write_outputs`) — same extraction shape as
`run_branch_probe` got.

## The one control-flow difference that must NOT be flattened toward the sibling

`branch_probe.py`, on cascade-reproduction failure, writes a STOP note and returns early —
report and findings are never written. `acquire_probe.py` does something different on the same
condition: it prints a WARNING to stderr and **falls through anyway**, writing both the report and
the findings exactly as it would on success. This is not an oversight in either file, it is each
probe's own deliberate call about whether a failed-to-reproduce run still has data worth a report,
and the split preserves it exactly:

```python
async def run_acquire_probe(max_queries, smoke):
    _start_probe_clock()
    queries = _load_queries(QUERIES_FILE, max_queries)
    query_records = await _execute_queries(queries, smoke)
    zero_n, cascade_ok = _cascade_result(query_records, smoke)
    if smoke:
        _report_smoke_ok()
        return
    if not cascade_ok:
        _report_cascade_warning()
    _write_outputs(query_records, cascade_ok, zero_n)
```

Note there is no `return` after `_report_cascade_warning()` — `_write_outputs` runs unconditionally
whenever `smoke` is false, regardless of `cascade_ok`. This was verified two ways, not just read: (1)
a synthetic run with four fake `normal`-category records (`zero_n=0`, `min_expected=3`,
`cascade_ok=False`) went through the real `_cascade_result` → `_write_outputs` call chain and both
`md/acquire_probe_<ts>.md` and `md/02_acquire_probe.md` were confirmed present on disk afterward;
(2) `run_acquire_probe` was run with every callee monkeypatched to a call-recording stub, once with
`smoke=True` (recorded calls: `execute → cascade → smoke_ok`, no `write_outputs`) and once with
`smoke=False` and a stubbed `cascade_ok=False` (recorded calls: `execute → cascade → warning →
write_outputs`) — confirming both branches of the orchestrator's own control flow, not just the
section contents. A later reader comparing this file's orchestrator to `run_branch_probe`'s should
not "fix" this into matching the STOP-note early-return shape; that would silently change which
artifacts a failed run produces, which is a behaviour change a diff reviewing seams-not-control-flow
would not catch.

## The other real asymmetry: _agg_ratios is centralized here, duplicated there

`branch_probe.py` has no single reusable "aggregate ratios across a set of query records" function
— each report/findings section that needs per-category averages (`_report_branch_fire_aggregate`,
`_findings_averages`) recomputes the same shape of ratio math inline, independently. `acquire_probe.py`
has always had one function, `_agg_ratios`, that both `_write_report`'s aggregate-by-category section
and `_write_findings`'s zero-cascade key numbers call. The split kept this centralization — `_agg_ratios`
lives in `_acquire_probe_analysis.py` and both `_acquire_probe_report.py` and
`_acquire_probe_findings.py` import it — rather than either (a) duplicating it into each report
section to "match" `branch_probe.py`'s shape, or (b) flattening `branch_probe.py`'s duplicated inline
math into a shared function it never had, which would have been an unasked-for behavior-preserving
refactor of a file this task wasn't touching. Recording this explicitly so a later reader comparing
the two sibling splits sees two different pre-existing shapes, correctly preserved, rather than
assuming one split "forgot" to centralize or duplicate to match the other.

One consequence of centralizing `_agg_ratios`: it depends on `_pct` (percentile calculation), which
is owned by the canary module in both files (used there for canary latency percentiles). In
`branch_probe.py`'s split, `_pct` only had one internal caller (`_canary_stats`, same module) so no
cross-module import was needed for it. Here, `_acquire_probe_analysis.py` imports `_pct` from
`_acquire_probe_canary.py` — a cross-module dependency the `branch_probe.py` split never needed,
directly because of this centralization difference.

## Dead code

No new dead constants or imports were found on this file during the split (unlike
`14_download_classify_probe.py`'s `PDF_SNIFF_BYTES`/`parse_qs`/`urlencode`). Every import and
constant in `acquire_probe.py` is used somewhere in the file.

## Verification

All six modules import cleanly standalone (`python3 -c "import <module>"` from inside
`dev/search_pipeline/`), no live browser/network involved — `_acquire_probe_instrument.py` applies
the real monkeypatch against `src.search.rate_limiter.RateLimiter` (both `__init__` and `acquire`)
but never calls either. `--help` output confirmed byte-identical to the pre-split CLI (no flags
changed). `git diff` against the original reviewed concern by concern: every relocated block is
line-for-line identical apart from indentation and the new `import`/directory-parameter lines
(`report_dir` added to `_write_report`, `findings_dir` added to `_write_findings` — same treatment
as the previous two splits, since the constant's owning module moved out from under the functions
that used to read it as a bare global). `./venv/bin/python3 -m pytest dev/tests/`: 431 passed before
the split (via `git stash`) and 431 passed after — unchanged, nothing in that suite exercises this
dev probe. Every function across all six files is ≤41 LOC (`_run_single_query`, the largest).

See `dev/search_pipeline/` (this DOCS.md) for the resulting module list. See the `branch_probe.py`
section above in this same file for the sibling split this one was compared against — the
comparison is the point of this section, not incidental.

# Splitting dev/search_pipeline/cdp_starvation_probe.py by concern (2026-09-18)

Fourth and last unit in this sweep, and the third sibling in the bee investigation (Phase 1, the
earliest of the three — `acquire_probe.py` is Phase 2, `branch_probe.py` is Phase 3). 581 LOC. The
scan named `_write_findings` (124 LOC); an AST pass over every function in the file (same technique
as the previous two units) found a second: `run_cdp_probe` at 84 LOC. Everything else — including
`_compute_stats` (34), `_derive_verdict` (22), `_r_timeseries` (30), and every other `_r_*` report
renderer — was already under 50.

By this point in the sweep the pull toward making all three siblings' file lists identical is real
and was resisted deliberately, point by point, rather than argued about in the abstract:

## Where this split genuinely matches its siblings

- **Canary (Pattern B).** `_canary_monitor`, `_sample_category`, `_pct` line up closely with both
  `_branch_probe_canary.py` and `_acquire_probe_canary.py`. `_start_probe_clock`/
  `_start_canary_monitor`/`_stop_canary_monitor` — the same orchestrator-shrinking extraction
  technique used on both prior units — applies unchanged here too.
- **Verdict-function placement.** Same as both siblings: the verdict-deriving function lives in the
  report module, findings imports it from there. `_derive_verdict` moved into
  `_cdp_starvation_probe_report.py`, exactly where `_overall_verdict`/`_overall_disc` live in their
  respective modules.
- **Report/findings split into a two-file, section-builder shape.** Same overall shape as both
  siblings: a timestamped report module and a fixed-path findings module, each with report split
  into small single-purpose section builders.

## Where it does not, and was not forced to

- **`_compute_stats` is richer than its cousins, and stayed richer.** `_canary_samples` here is a
  3-tuple (`ts, latency_ms, num_tasks`) where both siblings use a 2-tuple (no task-count tracking).
  `_compute_stats` returns five category buckets (`overall`, `normal`, `empty`, `zero_cascade`,
  `cold_start`) where the siblings' equivalents (`_canary_stats`/`_agg_ratios`-adjacent territory)
  return three. Nothing was trimmed to make the shapes match.
- **No analysis-layer module exists, and none was invented.** Both `branch_probe.py` and
  `acquire_probe.py` have a module reducing per-engine event lists into a per-query summary
  (`_build_engine_detail`/`_query_discriminator`, `_build_engine_summary`/`_discriminator`). This
  file has nothing like it — CDP events are a single global message count in a time window, computed
  inline with one `sum()` expression in the query loop, not per-engine at all. There is no
  `_cdp_starvation_probe_analysis.py`. `_load_queries` (4 LOC), which lived in the analysis sibling
  on both prior units, has no analysis sibling to go into here and was left in the entry file
  instead — forcing an analysis module into existence purely to give this file the same five-sibling
  shape as the other two would have been exactly the harmonization this sweep is supposed to avoid.
- **`_write_report` was already split before this task touched it, and was left alone internally.**
  A prior author had already broken `_write_report` into one-function-per-section renderers
  (`_r_header`, `_r_query_table`, `_r_latency_stats`, `_r_timeseries`, `_r_cdp_table`,
  `_r_slow_callbacks`, `_r_verdict_section`) under an explicit `# Report section renderers` marker —
  18 LOC calling seven helpers, already compliant. All seven renderers moved into
  `_cdp_starvation_probe_report.py` byte-for-byte; none were rewritten, resequenced, or touched
  beyond the file they now live in.
- **Two instrumentation mechanisms bundled into one module, not two.** Neither sibling patches
  pydoll — this file's "Pattern C" is a monkeypatch on
  `ConnectionHandler._process_single_message` (CDP message timestamps), a different target
  entirely from the siblings' `RateLimiter` patches. It also has "Pattern A" (an asyncio-logger
  handler capturing slow-callback warnings) which neither sibling has at all. Both are passive,
  install-once hooks populating shared state nobody polls until report time, so they share one
  module, `_cdp_starvation_probe_instrument.py` — one module holding two distinct instrumentation
  mechanisms, a shape neither prior split needed.
- **No smoke mode, no cascade-reproduction branch — verified, not just read.** `branch_probe.py`
  stops and writes a STOP note on cascade failure; `acquire_probe.py` warns and writes anyway; this
  file has neither behavior and never did — no `--smoke` flag in its `argparse`, no
  cascade-reproduction check anywhere in `run_cdp_probe`. It always runs the full query set and
  always writes both outputs. Per the standing instruction to use a call-recording stub on any
  control-flow claim rather than assert it from reading alone, the extracted orchestrator was run
  twice with every callee replaced by a call-recording stub — once with `max_queries=None`, once
  with `max_queries=5` — and both recorded the identical sequence `clock → pattern_a →
  load_queries → execute → write_outputs`, with `write_outputs` reached exactly once in both runs
  and no conditional anywhere in between. A negative result (no branching exists) checked the same
  way a positive one would be, per the standing instruction from the `acquire_probe.py` round: an
  assumption that "this one has no branches" is worth less than a call trace that shows it.

## Dead code

None found. Every import, constant, and module-level list in the original file is used somewhere —
unlike `14_download_classify_probe.py` (`PDF_SNIFF_BYTES`, `parse_qs`, `urlencode`, all dead) and
consistent with `acquire_probe.py` (also nothing dead). Checked the same way both times: read every
import and every top-level name against its usages across the whole file before moving anything.

## Verification

All five modules import cleanly standalone (`python3 -c "import <module>"` from inside
`dev/search_pipeline/`), no live browser/network involved — `_cdp_starvation_probe_instrument.py`
applies the real monkeypatch against `pydoll.connection.connection_handler.ConnectionHandler` but
never drives a connection through it. `--help` output confirmed unchanged (same single
`--max-queries` flag, same description string). `git diff` against the original reviewed concern by
concern: every relocated block is line-for-line identical apart from indentation and the new
`import`/directory-parameter lines (`report_dir` added to `_write_report`, `findings_dir` added to
`_write_findings`, `total` replacing an inline `len(queries)` in the per-query print — same
treatment as both prior splits). The call-recording stub check on `run_cdp_probe` is documented
above under its own heading rather than folded into this paragraph, since it was the specific
instrument requested for this round. A synthetic end-to-end run (one fake canary sample, one fake
query record, `REPORT_DIR`/`FINDINGS_DIR` pointed at a scratch `dev/search_pipeline/debug/` dir,
deleted afterward) drove `_write_outputs` through the real cross-module call chain and produced both
`md/cdp_probe_<ts>.md` and `md/01_probe.md` with the expected header content.
`./venv/bin/python3 -m pytest dev/tests/`: 431 passed before the split (via `git stash`) and 431
passed after — unchanged, nothing in that suite exercises this dev probe. Every function across all
five files is ≤49 LOC (`_run_single_query`, the largest — one line under the threshold).

See `dev/search_pipeline/` (this DOCS.md) for the resulting module list. See the `branch_probe.py`
and `acquire_probe.py` sections above in this same file for the two sibling splits this one was
compared against throughout.
