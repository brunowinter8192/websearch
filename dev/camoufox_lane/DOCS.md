# dev/camoufox_lane/

## Role
Probe for how the camoufox launch timeout behaves on the production launch chain. Touch it to re-measure launch-timeout enforcement; do not touch it for scrape behaviour, which lives in `src/scraper`.

## Public Interface
No `__init__.py` — not a package. The single numbered probe is the entry point, run directly via `./venv/bin/python`.

## Flow
Two launches through the production chain (a 1 ms timeout and the production 30000 ms control) -> outcome, wall time and traceback per run -> markdown report in `md/`.

## Modules

### 01_launch_timeout_probe.py (99 LOC)

**Purpose:** Launches camoufox with a 1 ms and a 30000 ms timeout and records whether the timeout is enforced.
**Reads:** nothing; hardcoded launch kwargs.
**Writes:** `md/01_launch_timeout_probe_<ts>.md`; a real camoufox browser is started and closed.
**Called by:** CLI only.
**Calls out:** `camoufox`.

---

## State
No shared state. Findings live in `md/` and the process-docs area for the camoufox lane.
