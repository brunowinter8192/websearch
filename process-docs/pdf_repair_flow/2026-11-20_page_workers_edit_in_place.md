# 2026-11-20 - Edit-only fallback for a page worker blocked by the content filter

Area: pdf_repair_flow. Worker branch `pdf-editflow`, base `integration` (317b480).

Commits:
- 5c2b768: first design, the Edit flow for every page worker. Reverted by the next commit.
- Its revert commit.
- "feat: edit-only fallback for a page worker blocked by the filter": the final design.

Builds on the text layer repair flow and the third batch work recorded earlier in this area.

## Starting point (facts relayed by the orchestrator, 2026-11-20)

First and only content-filter block in the repair flow so far:
- PDF: Schelling 1981, batch `/tmp/pdf_SGSC_Literatur_SchellingEconomicReasoningEthicsPolicy_1981/`. It is a scan with an invisible old OCR text layer, and that layer splits many letters off as markup: `distri **b** uti **on** o **f** the costs`, `opportunitie _s_ and`.
- Worker `pages-21-25` ran the normal `pages_prompt.md`, which tells it to read `p<N>_outlined.md` and write `p<N>_fixed.md` with the Write tool. It wrote p21 to p23, then stopped with `API Error: Output blocked by content filtering policy`. p24 and p25 were never written.
- Retry 1: the outlined file was copied to `p24_fixed.md` and `p25_fixed.md`. A Haiku worker got the page image plus that file, the statement that the content already exists and the task is quality repair only, and the order to edit in place with the Edit tool, one short fragment per edit, never Write. Result: not blocked, 31 edits on p24, 17 on p25, no split markup left. Prompt: `/tmp/spawn-worker-websearch-pdf-schelling-24-25.md`. Its output stands as `p24_fixed.md` and `p25_fixed.md` in the original batch.
- Retry 2, on copies: Bash (sed or python) plus Edit, no Write. Also not blocked, and p24 came out identical word for word.

## Scope history (user decisions)

1. First order: the Edit way becomes the standard for every page worker. Built in 5c2b768: apply-outline pre-filled every `p<N>_fixed.md`, the normal page prompt became edit-only, and apply-outline got a tripwire against overwriting edits.
2. Second order, after that commit: the normal flow stays exactly as it was. Workers write with Write as before. The Edit way is only a fallback for a worker blocked by the content filter. 5c2b768 was reverted with `git revert`. Afterwards `git diff integration` is empty for `extract.py`, `apply_outline.py`, `assemble.py`, `status.py`, `pages_prompt.md` and their tests.

## What was built (final)

### Command `pdf fallback --batch-dir <DIR> --worker <name>` (`src/pdf/fallback.py`)
- It looks up the worker in the manifest.
- It takes as missing the pages whose `p<N>_fixed.md` status counts as missing.
- It writes each of them as `<!-- REPAIR PENDING -->`, an empty line, and the content of `p<N>_outlined.md`.
- It writes the prompt `prompt_fallback_<worker>.md` from the template `prompts/fallback_pages_prompt.md`.
- The main agent spawns one new worker with that prompt.
- Files the blocked worker already wrote (p21 to p23) are not touched.
- The pre-fill source is `p<N>_outlined.md`, the text the blocked worker would have read, with the heading levels. So the `#` runs and the placeholders match what assemble compares against.
- Output on the Schelling copy:
  ```
  fallback ok: pages-21-25
  pre-filled from the outlined pages: pages/p24_fixed.md pages/p25_fixed.md
  each starts with <!-- REPAIR PENDING -->; status counts a page as done once its fallback worker removed that line
  prompt: <batch>/prompt_fallback_pages-21-25.md
  ```
- Tripwires, none of these conditions was observed:
    - `unknown_worker`: the name is not in the manifest.
    - `fallback_not_observed`: the worker has no `pages` entry, so it is a table, figure, formula or outline worker.
    - `nothing_missing`: every page file is complete.
    - `fallback_started`: a missing page file already exists. A second fallback on the same pages would overwrite the edits of the first; the user rule says a blocked fallback worker means the PDF is not indexed.
    - `outline_not_applied`: `p<N>_outlined.md` is absent.
- extract's stale-file cleanup already removes `prompt_fallback_*.md` (pattern `prompt_*.md`) together with `pages/`.
- The new template is hashed into `prompt_sha`, so the next extract has a new `config_hash`, although the normal prompts are unchanged.

