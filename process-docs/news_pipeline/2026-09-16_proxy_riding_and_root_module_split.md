# dev/news_pipeline/coindesk_proxy_riding/ and dev/news_pipeline/ root module split (2026-09-16)

Worker entry for the second `iterative-dev-refactor` batch of this session, covering
`dev/news_pipeline/coindesk_proxy_riding/` (a genuinely wired pipeline, not independent scripts —
`p0_pool`, `p2_browser_rider`, `p3_url_sampler`, `p4_reporter` feed `run_coindesk_riding.py`, and
`p4_reporter.py`/`test_watchdog.py` import back into `p2_browser_rider.py`, two of those imports
private) plus the three root-level hits in `dev/news_pipeline/`. Worked one file at a time in the
order `p2_browser_rider, p4_reporter, run_coindesk_riding, analyze_write_times, test_tail_race,
test_sigint_report, smoke_stage1, 01_coindesk_discover, 02_coindesk_scrape, 03_coindesk_cleanup`,
each committed separately. All ten files are now at zero hits, verified by an AST scan over both
directories after the last commit. For the companion `exploration/` batch's findings (the two
`while True`/`for...else` → boolean-returning-helper transformations, the dead-code inventory, the
cross-module test-patching gotcha), see this same folder's `2026-09-16_exploration_module_split.md`.

## Starting numbers, ending numbers

| File | Before | After |
|---|---|---|
| `p2_browser_rider.py` | 498 LOC, 3 functions >50 | 283 LOC / `_p2_state.py` 77, `_p2_fetch.py` 104, `_p2_watchdog.py` 111 |
| `p4_reporter.py` | 344 LOC, 2 functions >50 | 208 LOC / `_p4_stats.py` 169, `_p4_plots.py` 62 |
| `run_coindesk_riding.py` | 115 LOC, 1 function >50 | 123 LOC (no module split needed) |
| `analyze_write_times.py` | 258 LOC, 2 functions >50 | 288 LOC (no module split needed) |
| `test_tail_race.py` | 445 LOC, 1 function >50 | 367 LOC / `_test_tail_race_watchdog.py` 104 |
| `test_sigint_report.py` | 213 LOC, 1 function >50 | 227 LOC (no module split needed) |
| `smoke_stage1.py` | 254 LOC, 2 functions >50 | 274 LOC (no module split needed) |
| `01_coindesk_discover.py` | 370 LOC, 1 function >50 | 384 LOC (no module split needed) |
| `02_coindesk_scrape.py` | 156 LOC, 1 function >50 | 160 LOC (no module split needed) |
| `03_coindesk_cleanup.py` | 252 LOC, 1 function >50 | 261 LOC (no module split needed) |

Six of the ten only ever needed function-level decomposition, not a module split — this batch had
far fewer over-400 modules than `exploration/` (2 vs 7), and every one of the six "no split needed"
files started and ended comfortably under 400, decomposition alone pushing them up by 10-30 lines
of new `def`/blank-line overhead but never past the threshold. `p4_reporter.py` is the one exception
worth naming explicitly below.

## The `p4_reporter.py` LOC-inflation trap, and how it differs from a real module hit

`p4_reporter.py` started at 344 LOC — under 400, with two functions over 50. Decomposing
`_compute_stats` (88→25) and `_write_md` (141→32) **in place, inside the same file**, pushed the
file to **423 LOC** — over threshold, purely from the bookkeeping cost of ~15 new `def` lines and
their blank-line separators. This is exactly the shape the task's "cosmetic LOC shrinking is not a
split" warning cuts the other way on: the file crossing 400 was not itself a signal to invent a
split, but stats-computation (`_compute_stats` and its seven new helpers, `_percentiles`,
`_distribution_stats`) and matplotlib plotting (`_write_cumulative_plot` and its two siblings) were
already two distinct, real concerns sitting in the one file before I ever touched it — the
in-place decomposition just made the existing concern boundary visible by exceeding the threshold
first. Moved to `_p4_stats.py` (169 LOC) and `_p4_plots.py` (62 LOC), `p4_reporter.py` dropped to
208 LOC holding only the orchestrator and the markdown-section renderers. `write_riding_report`'s
import surface for `run_coindesk_riding.py` and `p2_browser_rider.py`'s lazy-imported
`write_riding_report` call were unaffected — that name never moved.

