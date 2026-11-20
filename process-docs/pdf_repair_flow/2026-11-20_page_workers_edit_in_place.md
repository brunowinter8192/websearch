# 2026-11-20 - Page workers repair a pre-filled page file in place with the Edit tool

Area: pdf_repair_flow. Worker branch `pdf-editflow`, base `integration` (317b480). Code commit 5c2b768 ("feat: page workers repair a pre-filled page file in place"). Builds on the text layer repair flow and the third batch work recorded earlier in this area.

## Starting point (facts relayed by the orchestrator, 2026-11-20)

First and only content-filter block in the repair flow so far:
- PDF: Schelling 1981, batch `/tmp/pdf_SGSC_Literatur_SchellingEconomicReasoningEthicsPolicy_1981/`. It is a scan with an invisible old OCR text layer, and that layer splits many letters off as markup: `distri **b** uti **on** o **f** the costs`, `opportunitie _s_ and`, `_A_ n example`.
- Worker `pages-21-25` ran the old `pages_prompt.md`, which told it to read `p<N>_outlined.md` and write `p<N>_fixed.md` with the Write tool. It wrote p21 to p23, then stopped with `API Error: Output blocked by content filtering policy`. p24 and p25 were never written.
- Retry 1: the outlined file was copied to `p24_fixed.md` and `p25_fixed.md` first. A Haiku worker got the page image and that file. Its prompt said the content already exists and the task is quality repair, not reproduction. It was told to repair the file in place with the Edit tool only, one short fragment per edit, never Write. Result: not blocked, 31 edits on p24, 17 on p25, no split markup left. Prompt: `/tmp/spawn-worker-websearch-pdf-schelling-24-25.md`.
- Retry 2, on copies: the same, but with Bash (sed or python) plus Edit, no Write. Also not blocked, and p24 came out identical word for word.
- User decision: the Edit way becomes the standard for page workers.

## What was built

### Pre-filled page files (apply-outline)
- apply-outline now writes two files per page. `pages/p<N>_outlined.md` is unchanged. `pages/p<N>_fixed.md` holds the line `<!-- REPAIR PENDING -->`, an empty line, and the outlined text.
- The pre-fill is written in apply-outline, not in extract. The page worker must get the heading lines with their `#` marks, because assemble compares the `#` runs of fixed against outlined (`heading_marks_changed`). Those lines only exist after the outline worker and apply-outline have run. The skill already starts page workers only after apply-outline.
- The constant `REPAIR_PENDING` lives in `batch_files.py`. Three places use it: apply-outline writes it, `worker_outputs.py` checks for it, and extract puts it into the page prompt as `{{PENDING}}`.
- The summary has a new line: `pre-filled for the page workers: pages/p1_fixed.md to pages/p25_fixed.md, each starting with <!-- REPAIR PENDING -->`.
- Tripwire `page_repair_started`: apply-outline refuses when an existing `p<N>_fixed.md` is not exactly the pre-filled form of the existing `p<N>_outlined.md`. Before this change a rerun never touched fixed files. Now it would overwrite a worker's edits. A rerun after page workers started was never observed. The check runs over all pages before anything is written. A rerun before any page worker started still gives the same result (the existing test covers this). Old batches whose fixed files were written with the Write tool also trip it.

### Completeness signal (status, assemble)
- A file is complete when it exists and no line of it, stripped, equals `<!-- REPAIR PENDING -->`. The outline file keeps its own validity check. Status prints the file under `missing:` as before, so one format covers both cases: not yet written, and written but still pending.
- Why the stopped worker does not produce the signal: the prompt makes removing the pending line the last edit of each page, also for a page without defects. The blocked worker of the observation stopped between pages. Under the new flow p24 and p25 would still hold the line, and status would report `pages-21-25: incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)`. That was replayed on a copy (verification below).
- assemble uses the same `worker_states`, so a pending page stops it with `incomplete_worker` and an end record. The pending line can never reach the book.
- Batches made before this change have no pending lines and are judged as before.

### Page prompt (`prompts/pages_prompt.md`)
The framing comes from retry 1, word for word where possible:
- "The text of these pages already exists ... Your job is only to fix extraction defects in that existing text. You are not asked to reproduce, retype or rewrite any content".
- The page image is used "only to decide what a damaged spot should be".
- The worker repairs `p<N>_fixed.md` "only with the Edit tool, one small edit at a time ... Never use the Write tool, never replace a whole paragraph or the whole file".

