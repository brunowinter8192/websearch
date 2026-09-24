# dev/search_pipeline/bee_probes/

## Role
Three investigation probes for RateLimiter and event-loop behaviour under engine cascades (CDP starvation, acquire, branch), each split into instrumentation, canary, analysis, report and findings siblings. Touch to rerun or extend those investigations; not for production rate-limiter code.

## Public Interface
No `__init__.py`. Entry scripts `cdp_starvation_probe.py`, `acquire_probe.py`, `branch_probe.py` run as `./venv/bin/python3 dev/search_pipeline/bee_probes/<script>.py`; each imports its own `_<probe>_*` siblings by flat name.

## Flow
Query set from `../queries.txt` runs through the instrumented production pipeline; siblings reduce events to per-query records, then write a timestamped report and a fixed-path findings file under `../md/`.

## Modules

### cdp_starvation_probe.py (153 LOC)

**Purpose:** Phase 1 bee probe: tests whether asyncio event-loop starvation delays CDP events during engine cascades; always writes both outputs.
**Reads:** `../queries.txt`.
**Writes:** `../md/cdp_probe_<ts>.md`, `../md/01_probe.md`.
**Called by:** CLI only (`--max-queries`).
**Calls out:** `src.search.browser`, `src.search.search_web`, the four `_cdp_starvation_probe_*` siblings.

### _cdp_starvation_probe_canary.py (97 LOC)

**Purpose:** Scheduling-latency canary task and five-bucket percentile stats for the CDP probe.
**Reads:** none (owns `_canary_samples`).
**Writes:** none (returns stats dicts).
**Called by:** `cdp_starvation_probe.py`, report and findings siblings.
**Calls out:** stdlib only.

### _cdp_starvation_probe_findings.py (173 LOC)

**Purpose:** Fixed-path narrative findings document for the CDP probe, overwritten each run.
**Reads:** none (records and report path as arguments).
**Writes:** `../md/01_probe.md`.
**Called by:** `cdp_starvation_probe.py`.
**Calls out:** instrument, canary and report siblings.

### _cdp_starvation_probe_instrument.py (45 LOC)

**Purpose:** Passive instrumentation: pydoll message-timestamp monkeypatch plus asyncio slow-callback log handler.
**Reads:** none (patches pydoll at import).
**Writes:** own `_cdp_ts` / `_slow_cb_events` lists.
**Called by:** `cdp_starvation_probe.py`, report and findings siblings.
**Calls out:** `pydoll.connection.connection_handler`.

### _cdp_starvation_probe_report.py (211 LOC)

**Purpose:** Timestamped Markdown report for the CDP probe plus the threshold-based verdict classifier.
**Reads:** none (arguments only).
**Writes:** `../md/cdp_probe_<ts>.md`.
**Called by:** `cdp_starvation_probe.py`, findings sibling.
**Calls out:** instrument and canary siblings.

### acquire_probe.py (170 LOC)

**Purpose:** Phase 2 bee probe: instruments `RateLimiter.acquire()` to discriminate stale lock, backoff sleep and innocent acquire.
**Reads:** none (live instrumented run).
**Writes:** `../md/acquire_probe_<ts>.md`, `../md/02_acquire_probe.md`; `--smoke` writes nothing.
**Called by:** CLI only (`--max-queries`, `--smoke`).
**Calls out:** `src.search.browser`, `src.search.search_web` (via importlib after the instrument), the five `_acquire_probe_*` siblings.

### _acquire_probe_analysis.py (92 LOC)

**Purpose:** Per-query analysis for the acquire probe: query loading, event reduction, discriminator, aggregate ratios.
**Reads:** `../queries.txt` path passed in.
**Writes:** stderr (smoke dump).
**Called by:** `acquire_probe.py`, report and findings siblings.
**Calls out:** canary sibling.

### _acquire_probe_canary.py (72 LOC)

