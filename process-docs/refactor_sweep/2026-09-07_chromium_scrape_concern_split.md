# Splitting chromium_scrape.py by concern (2026-09-07)

`src/scraper/chromium_scrape.py` had grown to 630 LOC by mixing two concerns: scrape orchestration
(`try_scrape`, config stamping, hooks, diagnosis extraction, output formatting) and the
self-launched Chrome process lifecycle (bundle-path resolution, self-launch flags, the macOS
focus-steal watchdog, DevToolsActivePort wait, process/dir teardown). A separate, unrelated
function — `is_garbage_content` — also lived there despite being consumed only by
`src/crawler/crawl_site.py`. Pure relocation across two commits, zero behavior change: 378 passed
before and after each commit.

## Module boundary and import direction

`src/scraper/chromium_process.py` (254 LOC) took the process-lifecycle concern: `_find_app_bundle`,
`_resolve_chromium_bundle_path`, `_build_self_launch_flags`, `_get_frontmost_app`, `_activate_app`,
`_focus_steal_watchdog`, `_self_launch_chrome`, `_wait_for_devtools_port`, `_pids_on_profile`,
`_kill_by_profile`, `_reap_orphaned_scrapes`, `_pids_matching_scrape_profiles`,
`_live_scrape_profile_dirs`, plus `CDP_PORT_WAIT_TIMEOUT_S`/`FOCUS_STEAL_POLL_INTERVAL_S`.
`chromium_scrape.py` (350 LOC) kept orchestration and imports what it needs from the new module.

**`TOTAL_SCRAPE_BUDGET_S` was placed in `chromium_process.py`, not `chromium_scrape.py`, specifically
to avoid a circular import.** The constant is read by both `try_scrape` (orchestration) and
`_reap_orphaned_scrapes` (process lifecycle). Since `chromium_scrape.py` already needs to import
many symbols FROM `chromium_process.py` (one-directional: orchestrator depends on the process-
lifecycle helper), leaving the budget constant in `chromium_scrape.py` would have forced
`chromium_process.py` to import it back, creating a cycle. Putting it alongside the other
process-lifecycle constants (`CDP_PORT_WAIT_TIMEOUT_S`) keeps the dependency strictly one-directional
— `chromium_scrape.py` imports it from there like everything else.

## Test-patch retargeting: which module's globals actually matter

The non-obvious part of this move: a function's own body resolves bare names (helper calls,
`subprocess`, `psutil`, `tempfile`, `death_pipe`) via **its home module's globals** — the module it
is DEFINED in — never the caller's globals, regardless of which module's attribute you use to
invoke it. Concretely:

- Patches that intercept calls MADE BY `_acquire_cdp_headed`/`try_scrape` (both staying in
  `chromium_scrape.py`) — e.g. `chromium_scrape._resolve_chromium_bundle_path`,
  `._self_launch_chrome`, `._wait_for_devtools_port`, `._pids_on_profile`, `._kill_by_profile`,
  `._reap_orphaned_scrapes`, `.TOTAL_SCRAPE_BUDGET_S`, `.death_pipe` — correctly stay pointed at
  `chromium_scrape`, because that module imports these names into its OWN namespace and
  `_acquire_cdp_headed`/`try_scrape`'s bare-name lookups resolve there.
- Patches/calls exercising a MOVED function's OWN internals (`_kill_by_profile` calling
  `_pids_on_profile`; `_reap_orphaned_scrapes` calling `psutil`/`tempfile`/`death_pipe`/
  `_pids_matching_scrape_profiles`/`_live_scrape_profile_dirs`; `_pids_on_profile`/
  `_pids_matching_scrape_profiles` calling `subprocess`) had to retarget to `chromium_process`, AND
  the test had to call the function via `chromium_process.<fn>(...)` — patching
  `chromium_scrape.subprocess` after the move would silently no-op (the attribute doesn't even
  exist there anymore once the now-unused `import subprocess` is dropped from `chromium_scrape.py`).

`dev/tests/test_chromium_scrape.py` was updated function-by-function against this rule: 13 tests
needed their patch target and/or call site moved to `chromium_process` (the two `_pids_on_profile`
tests, two `_kill_by_profile` tests, three `_reap_orphaned_scrapes` tests, two
`_live_scrape_profile_dirs` tests, two `_wait_for_devtools_port` tests, two `_find_app_bundle` tests,
two `_build_self_launch_flags` tests — some counted above already, see the commit diff for the
exact list) plus the shared `_patch_cdp_launch_mechanics` helper's one `chromium_scrape.Path(...)`
reference (chromium_scrape.py no longer imports `Path` at all).

## is_garbage_content: two moves, not one

First pass moved `is_garbage_content`/`_LINK_LINE_RE` directly into `crawl_site.py` (its only
consumer) — correct relocation target, but it pushed `crawl_site.py` to 403 LOC, one file-split
threshold this same sweep enforces. Second pass split it back out into a new sibling,
`src/crawler/garbage_filter.py` (51 LOC, INFRASTRUCTURE + FUNCTIONS only, no ORCHESTRATOR — same
utility-module shape as `scrape_logger.py`), bringing `crawl_site.py` back to its original 359 LOC.
`crawl_site.py` now imports `is_garbage_content` from `garbage_filter.py` via a plain absolute
import, no re-export needed since nothing outside `crawl_site.py` calls it directly except the
tests and one dev script below.

Two consumers needed re-pointing across both passes: `dev/scrape_pipeline/garbage_eval/
08_garbage_edge_cases.py` (a pre-existing one-shot dev script, imports the classifier directly —
not part of the grep scope the task named, `src/`/`cli.py`/`dev/tests/`, but left broken it would
have been a silent regression, so it was fixed too) and the two `is_garbage_content`-specific tests
in `dev/tests/test_chromium_scrape.py` (`test_is_garbage_content_still_importable_and_functioning`,
`test_try_scrape_does_not_call_is_garbage_content`) — both ended up importing `garbage_filter`
directly rather than `crawl_site`, since that is the function's actual, final home.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed after the chromium_process split, 378 passed again
after the garbage_filter split (same count both times — no test was added or removed, only
relocated/retargeted). A live `python -c` import check after each commit confirmed every
public/reused-private symbol still resolves from its new location (`chromium_scrape`,
`chromium_process`, `crawl_site`, `garbage_filter`, and `cli.py`'s own import chain).