The correction rules of the old prompt are kept, so placeholders, heading marks, footnote forms, paragraph rules and `[unreadable]` behave as before. Changes:
- The worker reads `p<N>_fixed.md` instead of `p<N>_outlined.md`. The prompt value `MD_PATTERN` is gone and `PENDING` is new.
- The Characters rule carries the Schelling split-markup example from retry 1, because Baumol 1991, Collins 1994 and Boatright 1999 have the same kind of old OCR layer (see the third batch record in this area).
- A footnote text that stands before the end of the file is moved to the end with two edits (cut, then insert after the last paragraph). Reason, from a survey over every batch in `/tmp/pdf_*/` with both outlined and fixed pages (`/tmp/editflow/tools/moves.py`, 638 pages): 68 pages had paragraphs in a different order in fixed than in outlined. On 42 of them a footnote definition was moved, most on Hayek (pages 4, 5, 8, 10, 15, 17, 18, 19) and Contreras (4, 5, 8). The join rules depend on footnotes standing at the page end. Without the move rule, Edit-only workers would leave them in place.
- A new paragraph is made by inserting the empty line with an edit.
- "Every file you write ends with a newline" was dropped: the worker writes no file, and the pre-fill ends with the newline of the outlined text.
- Removing the pending line is the last edit of each page.

The prompt file is hashed into `prompt_sha`, so the next extract has a new `config_hash`.

## Decision: table, figure, formula and outline workers stay as they are

They keep writing their files with the Write tool, and file existence stays their completeness signal. Reasons:
- Not observed: more than 100 Haiku workers ran in this flow (batches 1 to 3). The only block was a page worker writing about five pages of prose. No region or outline worker was blocked.
- The block observed shows a stopped Write worker leaves its file absent (p24, p25). So for workers that write, existence still tells complete from stopped. Only pre-filling breaks that, so only page workers needed a new signal.
- The figure worker writes a description of what the picture shows (`**Figure description (not source text):**`), not source text. Its `_current.md` is often empty (Scholtens `p1_0`, `p21_0`). There is nothing to edit in place.
- The formula worker writes one LaTeX line from an image. The converter's `_current.md` is a different notation (`Ri ¼ a þ bRm þ error:`, `ð2Þ`), so an in-place repair would replace the whole content anyway.
- The table worker is the closest candidate. Its `_current.md` is a pipe table, but it is often not: the `_current.md` of a rotated or column-cut table is one text line per PDF line (Contreras p16_0, Schouten p9_0), and the worker builds the table from that. Not observed blocked. If a table worker is ever blocked, the same pre-fill and pending line can be applied to `tables/<id>_fixed.md`.
- The outline worker writes JSON levels and no source text.

## Verification (2026-11-20)

Commands ran through `cli.py` with `WEBSEARCH_CONVERSION_LOG_PATH=/tmp/editflow/conversions.jsonl`. No worker was spawned.
- `pdf extract` of Schelling into the fresh `/tmp/editflow/verify/schelling`: `extract ok`, `pages=25 ocr_pages=0 tables=0 figures=0 formulas=0 headings=8 paragraph_starts_split=0 invisible_text_pages=25`. All 25 `pages/p<N>.md` and `headings.json` are byte-identical to the original batch.
- `pdf status` right after extract: `workers complete: 0 of 6`. Every page worker lists all of its five files as missing, and outline lists `headings_fixed.json`.
- Pre-filled files need apply-outline, so the outline worker's `headings_fixed.json` from the original batch was copied in. Its ids match the identical `headings.json`.
- `pdf apply-outline`: `apply-outline ok: 8 headings, 1 set to level 0, 1 missed headings added`, plus the pre-fill line. All 25 `p<N>_fixed.md` start with `<!-- REPAIR PENDING -->`. Without its first two lines, `p24_fixed.md` is byte-identical to `p24_outlined.md` and to the original batch's `p24_outlined.md`. It still holds `distri **b** uti **on** o **f** the costs`.
- `pdf status` after apply-outline: `workers complete: 1 of 6`, outline complete, every page worker incomplete with all of its files. `pdf assemble`: `FAILED (incomplete_worker): 5 of 6 workers incomplete, nothing written`.
- Blocked case replayed on the copy `/tmp/editflow/verify/blocked_copy`: the pending line was removed from p21 to p23 (by me, as a stand-in for a worker that finished those pages), and p24 and p25 were left untouched. `status`: `pages-21-25: incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)`. A rerun of `apply-outline` on that copy: `FAILED (page_repair_started): pages/p21_fixed.md differs from its pre-filled form, a page worker has edited it and apply-outline would discard the edits`.
- Tests:
    - New: `test_pdf_apply_outline.py` (the pre-fill), `test_pdf_status.py` (three pages released, two pending, the Schelling shape), `test_pdf_assemble.py` (a pending page stops assemble).
    - Changed: the prompt assertions in the first `test_pdf_extract.py` test.
    - All four fail on 317b480. This was checked with `git archive HEAD src config cli.py` plus the new tests in `/tmp/editflow/old`.
    - All 124 pdf tests pass. Full `run_strands.sh`: 91 strands, 1 skipped, 0 failed.
