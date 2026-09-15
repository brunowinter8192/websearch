# dev-wide backgrounded-browser launch helper — 2026-09-15

Worker session (worktree `devbrowser`). Milestone: give `dev/` one shared helper for launching a
browser that never steals focus, after a probe caused the exact steal this line of work already
fixed in production earlier the same day.

## The failure, stated plainly

`dev/access_recovery/01_google_dom_probe.py` launched Chrome with macOS `open -g -n` — the same
mechanism production uses, applied correctly. Chrome windows still jumped to the foreground and
took focus away from the user, repeatedly, across several runs. `open -g` only suppresses
activation at the LAUNCH MOMENT (playwright#42343). Every window created after that moment —
every `new_tab()` call is a separate CDP `Target.createTarget` window-creation event — can still
auto-activate the app regardless of `-g`. Production's search lane hit this same bug earlier the
same day and fixed it with a background watchdog that reclaims focus
(`process-docs/browser_posture/2026-09-15_search_lane_focus_steal_watchdog.md`). Dev scripts never
got that fix, because they deliberately do not import from `src/` (dev-script isolation), and
`dev/browser_posture/_lib.py` — the closest existing dev launch helper — only ever grew a
frontmost-app READER (`get_frontmost_app()`), never a reclaimer.

## Why this wasn't just "copy `_lib.py`'s launch code again"

Grepping `dev/` for `open -g`/`open -gna` launch strings found roughly a dozen scripts that each
rolled their own launch, independently, across `dev/browser_posture/`, `dev/search_pipeline/`,
`dev/news_pipeline/`, `dev/lane_choice/` — every one of those authors also had
`dev/browser_posture/_lib.py` available (or its own area's equivalent) and did not reach for it,
because it is area-scoped: `dev/search_pipeline/*.py` reaches its own `_lib/` only because Python
auto-adds the running script's own directory to `sys.path[0]`, which does not extend to any other
area. A helper nobody can reach from their own area is a helper nobody uses — the twelve scripts
are the proof, not a hypothesis.

## Location: `dev/_lib/browser_launch.py`, and how it's actually reachable

Verified concretely, not assumed, before writing any implementation: built a throwaway `/tmp`
sandbox (`dev/_lib/__init__.py` + a dummy module) and confirmed `sys.path.insert(0, repo_root)`
followed by `from dev._lib.mod import X` resolves correctly with NO `dev/__init__.py` present —
`dev/` resolves as a PEP 420 namespace package, `_lib/` as a regular package via its own
`__init__.py`. This is the same `REPO_ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0,
str(REPO_ROOT))` pattern already used in `dev/news_pipeline/scrape_isolation_smoke.py` and
`prod_scrape_smoke.py` to reach `src/` from any script's own directory — applied here to reach
`dev/_lib` instead. `dev/_lib/browser_launch.py` is therefore reachable from literally any area
under `dev/`, present and future, with the same three lines every time.

**Findability, not just reachability** — the mechanism above only helps an agent who already knows
`dev/_lib/browser_launch.py` exists. Three things point at it for an agent who doesn't:
- `dev/DOCS.md` (new — none existed before this session) is a short map, not a tour: one line per
  area plus a "Shared code" section naming `dev/_lib/` and saying to check there before writing a
  new area-local `_lib` or reimplementing an OS-level launch primitive.
- `dev/_lib/DOCS.md` (new) documents the module itself in standard DOCS.md format.
- `dev/browser_posture/DOCS.md` and `dev/search_pipeline/DOCS.md` (both edited) — the two areas
  whose scripts launch backgrounded Chrome today — got a Gotcha each, naming the specific script
  with no reclaim watchdog (`_lib.py`'s launch functions; `27_brave_headed_lane_probe.py`) and
  pointing any NEW headed-backgrounded launch in that area at the shared helper instead.

## The PID hazard, and how it's handled here

Same hazard `src/search/browser.py`'s watchdog already solved, reasoned through again because dev
probes hit the identical shape: `dev/access_recovery/01_google_dom_probe.py` (like the search lane,
unlike the scrape lane) launches the user's REAL `"Google Chrome"` bundle, bare name — not a
dedicated bundle. A name-keyed watchdog cannot tell the probe's own window apart from the user's own
separate Chrome window, and would yank focus away from the user's deliberate switch to it. Fixed the
same way production fixed it: `_pids_for_profile(profile)` (`pgrep -f user-data-dir=<profile>`)
fingerprints exactly this launch's own Chrome PIDs — the user's separate Chrome instance, on its own
profile, can never match that pattern — and the watchdog (`_focus_steal_watchdog_by_pid`) compares
the frontmost PID against that set, not against any app name.

`anchor_pid` (the "known-good app to restore" reference) is captured via `_get_frontmost_pid()`
BEFORE `Chrome(options)`/`browser.start()` runs, inside `launch_backgrounded_chrome()` — not inside
the watchdog coroutine's own first line. This was a real, live-caught bug in the search lane's first
implementation (see the 2026-09-15 search-lane entry above): capturing the anchor after launch races
the moment Chrome first becomes frontmost from its own launch, and can permanently disable reclaim.
Ported the fix, not just the mechanism — copying the watchdog's SHAPE without this specific ordering
would have reintroduced a bug that already cost a full session to find once.

## Design choice: a returned handle, not module globals

`src/search/browser.py` and `dev/browser_posture/_lib.py`'s probe scripts both hold browser state in
module-level globals (`_browser`, `_tab`, `_focus_watchdog_task`). `dev/_lib/browser_launch.py`
instead returns a `BackgroundedBrowser` dataclass (`browser`, `profile`, `owned_pids`,
`watchdog_task`) from `launch_backgrounded_chrome()`. Reasoning: this module is imported by many
separate dev scripts across many separate processes, each with exactly one browser lifecycle of its
own (confirmed: no dev script today launches two backgrounded Chrome instances concurrently in one
process) — a returned handle is simpler to reason about per-caller than a shared module global, and
the one existing production precedent (`src/search/browser.py`'s globals) exists because THAT module
is a long-lived singleton behind `get_tab()`, a shape this dev helper does not have.

## What was migrated, and what was deliberately not

Only `dev/access_recovery/01_google_dom_probe.py` — the script that caused tonight's focus-steal and
was unfinished anyway. Its own `_open_background_process_creator`, `_new_tab`'s inline
`Chrome(...)`/`BrowserProcessManager` wiring, `_kill_tab`'s CDP close, and `close_browser` are gone;
it now calls `launch_backgrounded_chrome(SESSION_DIR, options)` once (options still built by the
probe's own `_build_options()` — the probe's specific stealth-flag set is a measurement decision,
kept out of the shared helper on purpose), `close_tab(handle.browser, tab)` per navigation, and
`teardown(handle)` in its `finally`.

The other ~12 scripts using `open -g`/`open -gna` inline (`dev/browser_posture/{01,02,03,05}.py` +
`_lib.py`, `dev/search_pipeline/27_brave_headed_lane_probe.py`, several `dev/news_pipeline/*.py`,
`dev/lane_choice/{02,03}*.py`) were deliberately NOT touched — they work, they are not what broke,
and migrating a dozen working scripts onto a new helper in the same milestone that introduces it is
a separate decision nobody has made yet. `dev/browser_posture/DOCS.md`'s new Gotcha states this
explicitly so a future agent doesn't read the helper's existence as an implicit "and everything else
was migrated too."

## Live verification performed, and what's still outstanding

Ran the helper once, live, via a throwaway `/tmp` script (never staged): launched Chrome on an
isolated verify-only profile (`~/.websearch/devbrowser-verify-profile`), confirmed 9 owned PIDs
recorded and the watchdog task alive, opened a tab, navigated to `about:blank`, closed the tab,
tore down. Immediately after `teardown()`, `pgrep -f user-data-dir=<profile>` still showed one PID —
re-checked with `ps -p <pid>` a few seconds later and it was already gone (a transient artifact of
`pgrep` catching a process mid-termination, not a leak); a second `pgrep` pass and a `ps aux` grep
both came back empty. `dev/tests/` re-run after the change: 377 passed, unchanged (this milestone
touches no `src/`, so this was expected, not a close call).

**Not verified, and explicitly not mine to verify per this milestone's division of labor:** whether
the reclaim watchdog actually stops a real focus steal during a live, multi-navigation
`01_google_dom_probe.py` run. Judging that needs an external frontmost-app poll running alongside a
real probe run, watched by a human, matching exactly how the search-lane fix above was itself
verified live before being trusted. That run is explicitly the next step, not part of what shipped
in this entry.

## Main's live focus measurement, and a second finding it produced

Main ran the focus proof this entry left outstanding: the helper, driven from a throwaway `/tmp`
script against 5 real live Google navigations on an isolated profile, with an external `osascript`
poller sampling the frontmost app every 0.2s for the whole run. One run per variant — a clear
signal, not a large sample.

**RUN 1 — fresh tab per navigation (what `01_google_dom_probe.py` does today):** 84 samples, 6
non-ghostty (i.e. 6 samples where some other app briefly held frontmost). Four separate focus
steals, every one reclaimed: 0.70s, 0.68s, 0.38s, 0.35s. Watchdog behavior matches production's own
documented guarantee (`process-docs/browser_posture/2026-09-15_search_lane_focus_steal_watchdog.md`)
— every steal bounded, none stuck.

**RUN 2 — identical script, one change: a single tab created once and reused for all 5
navigations instead of `new_tab` per navigation:** 83 samples, 2 non-ghostty. ONE steal, at launch,
0.69s. Nothing for the remaining four navigations.

**Conclusion:** four steals vs. one, same helper, same pages, same pacing — the steals are not
caused by navigation, they are caused by TARGET CREATION. Every `new_tab()` call is a separate CDP
window-creation event, and playwright#42343 says each one can re-activate the app regardless of
`open -g`. The watchdog reclaims the symptom (bounds every steal to well under a second); not
creating the extra targets removes the cause outright — roughly three quarters of the steals in this
5-navigation run. Both are real, complementary findings, not competing ones: a script that both
reuses tabs where it safely can AND keeps the watchdog running gets fewer steals, each shorter.

## Is `01_google_dom_probe.py`'s fresh-tab-per-navigation load-bearing for its own measurement?

Checked before changing anything, per instruction. Answer: **yes, load-bearing — left alone.**

The reason is not primarily cookie isolation — `NetworkCommands.set_cookie` (the SOCS injection both
the probe and production call before every navigation) writes to the browser's shared cookie jar,
scoped to the profile, not the tab; a reused tab would see the same cookies a fresh tab does, since
they live in the same `user-data-dir`.

The real reason: `src/search/engines/google.py`'s `GoogleEngine.search_with_reason` — the exact
production code path this probe exists to reproduce — does `tab = await new_tab()` at the top of
every single search call and `await kill_tab(tab)` in its own `finally`, unconditionally, one fresh
tab per query, every time (confirmed by reading the method body, not assumed). This is not a probe-
specific design choice sitting on top of a shared browser session; it is the identical shape
production itself uses per search. `01_google_dom_probe.py`'s `run_navigation()` — `tab = await
_new_tab()` ... `finally: await _kill_tab(tab)`, called once per navigation — reproduces that shape
navigation-for-navigation (this probe runs 2 navigations per query, matching 2 separate
`search_with_reason` calls production would make for num=100 and num=10 if it ever varied `num`).

A reused tab across the probe's 20 navigations (10 queries x 2 num-variants) would stop measuring
what production's actual per-search tab lifecycle produces and start measuring an untested-in-
production code path instead. RUN 2 above already shows that reusing the tab measurably changes
browser-level behavior (focus steals, 4 vs. 1) even though nothing about the pages themselves
changed — proof that tab lifecycle is not a neutral harness detail here, and no reason to assume it
is neutral for the thing this probe actually measures (Google's DOM/selector behavior) either. A
reused tab also accumulates `sessionStorage` across navigations to the same origin, tab-scoped state
a fresh tab never carries — an unmeasured, plausible confound for a probe whose entire purpose is
telling a real DOM break apart from an artifact of the harness. The probe pays four flickers (now
bounded to well under a second each by the watchdog) for a clean, production-faithful measurement —
a fair trade. Not changed.