### Fallback prompt (`prompts/fallback_pages_prompt.md`)
Wording and rules of retry 1, generalized from "two pages 24 and 25" to `For each page N in {{PAGES}}` (here `24, 25`):
- The content already exists; the task is quality repair only, not reproduction.
- The image is used only to decide a damaged spot.
- Edit tool only, one short fragment per edit, never Write, never a whole paragraph or file.
- Fix only split-off markup, wrong characters and footnote markers.
- Leave wording, order, paragraphs, `#` lines and `<!-- ... -->` lines exactly as they are.

Two additions:
- "or by OCR" in the source sentence.
- Step 5: remove the first line `<!-- REPAIR PENDING -->` with one last Edit when the page is repaired, also when it needed no repair, and only then go to the next page. Step 4 names step 5 as its only exception, because step 4 otherwise forbids touching `<!-- ... -->` lines.

The Schelling markup example from retry 1 stays as "Typical defects". It names the defect class of the old OCR layers (Schelling, Baumol, Collins, Boatright).

### Completeness signal (`worker_outputs.py`, used by status, apply-outline and assemble)
- A file is complete when it exists and no line of it, stripped, equals `<!-- REPAIR PENDING -->`. The outline file keeps its own check.
- In the normal flow no file ever holds the line, so status behaves as before.
- Why a worker that stops early does not produce the signal: the line goes only when a page is finished, as the last edit of that page. A fallback worker blocked like the first one stops between edits, and every page it did not finish keeps the line.
- Status prints such a file under `missing:`, like an absent file. assemble refuses with `incomplete_worker`, so the line never reaches the book. On the Schelling copy, after assemble the marker occurs only in `prompt_fallback_pages-21-25.md`.

## Decision: the fallback covers page workers only

- Observed: one block, in a page worker. Across batches 1 to 3, more than 100 Haiku workers ran, and no table, figure, formula or outline worker was blocked. Building a fallback for an unobserved block is YAGNI; those workers stop at the tripwire `fallback_not_observed`.
- No usable pre-fill exists for most of them:
    - Figure descriptions are new text (`**Figure description (not source text):**`), and `_current.md` is often empty (Scholtens `p1_0`, `p21_0`).
    - Formulas are written as LaTeX from a different converter notation (`Ri ¼ a þ bRm þ error:`, `ð2Þ`).
    - The outline is JSON with levels, not source text.
    - Tables come closest. But `_current.md` of a rotated or column-cut table is one text line per PDF line (Contreras p16_0, Schouten p9_0), not a table to repair in place.
- If such a block is observed, the tripwire shows it. For tables, pre-filling `tables/<id>_fixed.md` from `_current.md` under the same pending line would be the direct extension.

## Verification (2026-11-20)

Copy of the original Schelling batch at `/tmp/editflow/verify2/schelling`. The original batch was not modified. The retry-1 outputs `p24_fixed.md` and `p25_fixed.md` were saved to `/tmp/editflow/verify2/retry1/` first, then deleted in the copy to simulate the block. No worker was spawned. Commands ran through `cli.py` with `WEBSEARCH_CONVERSION_LOG_PATH=/tmp/editflow/conversions.jsonl`.

| step | `pages-21-25` in `status` |
|---|---|
| blocked (p24, p25 deleted) | `incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)` |
| after `pdf fallback` (pre-filled, no worker yet) | `incomplete (missing: pages/p24_fixed.md pages/p25_fixed.md)` |
| simulated stop after p24 (retry-1 p24 copied in, p25 still pre-filled) | `incomplete (missing: pages/p25_fixed.md)` |
| simulated finished fallback worker (retry-1 p25 copied in) | `complete`, `workers complete: 6 of 6` |

- The pre-filled `p24_fixed.md` starts `<!-- REPAIR PENDING -->`, then an empty line, then `done cleverly to disguise the size **an** d distri **b** uti **on** o **f** the costs`. Below the pending line it is byte-identical to `p24_outlined.md`. The same holds for p25 (`c **o** st at regulated prices`).
- A second `pdf fallback` on the copy: `FAILED (fallback_started): pages/p24_fixed.md already exists as a pre-filled file`.
- After `samples/` was removed from the copy, `pdf assemble` gave `assemble ok`, 25 pages, 20 joins including 23->24 and 24->25. So the retry-1 edit output passes the placeholder and heading-mark checks.
- Tests:
    - New: `dev/tests/test_pdf_fallback.py`, 3 tests. They cover the pre-fill and the prompt, the status and assemble signal through an early stop to finished, and the non-page-worker tripwire.
    - Changed: `test_pdf_cli.py` parses `fallback --worker`.
    - On integration 317b480 the new module test fails at import (`No module named 'src.pdf.fallback'`) and the CLI test fails. Checked with `git archive integration src config cli.py` plus the new tests in `/tmp/editflow/old2`.
    - All 124 pdf tests pass. Full `run_strands.sh`: 92 strands, 1 skipped, 0 failed.