**Purpose:** Scheduling-latency canary and percentile stats for the acquire probe.
**Reads:** none (owns `_canary_samples`).
**Writes:** none.
**Called by:** `acquire_probe.py`, analysis, report and findings siblings.
**Calls out:** stdlib only.

### _acquire_probe_findings.py (184 LOC)

**Purpose:** Fixed-path narrative findings document for the acquire probe.
**Reads:** none (arguments only).
**Writes:** `../md/02_acquire_probe.md`.
**Called by:** `acquire_probe.py`.
**Calls out:** canary, analysis and report siblings.

### _acquire_probe_instrument.py (80 LOC)

**Purpose:** Lock-watching `RateLimiter.__init__`/`acquire()` monkeypatch with enter/exit event emission, applied at import.
**Reads:** none (patches `src.search.rate_limiter`).
**Writes:** own `_acq_events` list.
**Called by:** `acquire_probe.py`, report sibling.
**Calls out:** `src.search.rate_limiter` (via importlib).

### _acquire_probe_report.py (155 LOC)

**Purpose:** Timestamped Markdown report for the acquire probe plus the shared overall-discriminator classifier.
**Reads:** none (arguments only).
**Writes:** `../md/acquire_probe_<ts>.md`.
**Called by:** `acquire_probe.py`, findings sibling.
**Calls out:** instrument, canary and analysis siblings.

### branch_probe.py (196 LOC)

**Purpose:** Phase 3 bee probe: discriminates which `asyncio.sleep` branch in `RateLimiter.acquire()` fires; stops on failed cascade reproduction.
**Reads:** none (live instrumented run).
**Writes:** `../md/branch_probe_<ts>.md`, `../md/03_branch_probe.md`; `--smoke` writes nothing.
**Called by:** CLI only (`--max-queries`, `--smoke`).
**Calls out:** `src.search.browser`, `src.search.search_web` (via importlib after the instrument), the five `_branch_probe_*` siblings.

### _branch_probe_analysis.py (107 LOC)

**Purpose:** Per-query analysis for the branch probe: limiter snapshots, event reduction, branch discriminator.
**Reads:** `../queries.txt` path passed in; limiter state via the instrument sibling.
**Writes:** stderr (smoke dump).
**Called by:** `branch_probe.py`.
**Calls out:** instrument sibling.

### _branch_probe_canary.py (76 LOC)

**Purpose:** Scheduling-latency canary and percentile stats for the branch probe.
**Reads:** none (owns `_canary_samples`).
**Writes:** none.
**Called by:** `branch_probe.py`, report and findings siblings.
**Calls out:** stdlib only.

### _branch_probe_findings.py (221 LOC)

**Purpose:** Fixed-path narrative findings document for the branch probe.
**Reads:** none (arguments only).
**Writes:** `../md/03_branch_probe.md`.
**Called by:** `branch_probe.py`.
**Calls out:** canary and report siblings.

### _branch_probe_instrument.py (68 LOC)

**Purpose:** Byte-identical `RateLimiter.acquire()` replacement adding branch-discriminator event emission, applied at import.
**Reads:** none (patches `src.search.rate_limiter`).
**Writes:** own `_acq_events` / `_pre_snapshots` lists.
**Called by:** `branch_probe.py`, analysis and report siblings.
**Calls out:** `src.search.rate_limiter` (via importlib).

### _branch_probe_report.py (207 LOC)

**Purpose:** Timestamped Markdown report for the branch probe plus the shared overall-verdict classifier.
**Reads:** none (arguments only).
**Writes:** `../md/branch_probe_<ts>.md`.
**Called by:** `branch_probe.py`, findings sibling.
**Calls out:** canary and instrument siblings.

---

## State
Each `_<probe>_instrument.py` (or `_cdp_starvation_probe_instrument.py`) owns its patched-event lists, each `_<probe>_canary.py` its latency samples; entry scripts read them, siblings never mutate another probe's state.
