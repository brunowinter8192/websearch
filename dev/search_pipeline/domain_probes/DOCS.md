# dev/search_pipeline/domain_probes/

## Role
Empirical domain-inventory probes for the `--books` and `--docs` whitelist and heuristic design: raw URL pools from Google and DuckDuckGo with a free word appended. Touch to refresh those inventories; not production filtering code.

## Public Interface
No `__init__.py`. Entry scripts `19_books_probe.py` and `20_docs_probe.py` run as `./venv/bin/python dev/search_pipeline/domain_probes/<script>.py`.

## Flow
Twelve broad queries plus `book` or `documentation` run against Google and DuckDuckGo; the URL pool is tallied by domain (and, for docs, scored against heuristics H1-H13) and written to `../md/`. The probes call the production engines and browser layer in `src/search/`.

## Modules

### 19_books_probe.py (290 LOC)

**Purpose:** Book-domain inventory: appends `book` to twelve broad queries and records the raw domain pool, no classification.
**Reads:** hardcoded 12-query set.
**Writes:** `../md/books_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### 20_docs_probe.py (85 LOC)

**Purpose:** Docs-domain probe: appends `documentation` to twelve tech queries and evaluates heuristics H1-H13 against the URL pool.
**Reads:** hardcoded query set via the config sibling.
**Writes:** `../md/docs_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** none.

### _docs_probe_config.py (19 LOC)

**Purpose:** Constants shared by the docs probe entry and report: query set, suffix, engine names.
**Reads:** none.
**Writes:** none.
**Called by:** `20_docs_probe.py`, report sibling.
**Calls out:** stdlib only.

### _docs_probe_report.py (343 LOC)

**Purpose:** Markdown report assembly for the docs probe: URL listings, domain frequency, heuristic coverage, miss-set analysis, run stats.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/docs_probe_<ts>.md`.
**Called by:** `20_docs_probe.py`.
**Calls out:** none.

---

## State
none.
