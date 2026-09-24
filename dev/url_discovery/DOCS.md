# dev/url_discovery/

## Role
Two independent tools for the capture pipeline's URL-discovery step: a dormant live-site probe of crawl4ai deep-crawl resume mechanics, and a deterministic local fixture site whose page inventory is stated in code and serves as ground truth for the seed feeders. Not the place for feeder implementations.

## Public Interface
No `__init__.py` — not a package. Two CLI entry points: the resume-state probe and the fixture server. The fixture-site module is also imported by dev tests as the deterministic discovery target.

## Flow
Probe: fixed live URLs -> small BFS runs on one shared crawler -> timestamped report in `md/`.
Fixture: source lists of page paths -> generated routes on a local threaded HTTP server -> callers are checked against ground truth computed from the same lists.

## Modules

### 01_resume_state_probe.py (258 LOC)

**Purpose:** Verifies by execution whether BFS resume state can pre-seed the frontier with an arbitrary URL set.
**Reads:** nothing on disk; live pages via crawl4ai.
**Writes:** `md/01_resume_state_probe_report_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `crawl4ai`.

---

### _fixture_site.py (117 LOC)

**Purpose:** HTTP serving mechanics of the fixture site: request handling, switchable failure modes, and server lifecycle.
**Reads:** nothing on disk.
**Writes:** nothing; in-memory HTTP responses only.
**Called by:** `02_fixture_site_server.py`, `dev/tests/test_discovery.py`, `dev/tests/test_seed_feeders.py`.
**Calls out:** `_fixture_site_content.py`.

### _fixture_site_content.py (226 LOC)

**Purpose:** Defines the fixture site's shape: page lists, page content generators, routes, and ground truth.
**Reads:** nothing on disk.
**Writes:** nothing.
**Called by:** `_fixture_site.py`.
**Calls out:** none.

### 02_fixture_site_server.py (35 LOC)

**Purpose:** Standalone entry point that starts the fixture site, prints its seed URL and ground truth, and blocks until interrupted.
**Reads:** nothing.
**Writes:** Startup banner to stdout.
**Called by:** CLI only.
**Calls out:** `_fixture_site.py`.

---

## State
`_fixture_site.py` holds module-level route and control state, so only one fixture server per process is meant to run. The probe keeps no state; each report is a standalone snapshot. Gotchas: process-docs area refactor_sweep and url_discovery.
