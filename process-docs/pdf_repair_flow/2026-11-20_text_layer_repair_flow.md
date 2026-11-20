# 2026-11-20 - Text layer repair flow: extract, outline, page workers, assemble

Area: pdf_repair_flow. Worker branch `pdf-flow`, base `integration` (d8cada6), not pushed. Replaces split, resplit and merge of the area pdf_image_flow. The sample loop and publish of that area stay; the form rules of the area pdf_form are carried into the new prompts.

## Why the flow changed (facts relayed by the orchestrator)

- Image-only transcription by Haiku workers: 8 of 17 PDFs were blocked by `API Error: Output blocked by content filtering policy` and never indexed.
- On 2026-11-20 the new flow was run by hand on Scholtens & Dam 2007 (22 pages): a tool extracts the text, Haiku workers only repair it against images. None of 9 workers was blocked. Artefacts: `/tmp/pdfx_run/` and the prompts `/tmp/spawn-worker-websearch-pdf-{tables,figures,outline,pages-1-5,sample}.md` (in `/tmp`, may be gone).
- The skill `skills/websearch-pdf/SKILL.md` (user-owned, committed on integration at d8cada6) is the specification of the commands. It names `extract`, `status`, `apply-outline`, `assemble`, `sample`, `sample-report`, `sample-close`, `publish`, the manifest, `prompt_tables.md`, `prompt_figures.md`, `prompt_outline.md`, `prompt_pages_<a>-<b>.md` and the worker names `tables`, `figures`, `outline`, `pages-<a>-<b>`.

## Command flow as built

```
pdf extract --pdf <PDF> --batch-dir /tmp/pdf_<STEM>/     no model; manifest + prompts; start record
  workers tables, figures, outline write their _fixed files
pdf status --batch-dir ...                               per worker: complete | incomplete (missing: <files>)
pdf apply-outline --batch-dir ...                        headings_fixed.json -> pages/p<N>_outlined.md
  workers pages-<a>-<b> (5 pages each) write pages/p<N>_fixed.md
pdf assemble --batch-dir ...                             -> <STEM>.md with <!-- page N --> markers
sample / sample-report / sample-close / publish          unchanged behaviour (area pdf_image_flow)
```

Batch directory:

```
manifest.json  extract_log.txt  bookmarks.json  headings.json  headings_fixed.json
pages/p<N>.md  pages/p<N>_outlined.md  pages/p<N>_fixed.md  page_png/p<N>.png (150 dpi)
tables/<id>.png (200 dpi) <id>_current.md <id>_fixed.md   (id p<page>_<k>)
figures/<id>.png <id>_current.md <id>_fixed.md
prompt_tables.md prompt_figures.md prompt_outline.md prompt_pages_<a>-<b>.md
<STEM>.md  samples/run_<k>/
```

The fixed-file names equal those of `/tmp/pdfx_run`, so hand-run files could be copied one to one for the verification. The hand run's `_changes.md` files are not requested any more: no command reads them.

## User decisions (2026-11-20, fixed)

