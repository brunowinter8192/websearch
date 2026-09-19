# The search lane's persistent profile gets rate-limited by Brave; switched to fresh-per-run (2026-09-19)

## What the owner measured, before any code changed

`src/search/browser.py`'s `SESSION_DIR` pinned the search lane to one persistent profile directory,
`~/.websearch/browser-session-selflaunch`, reused by every run since the M2 no-Spaces-drag
milestone (`2026-09-17_search_lane_no_spaces_drag.md`, this same area). That directory had grown
to 297 MB.

Three runs back to back, same query, same minute, same address: with the grown profile, Brave
returned 0 results (`document_status_chain: [429]`, `pow_link: true`, title `"Brave Search"`).
With the directory moved aside so Chrome built an empty one, Brave returned 10 results,
`document_status_chain: [200]`. Grown profile restored: 0 again. A plain visible browser on a
fresh profile, same URL, same minute, got a full page of results by hand. The block tracks the
profile directory, not the address and not the query. The profile's cookie store holds zero
entries for any Brave domain — whatever carries the mark is not a cookie, not chased further.

Decision, made by the owner, not re-derived here: the search lane gets a fresh profile per run.

## Why `_clear_stale_devtools_port()` is gone, not just unused

It existed for exactly one reason, recorded in `2026-09-15_dev_wide_browser_launch_helper.md` in
this same area: *"The scrape lane uses a fresh `tempfile.mkdtemp()` per scrape, so a leftover
`DevToolsActivePort` file from a prior run is structurally impossible there. This module reuses
one persistent `SESSION_DIR` across every run, so a crashed prior Chrome can leave a stale file
behind."* The function deleted that stale file before every launch so the port-wait loop could
only ever read a freshly-written port, never a dead one left over from whatever crashed last time
on the SAME directory.

Once every run gets its own uniquely-named `tempfile.mkdtemp()` directory, "a prior run's stale
file sitting in THIS run's directory" stops being a describable event — this run's directory did
not exist yet when any prior file could have been written to it. The precondition the function
existed to guard against is gone by construction, the same way the scrape lane never needed the
guard in the first place. This is not "removed because it's dead code now" — it is "removed
because the fact it protected against can no longer occur," and the distinction is why this entry
spells it out rather than just noting a deletion in a diff.

## Design

**`SESSION_DIR_PREFIX = "websearch-browser-session-"`** replaces the fixed `SESSION_DIR` constant.
`tempfile.mkdtemp(prefix=SESSION_DIR_PREFIX)` (default location, no `dir=` — matches
`chromium_process.py`'s `tempfile.mkdtemp(prefix="scrape-url-cdp-")` exactly, not `~/.websearch/`)
creates one fresh directory per `get_tab()` launch, held in a new module global `_session_dir`
alongside the existing `_browser`/`_lock_handle`/`_owned_pids` run-scoped state.

**`LOCK_PATH` goes back to being a fixed, independent constant**: `Path.home() / ".websearch" /
"browser-session.lock"`. It was deliberately derived from `SESSION_DIR`'s own name on 2026-09-17
(`2026-09-17_search_lane_no_spaces_drag.md`, this same area) specifically so the lock file could
not silently drift out of sync if the profile directory was ever renamed again — reasonable when
renames are rare, wrong once the directory changes on every single run: deriving the lock name the
same way now would give every run a DIFFERENT lock file, and two concurrent `websearch` invocations
would never see each other's lock at all, silently defeating the one thing the lock exists for.
Reverting the derivation is not an oversight in the 2026-09-17 entry — it was the right call for
the problem that milestone had, and stopped being the right call the moment the thing it derived
from stopped being stable.

**Reap broadened to prefix-matching, not one exact path**, mirroring `chromium_process.py`'s own
`_pids_matching_scrape_profiles`/`_reap_orphaned_scrapes` shape — deliberately not copied
verbatim, since browser.py has a cross-process lock the scrape lane does not:
- `_pids_matching_session_profiles()`: `pgrep -f "user-data-dir=.*{SESSION_DIR_PREFIX}"` — catches
  Chrome from ANY leftover run's directory.
- `_remove_orphaned_session_dirs()`: globs `{tempdir}/{SESSION_DIR_PREFIX}*` and removes every
  match, unconditionally.
- `_reap_session_profile()`: kills whatever `_pids_matching_session_profiles()` finds, then always
  calls `_remove_orphaned_session_dirs()` — no age check. The scrape lane needs one
  (`TOTAL_SCRAPE_BUDGET_S`) because it has no lock and cannot otherwise tell "still legitimately
  running" apart from "stuck". This module's `_reap_session_profile()` only ever runs as
  `browser_lock`'s `on_stale` callback (the lock has ALREADY decided the prior holder exceeded its
  budget) or immediately after THIS process cleanly acquires a free lock (which means, by
  construction, no other process can be legitimately mid-run right now) — either way, anything
  found at that point is an orphan, not a slow-but-alive peer. An age check here would duplicate a
  guarantee the lock already provides.