## The `job_records` skip — a real bug my own draft introduced, caught by the synthetic proof, not by reading

This is the finding to carry forward verbatim, because it is exactly the shape of mistake this
whole sweep exists to catch.

**The original, pre-refactor behavior of `p2_browser_rider.py::_run_slot`:** inside the per-proxy
`while burn_count < state.burn_threshold:` loop, the status-handling `if/elif/elif/else` chain ends,
and only *after* that chain — at the same indentation, still inside the `while`, but textually below
the `if/elif/else` — sits `state.job_records.append(job)`. Two of the four status branches contain a
`break` that exits the `while` loop **before execution ever reaches that append line**:
- `status == "connect_fail"`: increments `n_connect_fail`, requeues the URL, sets `cf_broke = True`,
  logs, then `break`.
- `status in ("failed", "empty")` **and** `fail_count >= FAIL_THRESHOLD`: increments `fail_count`,
  requeues, logs, then `break`.

In both of these cases, **no `JobRecord` is ever created for that fetch attempt.** Only `status ==
"ok"`, `status == "regwall"`, and `status in ("failed", "empty")` *below* the fail threshold reach
the append. This is why `p4_reporter.py::_compute_counts` has its own comment reading
`# connect_fail breaks before job_records.append() → use authoritative state counter` and sources
`n_connect_fail` from `state.n_connect_fail` rather than by counting `job_records` — the counter and
the record list are **deliberately** not in agreement for connect_fail. A successor should treat
this as confirmed original behavior, not a bug to fix: it is why the reporter reads two different
sources of truth for different metrics, and that split is intentional, evidenced by the comment
already present in production code before this refactor touched anything.

**What went wrong in my first draft:** when `_run_slot` was decomposed into `_ride_one_proxy` /
`_ride_one_url` / `_apply_url_status`, the natural-looking shape was: `_ride_one_url` builds the
`job` object, calls `_apply_url_status` to classify/record the outcome and get back a
`should_break` flag, and then **unconditionally** appends `job` to `state.job_records` before
returning `should_break` to the caller. That unconditional append is wrong — it resurrects the
append for exactly the two cases the original code was structured to skip.

**How it was caught:** not by re-reading the diff against the original (which I had already done,
and which did not surface it — the append-skip is implicit in control flow, not stated as a
sentence anywhere), but by the synthetic-fixture proof: two scenarios, `connect_fail_rotates` and
`failed_twice_drops`, compared full `RiderState` snapshots (job-record counts and statuses, ride
records, queue state) between the pre-refactor reconstruction and the new decomposition. Both
showed **one extra `JobRecord`** on the new side (3 vs 2, 5 vs 4) with an extra `"connect_fail"` or
`"failed"` entry the original never produced. The fix was one line: gate the append on
`if not should_break:` in `_ride_one_url`. Re-ran the same two scenarios plus three more
(`two_ok_then_done`, `regwall_burns_proxy`, `pool_exhausted`) — all five matched exactly after the
fix, including job-record lists, ride-record summaries, queue/in-flight state, and the exact printed
`stderr` narrative.

**The general lesson:** a `break` sitting *before* a line of bookkeeping code that runs
unconditionally on the non-break paths is a control-flow-dependent side effect that is trivially
lost when the loop body is extracted into a function that returns a status instead of physically
`break`-ing. It will not show up in a read-through of the extracted code, because the extracted
code looks locally correct — the missing information is what the *original* code's `break`
*prevented from happening*, which is invisible unless you diff behavior, not text.

## Re-export verification for `p2_browser_rider.py`

