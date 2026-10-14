# dev/adhoc_persistence/

## Role
Measures whether the deep dive rule in `skills/websearch-web-research/SKILL.md` fires on the right cases, from the production scrape log, the Claude Code transcripts and the pipe log. Touch it to rerun the measurement or change a label. It never changes the skill; rule changes go to `patch/` as patch files.

## Public Interface
No `__init__.py`. Run from the repo root as `./venv/bin/python -m dev.adhoc_persistence.deepdive_rule_measurement`. No flags. Prints the report path. Tests: `dev/tests/test_deepdive_measurement.py`.

## Flow
Scrape log, query log, transcripts, pipe log, rag-cli search log and the collection directory are read -> scrapes are joined to transcript calls, grouped per session and host, classified as research, dev or unattributed -> `deepdive_labels.json` supplies host types, judgments and run triggers -> markdown report to `md/`.

## Modules

### deepdive_rule_measurement.py (53 LOC)

**Purpose:** Entry point: loads the sources, builds the groups and runs, writes the report.
**Reads:** `scrape_log.jsonl`, `query_log.jsonl`, `pipe_scrape_log.jsonl`, rag-cli `search.jsonl`, transcripts under `~/.claude/projects`, the collection directory, `deepdive_labels.json`.
**Writes:** `md/deepdive_rule_measurement_<timestamp>.md`; the path on stdout.
**Called by:** invoked directly with `-m`.
**Calls out:** none.

---

### deepdive_config.py (49 LOC)

**Purpose:** Paths, rule eras, type lists and thresholds shared by several modules.
**Reads:** none.
**Writes:** none.
**Called by:** every other module here.
**Calls out:** none.

---

### deepdive_transcripts.py (201 LOC)

**Purpose:** Reads transcripts: scrape, discover and index calls with their result time, skill activation, injected skill text era, agent mentions of a deep dive.
**Reads:** `~/.claude/projects/*/*.jsonl`; skips the measuring session itself.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py, dev/tests/test_deepdive_measurement.py.
**Calls out:** none.

---

### deepdive_join.py (48 LOC)

**Purpose:** Matches scrape records to transcript calls by normalized URL and time window.
**Reads:** none.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py, dev/tests/test_deepdive_measurement.py.
**Calls out:** dev/kvp/kvp_load.py.

---

### deepdive_candidates.py (138 LOC)

**Purpose:** Marks offered pages, groups scrapes per session and host, assigns era and kind, adds cross-session recurrence, selects candidates.
**Reads:** `query_log.jsonl` drilldown records.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py, deepdive_assessment.py, deepdive_deepdives.py, deepdive_render.py, deepdive_report_data.py, dev/tests/test_deepdive_measurement.py.
**Calls out:** dev/kvp/kvp_classify.py, dev/kvp/kvp_load.py.

---

### deepdive_assessment.py (144 LOC)

**Purpose:** Applies labels: host type, list verdict, derived judgment; builds the list-against-judgment matrix and the three readings of the rule.
**Reads:** `deepdive_labels.json`.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py, deepdive_report_data.py, deepdive_render.py, dev/tests/test_deepdive_measurement.py.
**Calls out:** none.

---

### deepdive_deepdives.py (111 LOC)

**Purpose:** Summarizes pipe runs with collection presence and rag-cli retrievals; extracts fetching `discover_urls` and `index_scrapes` calls.
**Reads:** the collection directory listing, rag-cli search hits.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py, deepdive_report_data.py.
**Calls out:** none.

---

### deepdive_report_data.py (98 LOC)

**Purpose:** Assembles the data structure the report renders.
**Reads:** none.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py.
**Calls out:** none.

---

### deepdive_render.py (402 LOC)

**Purpose:** Renders the report sections as markdown.
**Reads:** none.
**Writes:** none.
**Called by:** deepdive_rule_measurement.py.
**Calls out:** none.

---

### deepdive_labels.json (230 LOC)

**Purpose:** Hand-maintained data file: host types, per-candidate judgments, pipe-run triggers, session purposes. The one input a reader changes to move a row.
**Called by:** deepdive_assessment.py, deepdive_deepdives.py.

---

## State
None. Reports in `md/` are written once. `patch/deepdive_rule_perishable_content.patch` is the proposed rule change, not applied. Method, results and the decision: process-docs area adhoc_persistence.
