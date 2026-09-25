# dev/refactor_sweep/

## Role
Layout tooling for the module standard (INFRASTRUCTURE, ORCHESTRATOR, FUNCTIONS) over every tracked `dev/` module: a scan, a mechanical re-layout, and equivalence proofs. Touch it to re-measure layout conformance or to lay out new dev files; do not use it on `src/`.

## Public Interface
No `__init__.py` — not a package. Each script is run directly via `./venv/bin/python`; `_layout_lib.py` is the shared analysis library imported by sibling scripts.

## Flow
Tracked `dev/**/*.py` -> AST analysis (markers, sections, orchestrator shape, stepdown order) -> report under `md/`; the re-layout script rewrites files with the same top-level nodes reordered and verifies node equality; the snapshot script imports every module in an isolated tree copy and records its module-level names.

## Modules

### _layout_lib.py (265 LOC)

**Purpose:** Shared AST helpers: marker reading, definition-time dependency analysis, orchestrator purity check, reference graph, node fingerprints.
**Reads:** source text passed in; `git ls-files` for the file list.
**Writes:** nothing.
**Called by:** 01_layout_scan.py, 02_relayout.py, 03_ast_equivalence.py, 04_import_snapshot.py.
**Calls out:** none.

---

### 01_layout_scan.py (193 LOC)

**Purpose:** Scans every tracked dev module for layout findings and writes the report.
**Reads:** tracked `dev/**/*.py`.
**Writes:** `md/01_layout_scan.md`.
**Called by:** CLI only.
**Calls out:** none.

---

### 02_relayout.py (357 LOC)

**Purpose:** Rewrites dev modules into marker layout by reordering top-level nodes, aborting on unsafe cases and verifying node equality.
**Reads:** tracked `dev/**/*.py`.
**Writes:** the rewritten modules when `--apply` is given; stdout otherwise.
**Called by:** CLI only.
**Calls out:** none.

---

### 03_ast_equivalence.py (98 LOC)

**Purpose:** Compares the top-level node multiset of every modified dev file against the merge base with integration.
**Reads:** git objects and working tree.
**Writes:** `md/03_ast_equivalence.md`.
**Called by:** CLI only.
**Calls out:** none.

---

### 04_import_snapshot.py (125 LOC)

**Purpose:** Imports every dev module in a separate interpreter and dumps its module-level names as JSON for before/after comparison.
**Reads:** a tree copy given by `--tree`.
**Writes:** the JSON file given by `--out`.
**Called by:** CLI only.
**Calls out:** none.

---

### 05_fix_doc_loc.py (43 LOC)

**Purpose:** Rewrites the LOC numbers in module headings of all dev DOCS.md files from the actual line counts.
**Reads:** `dev/**/DOCS.md` and the documented modules.
**Writes:** the DOCS.md files.
**Called by:** CLI only.
**Calls out:** none.

---

## State
None.