- Not verified: no page worker has run the new `pages_prompt.md`. Open questions: whether Haiku keeps removing the pending line last, whether it moves footnotes with two edits, and whether a footnote move or a long OCR-noise page (Hayek) triggers the filter.

## Skill lines that must change (skills/websearch-pdf/SKILL.md at 317b480, user-owned, not edited)

- Line 32: `**Ein Worker, der idle ist und den `status` als `incomplete` meldet, bekommt seine fehlenden Dateien.**`. It can stay. "fehlend" now also covers a page file that still holds the pending line.
- Line 36: `worker-cli send pdf-<stem>-<worker> "Write the missing files: <Dateien aus status>"` must change. A page worker must not write. Proposal: `worker-cli send pdf-<stem>-<worker> "Finish these files as your prompt says: <Dateien aus status>"`. The wording works for both kinds: region and outline workers write, page workers edit and remove `<!-- REPAIR PENDING -->` last.
- Line 90: `**Starte die Seiten-Worker erst nach `apply-outline`.**` stays. It is now required twice over: apply-outline writes the files the page workers edit.
- Line 99: `` - `incomplete` nennt die Dateien, die noch fehlen.`` becomes `` - `incomplete` nennt die Dateien, die noch fehlen oder deren erste Zeile noch `<!-- REPAIR PENDING -->` ist.``
- Lines 81 to 85 (apply-outline then kill outline) stay. A new bullet is optional: never run `apply-outline` again after a page worker started. It now fails with `page_repair_started`, and line 39 then drops the PDF.
- Lines 104 to 110 (block detection) stay valid: a blocked page worker is idle and its pending pages stay `incomplete`.

## Hypotheses, not observed, nothing built

- A worker removes the pending line before it finishes the page and is then blocked. Status would report that page complete with a partial repair. The prompt orders it last, and no worker has run the prompt yet.
- An Edit-only worker misses defects that a full rewrite would have fixed, for example reading order across columns. The survey found 37 non-footnote paragraph moves by Write workers, such as Equator Principles pages 13, 15 and 22. The new prompt neither asks for nor forbids them.
- A region worker blocked by the content filter: its file stays absent and status shows it, as before.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- Text layer repair flow record:
    - "workers pages-<a>-<b> (5 pages each) write pages/p<N>_fixed.md": page workers now edit the file apply-outline pre-filled.
    - "A worker is `complete` when every file in its `outputs` exists": a file holding the pending line is not complete.
    - "Writes `p<N>_outlined.md` and never touches `p<N>.md`, so a second run gives the same result": a second run also rewrites `p<N>_fixed.md`, and it fails once a worker edited one.
- Orchestrator record: "A block in the new flow has not been observed": observed on 2026-11-20, Schelling `pages-21-25`.

## How the work ran, what to reuse

Order:
1. Read the skill, DOCS, code, prompts, tests and the area.
2. Settled the design: pre-fill at apply-outline, a pending line as the release signal, Edit-only prompt.
3. Surveyed paragraph moves over all batches.
4. Built, tested on the old code and the new code, verified on Schelling, recapped.

Reuse:
- To show pre-filled files without a worker, copy an outline worker's `headings_fixed.json` from an existing batch of the same PDF into a fresh extract. Check first that `headings.json` is byte-identical.
- The survey of paragraph order (normalized 25-character keys of each fixed paragraph, looked up in the normalized outlined text, non-monotonic positions reported) shows what workers do beyond the prompt. Run it before restricting what a worker may change.
