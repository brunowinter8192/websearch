# dev/news_pipeline/exploration/ module split (2026-09-16)

Worker entry for the `iterative-dev-refactor` pass assigned to `dev/news_pipeline/exploration/`,
one of the areas the orchestrator record in `process-docs/refactor_sweep/` listed as still
carrying its debt. Seven standalone CoinDesk probe scripts, worked one file at a time in the order
`01, 05b, 06, 05, 02, 03, 04`, each committed separately. All seven are now at zero hits: no module
over 400 LOC, no function at or above 50 LOC, verified by an AST scan over the whole directory
after the last commit.

## Starting numbers, ending numbers

| Script | Before | After (main file / split files) |
|---|---|---|
| `01_coindesk_ui_probe.py` | 454 LOC, 1 function >50 | 236 / `_01_dom.py` 239 |
| `05b_coindesk_warmth_probe.py` | 422 LOC, 2 functions >50 | 354 / `_05b_report.py` 107 |
| `06_coindesk_full_discovery.py` | 508 LOC, 3 functions >50 | 366 / `_06_capture.py` 179, `_06_progress.py` 44, `_06_report.py` 36 |
| `05_coindesk_cursor_probe.py` | 592 LOC, 5 functions >50 | 244 / `_05_capture.py` 132, `_05_parse.py` 49, `_05_fixed.py` 125, `_05_report.py` 158 |
| `02_coindesk_pagination_probe.py` | 609 LOC, 3 functions >50 | 24 / `_02_dom.py` 139, `_02_quick.py` 220, `_02_depth.py` 167, `_02_report.py` 192 |
| `03_coindesk_backfill_traversal.py` | 622 LOC, 2 functions >50 | 345 / `_03_capture.py` 240, `_03_log.py` 25, `_03_report.py` 141 |
| `04_coindesk_timeline_replay_probe.py` | 652 LOC, 4 functions >50 | 151 / `_04_capture.py` 127, `_04_replay.py` 347, `_04_report.py` 174 |

## The shape every split followed, and why it did not collapse into one shared module

