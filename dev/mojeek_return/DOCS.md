# dev/mojeek_return/

## Role
Measurement tooling for the question of whether mojeek.com can return to the engine pool, asked against the SEARCH lane's browser (pydoll, `src/search/browser.py` shape) rather than the scrape lane's. Touch this to re-measure Mojeek's ALTCHA behaviour or to check for drift. Do not touch it to change production: nothing here is wired into `src/`, and `mojeek` is still absent from the engine pool.

## Public Interface
No `__init__.py`. Two entry points, both run directly and both relying on Python putting the script's own directory on `sys.path` for the sibling `_*` imports:
`./venv/bin/python3 dev/mojeek_return/test_mojeek_pydoll_core.py` — offline, deterministic, no network.
`./venv/bin/python3 dev/mojeek_return/mojeek_pydoll_probe.py` — live, spends requests against mojeek.com.

## Flow
Launch Chrome on a dedicated profile -> control-URL tripwire -> per query: navigate, poll the DOM into one of five states, fire `verify()` if a widget appears, snapshot cookies before/after -> three phases (cold, same profile after a process kill, second fresh profile) -> markdown report into `md/`.

## Modules

### mojeek_pydoll_probe.py (182 LOC)

**Purpose:** Live three-phase probe answering whether the ALTCHA flow completes, what it costs, and whether a solved challenge carries over.
**Reads:** nothing (queries are hardcoded per phase; live navigations against mojeek.com and a neutral control URL).
**Writes:** `md/mojeek_pydoll_probe_<ts>.md`; creates and deletes two temporary Chrome profiles.
**Called by:** CLI only.
**Calls out:** its `_mojeek_pydoll_probe_*` siblings.

### _mojeek_pydoll_probe_launch.py (213 LOC)

**Purpose:** Chrome launch, focus-steal watchdog and teardown — an inline copy of `src/search/browser.py`'s shape, not a shared import.
**Reads:** the profile's `DevToolsActivePort`.
**Writes:** nothing directly; spawns and kills Chrome processes and an asyncio watchdog task.
**Called by:** `mojeek_pydoll_probe.py`, `test_mojeek_pydoll_core.py`.
**Calls out:** `pydoll` (Chrome, ChromiumOptions, BrowserProcessManager, ConnectionHandler, TargetCommands), `psutil`, macOS `open`/`osascript`/`pgrep`/`pkill`.

### _mojeek_pydoll_probe_query.py (233 LOC)

**Purpose:** Drives and times one query on one tab — navigate, poll, fire the trigger, buffer widget events, snapshot cookies — plus the control-URL tripwire.
**Reads:** the live DOM and the browser cookie store via CDP.
**Writes:** nothing; returns a `QueryMeasurement`.
**Called by:** `mojeek_pydoll_probe.py`, `test_mojeek_pydoll_core.py`.
**Calls out:** `pydoll` (StorageCommands), sibling core/js/launch modules.

### _mojeek_pydoll_probe_core.py (208 LOC)

**Purpose:** The decidable core — page-state classifier, per-query verdicts, carry-over verdict, cookie fingerprinting and diffing, payload and duration maths.
**Reads:** nothing (pure functions over dicts and lists).
**Writes:** nothing.
**Called by:** `_mojeek_pydoll_probe_query.py`, `_mojeek_pydoll_probe_report.py`, `_mojeek_pydoll_pure_checks.py`.
**Calls out:** none beyond stdlib.

### _mojeek_pydoll_probe_js.py (85 LOC)

**Purpose:** JS snippet constants and builders — page facts, widget event buffer, the `verify()` call, widget attributes and configuration.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_mojeek_pydoll_probe_query.py`.
**Calls out:** none beyond stdlib.

### _mojeek_pydoll_probe_report.py (321 LOC)

**Purpose:** Assembles the markdown report, one section per question plus phases, cookies, limits and methodology.
**Reads:** nothing (pure assembly over the objects passed in).
**Writes:** `md/mojeek_pydoll_probe_<ts>.md` via `write_report`.
**Called by:** `mojeek_pydoll_probe.py`, `test_mojeek_pydoll_core.py`.
**Calls out:** `_mojeek_pydoll_probe_core.py`.

### test_mojeek_pydoll_core.py (287 LOC)

**Purpose:** Offline test module — serves local fixtures over a loopback HTTP server and drives the real query runner against them, then builds a report from the result.
**Reads:** `fixtures/*.html`.
**Writes:** `/tmp/mojeek_pydoll_probe_fixture_report.md`; creates and deletes a temporary Chrome profile.
**Called by:** CLI only. Exit code 1 on any failed check.
**Calls out:** `pydoll` via the launch/query siblings, stdlib `http.server`.

### _mojeek_pydoll_pure_checks.py (147 LOC)

**Purpose:** The network-free half of the test module — classifier, verdict, carry-over, cookie-diff and maths checks.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `test_mojeek_pydoll_core.py`.
**Calls out:** `_mojeek_pydoll_probe_core.py`.

### _mojeek_pydoll_check_result.py (23 LOC)

**Purpose:** Shared pass/fail accounting for both halves of the test module.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `test_mojeek_pydoll_core.py`, `_mojeek_pydoll_pure_checks.py`.
**Calls out:** none beyond stdlib.

---

## State
`fixtures/` holds four static pages driving the offline checks: a results page with no challenge, a challenge that succeeds, one that stalls in the server round trip, and one that ends in a refusal. The three challenge fixtures define their own `altcha-widget` custom element, so the trigger is exercised against a page-defined class method without touching the network. Reports go to `md/`, named after the script that wrote them. Chrome profiles are temporary directories created and deleted per run — production's profile at `~/.websearch/browser-session` is never touched.

## Gotchas
Cookies must be read browser-wide. `Tab.get_cookies()` resolves to CDP `Network.getCookies` scoped to whatever the tab currently shows, so a snapshot taken on `about:blank` before a navigation comes back empty and silently voids any before/after comparison. This cost one full live run. The query module uses `Storage.getCookies` instead, and `test_mojeek_pydoll_core.py` guards it with a check that reads a known cookie from a blank tab.

The page-state classifier must never call a terminal verdict on Mojeek's block-page boilerplate. That text is on screen from the first poll and stays there for the whole verification sequence, so `CHALLENGE_PENDING` and `IN_FLIGHT` exist as explicitly non-terminal states and `challenge_success.html` keeps the boilerplate visible along the entire success path to assert it.

The results poll stops at the first matching result link, which is what the removed production engine did too — so a challenged query's measured time is time-to-first-link, and the table's link count can read 1 rather than 10 when the list is still rendering.
