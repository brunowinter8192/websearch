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

## `--no-startup-window` on the search lane — 2026-09-15, same day, third round

Same worker session. Milestone: the scrape lane never flickers ("der scrape ist perfekt im
background", user's own words); the search lane still does — Main measured 2 focus steals per
`search_web` run (0.5s, 1.03s) on integration, both reclaimed but visible. Both lanes use `open -g
-n` and both now have a watchdog. Main found the difference by reading both launch commands
side-by-side: the scrape lane's `_self_launch_chrome` (`src/scraper/chromium_process.py`) passes
`--no-startup-window`; the search lane's `_open_background_process_creator`
(`src/search/browser.py`) does not. `--no-startup-window` means Chrome opens zero windows at
launch — no window-creation event for the OS to activate at all, not merely a reclaim after one.

**Change shipped:** one line, `options.add_argument("--no-startup-window")` in `build_options()`
(`src/search/browser.py`). Nothing else in the launch path, the watchdog, PID keying, or teardown
touched.

**Whether pydoll already sets it or rejects it as a duplicate — checked in the installed package,
not assumed:** `venv/lib/python3.14/site-packages/pydoll/browser/managers/
browser_options_manager.py::add_default_arguments()` already calls `self.options.add_argument
('--no-first-run')` and `('--no-default-browser-check')` unconditionally during
`Chrome.start()` — this is exactly why Main hit `ArgumentAlreadyExistsInOptions` adding
`--no-first-run` by hand earlier tonight; pydoll already owns that flag. Grepped the same file and
the rest of `pydoll/browser/` for `no-startup-window`/`no_startup_window`: zero matches anywhere in
the installed package. Safe to add — confirmed by reading the actual installed source, not by
absence of an error in a run I'm not allowed to make.

**A structural risk found by reading `Chrome.start()`, not yet resolved, and not resolvable without
a live launch:** `pydoll/browser/chromium/base.py::start()` does `valid_tab_id = await
self._get_valid_tab_id(await self.get_targets())` immediately after the process comes up —
`_get_valid_tab_id` raises `NoValidTabFound` if `get_targets()` returns no `type == 'page'` entry.
This assumes Chrome already has an existing tab the moment `.start()` asks for one. The scrape lane
never hits this: it does not call `.start()` at all — it launches the process directly, waits for
the DevTools port file, then hands a `cdp_url` to crawl4ai/patchright's `connect_over_cdp` path,
which creates its OWN first page via `context.new_page()` (a fresh `Target.createTarget`) rather
than looking for one that's already there. `--no-startup-window` is safe for that pattern by
construction. Whether Chromium's CDP target list is truly empty of `page`-type entries under
`--no-startup-window` + `--remote-debugging-port` — and therefore whether pydoll's `.start()` will
raise `NoValidTabFound` on every single search — is NOT something I could establish by reading
alone, and I did not launch a browser to check it, per the standing rule for this milestone. If this
is wrong, the failure will not be silent or subtle: `get_tab()`'s own try/except will catch the
raised exception, reset `_browser`/`_tab`, release the lock, and re-raise — every engine's
`search_with_reason` would fail loudly and identically, not hang or degrade quietly. **If Main's
live run produces exactly that (an exception naming `NoValidTabFound`, or every engine failing
identically on the very first tab it tries to get), that is this mechanism, and the fix is reverting
the one `add_argument` line above — not a deeper investigation.** Did not attempt any workaround
(e.g. bypassing `.start()`'s own tab lookup and calling `new_tab()` manually instead, mirroring the
scrape lane's own explicit-create pattern more closely) — that is a materially bigger change than
one flag, was not asked for, and risks its own new bugs in a launch path three other things already
depend on (the watchdog's anchor capture, `_record_own_pids`, `death_pipe`).

**Second, separate difference — not touched, per explicit instruction:** the scrape lane launches a
dedicated, dynamically-resolved Chromium bundle; the search lane launches the user's real "Google
Chrome". Whether this also matters is Main's to decide after measuring `--no-startup-window` alone.

**Test:** `dev/tests/test_browser.py`, two new tests — `test_build_options_carries_no_startup_window_
flag` (`"--no-startup-window" in browser.build_options().arguments`, a pure function call, no
mocking needed) and `test_open_background_process_creator_forwards_no_startup_window_into_open_
command` (mocks `browser.subprocess.Popen`, captures the argv `_open_background_process_creator`
actually invokes, asserts the flag survives the `command[1:]` reslice into the final `open` argv —
the "launch command carries the flag" proof the milestone asked for). Neither test touches
`browser.Chrome`, so `dev/tests/conftest.py`'s launch-primitive tripwire does not fire for either.
Suite: 377 -> 379 passed (two new tests, nothing else changed count).

**Callers checked, via import-grep, not assumed:** `build_options`/`_open_background_process_creator`
are module-private to `src/search/browser.py` — grepped the whole repo for both names; the only call
site for either is `get_tab()` in the same file. No external caller imports them directly. Grepped
`from src.search.browser import` separately: `search_web.py` (`get_tab`, `kill_own_chrome`), all 6
browser engine files (`new_tab`, `kill_tab`), and 20+ `dev/search_pipeline/*.py` scripts (`new_tab`/
`close_browser` direct callers) — none of these call `build_options` themselves or inspect its
return value; they only reach it transitively through `get_tab()`, whose signature and return type
are unchanged. Their own code cannot observe this change except through whether the browser launches
at all (the one risk above, which is Main's live run to confirm or refute).

## REVERTED same day — the predicted failure happened exactly as predicted

Main ran one live `search_web` search against this change. All 7 engines returned 0. The log:
`No valid tab found among 0 targets`, then `Engine browser error: No valid attached tab found`,
once per engine. This is exactly the failure mode named in the section above before Main ran
anything — written down as a risk, now confirmed as the actual outcome, not a hypothesis anymore.

**Reverted:** `options.add_argument("--no-startup-window")` in `build_options()`
(`src/search/browser.py`), and the two tests that asserted on it
(`test_build_options_carries_no_startup_window_flag`,
`test_open_background_process_creator_forwards_no_startup_window_into_open_command`,
`dev/tests/test_browser.py`) — reverted via `git checkout <pre-change-commit> --
src/search/browser.py dev/tests/test_browser.py dev/tests/DOCS.md src/search/DOCS.md`, restoring
all four files byte-for-byte to their state before the flag was added (LOC counts, Purpose prose,
everything). `dev/tests/`: 377 passed, back to the pre-change baseline. The dev-wide launch helper
milestone earlier in this same file (`dev/_lib/browser_launch.py` and everything documenting it) is
untouched by this revert — only the search-lane flag attempt and its direct evidence are undone.

**The finding, stated for whoever picks this up next, so nobody rediscovers it by hitting the same
wall:**

- The search lane flickers because Chrome creates a window at launch; the scrape lane does not,
  because it passes `--no-startup-window`.
- Adding that flag to the search lane ALONE does not work. The reason is not the flag itself — the
  flag does exactly what it says, Chrome opens with zero windows. The reason is that pydoll's
  `Chrome.start()` (`pydoll/browser/chromium/base.py`) requires an EXISTING page-type CDP target the
  instant it asks for one (`_get_valid_tab_id(await self.get_targets())`, raises `NoValidTabFound`
  otherwise) — and the search lane's whole `get_tab()` flow is built around calling `.start()` and
  taking whatever tab it hands back. The scrape lane never calls `.start()` at all: it self-launches
  the process directly, waits for the DevTools port file to appear, then connects over CDP
  (`BrowserConfig(cdp_url=...)` + patchright's `connect_over_cdp`) and creates its OWN first page via
  `context.new_page()` — a fresh `Target.createTarget`, not a lookup for one already there. Starting
  with zero windows is only survivable if whatever attaches next creates its own first target instead
  of expecting to find one.
- **Closing this properly means the search lane adopting the scrape lane's whole launch shape, not
  one flag: self-launch the process directly (not `Chrome(options).start()`), wait for the devtools
  port file, connect over CDP, create the first page itself.** That is a real rework of `get_tab()`'s
  launch sequence — it has to thread through the anchor-pid capture (currently taken right before
  `Chrome(options)`/`.start()`), `_record_own_pids`, and `death_pipe.spawn_watchdog`, all of which
  currently assume `.start()`'s return value is the first tab. Whether pydoll exposes a lower-level
  "attach to an already-running CDP endpoint and create your own tab" path (something closer to its
  own `connect(ws_address)` method, which itself currently does `tabs = await
  self.get_opened_tabs(); return tabs[0]` — same "assumes an existing tab" shape, not checked in
  detail this session) or whether the search lane needs to drop pydoll's `Chrome` class for its own
  launch step entirely, the way the scrape lane dropped patchright's own `launch()` in favor of
  self-launch-plus-connect, is the open question for whoever does this next.
- **Measured evidence, both Main's, both 2026-09-15:** on the CURRENT (flag-less) integration state,
  the search lane steals focus twice per `search_web` run, 0.5s and 1.03s, each reclaimed by the
  existing PID-keyed watchdog. With `--no-startup-window` added alone, zero engines return results
  (`No valid tab found among 0 targets` / `No valid attached tab found`, all 7 engines, one live run).

This is unfinished work with the cause identified, not a failed attempt to be forgotten. The watchdog
already bounds every steal to close to a second, so the search lane is not broken today — it is
exactly as good as it was before this sub-milestone, flickering but recoverable. The next step is
the launch-shape rework above, not another attempt at threading the single flag through pydoll's
`.start()`.

## The full rework — 2026-09-15, same day, fourth round: search lane adopts the scrape lane's shape

Same worker session. This is the launch-shape rework the section above named as the actual fix.
`get_tab()` (`src/search/browser.py`) no longer calls `Chrome.start()` or `Chrome.connect()` at all.

**Three things this needed that weren't obvious from the two source files alone, each verified by
reading the installed pydoll source, not assumed:**

1. **No `connect()` call is needed.** `ConnectionHandler.execute_command()` resolves its own
   WebSocket address lazily, on first use, via `get_browser_ws_address(port)`
   (`pydoll/utils/general.py`) — a plain `GET http://localhost:{port}/json/version`, a browser-level
   HTTP endpoint Chrome serves with zero tabs open. So the "connect" step is just: get the right port
   into the `Browser` instance, and let the first real CDP call do the rest. `Chrome.connect()`
   itself was checked and confirmed broken the same way `.start()` was (`tabs = await
   self.get_opened_tabs(); return tabs[0]` — `IndexError` on an empty list) and is not called
   anywhere in the new code.
2. **`Chrome.start()`'s `_setup_user_dir()` is the ONLY place `block_popups`/`block_notifications`/
   `browser_preferences` reach disk.** These are not CLI arguments — `ChromiumOptions.block_popups`
   etc. write into an in-memory `_browser_preferences` dict, and `_setup_user_dir()` is what
   serializes that dict into `<user-data-dir>/Default/Preferences` before Chrome reads its profile.
   Skipping `.start()` without also calling `_setup_user_dir()` would have silently dropped these —
   a real behavior change wearing a "just a launch mechanism change" disguise. `get_tab()` now calls
   `_browser._setup_user_dir()` directly, before self-launching.
3. **A stale-`DevToolsActivePort`-file race the scrape lane cannot have.** The scrape lane uses a
   fresh `tempfile.mkdtemp()` per scrape, so no prior file can ever be sitting there. This module
   reuses one persistent `SESSION_DIR` across every run — a crashed prior Chrome can leave the file
   behind, and the new port-wait loop could read that stale, dead port on its very first poll instead
   of waiting for the new one. Fixed by unlinking the file (`_clear_stale_devtools_port()`) right
   after `_reap_session_profile()`, before every launch.

**The new sequence in `get_tab()`:** lock -> reap stale processes -> clear stale devtools-port file
-> capture the focus anchor (unchanged position, before anything launches) -> `Chrome(options)`
(construction alone already runs pydoll's own `--no-first-run`/`--no-default-browser-check`
defaulting, confirmed by reading `ChromiumOptionsManager.add_default_arguments()` — this is why
`--no-first-run` collided when added by hand in the reverted attempt) -> `_setup_user_dir()` ->
self-launch via the existing `_open_background_process_creator` with `--remote-debugging-port=0`
(OS-assigned, matching the scrape lane, not a guessed port) -> wait for `DevToolsActivePort` -> patch
`_browser._connection_port`/`_browser._connection_handler` to the real, now-known port (both needed:
`_connection_port` feeds every future `Tab`'s own kwargs via `_get_tab_kwargs`, `_connection_handler`
is what browser-level commands go through) -> record own PIDs -> spawn `death_pipe` watchdog -> spawn
the focus watchdog. No tab is created during any of this.

**`_tab` is gone, not left as a `None` vestige.** Checked every consumer via grep before deciding:
`get_tab()`'s return value was discarded by both its only two callers
(`search_web.py::_prewarm_browser`, `browser.py::new_tab` itself) and by nothing else in `src/` or
`dev/`. Every engine already creates its own tab via `new_tab()` -> `_browser.new_tab()`, which
issues `TargetCommands.create_target` directly with no dependency on a pre-existing tab (confirmed by
reading pydoll's `new_tab()` — this is exactly why engines were never affected by any of this). The
module global, its two reset sites (`close_browser()`, `kill_own_chrome()`'s except-branch), and
`get_tab()`'s `return _tab` are all removed; `get_tab()` now returns `None` implicitly, matching what
every caller already assumed.

**Deliberately not replicated, and said once so it isn't rediscovered as a mystery:** `.start()`'s
proxy-credential configuration (`_configure_proxy`) and `--user-agent=` override plumbing
(`_apply_user_agent_override`/`_setup_worker_user_agent_override`) are not called anywhere in the new
sequence. `build_options()` sets neither a `--proxy-server=` nor a `--user-agent=` argument today, so
both are dead code paths regardless of launch mechanism — this is a no-op gap, not an observed
regression. Whoever adds proxy or UA-override support later needs to wire the equivalent calls into
`get_tab()` explicitly; they will not come back "for free" by touching `build_options()` alone the way
`webrtc_leak_protection`/`BACKGROUNDING_FLAGS` do. Documented in `src/search/DOCS.md`'s Gotchas too.

**`--remote-debugging-port=0` reaching the actual `open` command, confirmed by reading, not trusted:**
`BrowserProcessManager.start_browser_process(binary_location, port, arguments)` builds `command =
[binary_location, f'--remote-debugging-port={port}', *arguments]` and hands the whole list to
`_process_creator`. `_open_background_process_creator` does `args = command[1:]` — slices off only
`command[0]` (the resolved binary path, unused since `open -a "Google Chrome"` targets the bundle by
name) — so `--remote-debugging-port=0` and the rest of `arguments` both survive into the final `open
... --args` list unchanged. Verified against the actual `start_browser_process` source before relying
on it, per the specific instruction to check this rather than trust that passing `0` was enough.

**Tests:** `dev/tests/test_browser.py`'s three `get_tab()` tests were rewritten, not patched, per
instruction. `FakeChrome` lost its `.start()`/`"fake-tab"` shape and gained `_setup_user_dir()`
(flag-setting) and `_get_default_binary_location()` stand-ins; a new `FakeProcessManager` records
`start_browser_process(binary_location, port, arguments)` calls instead of returning `None` (the old
`BrowserProcessManager` mock, `lambda process_creator: None`, would have made the new code crash on
`_browser_process_manager.start_browser_process(...)` — caught before it became a real bug, not
after). `_wait_for_devtools_port` and `ConnectionHandler` are mocked at the module boundary in every
`get_tab()` test — no real filesystem polling or websocket construction. The ordering assertion
(`lock -> reap -> anchor -> launch -> record -> watchdog -> focus_watchdog`) is kept exactly as it
was, per instruction; it turned out the pre-existing `dev/tests/DOCS.md` prose for this test already
had "launch" and "anchor-capture" in the wrong order relative to the actual code (a pre-existing doc
drift, not something this session introduced) — corrected while touching that line anyway. One new
test added (`test_get_tab_self_launches_with_port_zero_and_forwards_arguments`) asserting the port-0
and `--no-startup-window` claims above directly against `FakeProcessManager.start_calls`, not just
against `build_options()` in isolation. Suite: 377 -> 378 (one net new test; the three rewrites
replace their old bodies in place).

**Callers checked, via import-grep, not assumed:** grepped `from src.search.browser import` across
the whole repo — `search_web.py` (`get_tab`, `kill_own_chrome`), all 6 browser engine files
(`new_tab`, `kill_tab`), 20+ `dev/search_pipeline/*.py` scripts (`new_tab`/`close_browser` direct
callers), and `dev/tests/conftest.py` (imports the module itself to patch `browser.Chrome`, still the
same patch point, still fires the same way — confirmed by the suite staying green). None of these
call `build_options`, `get_tab`'s removed internals, or read `get_tab()`'s return value — every one
of them reaches this only through `get_tab()`/`new_tab()`/`kill_tab()`/`close_browser()`, whose
external signatures are unchanged.

**What I could not verify, and what remains outstanding:** whether this actually launches, whether
all 7 engines return results, and whether the flicker is gone or merely reduced. I did not launch a
browser at any point in this milestone, per the standing rule. That live run, and the frontmost-app
measurement around it, is Main's to produce next.

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
