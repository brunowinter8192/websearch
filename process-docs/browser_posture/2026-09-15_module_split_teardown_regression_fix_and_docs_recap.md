# browser_posture — module split teardown regression fix + DOCS.md recap, 2026-09-15

Worker session. Two tasks: (1) fix a teardown regression left behind by an earlier, already-merged
refactor sweep that split `03_fingerprint_patch_probe.py`, `04_headed_chromium_probe.py`, and
`05_cdp_headed_probe.py` into 13 modules total; (2) bring `dev/browser_posture/DOCS.md` into the
project's DOCS.md format (Role / Public Interface / Flow / Modules / State only) and write this
recap, since the merged split never got one. This session did not do the split itself — it inherited
it and fixed a defect plus wrote the missing paperwork.

## The regression (Task 1) — what it was, concretely

A function extraction is not behavior-preserving by default when the extracted piece used to sit
inside a `try/except Exception/finally` and the extraction only carries the `try/except` in with it,
leaving the `finally`'s unconditional cleanup behind at the call site with no guard at all.

`04_headed_chromium_probe.py::observe_run` (pre-split, `git show integration~1:...`) wrapped the
`AsyncWebCrawler` call in `try / except Exception / finally`, with `finally` guaranteeing
`stop_event.set()`, `await poll_task`, `stop_probe_server(server, thread)`. The split moved the
`AsyncWebCrawler` call and its `except Exception` into a new `_run_crawl4ai_once` helper (which now
returns `(False, msg)` instead of raising on `Exception`). The three cleanup lines were left in
`observe_run`, unconditional, no `try/finally` around them. Concretely: `_run_crawl4ai_once` still
absorbs a plain `Exception` and returns normally, so on the ordinary error path nothing changed —
this is why the defect was easy to merge without noticing, a normal test run looks identical either
way. The gap only opens for a `BaseException` that is NOT an `Exception` subclass — `asyncio.
CancelledError` (3.8+, no longer an `Exception` subclass) and `KeyboardInterrupt` are the two real
ones — which now propagates straight out of `_run_crawl4ai_once`, skips past `observe_run`'s cleanup
entirely (no `finally` to catch it), and leaks the polling task plus leaves the local throwaway HTTP
probe server running.

`05_cdp_headed_probe.py::run_probe` had the identical shape at a higher stake: the pre-split
`finally` guaranteed `kill_by_profile(user_data_dir)`, `kill_survivors()`, `shutil.rmtree(user_data_
dir, ...)`, `stop_event.set()`, `await poll_task`. The split moved the self-launch-through-scrape
sequence (and its `except Exception`) into `_run_self_launch_and_scrape`, again leaving those five
cleanup lines unconditional in `run_probe`. Here a `BaseException` mid-run (e.g. Ctrl-C during the
`arun()` call) would leave a REAL self-launched Chrome for Testing process running and a temp profile
directory on disk — not just a leaked asyncio task.

### The fix

In both files, wrap the single call site into the split-out helper in `try: ... finally:`, moving the
already-existing cleanup lines into the `finally`. No change to the extracted helpers themselves — the
split's shape stays exactly as it was, this is purely restoring the guard the split dropped.

```python
# 04_headed_chromium_probe.py::observe_run — before
poll_task = asyncio.create_task(_poll_browser_and_focus(...))
launch_success, error_message = await _run_crawl4ai_once(headless, dwell_s, url)

stop_event.set()
await poll_task
stop_probe_server(server, thread)

# after
poll_task = asyncio.create_task(_poll_browser_and_focus(...))
launch_success = False
error_message = None
try:
    launch_success, error_message = await _run_crawl4ai_once(headless, dwell_s, url)
finally:
    stop_event.set()
    await poll_task
    stop_probe_server(server, thread)
```

```python
# 05_cdp_headed_probe.py::run_probe — before
user_data_dir = tempfile.mkdtemp(prefix="browser-posture-cdp-probe-")
run_result = await _run_self_launch_and_scrape(bundle_path, user_data_dir, stage)

stage["name"] = "teardown"
await asyncio.to_thread(kill_by_profile, user_data_dir)
await asyncio.to_thread(kill_survivors)
shutil.rmtree(user_data_dir, ignore_errors=True)
stop_event.set()
await poll_task

# after
user_data_dir = tempfile.mkdtemp(prefix="browser-posture-cdp-probe-")
try:
    run_result = await _run_self_launch_and_scrape(bundle_path, user_data_dir, stage)
finally:
    stage["name"] = "teardown"
    await asyncio.to_thread(kill_by_profile, user_data_dir)
    await asyncio.to_thread(kill_survivors)
    shutil.rmtree(user_data_dir, ignore_errors=True)
    stop_event.set()
    await poll_task
```