- Not verified: no worker has run `fallback_pages_prompt.md` as generated. Retry 1 ran an equivalent prompt without the pending-line step.

## Skill block section (skills/websearch-pdf/SKILL.md at 317b480, lines 102 to 110, user-owned, not edited)

Replace lines 108 to 110 (`1. Kille alle Worker dieses PDFs.` / `2. Notiere das PDF, den Worker und die fehlenden Dateien für den Report.` / `3. Mach mit dem nächsten PDF weiter.`) with:

```
1. Kille den geblockten Worker.
2. Bereite den Fallback vor und lies die Ausgabe vollständig.

   ```bash
   WORKFLOW fallback --batch-dir BATCH_DIR --worker <worker> > /tmp/pdf_<STEM>_fallback.txt 2>&1
   ```

3. Starte einen neuen Worker mit dem Fallback-Prompt.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<worker>-fallback BATCH_DIR/prompt_fallback_<worker>.md
   ```

4. Rufe `status` auf, bis `<worker>` `complete` ist.
5. Notiere das PDF und den Worker für den Report als geblockt und per Fallback repariert.

**Wird auch der Fallback-Worker geblockt, wird das PDF nicht indexiert.**
- Kille alle Worker dieses PDFs.
- Notiere das PDF, den Worker und die fehlenden Dateien für den Report.
- Mach mit dem nächsten PDF weiter.
```

Further lines:
- Lines 104 to 106 (block detection) stay. They also detect a blocked fallback worker: it is idle, `status` still shows `<worker>` `incomplete`, and its response shows the filter error.
- Line 33 (`Prüfe zuerst, ob er geblockt wurde, wie in Step 3 beschrieben.`) stays.
- Line 36 (`"Write the missing files: <Dateien aus status>"`) is wrong for an idle fallback worker that is not blocked, because it must not write. For that case: `worker-cli send pdf-<stem>-<worker>-fallback "Repair these files as your prompt says: <Dateien aus status>"`.
- Line 196 (report `Geblockte Worker: <PDF, Worker, oder "keine">`) can become `Geblockte Worker: <PDF, Worker, per Fallback repariert oder nicht indexiert, oder "keine">`.
- `fallback FAILED (fallback_not_observed)` (a blocked table, figure, formula or outline worker) needs a line in the block section: the PDF is not indexed, as before.

## Hypotheses, not observed, nothing built

- A fallback worker removes the pending line before it finishes the page and is then blocked. Status would count that page as complete with a partial repair. The prompt orders the removal last.
- A page that needs more than retry 1's rules (paragraph splits from the image, a footnote moved to the page end, a display formula as `$$...$$`) keeps those defects under the fallback. Retry 1's rule 3 allows only markup, characters and footnote markers.
- A blocked worker that wrote no page at all: all its pages are pre-filled. Only the case with some pages written was observed.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- Orchestrator record: "A block in the new flow has not been observed. The skill therefore only aborts the PDF and reports it, without a resplit path." A block was observed on 2026-11-20 (Schelling `pages-21-25`), and the fallback is the path.
- Text layer repair flow record: "A worker is `complete` when every file in its `outputs` exists". A file holding the pending line is not complete.

## How the work ran, what to reuse, what went wrong

Order:
1. Read the skill, DOCS, code, prompts, tests and the area.
2. Built the first design (every page worker edits in place) and verified it on a fresh Schelling extract.
3. Scope change: reverted the commit, kept the pending-line signal, built the separate `fallback` command.
4. Verified on a copy of the original batch with the retry-1 outputs as the simulated finished worker.

Reuse:
- The retry-1 outputs in the original batch give a real finished fallback result for simulations. Save them before deleting the files in a copy.
- A survey over all batches (`/tmp/editflow/tools/moves.py`) compared paragraph order in `p<N>_fixed.md` against `p<N>_outlined.md`. Of 638 pages, 68 had reordered paragraphs, 42 of them with a footnote definition moved, mostly Hayek and Contreras. Edit-only workers with retry 1's rules will not do this, which is one more reason to keep Write as the normal flow.

Mistake: the first design was built on the reading "the Edit way becomes the standard" without asking whether it should replace the normal flow or only the blocked case. A short question before building would have saved the revert.