Per the task's specific proof obligation: actually imported (not just statically checked)
`RiderState`, `RideRecord`, `JobRecord`, `FAIL_THRESHOLD`, `_abort_stall`, `_watchdog`,
`run_riding_pool`, `_next_proxy` via `from p2_browser_rider import ...` after the split. All eight
resolve; `RiderState` reports as `_p2_state.RiderState` (the re-export works because importing a
name at module level binds it in the importing module's own namespace — no `__all__` or explicit
re-export statement was needed). Then separately imported `p4_reporter` and `test_watchdog.py`
(which import `RiderState`/`FAIL_THRESHOLD` and `RiderState`/`_abort_stall`/`_watchdog` respectively
from `p2_browser_rider`) to confirm the whole downstream chain, not just the direct names.

## The `try`/`finally` shape, checked file by file

Every browser-owning orchestrator in this batch (`p2_browser_rider.py::run_riding_pool`,
`01_coindesk_discover.py::discover_workflow`) kept the same pattern already established in the
`exploration/` batch: chrome/tab creation and the `try:`/`finally:` keywords never left the
orchestrator function; only logic *after* a successful connect was extracted into helpers that
raise normally instead of swallowing.

One extra detail worth recording for `01_coindesk_discover.py`: its `finally` block has `await
tab.close()` **unguarded** (no `try/except` around it) while `await chrome.close()` **is** wrapped
in `try/except Exception`. This asymmetry is original, pre-refactor behavior — preserved exactly in
`teardown_chrome_session`, not "fixed" into symmetry. A successor should not read the difference as
an oversight to correct.

## `p2_browser_rider.py::_fetch_one_url`'s `try/except/finally` — untouched in shape

The `finally` here calls `crawler.crawler_strategy.browser_manager.kill_session(sid)`, releasing the
proxy-bound browser context — the actual resource-cleanup hazard site named in the task prompt. The
extraction only pulled the *classification* logic (the `if/elif/else` that turns a `result` object
into a status tuple) into `_classify_fetch_result`, called from *inside* the existing `try` block.
The `try`, `except Exception as exc`, and `finally` clauses themselves were never split apart or
moved to a different function than the one that already owned them. Verified via 7 synthetic
scenarios covering success, both non-success branches (proxy-error-substring match vs generic
failure), empty HTML, regwall detection, an exception raised by `crawler.arun`, and a `kill_session`
call that itself raises (confirming the non-fatal warning print still fires from the same place).

## `clean_body`'s two-pass split — the opposite case from the cookieyes precedent

The `refactor_sweep` orchestrator record (see that folder) documents a hazard from an earlier
session: `clean_web_cookieyes.py::clean_file` looked like a candidate for "phase" extraction (header
pass, then body pass) but several rules were *not* gated on a `heading_done` flag in the original,
so phasing them would have silently changed behavior for inputs where a marker appeared before the
heading expected to gate it. `03_coindesk_cleanup.py::clean_body` looks superficially similar (it
was flagged at 53 LOC) but is the opposite case: its own docstring-comment already documents it as
"Two passes: (1) line-level strip/substitution + trailing-ws; (2) paragraph normalization", and pass
2 only ever consumes pass 1's **completed** output list — there is no rule in pass 2 that fires
conditionally based on where in pass 1's execution something happened. Split into
`_clean_body_pass1` (returns the line list + two counters) and `_clean_body_pass2` (consumes that
list, returns the final lines + one counter), with `clean_body` reduced to three lines gluing them
together. Verified with 8 synthetic fixtures exercising every one of the nine noise rules
individually and in combination (tag-footer strip, orphan single-tag line, Google badge, date
byline, author byline, standalone image, image-link, empty-link substitution, inline-link
substitution, trailing-whitespace strip, consecutive-body-paragraph blank insertion, and
leading/trailing blank stripping) — all matched byte-for-byte against the original.

The distinguishing question for a successor facing a "looks like sequential phases" candidate:
**does the later phase's behavior depend on anything from the earlier phase other than its finished
output value?** If yes (cookieyes), phasing is unsafe without also verifying every rule's gating
condition. If no (this file), phasing is exactly the type of split that turns a genuine dual-concern
function into two clean ones.

## A pre-existing test bug surfaced, not introduced, in `smoke_stage1.py`