Verification: no dedicated test file was added — this is a control-flow fix to a dev probe script,
not a src/ behavior change, and the project's own test-necessity rule ("a test is required once
behavior changes") points at the NORMAL path staying identical (confirmed: neither helper's own
`except Exception` branch changed, so a plain-Exception run produces byte-identical `launch_success`/
`error_message`/`run_result` values before and after). What changed is BaseException-path behavior,
which cannot be exercised deterministically in a sandbox (it depends on an external SIGINT/cancel
arriving mid-`await`) — this is exactly the kind of hypothesis the standards call out as "kept short,
not tested," since nobody has (yet) observed the leak in production logs; the fix is justified by the
line-by-line equivalence to the pre-split `finally` block, not by a reproduced incident. All 5 entry
scripts (`01`-`05`) still import cleanly under `./venv/bin/python3` (`runpy.run_path` with a non-
`__main__` run name, so `if __name__ == "__main__"` never fires) after the change. No function in the
area reached 50 LOC as a result (checked via an `ast`-based walk over every `FunctionDef`/
`AsyncFunctionDef` in every file in the dir) — `observe_run` sits at ~26 LOC, `run_probe` (05) at
~34 LOC.

## Lesson for the next split of this shape

When a `try/except Exception/finally` block gets pulled apart across a module boundary, the `except`
half is easy to carry along faithfully (it has an obvious visual boundary and a return value), but the
`finally` half has no return value and looks like "just some cleanup code that runs after the call" —
easy to leave sitting unguarded at the new call site because it still LOOKS correct on the only path
anyone runs by hand (the Exception path, which the extracted helper still swallows). Check every
`finally` block explicitly when auditing a split for this pattern: if the guarded call moved to a new
function but the `finally` did not move WITH it, the caller needs its own `try/finally` wrapping the
new call, not just the bare cleanup lines. `git show <parent-commit>:<path>` on the pre-split file is
the fastest way to get the exact original guarantee to diff against — that is how both regressions in
this session were confirmed rather than inferred from reading the post-split code alone.

## DOCS.md recap (Task 2)

`dev/browser_posture/DOCS.md` predated the split — it described `_lib.py` + `01`-`05` (6 modules) and
carried a `## Gotchas` section, which is not part of the project's DOCS.md format (Role / Public
Interface / Flow / Modules / State only, per the code standard). Rewrote it to cover all 13 modules
that exist post-split (`_lib.py`, `01`-`05`, plus the seven helper modules: `_fingerprint_report.py`,
`_chromium_bundle.py`, `_chromium_teardown.py`, `_headed_chromium_report.py`, `_cdp_launch.py`,
`_cdp_teardown.py`, `_cdp_report.py`), with every LOC number checked against real `wc -l` (see table
below). Modules are ordered by lane and call order: `_lib.py` first (shared across `01`-`03`), then
`01`, `02`, `03` + its `_fingerprint_report.py`, then `04` + its three helpers
(`_chromium_bundle.py`, `_chromium_teardown.py`, `_headed_chromium_report.py`), then `05` + its three
helpers (`_cdp_launch.py`, `_cdp_teardown.py`, `_cdp_report.py`).

```
_lib.py                        307
01_launch_latency_probe.py     300
02_parallel_chrome_probe.py    221
03_fingerprint_patch_probe.py  230
_fingerprint_report.py         257
04_headed_chromium_probe.py    172
_chromium_bundle.py             60
_chromium_teardown.py           68
_headed_chromium_report.py     211
05_cdp_headed_probe.py         238
_cdp_launch.py                  87
_cdp_teardown.py                51
_cdp_report.py                 183
```

The old DOCS.md's Role paragraph and per-module descriptions matched the project's format reasonably
well already — the six original module entries were reused near-verbatim, trimmed of detail that had
drifted into function-level territory (constants, specific flag lists), and extended with seven new
entries for the split-out helpers.

## Salvage from dev/browser_posture/DOCS.md

The old `## Gotchas` section (and everything else that did not fit Role / Public Interface / Flow /
Modules / State) is reproduced verbatim below, unparaphrased, per instruction. This is real,
previously-hard-won process knowledge about running these probes on this machine — it belongs in
process-docs, not in a module map, but it must not be lost. If a future session touches `01`-`05` or
adds a new probe to this dir, read this section before assuming any of these mechanisms are simple.

---

