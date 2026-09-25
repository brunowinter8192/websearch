# dev/refactor_sweep/

## Role
Layout tooling for the module standard (INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS) over every tracked `dev/` module: a scan, a mechanical re-layout, an orchestrator extraction, and equivalence proofs. Touch it to re-measure layout conformance or to lay out new dev files; do not use it on `src/`.

## Public Interface
No `__init__.py` — not a package. Each script is run directly via `./venv/bin/python`; `_layout_lib.py` is the shared analysis library imported by sibling scripts.

## Flow
Tracked `dev/**/*.py` -> AST analysis (markers, sections, orchestrator shape, stepdown order) -> report under `md/`; the re-layout script rewrites files with the same top-level nodes reordered and verifies node equality; the extraction script moves impure orchestrator statements into named helper functions; the snapshot, inline and run-compare scripts prove before/after equivalence against the merge base.

## Modules

### _extract_plan.py (242 LOC)

**Purpose:** Plans the extraction: finds impure statements in an orchestrator, groups them, and computes helper parameters and returned names.
**Reads:** AST nodes passed in.
**Writes:** nothing.
**Called by:** 06_extract_orchestrator.py.
**Calls out:** none.

---

### _layout_lib.py (280 LOC)

**Purpose:** Shared AST helpers: marker reading, definition-time dependency analysis, orchestrator purity check, reference graph, node fingerprints.
**Reads:** source text passed in; `git ls-files` for the file list.
**Writes:** nothing.
**Called by:** 01_layout_scan.py, 02_relayout.py, 03_ast_equivalence.py, 04_import_snapshot.py, 06_extract_orchestrator.py, 07_inline_equivalence.py, _extract_plan.py.
**Calls out:** none.

---

### 01_layout_scan.py (209 LOC)

**Purpose:** Scans every tracked dev module for layout findings and writes the report.
**Reads:** tracked `dev/**/*.py`.
**Writes:** `md/01_layout_scan.md`.
**Called by:** CLI only.
**Calls out:** none.

---

### 02_relayout.py (338 LOC)

**Purpose:** Rewrites dev modules into marker layout by reordering top-level nodes, aborting on unsafe cases and verifying node equality.
**Reads:** tracked `dev/**/*.py`.
**Writes:** the rewritten modules when `--apply` is given; stdout otherwise.
**Called by:** CLI only.
**Calls out:** none.

---

### 03_ast_equivalence.py (103 LOC)

**Purpose:** Compares the top-level node multiset of every modified dev file against the merge base with integration.
**Reads:** git objects and working tree.
**Writes:** `md/03_ast_equivalence.md`.
**Called by:** CLI only.
**Calls out:** none.

---

### 04_import_snapshot.py (130 LOC)

**Purpose:** Imports every dev module in a separate interpreter and dumps its module-level names as JSON for before/after comparison.
**Reads:** a tree copy given by `--tree`.
**Writes:** the JSON file given by `--out`.
**Called by:** CLI only.
**Calls out:** none.

---

### 05_fix_doc_loc.py (47 LOC)

**Purpose:** Rewrites the LOC numbers in module headings of all dev DOCS.md files from the actual line counts.
**Reads:** `dev/**/DOCS.md` and the documented modules.
**Writes:** the DOCS.md files.
**Called by:** CLI only.
**Calls out:** none.

---

### 06_extract_orchestrator.py (303 LOC)

**Purpose:** Moves statements with logic out of an orchestrator body into named helper functions and lifts logic in a main guard into a function.
**Reads:** tracked `dev/**/*.py` (not `dev/tests/`), optional names JSON.
**Writes:** the rewritten modules when `--apply` is given; stdout otherwise.
**Called by:** CLI only.
**Calls out:** none.

---

### 07_inline_equivalence.py (346 LOC)

**Purpose:** Inlines every extraction helper back into its caller and compares the result with the merge-base function.
**Reads:** git objects and working tree.
**Writes:** `md/07_inline_equivalence.md`.
**Called by:** CLI only.
**Calls out:** none.

---

### 08_run_compare.py (133 LOC)

**Purpose:** Runs sandbox-safe dev scripts in a base tree and a current tree and compares exit code, output and written files.
**Reads:** two tree copies, a script list.
**Writes:** the report path given by `--out`.
**Called by:** CLI only.
**Calls out:** none.

---

### 09_instrument_check.py (69 LOC)

**Purpose:** Prints lock types, patched method and recorded events of a bee-probe instrument module for comparison between two trees.
**Reads:** a tree copy given by `--tree`.
**Writes:** JSON to stdout.
**Called by:** CLI only.
**Calls out:** none.

---

### 10_sink_literals.py (267 LOC)

**Purpose:** Moves literal initialisations out of an orchestrator by hoisting constants or pushing accumulators into the helper that fills them.
**Reads:** tracked `dev/**/*.py` (not `dev/tests/`).
**Writes:** the rewritten modules when `--apply` is given; stdout otherwise.
**Called by:** CLI only.
**Calls out:** none.

---

## State
None.
