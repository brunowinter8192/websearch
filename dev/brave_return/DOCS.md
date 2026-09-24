# dev/brave_return/

## Role
Measurement tooling for whether Brave's proof-of-work button challenge can be solved unattended from code. Never imported by production code, but its live report is the evidence the production Brave engine's challenge handling was built from.

## Public Interface
No `__init__.py` — not a package. Two entry points: the live probe script (spends requests against search.brave.com) and the verification module (loopback fixtures, one real headless Chrome per check; a verification, not a test, and never collected by the default pytest run).

## Flow
Launch Chrome on a dedicated profile -> control-URL tripwire -> per query navigate, poll the DOM into a page state, fire the trigger, snapshot cookies -> four phases -> markdown report in `md/`.

## Modules

### brave_pydoll_probe.py (224 LOC)

**Purpose:** Live four-phase probe: does the button flow complete, what does it cost, does a solved challenge carry over.
**Reads:** nothing; hardcoded queries, live navigations.
**Writes:** `md/brave_pydoll_probe_<ts>.md`; temporary Chrome profiles.
**Called by:** CLI only.
**Calls out:** the `_brave_probe_*` siblings.

### _brave_probe_launch.py (234 LOC)

**Purpose:** Chrome launch, focus-steal watchdog, and teardown, an inline copy of the production browser shape.
**Reads:** The profile's DevTools port file.
**Writes:** nothing directly; spawns and kills Chrome processes.
**Called by:** `brave_pydoll_probe.py`, `_brave_probe_query.py`, `verify_brave_pydoll_core.py`.
**Calls out:** `patchright`, `pydoll`, `psutil`, macOS process tools.

### _brave_probe_query.py (183 LOC)

**Purpose:** Drives and times one query on one tab, plus the control-URL tripwire.
**Reads:** Live DOM and browser cookie store via CDP.
**Writes:** nothing; returns a measurement.
**Called by:** `brave_pydoll_probe.py`, `verify_brave_pydoll_core.py`.
**Calls out:** `pydoll`, the core, js, and launch siblings.

### _brave_probe_core.py (169 LOC)

**Purpose:** Decidable core: page-state classifier, verdicts, cookie fingerprinting and diffing, duration maths.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_brave_probe_query.py`, `_brave_probe_report.py`, `_brave_pure_checks.py`, `verify_brave_pydoll_core.py`.
**Calls out:** none.

### _brave_probe_js.py (119 LOC)

**Purpose:** JS snippets and builders for page facts (shadow-root aware) and the trigger.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_brave_probe_query.py`.
**Calls out:** none.

### _brave_probe_report.py (339 LOC)

**Purpose:** Assembles the markdown report, one section per question plus methodology.
**Reads:** nothing.
**Writes:** `md/brave_pydoll_probe_<ts>.md`.
**Called by:** `brave_pydoll_probe.py`, `verify_brave_pydoll_core.py`.
**Calls out:** `_brave_probe_core.py`.

### verify_brave_pydoll_core.py (381 LOC)

**Purpose:** Verification of the probe checks against a real headless Chrome, one check per fixture server and profile; run by explicit path.
**Reads:** `fixtures/*.html`.
**Writes:** A fixture report under the pytest tmp path.
**Called by:** pytest by explicit path only (verification, never collected by the default run).
**Calls out:** `pydoll` via the siblings, stdlib `http.server`.

### _brave_pure_checks.py (172 LOC)

**Purpose:** The network-free checks of the test module: classifier, verdict, carry-over, cookie-diff, and stats.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `verify_brave_pydoll_core.py`.
**Calls out:** `_brave_probe_core.py`.

### _brave_probe_check_result.py (5 LOC)

**Purpose:** Assertion helper that fails fast on a false condition.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `verify_brave_pydoll_core.py`, `_brave_pure_checks.py`.
**Calls out:** none.

---

## State
`fixtures/` holds six static pages driving the offline checks. Reports go to `md/`, named after the writing script. Chrome profiles are temporary and deleted per run; production's profile is never touched. Gotchas and live-run evidence: process-docs area refactor_sweep and brave_return.
