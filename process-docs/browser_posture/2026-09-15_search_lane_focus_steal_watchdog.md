# Search lane's focus-steal watchdog (M1) — 2026-09-15

Worker session (worktree `mechanics`). Milestone: `websearch search_web` must not steal window
focus. Root cause, hazard reasoning, and a real bug found and fixed during live verification, all
scoped to `src/search/browser.py`.

## The problem, as reported by the user

A live `websearch search_web` run on 2026-09-15 brought a Chrome window to the OS foreground mid-
search — specifically Brave's own bot-check page ("Es wird überprüft, dass du kein Bot bist"),
screenshotted by the user. `src/search/browser.py` launches Chrome via macOS `open -g -n -a
"Google Chrome"`, which only suppresses activation at the launch MOMENT (playwright#42343) — any
window created afterward (every engine's `new_tab()` call is a separate CDP `Target.createTarget`
window-creation event) can auto-activate the app regardless. The scrape lane
(`src/scraper/chromium_scrape.py`/`chromium_process.py`) already has a background asyncio watchdog
for exactly this (`_focus_steal_watchdog`, see `process-docs/browser_posture/
2026-09-07_chromium_lane_focus_steal_watchdog.md`); the search lane had none — confirmed by grep,
`_focus_steal_watchdog` had exactly one caller, not in `src/search/`.

## Why the scrape lane's watchdog could not be reused as-is

`_focus_steal_watchdog(app_name)` (`chromium_process.py`) is keyed on the frontmost app's NAME
(`_get_frontmost_app()`, System Events). Safe on the scrape lane because it launches a dynamically
resolved, dedicated Chromium bundle (patchright's own download) — structurally a different app
from the user's own `"Google Chrome"`, no name collision possible.

The search lane launches the user's ACTUAL `"Google Chrome"` bundle, bare name
(`_open_background_process_creator`, `open -g -n -a "Google Chrome"`). If the user has their own
separate Chrome window open and deliberately switches to it mid-search, BOTH processes report
frontmost app name `"Google Chrome"` — indistinguishable by name. A name-keyed watchdog would
misread the user's deliberate switch as "our" steal and yank focus away from it — a new bug, not a
fix. This was the explicit hazard Main called out before giving the go-ahead.

## The fix: PID-keyed, not name-keyed

`_record_own_pids()` (pre-existing, used by `death_pipe`'s crash watchdog) already fingerprints
exactly this run's own Chrome PIDs via `pgrep -f user-data-dir=<SESSION_DIR>` — a profile dir only
this module's own launches ever use. The user's own separate Chrome instance, on their normal
profile, can never match that pgrep pattern. So PID, not name, is the correct, already-available
discriminator.

New functions in `src/search/browser.py` (deliberately NOT imported from `chromium_process.py` —
the identity mechanism is structurally different between the two lanes, matching this codebase's
existing precedent of duplicating small lane-specific OS-interaction primitives rather than forcing
a shared abstraction across `src/search/` and `src/scraper/`):

- `_get_frontmost_pid()` / `_activate_pid(pid)` — System Events by `unix id`, not by name.
- `_focus_steal_watchdog_by_pid(owned_pids, last_other_pid)` — same reclaim-loop shape as the
  scrape lane's watchdog, compares/reactivates by PID.

**Verified live, before wiring anything, at Main's explicit request:** `tell application "System
Events" to set frontmost of (first process whose unix id is <pid>) to true` really does reactivate
the exact target process by PID (tested against Finder's own pid, confirmed via a before/after
`get name of first application process whose frontmost is true` read). This half of the mechanism
— the reactivation direction — was the one Main flagged as unverified and worth confirming before
building the loop around it.

## A real bug found during live verification (not caught by unit tests)

First implementation captured the watchdog's own "known-good app to restore" anchor INSIDE
`_focus_steal_watchdog_by_pid`'s own first line (`last_other_pid = await
asyncio.to_thread(_get_frontmost_pid)`, executed once when the watchdog coroutine starts running).
Unit tests (mocked `_get_frontmost_pid`) all passed. A live instrumented probe (traced
`_activate_pid`, external frontmost-app poller at 0.05-0.2s resolution, three separate real
`search_web` runs against the actual worktree venv) caught what the mocks could not:

- Run A: ~0.9s of sustained "Google Chrome" frontmost, ZERO `_activate_pid` calls logged — the
  steal self-resolved on its own, the watchdog never acted.
- Run B: ~2.56s of sustained "Google Chrome" frontmost across what was almost certainly several
  engines' `new_tab()` calls firing close together during `asyncio.gather` fanout, again ZERO
  `_activate_pid` calls.

Root cause, confirmed by adding a `SPAWN_WATCHDOG` trace print: `_spawn_focus_watchdog` (and
therefore the watchdog's own first `_get_frontmost_pid()` read) only runs AFTER `_record_own_pids`
— i.e. AFTER Chrome has finished launching, which is exactly the moment Chrome is likeliest to
still be the frontmost window from its OWN launch. When that happens, the watchdog's self-captured
`last_other_pid` is itself an OWNED pid. The reclaim condition (`last_other_pid is not None and
last_other_pid not in owned_pids`) is then permanently false — reclaim stays disabled — until
Chrome happens to cede focus back to some other app on its own via the loop's `else` branch, which
during a fast multi-engine fanout with several `new_tab()` calls in quick succession may not happen
for seconds. This is a data race between "when Chrome first becomes frontmost from its own launch"
and "when the watchdog's own first read runs" that no mock-based unit test surfaced, because every
existing test injects a deterministic, hand-written PID sequence rather than exercising real OS
timing.

**Fix:** the anchor is now captured by `get_tab()` itself — `anchor_pid = _get_frontmost_pid()`,
placed right after `_reap_session_profile()` and BEFORE `Chrome(options)`/`_browser.start()` — the
one point in the whole launch sequence that structurally cannot race the launch, since it runs
before Chrome is asked to start at all. `anchor_pid` is threaded through
`_spawn_focus_watchdog(pids, anchor_pid)` into `_focus_steal_watchdog_by_pid(owned_pids,
last_other_pid)` as a required parameter; the watchdog no longer performs its own initial read.

Regression-guarded by `test_focus_steal_watchdog_by_pid_reclaims_immediately_when_already_stolen_at_start`
(`dev/tests/test_browser.py`) — an owned pid frontmost on the very FIRST loop iteration still
reclaims immediately, given a valid externally-supplied anchor; this is precisely the scenario the
old self-capturing version got wrong.

## Post-fix live verification

Same instrumented-probe methodology, three fresh `search_web` runs against the fixed code:

- Run 1: steal window ~0.45s (3 polls at 0.05s), one `_activate_pid` call, reclaimed cleanly.
- Run 2: steal window ~0.65-0.9s, one `_activate_pid` call.
- Run 3: steal window ~0.78s, one `_activate_pid` call (confirmed via `SPAWN_WATCHDOG`/`ACTIVATE`
  trace timestamps that the reclaim call's timing brackets the observed frontmost-app flip back).

Every run now shows an explicit reclaim (not a lucky self-resolution) and a flicker bounded to
under ~1s — consistent with `FOCUS_STEAL_POLL_INTERVAL_S=0.25s` plus real `osascript` subprocess
round-trip overhead (~100-200ms per call), the same "bounded flicker, not elimination" guarantee
`process-docs/browser_posture/2026-09-07_chromium_lane_focus_steal_watchdog.md` already documents
for the scrape lane's identical mechanism. No unbounded/permanent steal was observed in any
post-fix run — a sharp contrast to both the original user-reported bug (no watchdog at all, so a
steal would never self-correct) and the intermediate broken version above (watchdog present but
silently disabled by the anchor race).

Not independently reproduced: a live scenario with the user's own SEPARATE Chrome window actually
open and deliberately focused during a `search_web` run. This was reasoned through and covered by
`test_focus_steal_watchdog_by_pid_ignores_non_owned_frontmost_pid`, but not observed against a real
second Chrome instance live. Flagged here as a hypothesis-backed guarantee (PID-set membership is
unambiguous by construction — the two processes' pgrep patterns cannot overlap), not a live-
observed one, per the process-docs convention of keeping unobserved edge cases explicitly labeled.

## Where things stand

`close_browser()` cancels the focus watchdog task as its first, unconditional action (before
`_browser.stop()`), not only inside `kill_own_chrome()`'s teardown — necessary because 40+
`dev/search_pipeline/*.py` probes call `close_browser()` directly, bypassing `kill_own_chrome()`
entirely (confirmed by grep, and separately confirmed by Main before the go-ahead). Without this,
every one of those direct callers would leak a live watchdog task polling `osascript` in the
background after the browser itself was gone.

`dev/tests/test_browser.py` grew from 20 to 25 tests, all in the existing file — no new test file
was created, per the "one file per fix, not a new file per fix" convention. The two `get_tab()`
ordering tests now also assert the anchor-capture step and its propagation into
`_spawn_focus_watchdog`; new tests cover `_get_frontmost_pid`/`_activate_pid`'s own subprocess
wrapping and the watchdog's three PID-membership branches (ignore, reclaim,
reclaim-when-already-stolen-at-start — the regression guard for the anchor-race bug above). Full
`dev/tests/` suite: 376 passed immediately after the first PID-keyed implementation pass (before
the anchor-capture bug was found via live probing and fixed); 377 passed after the fix and its
regression test were added — no other file in the suite needed a change, confirming the callers
identified via the DOCS.md map (`cli.py`, `search_web.py`, `engines/`, the 40+ dev-script direct
callers of `close_browser`/`new_tab`) still behave as before.

## Recap — 2026-09-15, same day, review round

Main reviewed the implementation commit above (`380d534`) and reran the suite independently (377
green, confirmed). Accepted as correct: PID keying, the anchor capture in `get_tab()` before
launch, `close_browser()` as the cancellation chokepoint, and the live-caught anchor-race bug.
Three follow-ups, all addressed in commit `22b98fa`:

**1. `src/search/DOCS.md` format violation.** The three new Gotchas this milestone added carried
measured numbers (`~0.45s`/`~0.9s`/`~2.6s` flicker durations, `FOCUS_STEAL_POLL_INTERVAL_S=0.25s`,
subprocess round-trip estimates) and a specific test-function-name citation — DOCS.md is supposed
to answer "where does what live", not repeat measurements or cite specific tests by name; those
belong in process-docs (this file already had them, in better context). Trimmed all three Gotchas
down to the constraining statement only, with a pointer to `process-docs/browser_posture/` for the
evidence. Lesson for next time touching a module's DOCS.md after a live-verification-heavy
milestone: draft the Gotcha, then re-read it asking "would this survive if I deleted every number
and every test name from it" — if not, the number/name belongs in process-docs, not DOCS.md, even
when it feels like exactly the kind of fact a Gotcha is FOR (it's the evidence for the fact, not
the fact's own shape, that has to leave).

**2. Test file comment bloat.** `dev/tests/test_browser.py` had grown a 7-line prose comment above
the watchdog tests retelling the same anchor-race story already told in DOCS.md and process-docs —
a third copy of the same narrative, in a place (a test file, where every other section marker in
the file is a single line) that doesn't need it. Collapsed to one line, matching the file's own
existing convention (compare the `_get_frontmost_pid`/`_activate_pid` section marker a few lines
above it).

**3. A genuine open question, deliberately left unguarded.** Main asked, without instructing a fix:
when `_get_frontmost_pid()` returns `None` (osascript failure or unparseable stdout), the watchdog
loop's `else` branch does `last_other_pid = None`, unconditionally — including when `None` isn't a
"real" observation at all, just a failed read. If a genuine steal is in progress on the VERY NEXT
tick, the reclaim guard (`last_other_pid is not None and ...`) is false, and reclaim is skipped —
structurally the exact same "poisoned anchor" failure class as the bug this milestone already fixed
(a bad value landing in `last_other_pid`, un-correctable until a tick observes a genuine non-owned,
non-`None` pid, which cannot happen while Chrome keeps holding focus). This is real and reachable.

What makes it different from the anchor-race bug, and why I left it unguarded: the anchor-race bug
was a near-guaranteed, ROUTINE timing collision — the watchdog's first read structurally tends to
land while Chrome is still frontmost from its own launch, and I hit it on roughly half of ~6 live
runs without trying to provoke it. A `None` return requires an ACTUAL `osascript`/System Events
failure (permission revocation, System Events unresponsive, a transient subprocess spawn failure) —
a materially rarer trigger class. Across this whole session's live verification (roughly 150+ real
`osascript` calls across ~6 full `search_web` runs plus the standalone Finder-reactivation check
before implementation even started) I never once observed a failure or unparseable stdout from
`_get_frontmost_pid`/`_activate_pid`. Per this project's standing rule that a guard needs a real
observed failure behind it, not a hypothetical, I did not add one. If a future agent ever catches
this live (a probe or a user report showing a sustained multi-second steal with a bare/failed
osascript read in the trace right before it), the fix is narrow and already known: only let the
`else` branch overwrite `last_other_pid` when `current_pid is not None` — a transient read failure
should never be allowed to clobber a known-good anchor. Do not add this guard pre-emptively; wait
for the observation, per the same standard the anchor-race fix itself was held to (it shipped only
after a live probe caught it, not from review alone).

No test was added for this — nothing to regress against without triggering the untested branch,
and the instruction was explicitly not to guard speculatively.