**`death_pipe.spawn_watchdog(_owned_pids, cleanup_dir=_session_dir)`** — one parameter, already
present in `death_pipe.py`, already used by the scrape lane, never passed from this call site
before because there was never a per-run directory worth deleting. This is Net 2 (the crash
backstop) for the directory now, same mechanism, no changes to `death_pipe.py` itself needed.

**`kill_own_chrome()`** gained one step — `shutil.rmtree(_session_dir, ignore_errors=True)` between
the PID safety-net kill and the lock release — Net 1, the fast deterministic clean-exit path,
matching the scrape lane's own `finally: shutil.rmtree(user_data_dir, ...)`.

**`get_tab()`'s exception path** also removes its own partially-created directory before
re-raising, so a launch failure after `mkdtemp` but before Chrome comes up doesn't leak a tiny
directory on every failed attempt.

Three nets, same shape `src/search/DOCS.md` already documents for PID cleanup, now covering the
directory too: Net 1 fast/deterministic, Net 2 the crash backstop, Net 3 (`_reap_session_profile`,
run at the start of the NEXT `get_tab()`) the sweep that catches whatever the first two miss —
including the ~40 `dev/search_pipeline/*.py` scripts that call `close_browser()` directly and
bypass `kill_own_chrome()`'s teardown entirely (documented pre-existing fact, not touched): their
leftover directories get swept on the next real production `get_tab()` call, same as their leftover
PIDs already were before this milestone.

## The one hole in "the lock makes an age check redundant," on the record

The reasoning above holds for the ordinary case, and was accepted as such. It has exactly one gap,
named here rather than engineered around, per instruction: `browser_lock.acquire`'s stale-takeover
fires once a holder's lock sidecar is older than `LOCK_HARD_BUDGET_S` (81.0s) — REGARDLESS of
whether that holder is actually stuck or just a legitimately slow run that has not finished yet. If
a real run is still alive and still using its own `_session_dir` past that budget, the NEXT process
to time out waiting for the lock will call `_reap_session_profile()` as its `on_stale` callback,
kill that still-running process's Chrome, AND remove its still-in-use directory out from under it.

This is not a new failure mode this milestone introduces. The exact same takeover already kills
that run's Chrome processes today, before this change, on the persistent directory — a slow run
was always at risk of being killed by a takeover once it crossed 81 seconds. What changes is only
the SHAPE of the collateral damage: before, the killed run's Chrome pointed at a directory that
would still be sitting there afterward, inspectable; after, the directory it was using disappears
in the same sweep. Recorded here because the failure would present as a search that simply dies for
no visible reason around the 81-second mark, and whoever hits it next should be able to find this
paragraph instead of re-deriving the mechanism from a stack trace.

## Startup cost — measured, not assumed

The worry: a profile built from nothing on every run costs real wall time even though it sits
outside any per-engine watchdog. Measured directly, `cli.py search_web "<query>"`, wall clock via
`date +%s.%N` around the whole process, 5 runs each side, distinct ordinary queries per run (avoids
the 1h disk cache short-circuiting the browser launch entirely), same machine, same session,
minutes apart:

| | n | mean | min | max |
|---|---|---|---|---|
| BEFORE (persistent profile, `git stash` back to pre-milestone `browser.py`) | 5 | 5.29s | 4.71s | 6.01s |
| AFTER (fresh profile per run) | 5 | 5.27s | 4.52s | 6.09s |

Mean delta: −0.02s. No measurable cost. Plausible reading, not confirmed further: the persistent
profile had grown to 297 MB of history/cache/extension state that Chrome itself has to read on
open, which may be costing close to what a from-scratch profile build costs — the two effects
could be landing in the same place by coincidence of THIS profile's size, not because building a
profile is free in general. Five runs a side is enough to say "no cost showed up here", not enough
to rule out a cost appearing on a much larger persistent profile than this one ever reached, or to
explain why the numbers came out this close. Also confirmed on disk: `~/.websearch/browser-session-
selflaunch` untouched (67 MB at time of writing — smaller than the 297 MB the owner measured,
already accounted for by the owner's own aside/restore during the original measurement, not
touched by this session in either direction), and zero `websearch-browser-session-*` directories
left in the system temp dir after any of the 5 AFTER runs — Net 1 confirmed working on real exits,
not just in the mocked test suite.

## Per-engine yield, before vs. after, same 10 runs

