# dev/mojeek_return/

## Role
Measurement tooling for whether mojeek.com can return to the engine pool, asked against the search lane's browser. Touch it to re-measure Mojeek's ALTCHA behaviour or check for drift. Nothing here is wired into `src/`, and mojeek remains absent from the engine pool.

## Public Interface
No `__init__.py` — not a package. Three entry points: the verification module (loopback fixtures, real headless Chrome; a verification, not a test), the live probe, and the live one-request challenge capture. Sibling `_*` modules are imported via the script's own directory.

## Flow
Launch Chrome on a dedicated profile -> control-URL tripwire -> per query navigate, poll the DOM into a page state, fire the widget verify, snapshot cookies -> three phases -> markdown report in `md/`.

## Modules

### mojeek_challenge_capture.py (165 LOC)

**Purpose:** Single-navigation capture of the challenge page as served, to settle which strings are real before an engine keys on one.
**Reads:** One live navigation against mojeek.com.
**Writes:** `md/mojeek_challenge_capture_<ts>.md`; temporary Chrome profile.
**Called by:** CLI only.
**Calls out:** none.

### mojeek_pydoll_probe.py (182 LOC)

**Purpose:** Live three-phase probe: does the ALTCHA flow complete, what does it cost, does a solved challenge carry over.
**Reads:** nothing; hardcoded queries, live navigations.
**Writes:** `md/mojeek_pydoll_probe_<ts>.md`; two temporary Chrome profiles.
**Called by:** CLI only.
**Calls out:** none.

### _mojeek_pydoll_probe_launch.py (213 LOC)

**Purpose:** Chrome launch, focus-steal watchdog, and teardown, an inline copy of the production browser shape.
**Reads:** The profile's DevTools port file.
**Writes:** nothing directly; spawns and kills Chrome processes.
**Called by:** `mojeek_pydoll_probe.py`, `verify_mojeek_pydoll_core.py`.
**Calls out:** `pydoll`, `psutil`, macOS process tools.

### _mojeek_pydoll_probe_query.py (227 LOC)

**Purpose:** Drives and times one query on one tab, plus the control-URL tripwire.
**Reads:** Live DOM and browser cookie store via CDP.
**Writes:** nothing; returns a measurement.
**Called by:** `mojeek_pydoll_probe.py`, `verify_mojeek_pydoll_core.py`.
**Calls out:** `pydoll`.

### _mojeek_pydoll_probe_core.py (202 LOC)

**Purpose:** Decidable core: page-state classifier, verdicts, cookie fingerprinting and diffing, payload and duration maths.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_mojeek_pydoll_probe_query.py`, `_mojeek_pydoll_probe_report.py`, `_mojeek_pydoll_pure_checks.py`.
**Calls out:** none.

### _mojeek_pydoll_probe_js.py (85 LOC)

**Purpose:** JS snippets and builders for page facts, the widget event buffer, and the verify call.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `_mojeek_pydoll_probe_query.py`.
**Calls out:** none.

### _mojeek_pydoll_probe_report.py (340 LOC)

**Purpose:** Assembles the markdown report, one section per question plus methodology.
**Reads:** nothing.
**Writes:** `md/mojeek_pydoll_probe_<ts>.md`.
**Called by:** `mojeek_pydoll_probe.py`, `verify_mojeek_pydoll_core.py`.
**Calls out:** none.

### verify_mojeek_pydoll_core.py (337 LOC)

**Purpose:** Verification of the probe checks against a real headless Chrome, one check per fixture server and profile; run by explicit path.
**Reads:** `fixtures/*.html`.
**Writes:** A fixture report under the pytest tmp path.
**Called by:** pytest by explicit path only (verification, never collected by the default run).
**Calls out:** `pydoll`.

### _mojeek_pydoll_pure_checks.py (155 LOC)

**Purpose:** The network-free checks of the test module: classifier, verdict, carry-over, cookie-diff, maths.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `verify_mojeek_pydoll_core.py`.
**Calls out:** none.

### _mojeek_pydoll_check_result.py (5 LOC)

**Purpose:** Assertion helper that fails fast on a false condition.
**Reads:** nothing.
**Writes:** stdout.
**Called by:** `verify_mojeek_pydoll_core.py`, `_mojeek_pydoll_pure_checks.py`.
**Calls out:** none.

---

## State
`fixtures/` holds four static pages driving the offline checks. Reports go to `md/`, named after the writing script. Chrome profiles are temporary and deleted per run; production's profile is never touched. Gotchas: process-docs area refactor_sweep and mojeek_return.
