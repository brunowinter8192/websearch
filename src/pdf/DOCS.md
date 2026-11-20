# src/pdf/

## Role

PDF to markdown tooling for the websearch-pdf skill: extracts the text layer (OCR for scans) without any model, writes prompts for the repair workers, applies their outline, assembles the book, runs the sample loop and publishes. The skill spawns the workers. Touch it when the batch layout, a worker prompt, the page join or the sample loop changes.

## Public Interface

`__init__.py` is empty. Entry path is `python cli.py pdf extract|status|apply-outline|assemble|sample|sample-report|sample-close|publish|stats`; cli.py imports the nine workflow functions. Other modules are internal.

## Flow

extract: PDF in, pymupdf4llm with RapidOCR, start record logged; page files with placeholders, table, figure and formula crops, headings, bookmarks, page images, worker prompts and manifest out. Workers write the `_fixed` files; status judges each worker by its expected files. apply-outline: the outline worker's levels into the page files the page workers read. assemble: every worker complete, fixed pages joined over page boundaries, placeholders replaced, `<STEM>.md` in the batch directory. sample loop and publish: as before, on `<STEM>.md`. stats: log in, summary text out.

## Modules

### extract.py (479 LOC)

**Purpose:** Orchestrates extract: start record, converter run, formula detection, page files with placeholders and paragraph starts split, crops, page images, worker prompts, manifest.
**Reads:** the PDF, `config/pdf_models.json`, `prompts/`.
**Writes:** the batch directory (removes its own stale files there, `samples/` and the working book); `extract_log.txt` with the converter stdout; start record or failure end record in the conversion log.
**Called by:** cli.py.
**Calls out:** pymupdf, pymupdf4llm (with pymupdf-layout), rapidocr, onnxruntime.

---

### status.py (23 LOC)

**Purpose:** Orchestrates the status command: per worker complete, or incomplete with the files still missing.
**Reads:** manifest and worker output files.
**Writes:** none.
**Called by:** cli.py.
**Calls out:** none.

---

### apply_outline.py (92 LOC)

**Purpose:** Orchestrates apply-outline: heading levels and missed headings of the outline worker into the outlined page files.
**Reads:** manifest, `headings.json`, `headings_fixed.json`, the extracted page files.
**Writes:** `pages/p<N>_outlined.md`.
**Called by:** cli.py.
**Calls out:** none.

---

### assemble.py (210 LOC)

**Purpose:** Orchestrates assemble: completeness, placeholder and heading mark checks, page boundary join, placeholder replacement, quote normalization, the working book.
**Reads:** manifest, outlined and fixed page files, fixed table, figure and formula files, `samples/` (refuses once sampling started).
**Writes:** `<STEM>.md` in the batch directory; an end record in the conversion log when a worker is incomplete or assemble fails.
**Called by:** cli.py.
**Calls out:** none.

---

### sample.py (132 LOC)

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

### stats.py (76 LOC)

**Purpose:** Orchestrates the stats command: runs, failures by reason, unfinished runs and averages from the conversion log.
**Reads:** the conversion log.
**Writes:** none.
**Called by:** cli.py.
**Calls out:** none.

---

### batch_files.py (70 LOC)

**Purpose:** Names and paths of the batch layout, placeholder lines, the bare page number pattern, JSON reading.
**Reads:** JSON files of the batch directory.
**Writes:** none.
**Called by:** extract.py, apply_outline.py, assemble.py, worker_outputs.py, sample.py.
**Calls out:** none.

---

### worker_outputs.py (42 LOC)

**Purpose:** Completeness of every worker from the files it owes, including the validity of the outline file.
**Reads:** worker output files, `headings.json`.
**Writes:** none.
**Called by:** status.py, apply_outline.py, assemble.py.
**Calls out:** none.

---

### sample_runs.py (81 LOC)

**Purpose:** Page marker lines and run files of the sample loop: loading, writing, sampled pages, loop end rule, changed excerpts and their marker check.
**Reads:** `samples/run_<k>/` files.
**Writes:** `run.json`.
**Called by:** sample.py, sample_report.py, sample_close.py, publish.py, assemble.py.
**Calls out:** none.

---

### manifest.py (22 LOC)

**Purpose:** Manifest read and write, path of the working book.
**Reads:** `manifest.json`.
**Writes:** `manifest.json`.
**Called by:** extract.py, status.py, apply_outline.py, assemble.py, sample.py, sample_close.py, publish.py.
**Calls out:** none.

---

### templates.py (27 LOC)

**Purpose:** Prompt template reading, placeholder filling and its tripwire, page-range notation.
**Reads:** `prompts/`.
**Writes:** none.
**Called by:** extract.py, sample.py.
**Calls out:** none.

---

### conversion_log.py (73 LOC)

**Purpose:** Append-only JSONL conversion log: path, record writer and reader, end-record builder, failure logging.
**Reads:** `WEBSEARCH_CONVERSION_LOG_PATH` from the environment; the log file.
**Writes:** `src/logs/conversions.jsonl` (gitignored, not pruned by the janitor).
**Called by:** extract.py, assemble.py, publish.py, stats.py.
**Calls out:** none.

---

### report.py (15 LOC)

**Purpose:** Result type of the workflows and the error type that carries a failure class.
**Reads:** none.
**Writes:** none.
**Called by:** every workflow module, batch_files.py, templates.py, manifest.py, sample_runs.py, conversion_log.py, cli.py.
**Calls out:** none.

---

## State

None in memory. Persistent state is the conversion log under `src/logs/` and the batch directory: extract writes the manifest, prompts, `pages/p<N>.md`, `page_png/`, `tables/`, `figures/` and `formulas/` crops with `_current.md`, `headings.json`, `bookmarks.json`; workers write the `_fixed` files and `headings_fixed.json`; apply-outline writes `pages/p<N>_outlined.md`; assemble and sample-close write `<STEM>.md`; sample and the sampling worker write `samples/run_<k>/`.

Prompt templates live in `prompts/`: repair workers (`tables_prompt.md`, `figures_prompt.md`, `formulas_prompt.md`, `outline_prompt.md`, `pages_prompt.md`) and sampling worker (`sample_prompt.md`, `sample_excerpt_steps.md`). Details, decisions and observed evidence: process-docs/pdf_repair_flow (this design), process-docs/pdf_image_flow (the sample loop and the earlier image-only flow), process-docs/pdf_form (form rules).