1. The page join skips content that is only placeholders, table captions and table notes; a paragraph from page 8 continues with the text on page 10 (Scholtens, table page 9 in between).
2. Glued paragraphs are split at indented lines during extract.
3. A word hyphenated over a page boundary is joined without hyphen and space. Observed: page 4 ends "may increase the ben-", page 5 starts "efits.".
4. Unreadable text is written `[unreadable]` (the hand run's form; the old prompts had `[?]`).
5. `stats` stays.
6. (after review) A figure caption directly after a figure placeholder is also skippable for the join. Observed: page 14 of Scholtens starts with Figure 3 and its caption, then "until one day after the event." which continues page 13.
7. Skill gaps the user fills himself: "send the worker its missing files" for idle and incomplete; "apply-outline or assemble FAILED = PDF not indexed, report it". Large outline or tables input (one worker for all pages or all tables): not observed, nothing built.

## Decisions taken in this session, with reasons and examples

### extract

- Converter: `pymupdf4llm.to_markdown(document, page_chunks=True, ocr_function=rapidocr_api.exec_ocr)` on an open `pymupdf.Document`. The OCR function is passed explicitly because `select_ocr_function` in `pymupdf4llm/helpers/document_layout.py` silently falls back to Tesseract when RapidOCR is missing, and Tesseract mixed two book pages line by line on Hayek ("assume an on lead to the suppression"). `rapidtess_api` (crashes in `rapidocr_391_backend.det_only`) is never used.
- The open document is passed, not the path, because pymupdf4llm OCRs and `remove_rotation`s the pages of the document it gets. Crops and page images are rendered afterwards from that same document, so bbox coordinates and rendering agree (Scholtens pages 11 and 21 are landscape: page PNG 1447x1016).
- Converter stdout: `rapidocr_api` prints "rapidocr_api using backend: rapidocr" at import, and `pymupdf.message` prints "=== Document parser messages ===" and "OCR on page.number=K/N." to the stdout object captured at pymupdf import. Both are caught by redirecting file descriptor 1 into `extract_log.txt`; `contextlib.redirect_stdout` is added because under pytest `sys.stdout` is not fd 1. The rapidocr module is loaded with `importlib.import_module` inside the redirect; a top-level import would print that line on every `cli.py` command.
- Box classes: observed on Scholtens `text`, `list-item`, `page-header`, `page-footer`, `section-header`, `caption`, `table`, `picture`; on Hayek additionally `formula` (page 18, holding `<!-- Start of picture text -->[31]<br>...`, the scan's page number). `formula` is kept as plain text for the page worker. Any other class fails extract with `unknown_box_class` (tripwire).
- Running boxes: `page-header` and `page-footer` are dropped, on page 1 kept unless the text is a bare page number (digits or roman, optionally bracketed). Scholtens page 1: "World Development Vol. 35 ..." kept, footer "1307" dropped. Empty boxes (Scholtens page 11 has `page-header` with text '') produce nothing.
- `table` and `picture` boxes always get a placeholder, crop and `_current.md`, even with an empty span (Scholtens `p1_0` logo and `p21_0` have empty spans). `section-header` spans go to `headings.json` with id `h<page>_<k>` and a placeholder.
- Paragraph split at indented lines (decision 2), only inside `text` boxes and only on pages not OCR'd. Rows of the box are rebuilt from `page.get_text("dict", clip=bbox)` with ligatures expanded (the converter writes "fi", the raw text "ﬁ"), lines grouped by bottom y within 2 pt because justified lines come back split into word pieces (Scholtens page 3: "project" at x 48.2, "ﬁnance" 85.7, "(Barclays," 123.7 on one row). A row starts a paragraph when it is not the first or last row, starts 3 to 30 pt right of the box's left edge and the next row starts at the left edge. Its first three words are searched in the converter text (markdown `*`/`_` allowed between) and an empty line is inserted before them; not found fails extract with `paragraph_start_not_found`.
    - Scholtens page 3: row "The history of the EP is described by Esty," at x 56.9 against 48.2 -> split (the sample finding of the hand run).
    - Scholtens page 2: "To find out whether the adopters of the" at x 56.9 -> split. The hand run had glued it to the paragraph before; the print shows a new paragraph.
    - Centered two-line blocks (author and affiliation on Scholtens page 1) are not split, because the indented row has no following row at the left edge.
    - Hayek (OCR on all 23 pages): the first run failed with `paragraph_start_not_found` on page 6, row "s From Prolceclionism through Planned Economy ..." against converter text "comprehens From Prolceclionism ...". OCR rows and converter text disagree, so OCR pages are skipped. Which pages were OCR'd is read from the "OCR on page.number=K/" lines in `extract_log.txt` (K is 0-based).
- Workers in the manifest: `tables` and `figures` only when ids exist, `outline` always, `pages-<a>-<b>` per 5 pages, last range shorter (`pages-21-22` for 22 pages, `pages-21-23` for 23). Each entry has `name`, `prompt` and `outputs` (paths relative to the batch directory); `status` and `assemble` judge only from these.
- Start record config: converter version, `ocr`, dpi values, `page_worker_pages`, `worker_model`, `prompt_sha` over all `prompts/*.md`, `sample_share`, `paragraph_limit_bytes`. New config hash compared with the image flow.

### Prompts

Wording taken from the hand-run prompts, plus the form rules of area pdf_form that still apply, plus the observed restrictions:
- tables: "Change nothing else. No italics, no bold, no indents, no &nbsp; ..." (without it the first hand run added italics and `&nbsp;` indents).
- figures: course and clearly readable points only, "Do not give a value for every single data point" (asked for every point, values were off by up to 0.06); "add no interpretation from outside the image, such as where the picture stands in the document or what kind of publication element it is" (sample finding on Scholtens page 22: "header", "database", "publisher banner").
- outline: bookmarks "can be incomplete or wrong ... several entries can carry the same title" (Scholtens: three appendix entries with one title); an entry that is not a heading, for example a formula, gets level 0 (`Ri ¼ a þ bRm þ error:`); the missed `line` must match a page line character for character.
- pages: `[^*]` for a symbol note (observed `[^*]` and `[^1]`); a footnote continuation gets no marker; paragraphs stay separate where the image shows a new one; quotation marks stay as they are (workers handled `‘‘ ’’` differently, assemble normalizes); `[unreadable]`.
- sample: the worker reads `page_png/p<N>.png` instead of PDF pages, as in the hand run; `[^*]`, missing italics or bold and `“ ”` for printed doubled single quotes are not findings; a figure description that states something not visible is.

### apply-outline

- Requires the `outline` worker complete. Level 1 to 4: `#`×level plus the original wording of `headings.json` without its `#` marks (the worker's `text` is not used, so a worker cannot reword a heading). Level 0: the original wording without `#`. Example: `#### Ri ¼ a þ bRm þ error:` at level 0 becomes the text line `Ri ¼ a þ bRm þ error:`.
- A missed heading must match exactly one line of `pages/p<N>.md` after stripping trailing spaces (the hand outline had "(a) Descriptives and t-test of equality of means " with a trailing space). Zero or several matches fail with `missed_heading_not_found`; nothing is written before every page is computed.
- Writes `p<N>_outlined.md` and never touches `p<N>.md`, so a second run gives the same result.

### status

- A worker is `complete` when every file in its `outputs` exists; `headings_fixed.json` additionally must be valid JSON with lists `headings` and `missed` and an entry for every id of `headings.json`. Otherwise `incomplete (missing: <files>)`. A worker that wrote nothing lists all its files. There is no separate state for a running worker.

### assemble

- Refuses once a sample run exists (`sampling_started`). Every worker complete, otherwise `FAILED (incomplete_worker)` with the list and an end record. `p<N>_outlined.md` must exist (`outline_not_applied`). The TABLE/FIGURE placeholders of `p<N>_fixed.md` must equal those of `p<N>_outlined.md` as a multiset (`placeholder_changed`).
- Page join, from page 1 upwards, repeated on the same page while it finds a continuation:
    - Body target: the last paragraph of page N that is not a heading, not a footnote definition `[^x]:` and not skippable. Footnote target: the last footnote definition.
    - Open = not ending in `. ! ? : ;` after stripping trailing `[^x]` marks and closing `” ’ " ' ) ] » * _`. Both open fails with `ambiguous_page_join` (never observed, tripwire).
    - Skippable: a placeholder line, a paragraph directly before a TABLE placeholder (caption), directly after a TABLE or FIGURE placeholder (note, figure caption), a bare page number paragraph.
    - Continuation: the first non-skippable paragraph of the following pages; a heading or footnote definition before it means no join. Joined with one space, or without space and hyphen when the target ends letter + `-`.
    - Observed results on Scholtens: 1->2 body (completed before footnote `[^*]`), 2->3, 3->4, 4->5 ("benefits."), 5->6, 6->7, 8->10 (over table page 9 and caption, table, "Source:" note on 10), 13->14 (over Figure 3 and its caption), 16->17 footnote (`[^1]` "private sector" + "projects. ..."). 12->13 is not joined because page 12 ends "linear:".
- Bare page numbers are skippable because of two observations: the hand-run `p1_fixed.md` still holds "1307", and the first verification joined page 2 onto it ("1307 costs or avoid ..."); Hayek has page numbers as `text` boxes ("iii", "[30]").
- After the join the placeholders are replaced by the fixed files, `‘‘`/`’’` become `“`/`”`, trailing spaces are stripped, every page starts with `<!-- page N -->`.

### Removed

`split.py`, `resplit.py`, `merge.py`, `pieces.py`, prompts `worker_prompt.md`, `steps_single.md`, `steps_split.md`, `chunk_steps.md`, constants `PIECE_PAGES`, `RESPLIT_PIECE_PAGES`, `BLOCKED_DIR_NAME` (the 50-page sample block is now `SAMPLE_BLOCK_PAGES` in `sample.py`), tests `test_pdf_split`, `test_pdf_resplit`, `test_pdf_merge`, `test_pdf_planning`, `test_pdf_worker_prompt`. The publish end record lists `workers` instead of `pieces`. `requirements.txt` got `pymupdf4llm==2.1`, `pymupdf-layout==2.1`, `rapidocr==3.10.0`, `onnxruntime==1.32.0`; they were installed into the venv of the main checkout (the worktree's `venv` is a symlink to it).

## Hypotheses, not observed, nothing built

- A page ending with a display formula `$$...$$` counts as open and would pull the next page's first paragraph onto the formula.
- A body paragraph directly before a table would be treated as a caption and skipped.
- A real bottom-of-page footnote whose continuation sits at the bottom of the next page: the first paragraph of that page would be joined to the footnote instead. Scholtens had endnotes at the top of the page.
- PDFs without first-line indents get no paragraph split, so a glued paragraph there stays glued.

## Verification (2026-11-20)

- Tests: 10 `test_pdf_*.py` plus `test_cli_bootstrap.py`, 73 tests pass; full suite `run_strands.sh` 90 strands, 1 skipped (browser), 0 failed. `test_cli_bootstrap` was narrowed to exit hooks from `cli` and `src.*`, because importing pymupdf registers its own `pymupdf._atexit`.
- Scholtens extract against `/tmp/pdfx_run`: 9 table `_current.md` identical, all crop and page PNG sizes identical, `bookmarks.json` identical, 2 paragraph splits (pages 2, 3). Differences: RapidOCR OCRs page 22, so the ScienceDirect logo is text plus a heading `h22_1 "# ScienceDirect"`, 6 figures instead of 7 (`p22_0` gone); heading `#` depths shift by one; figure `_current.md` of p1_0 and p21_0 empty instead of one newline. Takes about 4 s.
- Hayek extract: 23 OCR pages, 0 tables, 1 figure, 16 headings, no split, about 30 s. OCR noise remains for the page workers, e.g. "mor Sn e   e  ests" on page 6.
- Scholtens with the hand-run fixed files copied (38 files; `figures/p22_0` has no region): `status` 7 of 8, `outline: incomplete (missing: headings_fixed.json)` because `h22_1` is missing. With `h22_1` added at level 0 by hand: `apply-outline ok: 16 headings, 2 set to level 0, 4 missed headings added`, outline equal to the hand run. First `assemble`: `FAILED (placeholder_changed): page 22 ... extra placeholders [FIGURE p22_0]`; with `p22_fixed.md` replaced by `p22_outlined.md`: ok, 9 joins. Diff against `/tmp/pdfx_run/out/ScholtensDamBankingOnTheEquator_2007.md` (551 lines each): "1307" stays as its own line on page 1 (hand-run file artefact), pages 8->10 and 13->14 joined (decisions 1 and 6), page 22 OCR text instead of the logo description. The page 3 fix cannot show with the hand-run fixed pages (they predate the split); in a copy with the break kept in `p2_fixed.md` and `p3_fixed.md`, page 3 of the book starts with "The history of the EP ...".
- Not verified: no worker has run any of the new prompts. Whether Haiku keeps the indented-paragraph breaks, the placeholders and the quotation marks is unknown.

## Recap: how the work ran, what to reuse, what went wrong

Order: read everything, first reply with plan and questions, go with decisions 1 to 5, built `batch_files`, prompts, `extract`, then probed Scholtens directly in Python, then status, apply-outline, assemble, a dry run on a scratch batch with the hand-run files, then Hayek, then tests, then the verification through `cli.py` into `/tmp/pdf_<STEM>/`; review confirmed decision 6.

What to reuse:
- Probing pymupdf4llm: dump `to_markdown(..., page_chunks=True)` to JSON once (`/tmp/probe_chunks_*.json` in this session) and inspect box class, bbox and `text[pos[0]:pos[1]]` per page; the Hayek conversion takes about 30 s, Scholtens about 4 s.
- A hook blocks running `venv/bin/python ...` without redirecting its output to a file; write to `/tmp/<name>.txt 2>&1` and read the file.
- `run_strands.sh` deletes `STRAND_OUT_DIR` first; a summary file inside it disappears. Write the summary elsewhere.
- Generated test PDFs: the layout model starts a new box at every indented paragraph of a pymupdf-generated page, so the glued case cannot be reproduced with the real converter; the tests feed a fake chunk over real page geometry instead.

Mistakes, so that they are not repeated:
- A `sed -i` rename across several lines silently did nothing; check with `grep` after every scripted edit.
- The fd-level stdout redirect alone did not capture Python prints under pytest (`sys.stdout` is pytest's object there); the test exposed it.
- The first verification joined onto the bare "1307" line; check the paragraph a join attaches to, not only the moved text.
- Constants first defined twice (`WORKER_OUTLINE`, `BARE_PAGE_NUMBER`, a second `SENTENCE_END`); the duplicate scan `grep -h -E "^[A-Z_]+ = " src/pdf/*.py | awk -F' = ' '{print $1}' | sort | uniq -d` found them before the commit.

## Statements in other areas that no longer hold (recorded here, not edited there)

- Area pdf_image_flow: the command flow with `split`, `resplit`, `merge`, pieces, `blocked/`, `piece_state` and the publish end record field `pieces`; "No model runs here and no PDF text layer is read" (src/pdf now reads the text layer); the sampling worker reading PDF pages with the Read tool (it now reads `page_png/p<N>.png`).
- Area pdf_form: the `[?]` rule (now `[unreadable]`) and `outline.md` written by the orchestrator (now `headings_fixed.json` from the outline worker and `apply-outline`).
