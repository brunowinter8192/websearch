# dev/search_pipeline/bee_probes/

## Role
Three investigation probes for rate-limiter and event-loop behaviour under engine cascades (CDP starvation, acquire, branch), each split into instrumentation, canary, analysis, report, and findings siblings. Touch to rerun or extend those investigations; not for production rate-limiter code.

## Public Interface
No `__init__.py`. The three entry scripts run via `./venv/bin/python3`; each imports its own `_<probe>_*` siblings by flat name.

## Flow
Query set from `../queries.txt` runs through the instrumented production pipeline -> siblings reduce events to per-query records -> a timestamped report and a fixed-path findings file are written under `../md/`. The instrumentation wraps the `src/search/` browser layer, search workflow and rate limiter.

## Modules

### cdp_starvation_probe.py (131 LOC)

**Purpose:** Phase 1 probe: tests whether event-loop starvation delays CDP events during engine cascades; always writes both outputs.
**Reads:** `../queries.txt`.
**Writes:** Timestamped report and the fixed-path findings file in `../md/`.
**Called by:** CLI only.
**Calls out:** none.

### _cdp_starvation_probe_canary.py (92 LOC)

**Purpose:** Scheduling-latency canary task and bucketed percentile stats.
**Reads:** nothing; owns its samples.
**Writes:** nothing; returns stats.
**Called by:** `cdp_starvation_probe.py`, report and findings siblings.
**Calls out:** none.

### _cdp_starvation_probe_findings.py (172 LOC)

**Purpose:** Fixed-path narrative findings document, overwritten each run.
**Reads:** nothing; takes records and the report path.
**Writes:** Findings file in `../md/`.
**Called by:** `cdp_starvation_probe.py`.
**Calls out:** none.

### _cdp_starvation_probe_instrument.py (40 LOC)

**Purpose:** Passive instrumentation: pydoll message-timestamp patch and slow-callback log handler.
**Reads:** nothing; patches pydoll at import.
**Writes:** Its own event lists.
**Called by:** `cdp_starvation_probe.py`, report and findings siblings.
**Calls out:** `pydoll`.

### _cdp_starvation_probe_report.py (206 LOC)

**Purpose:** Timestamped markdown report plus the threshold-based verdict classifier.
**Reads:** nothing; arguments only.
**Writes:** Report in `../md/`.
**Called by:** `cdp_starvation_probe.py`, findings sibling.
**Calls out:** none.

### acquire_probe.py (143 LOC)

**Purpose:** Phase 2 probe: instruments the limiter acquire to discriminate stale lock, backoff sleep, and innocent acquire.
**Reads:** nothing; live instrumented run.
**Writes:** Timestamped report and findings file in `../md/`; smoke mode writes nothing.
**Called by:** CLI only.
**Calls out:** none.

### _acquire_probe_analysis.py (89 LOC)

**Purpose:** Per-query analysis: query loading, event reduction, discriminator, aggregate ratios.
**Reads:** The query file path passed in.
**Writes:** stderr smoke dump.
**Called by:** `acquire_probe.py`, report and findings siblings.
**Calls out:** none.

### _acquire_probe_canary.py (71 LOC)

**Purpose:** Scheduling-latency canary and percentile stats.
**Reads:** nothing; owns its samples.
**Writes:** nothing.
**Called by:** `acquire_probe.py`, analysis, report, and findings siblings.
**Calls out:** none.

### _acquire_probe_findings.py (184 LOC)

**Purpose:** Fixed-path narrative findings document.
**Reads:** nothing; arguments only.
**Writes:** Findings file in `../md/`.
**Called by:** `acquire_probe.py`.
**Calls out:** none.

### _acquire_probe_instrument.py (68 LOC)

**Purpose:** Lock-watching limiter monkeypatch emitting enter and exit events, applied at import.
**Reads:** nothing; patches the production rate limiter.
**Writes:** Its own event list.
**Called by:** `acquire_probe.py`, report sibling.
**Calls out:** none.

### _acquire_probe_report.py (155 LOC)

**Purpose:** Timestamped markdown report plus the overall discriminator classifier.
**Reads:** nothing; arguments only.
**Writes:** Report in `../md/`.
**Called by:** `acquire_probe.py`, findings sibling.
**Calls out:** none.

### branch_probe.py (163 LOC)

**Purpose:** Phase 3 probe: discriminates which sleep branch in the limiter acquire fires; stops on failed cascade reproduction.
**Reads:** nothing; live instrumented run.
**Writes:** Timestamped report and findings file in `../md/`; smoke mode writes nothing.
**Called by:** CLI only.
**Calls out:** none.

### _branch_probe_analysis.py (104 LOC)

**Purpose:** Per-query analysis: limiter snapshots, event reduction, branch discriminator.
**Reads:** The query file path passed in; limiter state via the instrument sibling.
**Writes:** stderr smoke dump.
**Called by:** `branch_probe.py`.
**Calls out:** none.

### _branch_probe_canary.py (75 LOC)

**Purpose:** Scheduling-latency canary and percentile stats.
**Reads:** nothing; owns its samples.
**Writes:** nothing.
**Called by:** `branch_probe.py`, report and findings siblings.
**Calls out:** none.

### _branch_probe_findings.py (221 LOC)

**Purpose:** Fixed-path narrative findings document.
**Reads:** nothing; arguments only.
**Writes:** Findings file in `../md/`.
**Called by:** `branch_probe.py`.
**Calls out:** none.

### _branch_probe_instrument.py (58 LOC)

**Purpose:** Byte-identical limiter acquire replacement adding branch-discriminator events, applied at import.
**Reads:** nothing; patches the production rate limiter.
**Writes:** Its own event and snapshot lists.
**Called by:** `branch_probe.py`, analysis and report siblings.
**Calls out:** none.

### _branch_probe_report.py (207 LOC)

**Purpose:** Timestamped markdown report plus the overall verdict classifier.
**Reads:** nothing; arguments only.
**Writes:** Report in `../md/`.
**Called by:** `branch_probe.py`, findings sibling.
**Calls out:** none.

---

## State
Each instrument sibling owns its patched-event lists and each canary sibling its latency samples; entry scripts read them, siblings never mutate another probe's state. Fixed-path findings files are numbered per phase and overwritten each run.
