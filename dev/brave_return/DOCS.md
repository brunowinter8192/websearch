# dev/brave_return/

## Role
Measurement tooling for the question of whether Brave's proof-of-work button challenge can be solved unattended from code, the way Mojeek's ALTCHA widget already is. Touch this to re-measure Brave's challenge behaviour. Nothing here is wired into `src/` directly — this package is never imported by production code — but its `brave_pydoll_probe_20260919_133706.md` report (the live run that finally reached a real challenge) is what `src/search/engines/brave.py`'s own challenge-solving mechanism was built and evidenced from; see that module's own entry in `src/search/engines/DOCS.md` and `process-docs/marker_reflection/` for the production side. `brave.py` is no longer unchanged by this area — it is no longer true to say a change here can't affect production reasoning, only that no import does.

## Public Interface
No `__init__.py`. Two entry points, both run directly and both relying on Python putting the script's own directory on `sys.path` for the sibling `_*` imports:
`./venv/bin/python3 dev/brave_return/test_brave_pydoll_core.py` — offline, deterministic, no network.
`./venv/bin/python3 dev/brave_return/brave_pydoll_probe.py` — live, spends requests against search.brave.com.

## Flow
Resolve the Chromium bundle production launches -> launch Chrome on a dedicated profile -> control-URL tripwire -> per query: navigate, poll the DOM into one of six states, fire the trigger if a button appears, snapshot cookies before/after -> four phases (cold, same profile after a process kill, an optional third fresh profile, fresh control last) -> markdown report into `md/`.

## Modules

### brave_pydoll_probe.py (224 LOC)

**Purpose:** Live four-phase probe answering whether the button flow completes, what it costs, whether a solved challenge carries over, and how it relates to the 429 shape.
**Reads:** nothing (queries are hardcoded per phase; live navigations against search.brave.com and a neutral control URL).
**Writes:** `md/brave_pydoll_probe_<ts>.md`; creates and deletes up to three temporary Chrome profiles.
**Called by:** CLI only; `test_brave_pydoll_core.py` imports its phase and accounting helpers.
**Calls out:** its `_brave_probe_*` siblings.

### _brave_probe_launch.py (234 LOC)

**Purpose:** Chrome launch, focus-steal watchdog and teardown — an inline copy of `src/search/browser.py`'s shape, not a shared import.
**Reads:** the profile's `DevToolsActivePort`.
**Writes:** nothing directly; spawns and kills Chrome processes and an asyncio watchdog task.
**Called by:** `brave_pydoll_probe.py`, `_brave_probe_query.py`, `test_brave_pydoll_core.py`.
**Calls out:** `patchright` (executable path resolution), `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager, ConnectionHandler, TargetCommands), `psutil`, macOS `open`/`osascript`/`pgrep`/`pkill`.

### _brave_probe_query.py (186 LOC)

**Purpose:** Drives and times one query on one tab — navigate, poll, fire the trigger, snapshot cookies — plus the control-URL tripwire.
**Reads:** the live DOM and the browser cookie store via CDP.
**Writes:** nothing; returns a `QueryMeasurement`.
**Called by:** `brave_pydoll_probe.py`, `test_brave_pydoll_core.py`.
**Calls out:** `pydoll` (InputCommands, StorageCommands), sibling core/js/launch modules.

### _brave_probe_core.py (169 LOC)

**Purpose:** The decidable core — page-state classifier, per-query verdicts, carry-over verdict, cookie fingerprinting and diffing, duration maths.
**Reads:** nothing (pure functions over dicts and lists).
**Writes:** nothing.
**Called by:** `_brave_probe_query.py`, `_brave_probe_report.py`, `_brave_pure_checks.py`, `test_brave_pydoll_core.py`.
**Calls out:** none beyond stdlib.

### _brave_probe_js.py (119 LOC)

**Purpose:** JS snippet constants and builders — page facts including a shadow-root-aware button search, and the trigger call.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_brave_probe_query.py`.
**Calls out:** none beyond stdlib.

### _brave_probe_report.py (339 LOC)

**Purpose:** Assembles the markdown report, one section per question plus phases, cookies, profile persistence, limits and methodology.
**Reads:** nothing (pure assembly over the objects passed in).
**Writes:** `md/brave_pydoll_probe_<ts>.md` via `write_report`.
**Called by:** `brave_pydoll_probe.py`, `test_brave_pydoll_core.py`.
**Calls out:** `_brave_probe_core.py`.

### test_brave_pydoll_core.py (318 LOC)

**Purpose:** Offline test module — serves local fixtures over a loopback HTTP server and drives the real query runner against them, then builds a report from the result.
**Reads:** `fixtures/*.html`.
**Writes:** a fixture report under the system temp directory; creates and deletes a temporary Chrome profile.
**Called by:** CLI only. Exit code 1 on any failed check.
**Calls out:** `pydoll` via the launch/query siblings, stdlib `http.server`.

### _brave_pure_checks.py (172 LOC)

**Purpose:** The network-free half of the test module — classifier, verdict, carry-over, cookie-diff, stats and pow-link-rate checks.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `test_brave_pydoll_core.py`.
**Calls out:** `_brave_probe_core.py`.

### _brave_probe_check_result.py (23 LOC)

**Purpose:** Shared pass/fail accounting for both halves of the test module.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `test_brave_pydoll_core.py`, `_brave_pure_checks.py`.
**Calls out:** none beyond stdlib.

---

## State
`fixtures/` holds six static pages driving the offline checks: a results page with no challenge, a button challenge that succeeds in the light DOM, the same one hosted in a shadow root, one that stalls, one that ends in a refusal, and a 429 pow-link page with no clickable element. Reports go to `md/`, named after the script that wrote them. Chrome profiles are temporary directories created and deleted per run — production's profile at `~/.websearch/browser-session` is never touched.

## Gotchas
The live run of 2026-09-18 met zero challenges across fourteen navigations and four separate fresh profiles, so every live question in its report is unanswered. Read that report as a record of the method, not of Brave's behaviour. The production query log later showed why: Brave challenges on the content of the search term, and this probe's hardcoded query lists are all ordinary technical questions. Changing the query lists is the lever; the pacing, the profile handling and the phase structure are not. The area's own process-docs carry the evidence.

Cookies must be read browser-wide via `Storage.getCookies`. `Tab.get_cookies()` is scoped to whatever the tab currently shows and reads empty on a blank tab, which voids any before/after comparison — the same trap the `mojeek_return` area paid a full live run for.

The page-state classifier must never call a terminal verdict on the mere presence of a challenge marker or a pow-link. That is the defect `src/search/engines/brave.py` carries today, and repeating it inside the probe would make the completion question unanswerable by construction.

The launch module resolves patchright's own Chromium bundle inline. It predates the 2026-09-24 fix that made `dev/_lib/browser_launch.py` launch the same patchright bundle; before that fix the shared helper launched the literal Google Chrome app and would have measured a different browser than production drives.
