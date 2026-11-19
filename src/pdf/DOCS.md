# src/pdf/

## Role

PDF to markdown tooling for the websearch-pdf skill: decides per PDF between text mode and scan mode, splits it into fixed-size batches with ready worker prompts, joins the worker output after a content check, and answers conversion statistics from an append-only log. No model runs here; the workers are spawned by the skill. Touch it when the batch protocol, a check or the log changes.

## Public Interface

`__init__.py` is empty. Entry path is `python cli.py pdf extract|assemble|stats`; cli.py imports the three workflow functions. Other modules are internal.

## Flow

extract: PDF in, mode decision from the text layer (`text` or `scan`, written to the manifest), start record logged. Text mode: one liteparse parse, per-batch anchor file and worker prompt. Scan mode: per-batch image-only worker prompt, a seeded draw of control pages (`control_pages` in the manifest) and one `prompt_control.md` for a single control worker. Skill spawns the workers. assemble: manifest and worker batch files in; text mode compares each batch against the PDF text layer (outlier pages left out and named); scan mode reads `control.json` of the control worker and fails on a missing file, a missing drawn page or a grave finding. One markdown file out only if everything passes, with over-long paragraphs split after the check, end record logged. stats: log in, summary text out.

## Modules

### extract.py (332 LOC)

**Purpose:** Orchestrates the extract command: mode decision, anchors and worker prompts (text) or scan prompts, control draw and control prompt (scan), manifest.
**Reads:** the PDF, `config/pdf_models.json`, `prompts/`.
**Writes:** anchors, prompts, `prompt_control.md` and manifest in the batch directory (removes its own stale files there, including `control.json`); start record in the conversion log.
**Called by:** cli.py.
**Calls out:** liteparse, poppler (via pdf_text.py).

---

### assemble.py (364 LOC)

**Purpose:** Orchestrates the assemble command: per-batch content check (text layer recall in text mode, `control.json` findings in scan mode), all-or-nothing join, paragraph splitting, atomic write of `<STEM>.md`.
**Reads:** manifest, batch files and `control.json` in the batch directory, the PDF text layer (text mode only).
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

### pdf_text.py (40 LOC)

**Purpose:** Poppler wrappers (page count, text of a page range, text per page) and the character count used by the gate and the content check.
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

Prompt templates live in `prompts/`: text worker (`worker_prompt.md`, `steps_single.md`, `steps_split.md`, `chunk_steps.md`), scan worker (`scan_worker_prompt.md`, `scan_steps_single.md`, `scan_steps_split.md`) and control worker (`control_prompt.md`, `control_page_steps.md`). Details, decisions and observed evidence: process-docs/pdf_workflow (text mode), process-docs/pdf_scan (scan mode) and process-docs/pdf_form (form rules of the output).