Not a repeat of the 141-run baseline table in `2026-09-17_search_lane_no_spaces_drag.md` — that
table predates this session's own `marker_reflection` area fixes to `brave.py`/`yandex.py`
(query-reflection false blocks, the button-challenge solve), so a direct comparison against it
would conflate "did the profile change matter" with "did this session's other fixes matter". The
BEFORE/AFTER split above already isolates the profile variable alone, same code on both sides,
same session, so its own `workflow_summary` records are the fairer comparison:

| Engine | BEFORE (persistent, 5 runs) | AFTER (fresh, 5 runs) |
|---|---|---|
| bing | 5/5 | 4/5 |
| brave | 5/5 | 5/5 |
| duckduckgo | 4/5 | 5/5 |
| google | 5/5 | 5/5 |
| mojeek | 4/5 | 3/5 |
| openalex | 5/5 | 5/5 |
| startpage | 5/5 | 5/5 |
| yandex | 2/5 | 1/5 |

Five runs a side cannot restate a percentage measured over 141, and this is not offered as one.
What it shows: nothing collapsed. Google (the engine most exposed to a cold-profile consent wall)
stayed 5/5 both sides, consistent with `2026-09-18_no_spaces_drag_verified_and_m2_dropped.md`'s
own finding that the expected consent-wall cost never materialized when this profile was made
persistent-but-separate in the first place. yandex stayed the weakest engine on both sides, which
matches its long-standing block-proneness independent of profile handling, not a new effect. The
small swings on bing/duckduckgo/mojeek (one run's difference each) sit inside what 5-run noise
already looks like elsewhere in this project's own measurements (see the 2026-09-18 entry's own
"three runs is far too small a sample" framing) — not read as a regression.

## Tests

`dev/tests/test_browser.py` and `dev/tests/test_browser_get_tab.py` (both extended, not replaced),
plus one line in `dev/tests/_browser_fakes.py`'s shared `_reset_state` (`_session_dir` added to the
per-test reset). `tempfile.mkdtemp` itself runs for real in every test that touches it — confirmed
this is the established precedent before relying on it: `test_chromium_scrape_facts.py` already
lets the scrape lane's identically-shaped `tempfile.mkdtemp(prefix="scrape-url-cdp-")` run for real
rather than mocking it, on the reasoning that a throwaway empty directory is cheap enough not to be
worth mocking. Covered: two `get_tab()` calls in sequence produce two different directories, both
prefix-matching; the same two calls see `browser_lock.acquire` receive the identical `LOCK_PATH`
both times, plus a standalone pure-constant assertion on `LOCK_PATH`'s fixed value;
`_remove_orphaned_session_dirs`/`_reap_session_profile` genuinely delete a real leftover directory
and genuinely leave an unrelated-prefix directory alone; `get_tab()`'s exception path removes its
own partial directory; `kill_own_chrome()`'s two existing teardown tests extended to assert the
session directory is gone from disk and the global reset. Full suite: 443 -> 451 passed (8 net new
tests; no existing test removed, several extended in place rather than replaced).

## What was deliberately not touched

`browser_lock.py` — already took `lock_path` as a parameter, no Chrome/SESSION_DIR knowledge per
its own module entry, nothing to change. `death_pipe.py` — `cleanup_dir` already existed as an
optional parameter, unused from this call site until now; no change to the module itself. The ~40
`dev/search_pipeline/*.py` scripts and `dev/browser_posture/*.py`/`dev/access_recovery/_browser.py`
that define their own independent, differently-named `SESSION_DIR` locals — grepped repo-wide
before touching anything; confirmed none of them import `browser.SESSION_DIR` (only
`dev/tests/test_browser_get_tab.py` did, and that is fixed above) — untouched, out of scope, same
standing precedent `2026-09-17_search_lane_no_spaces_drag.md` already recorded for this exact
class of script. `~/.websearch/browser-session-selflaunch` and its `.marked-*` sibling: never read
from, never written to, by any code path this milestone touches — confirmed by construction, not
just by not looking.

## Recap pass

`git diff integration --name-only` inventoried exactly the files this milestone touched — `src/
search/browser.py`, `dev/tests/test_browser.py`/`test_browser_get_tab.py`/`_browser_fakes.py`,
`src/search/DOCS.md`, `dev/tests/DOCS.md`, and this entry. Both `DOCS.md` files were already
updated during implementation, not left for the recap pass; re-checked every touched module's
`wc -l` against its own DOCS.md heading rather than trusting the earlier count still held. One
drift found: `dev/tests/_browser_fakes.py` grew from 22 to 23 lines (the `_session_dir` reset line
added to `_reset_state`) and its DOCS.md heading had not been re-measured after that edit —
corrected. `src/search/browser.py` (301), `dev/tests/test_browser.py` (386), and `dev/tests/
test_browser_get_tab.py` (225) all already matched their DOCS.md headings exactly.