Every probe that talks to a live Chrome via pydoll shares the same surface: `get_free_port`,
`launch_background_chrome` (`open -gna` + `--remote-debugging-port`), `wait_for_ws_url`,
`kill_chrome_on_port`, `_extract_value` for CDP unwrapping, plus a `tempfile.mkdtemp` session dir.
This is the exact "several `write_report` functions that share a surface shape" situation the
`refactor_sweep` entry already ruled on twice (`browser_posture`'s five `write_report`s, and its
two `kill_survivors` implementations). The instruction for this batch was explicit: do not unify
across the seven. Every `_NN_capture.py` in this batch is a **verbatim, byte-identical copy** of
that probe's own launch/CDP code — never imported from a sibling probe's capture module, never
merged into a shared `_lib.py`. Two probes (`02`'s quick and depth modes) even ended up with two
near-identical `get_final_button_state` implementations — one if/elif/else, one ternary — kept as
two separate functions in two separate files rather than picked-and-merged, because merging would
have silently rewritten one of them to the other's literal source.

The only sharing that happened was **within** one probe's own split, never across probes:
- `05`'s fixed-cursor algorithm (`_05_fixed.py`) needed `parse_articles`/`extract_cursor_std`/
  `build_cursor_url`, which the walk-mode code (kept in the main file) also needs. Pulling those
  into `_05_parse.py` was required to avoid a cycle (`_05_fixed.py` importing from the main file,
  which itself imports `fixed_cursor_loop` from `_05_fixed.py`). This is the one place in the batch
  where a genuinely new shared leaf module was introduced, and it was introduced by necessity
  (breaking a cycle), not by convenience.
- `02` turned out to be two full, independent probes bundled in one file (`probe_workflow` /quick
  mode/ and `depth_workflow` /depth mode/, dispatched by `--depth`). Splitting them into
  `_02_quick.py` and `_02_depth.py` left the original file as a 24-line pure CLI dispatcher with no
  `ORCHESTRATOR` or `FUNCTIONS` section at all — there was no function-level logic left to guard.
  This is not a degenerate case to fix later; it is the correct end state for a file whose only
  remaining job is `argparse` + a two-way `asyncio.run` dispatch.

## The hazard from `browser_posture`'s regression: checked for, not hit

The precedent's warning — extracting a `try`-guarded body into a helper that catches `Exception`
and returns silently drops the `finally` guarantee for a `BaseException` (Ctrl-C mid-probe leaves a
real Chrome process and a temp profile dir behind) — applies directly here, since every browser
probe in this batch has the same `try: <navigate/capture/loop> finally: <tab.close/chrome.close/
kill/rmtree>` shape. The pattern used in every single one of the seven splits was the same:
**chrome/tab creation and the `try:`/`finally:` keywords themselves never moved out of the
orchestrator.** Only two kinds of things were extracted:
1. Logic that runs *after* a successful connect, operating on an already-live `tab`/`page` (e.g.
   `05`'s `run_capture_phase`, `05b`'s `run_capture_phase`, `06`'s `run_capture_phase`, `03`'s
   `load_initial_feed`, `04`'s `run_capture_phase`/`extract_and_replay`). These don't own the
   resource, so a raise from inside them still reaches the orchestrator's own `finally` untouched.
2. The `finally` body itself, moved into a `teardown_*` helper called as the **sole statement** of
   `finally:` — not wrapped in a new `try/except` at the call site, so nothing new swallows a
   `BaseException` that used to propagate.

Every one of these was verified with a control-flow diff (where does each `try`/`except`/`finally`
guarantee live before and after) in addition to the output-identity proof, per file, before commit.
No teardown regression was introduced in this batch.

## Two `while True` loops became boolean-returning helpers — a real transformation, not a relocation

Two loops needed their *body*, not just trailing logic, pulled apart because the body itself was
the over-50-line function:

- **`06_coindesk_full_discovery.py`: `cursor_loop`.** The original `while True: ... break ...`
  became `while not run_cursor_iteration(state, year_files, seen_ids, log_fh): pass`, with three
  `break` statements collapsing into `return True` inside `run_cursor_iteration` (via `process_batch`
  and `get_next_body`). Loop-carried scalars were threaded through a `state` dict mutated in place
  rather than passed back as a long return tuple.
- **`03_coindesk_backfill_traversal.py`: the click loop.** The original `for click_n in range(...):
  ... break ... else: ...` kept its `for`/`else` **directly in a new `run_click_loop` function**
  (the `for`/`else` construct itself was not touched — only the body was pulled apart), and three
  `break` statements became `return True` calls split across two helpers, `check_stop_conditions`
  (button-gone / disabled-persistent) and `record_click_result` (plateau-reached).

Both are genuine control-flow transformations, not pure code motion, and both needed dedicated
proofs beyond the report/leaf-function byte-identity checks: multi-scenario harnesses reconstructing
the pre-refactor inline loop body from `git show` and running it against a scripted fake
`tab`/`page` side by side with the new decomposed functions, comparing the full result structure,
every log line, and — for `03` — the exact click count and `stop_reason` string produced by letting
the `for`/`else` actually exhaust the range. For `06`, three scenarios (empty-response stop,
stop-date-floor stop, fallback-then-403-rewarm forcing a `CHECKPOINT_EVERY` hit) all matched. For
`03`, five single-call scenarios plus two multi-call scenarios (plateau-stop firing at exactly the
3rd consecutive no-growth click, and cap-exhaustion driving the `for`/`else` branch) all matched.

## Dead code that had to be preserved exactly, not cleaned up

Every one of these was left in place because removing it would be a behavior claim ("this was truly
inert") that the task did not ask for and that a synthetic proof cannot fully back up beyond the
cases actually exercised:
- `06`: `depth_workflow`'s `content_fetches` list is computed and never read (only
  `any_content_fetch` is used). `cursor_loop`'s `start_url` parameter is accepted and never read.
- `05`: `storytype_walk`'s local `url = first_url` / `url = next_url` tracking is never read after
  assignment.
- `04`: `write_report`'s `call_rows = [r for r in cursor_results if r.get("call") != "SUMMARY"]` is
  computed and discarded (the actual per-call table uses a separately-built `call_rows_plain`).
  `test_recoverability`'s `hdrs10`/`hdrs40` are captured and discarded. `flag_headers`'s local
  `keys = {k.lower() for k in hdrs}` is computed and never used in the returned dict.
- `04`'s `write_fixed_report`-equivalent in `05` has a **live bug**, not dead code: a result row
  built from `{"call": i + 1, "error": "no articles in body"}` has no `"status"` key, and
  `_render_fixed_call_row` does `r.get("status") != 200` then unconditionally indexes `r['status']`
  in the f-string two lines later — `KeyError`. Confirmed both the pre-refactor and post-refactor
  code raise the **identical** `KeyError('status')` for this input. Not fixed; out of scope for a
  refactor task, and it was never observed to fire in a real run per this directory's `DOCS.md`
  findings.

All of the above were kept as literal, unread expressions/parameters in the new files. A successor
who "cleans up" any of them during a later comment-removal or dead-code pass should re-verify with
a fresh synthetic-fixture proof rather than assume `git blame` history covers it — commit logs are
not a belief source per this project's worker rules, and none of these were re-derived from
first principles here, only carried forward unchanged.

## Method notes

- Proof shape used for every file: (1) `git show` the pre-refactor function, (2) byte-diff every
  function that moved without behavior change (all of them came back `SAME`, dozens of functions
  across seven files, zero drift), (3) synthetic fixtures (fake `tab`/`page` objects dispatching on
  JS-string content, fixed `datetime.now`/`time.monotonic` patches shared across cross-module
  boundaries) feeding both the old monolith and the new split, comparing full output — report file
  bytes, returned data structures, and captured stderr/stdout together, not just one of the three.
- The comment-multiset diff caught two real drops on `04` (`# First 403/non-200: capture full
  diagnostics` and `# Response header signals`, both attached to logic that got pulled into new
  named helpers) before commit. Both were restored as leading comments on the new helper functions.
  The only comment ever *added* across all seven files is `# noqa: E402`, one per cross-file import
  line that follows a `sys.path.insert(0, str(Path(__file__).parent))` — the same convention already
  used and merged in `dev/browser_posture/`. This is a lint directive, not documentation prose, and
  it was disclosed as such in every per-file report rather than folded silently into the "empty
  diff" claim.
- Cross-module test patching inside one probe's own split needs care: a name imported directly into
  a file's namespace (`from _NN_capture import foo`) must be patched on *that* file's module object,
  while a name only reached indirectly (a helper in `_NN_capture.py` calling another name defined in
  the same file) must be patched on `_NN_capture`'s own module object via `sys.modules["_NN_capture"]`.
  Patching the wrong one silently no-ops and produces a false "MISMATCH" that looks like a real bug
  (hit this in the `05b`, `05`, and `04` proofs; in every case the fix was to patch both possible
  targets and let `hasattr` pick the right one, not to assume the import style from memory).

## What's left in `dev/`

This entry closes `news_pipeline`'s share of the `dev/` LOC debt the `refactor_sweep` orchestrator
record measured on 2026-09-15. `explore_pipeline`, `lane_choice`, `scrape_pipeline`,
`search_pipeline`, `tests`, `url_discovery`, and `cli.py::main` were out of scope for this session
and are untouched.
