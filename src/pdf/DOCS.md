# src/pdf/

## Role

PDF to markdown tooling for the websearch-pdf skill: splits a PDF into fixed-size batches with anchor text and ready worker prompts, joins the worker output after a content check, and answers conversion statistics from an append-only log. No model runs here; the workers are spawned by the skill. Touch it when the batch protocol, the check or the log changes.

## Public Interface

`__init__.py` is empty. Entry path is `python cli.py pdf extract|assemble|stats`; cli.py imports the three workflow functions. Other modules are internal.

## Flow

extract: PDF in, free-RAM tripwire, text-layer gate, one liteparse parse, per-batch anchor file and worker prompt plus manifest out, start record logged. Skill spawns the workers. assemble: manifest and worker batch files in, per-batch comparison against the PDF text layer, one markdown file out only if every batch passes, end record logged. stats: log in, summary text out.

## Modules

### extract.py (285 LOC)

**Purpose:** Orchestrates the extract command: free-RAM tripwire, text-layer gate, anchors, worker prompts and manifest with the fixed worker count.
**Reads:** the PDF, `config/pdf_models.json`, `prompts/`, available RAM via psutil.
**Writes:** anchors, prompts and manifest in the batch directory (removes its own stale files there); start record in the conversion log.
**Called by:** cli.py.
**Calls out:** liteparse, psutil, poppler (via pdf_text.py).

---

### assemble.py (145 LOC)

**Purpose:** Orchestrates the assemble command: content check per batch against the PDF text layer, all-or-nothing join into `<STEM>.md`.
**Reads:** manifest and batch files in the batch directory, the PDF text layer.
**Writes:** the markdown file in the output directory (atomic); end record in the conversion log.
**Called by:** cli.py.
**Calls out:** none.

---

### stats.py (76 LOC)

**Purpose:** Orchestrates the stats command: runs, failures by reason, unfinished runs and averages from the conversion log.
**Reads:** the conversion log.
**Writes:** none.
**Called by:** cli.py.
**Calls out:** none.

---

### conversion_log.py (73 LOC)

**Purpose:** Append-only JSONL conversion log: path, record writer and reader, end-record builder, failure logging.
**Reads:** `WEBSEARCH_CONVERSION_LOG_PATH` from the environment; the log file.
**Writes:** `src/logs/conversions.jsonl` (gitignored, not pruned by the janitor).
**Called by:** extract.py, assemble.py, stats.py.
**Calls out:** none.

---

### pdf_text.py (31 LOC)

**Purpose:** Poppler wrappers (page count, text of a page range) and the character count used by the gate and the content check.
**Reads:** the PDF.
**Writes:** none.
**Called by:** extract.py, assemble.py.
**Calls out:** poppler (`pdfinfo`, `pdftotext`).

---

### report.py (15 LOC)

**Purpose:** Result type of the workflows and the error type that carries a failure class.
**Reads:** none.
**Writes:** none.
**Called by:** extract.py, assemble.py, stats.py, pdf_text.py, conversion_log.py, cli.py.
**Calls out:** none.

---

## State

None in memory. Persistent state is the conversion log under `src/logs/` and the batch directory written by extract and completed by the workers.

Prompt templates live in `prompts/`. Details, decisions and observed evidence: process-docs/pdf_workflow.
