# src/pdf/

## Role

PDF to markdown tooling for the websearch-pdf skill: splits a PDF into page-range pieces with ready worker prompts, splits a blocked piece further, merges the piece files, runs the sample loop in which a sampling worker corrects excerpts, and publishes the book. No model runs here and no PDF text layer is read; the skill spawns the workers. Touch it when the piece protocol, the sample loop or the log changes.

## Public Interface

`__init__.py` is empty. Entry path is `python cli.py pdf split|resplit|status|merge|sample|sample-report|sample-close|publish|stats`; cli.py imports the nine workflow functions. Other modules are internal.

## Flow

split: PDF in, page count from `pdfinfo`, start record logged, one prompt per 50-page piece and the manifest out. Workers write the piece files. status: each piece judged complete, incomplete or missing by its page marker lines. resplit: one blocked, not complete piece in the manifest is replaced by smaller pieces with new prompts, its leftover files set aside. merge: all pieces complete, joined in page order into `<STEM>.md` in the batch directory. sample loop: `sample` draws new pages and cuts excerpts, the sampling worker corrects excerpts, `sample-report` shows every correction, `sample-close` writes the accepted ones back. publish: after the loop ended, paragraphs split to the embedder limit, `<STEM>.md` written to the output directory, end record logged. stats: log in, summary text out.

## Modules

### split.py (155 LOC)

**Purpose:** Orchestrates the split command: page count, start record, 50-page pieces with their prompts, manifest, cleanup of its own stale files.
**Reads:** the PDF (sha256 and `pdfinfo` page count only), `config/pdf_models.json`, `prompts/`.
**Writes:** prompts and manifest in the batch directory (removes its own stale files there, the merged book, `samples/` and `blocked/`); start record in the conversion log.
**Called by:** cli.py.
**Calls out:** poppler (`pdfinfo`).

---

### resplit.py (73 LOC)

**Purpose:** Orchestrates resplit: one blocked, not complete piece becomes pieces of the next smaller size with prompts, leftovers set aside; no smaller size means refusal.
**Reads:** manifest and piece files in the batch directory.
**Writes:** manifest, new prompts; removes the prompt of the replaced piece; moves its incomplete piece file and part files into `blocked/`.
**Called by:** cli.py.
**Calls out:** none.

---

### status.py (34 LOC)

**Purpose:** Orchestrates the status command: per piece complete, incomplete with the pages whose marker is missing, or missing.
**Reads:** manifest and piece files.
**Writes:** none.
**Called by:** cli.py.
**Calls out:** none.

---

### merge.py (74 LOC)

**Purpose:** Orchestrates the merge command: every piece complete, join in page order into the working book.
**Reads:** manifest, piece files, `samples/` (refuses once sampling started).
**Writes:** `<STEM>.md` in the batch directory; an end record in the conversion log when a piece is missing or incomplete or merge fails.
**Called by:** cli.py.
**Calls out:** none.

---

### sample.py (125 LOC)

**Purpose:** Orchestrates the sample command: draws the pages of the next run among pages never sampled, cuts excerpts, writes the run file and the sampling prompt.
**Reads:** manifest, the working book, earlier run files.
**Writes:** `samples/run_<k>/` with excerpt files, `run.json` and `prompt.md`.
**Called by:** cli.py.
**Calls out:** none.

---

### sample_report.py (79 LOC)

**Purpose:** Orchestrates the sample-report command: report of the open run with sampled pages, worker findings and every correction before and after.
**Reads:** the open run file, its excerpt files and `findings.md`.
**Writes:** `report.md` in the run directory.
**Called by:** cli.py.
**Calls out:** none.

---

### sample_close.py (77 LOC)

**Purpose:** Orchestrates the sample-close command: writes accepted excerpt corrections into the working book, closes the run, states whether the loop continues.
**Reads:** manifest, the open run file, its excerpt files and `findings.md`, the working book.
**Writes:** the working book, the run file.
**Called by:** cli.py.
**Calls out:** none.

---

### publish.py (156 LOC)

**Purpose:** Orchestrates the publish command: refuses before the sample loop ended, splits over-long paragraphs, atomic write of `<STEM>.md` to the output directory.
**Reads:** manifest, run files, the working book.
**Writes:** the markdown file in the output directory (atomic); the ok end record in the conversion log.
**Called by:** cli.py.
**Calls out:** none.

---

### sample_runs.py (72 LOC)

**Purpose:** Run files of the sample loop: loading, writing, sampled pages, loop end rule, changed excerpts and their marker check.
**Reads:** `samples/run_<k>/` files.
**Writes:** `run.json`.
**Called by:** sample.py, sample_report.py, sample_close.py, publish.py, merge.py.
**Calls out:** none.

---

### pieces.py (93 LOC)

**Purpose:** Piece planning, the rendered transcription worker prompt with its part files and concatenation command, page markers and the completeness state of a piece file.
**Reads:** `prompts/`, piece files.
**Writes:** prompt files.
**Called by:** split.py, resplit.py, status.py, merge.py, sample.py, sample_runs.py.
**Calls out:** none.

---

### manifest.py (22 LOC)

**Purpose:** Manifest read and write, path of the working book.
**Reads:** `manifest.json`.
**Writes:** `manifest.json`.
**Called by:** split.py, resplit.py, status.py, merge.py, sample.py, sample_close.py, publish.py.
**Calls out:** none.

---

### templates.py (27 LOC)

**Purpose:** Prompt template reading, placeholder filling and its tripwire, page-range notation.
**Reads:** `prompts/`.
**Writes:** none.
**Called by:** pieces.py, sample.py, split.py.
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
**Called by:** split.py, merge.py, publish.py, stats.py.
**Calls out:** none.

---

### report.py (15 LOC)

**Purpose:** Result type of the workflows and the error type that carries a failure class.
**Reads:** none.
**Writes:** none.
**Called by:** every workflow module, templates.py, manifest.py, sample_runs.py, conversion_log.py, cli.py.
**Calls out:** none.

---

## State

None in memory. Persistent state is the conversion log under `src/logs/` and the batch directory: manifest and prompts written by split and resplit, piece files by the workers, `blocked/` by resplit, the working book by merge and sample-close, `samples/run_<k>/` by sample and the sampling worker.

Prompt templates live in `prompts/`: transcription worker (`worker_prompt.md`, `steps_single.md`, `steps_split.md`, `chunk_steps.md`) and sampling worker (`sample_prompt.md`, `sample_excerpt_steps.md`). Details, decisions and observed evidence: process-docs/pdf_image_flow (this design), process-docs/pdf_form (form rules), process-docs/pdf_workflow and process-docs/pdf_scan (the earlier text and scan modes).