- None of `_lib.py`'s `open -g`-based launches (`open_background_process_creator`,
  `spawn_plain_chrome`) run a focus-steal reclaim watchdog — `open -g` only suppresses activation at
  the launch moment (playwright#42343), so a window from any of these can still steal focus later in
  the probe run. This went unnoticed here because these probes are short/self-contained; it caused a
  real, repeated focus-steal in `dev/access_recovery/01_google_dom_probe.py` (a longer-running,
  multi-navigation probe using the same pattern), which is why `dev/_lib/browser_launch.py` (own
  DOCS.md, dev-wide, not area-scoped) exists. Any NEW dev script that needs a headed-backgrounded
  Chrome for more than a one-shot launch should use that helper, not `_lib.py`'s launch functions —
  see `process-docs/browser_posture/` for the failure this addressed.
- Both scripts open real, visible Chrome windows on macOS (headed configs) — not safe to run on a
  headless CI runner; developed and verified interactively on the target Mac.
- `01`'s timer-drift measurement could NOT confirm real window occlusion in this environment
  (`document.visibilityState` stayed `visible` even with a same-geometry, `-g`-backgrounded coverer
  window on top) — the machine runs multiple concurrent real login sessions, so window-stacking
  assumptions don't hold. The drift numbers in the report are labeled "occlusion unconfirmed"; do not read a "no
  drift" result as proof the three flags make no difference under genuine occlusion.
- Full-screen `screencapture` was used once during development to debug the occlusion gap above and
  incidentally captured live, unrelated session content on this shared machine — deleted immediately,
  not part of either script. Do not add screenshot-based verification to these scripts without a
  window-specific (not full-screen) capture target.
- All probe profile dirs live under `~/.websearch/browser-posture-probe/` — isolated from
  `src/search/browser.py`'s shared `SESSION_DIR`, EXCEPT `02_parallel_chrome_probe.py`, which
  deliberately targets the real `SESSION_DIR` (that's the scenario under test).
- `03`'s CreepJS extraction does NOT look for "Trust Score"/"N lies" text — the live build (checked
  directly, not assumed from memory of another version) renders no such summary at all; every
  "trust"/"lie" substring in the page is a false positive (e.g. "CLIENT" contains "lie"). The real
  signal extracted is the "Headless" section's three percentages plus "confidence: &lt;level&gt;"
  notes. Re-verify this against the live page before reusing the extraction if CreepJS's UI changes.
- `03`'s getComputedStyle artifact test is `color: ActiveText` on a dedicated element, NOT a resting
  `<a>` — a plain link computes to the ordinary link color in every mode and never exercises what the
  patch targets (CSS ActiveText, the link's ACTIVE-state system color).
- `04` writes to the REAL, machine-shared chromium-1228 install under `~/Library/Caches/ms-playwright/`
  (not an isolated probe profile dir like `01`-`03`) — the `Info.plist` mutation is real, on the
  actual bundle patchright resolves in production. Hard-verifies the resolved bundle path contains
  `chromium-1228` before writing (refuses otherwise) — chromium-1223 (Playwright's own, separate
  revision) must never be touched.
- `04`'s plist revert is a byte-exact restore from a raw-bytes backup, NOT a `plistlib` round-trip —
  `plistlib.dump()` defaults to XML and silently converts a binary (`bplist00`) plist to XML even on
  a content-correct revert (caught during this probe's own development).
- `04` found that `LSUIElement=true` reliably CRASHES this bundle's launch (`icudtl.dat not found in
  bundle`, SIGTRAP) — differs from the Camoufox precedent (`process-docs/camoufox_lane/`), where the
  same mechanism worked. Isolated from plist format (XML-format-no-key launches fine); the crash
  tracks the `LSUIElement` key specifically.
- Deliberately triggering that crash makes macOS itself register a launchd per-app supervision job
  (`application.com.google.chrome.for.testing.<ids>`, visible via `launchctl list`) that auto-relaunches
  the full browser 10-20s later — independent of this script's own process-tree teardown, and NOT
  reliably bounded by any in-script sleep. `kill_survivors()` removes the launchd job every sweep
  round in addition to killing processes, but is not proven sufficient alone — verify manually
  (`pgrep -fl "ms-playwright/chromium"` + `launchctl list | grep chrome.for.testing`) ~20s after this
  script exits before trusting its own "0 orphans" line. One-shot-per-crash, not a repeating loop.
- `05`'s first draft called `wait_for_devtools_port`/`kill_by_profile`/`kill_survivors`/
  `self_launch_chrome` as plain synchronous functions from the async orchestrator instead of via
  `asyncio.to_thread` — their blocking `time.sleep`/`subprocess.run` calls starved the concurrently-
  running focus-poll task's event loop turns, silently producing 0 samples for the `cdp_port_wait`
  and `teardown` stages (looked like "these stages are just fast," was actually an instrumentation
  bug). Fixed by wrapping all of them in `asyncio.to_thread`; re-run confirmed real samples appear.
- `05`'s focus-poll headline number MUST exclude the `reference_launch` stage (an internal, direct,
  un-backgrounded patchright launch used only to capture a cmdline baseline for the args-delta, not
  part of the `cdp_url` route under test) — a first draft aggregated all stages into one percentage,
  which read as "the route steals focus ~50% of the time" when the actual route was 0% and the
  reference step (expected to steal focus, not a defect) was the entire cause. Report splits "route"
  vs. "reference" explicitly; do not re-merge them.

---

## What this session deliberately did NOT touch

The split's two deliberate non-decisions, as stated by the task that assigned this session (not
independently re-verified from code by me, since the split itself is out of my scope — flagging that
distinction explicitly): the five per-probe `write_report` functions were NOT merged into a shared
reporter, and `kill_survivors` was NOT unified between `04` and `05`, because `04`'s is multi-round
against an observed launchd auto-relaunch race while `05`'s is single-pass on a route where no crash
occurs. I did not revisit either decision — this session's scope was the teardown-guarantee fix plus
the DOCS.md/process-docs paperwork, nothing else. `_lib.py` was also left untouched, per the same
instruction; I read it in full for context but made no edits to it.