`smoke_stage1.py::test_watchdog_deterministic` constructs a `RiderState(...)` without `job_dir` or
`target_urls` keyword arguments. Called `test_import_clean()` and `test_watchdog_deterministic()`
directly (both are explicitly documented in the file's own docstring as needing no network or
browser) against **both** the pre-refactor copy and the refactored file. `test_import_clean` passes
identically in both, printing the same "imports ok, defaults ok, no sys.path hacks, late import
correct" line. `test_watchdog_deterministic` **fails identically in both** with `TypeError:
RiderState.__init__() missing 2 required positional arguments: 'job_dir' and 'target_urls'` —
confirmed the exact same traceback shape, same failing line inside the (differently-named, but
behaviorally identical) state-construction helper, before and after the split. This is a drift
between this smoke test and the current production `src/news/engine/proxy_riding/state.py` schema
— compare `test_sigint_report.py`'s own `_make_state`, which *does* pass `job_dir`/`target_urls` and
passes cleanly, so the drift is isolated to this one file's watchdog test. Not fixed here: fixing it
would be a behavior change to a test that currently reports green-for-the-wrong-reason (it never
actually reaches the assertions it claims to verify), and that decision needs the user, not a
refactor worker. `test_live_run` was never executed (real browser + network forbidden by the proof
rules); its extracted helpers (`_load_inventory_urls`, `_assert_manifest_shape`) were proven with
synthetic fixtures instead, and `_assert_pool_shuffle_effective` (which calls the network-touching
`load_backfill_pool`) was verified as a line-for-line, byte-identical relocation of the original
inline block by direct text comparison rather than execution.

## Running the actual test scripts end-to-end was the strongest proof available, and cheap

For `test_tail_race.py` and `test_sigint_report.py` — both explicitly documented as needing no
browser or proxy infrastructure, both targeting the real (not mocked-away) production
`src/news/engine/proxy_riding/` package — the fastest and strongest proof was to just run the whole
script twice, once from a pre-refactor copy placed in the same directory (so its `parents[N]`-based
`sys.path` resolution still worked) and once from the refactored file, and diff stdout. Both times
the only difference was the OS-randomized temp directory name baked into `tempfile.
TemporaryDirectory()`; every printed line, every PASS/FAIL, both exit codes, matched exactly. This
is a stronger check than any number of synthetic-fixture scenarios because it exercises the real
call chain into the real `rider.py`/`abort.py`/`reporter.py`, not a mock of it — worth defaulting to
whenever a script is self-contained, deterministic, and its own docstring says so.

## `DOCS.md` salvage

Both `DOCS.md` files touched in this batch carried a `## Gotchas` section, which is not part of the
DOCS.md format. Cut to format; content moved here verbatim.

### Salvage from `dev/news_pipeline/coindesk_proxy_riding/DOCS.md`

> `--page-timeout` (default 8000ms) is the dead-proxy timeout lever — dead proxies hit this before
> rotating. Regwall detection reads `result.markdown.raw_markdown`, not raw HTML (REGWALL_SIGNALS
> are hidden React components always present in HTML, so raw-HTML matching would false-positive on
> every page).

### Salvage from `dev/news_pipeline/DOCS.md`

> `02_coindesk_scrape.py` writes no report file — console-only progress; the two
> `md/coindesk_scrape_2026-05-27*.md` reports were produced by a separate historical run-analysis
> pass, not by the script itself.

## What's left in `dev/`

Between this entry and `2026-09-16_exploration_module_split.md`, `news_pipeline`'s entire share of
the `dev/`-wide LOC debt measured by the `refactor_sweep` orchestrator record on 2026-09-15 is now
closed: `exploration/` (7 files), `coindesk_proxy_riding/` (7 files touched of ~10 in the directory,
all now at zero hits), and the three root-level function-level hits. `theblock/` was never in scope
for either of these two batches and is untouched. `explore_pipeline`, `lane_choice`,
`scrape_pipeline`, `search_pipeline`, `tests`, `url_discovery`, and `cli.py::main` remain as
recorded in the orchestrator entry.
