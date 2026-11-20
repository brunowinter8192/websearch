# 2026-11-20 - Third batch: invisible OCR text layers over scans, missed heading named on the wrong page

Area: pdf_repair_flow. Worker branch `pdf-batch3`, base e07cc18. Code commits fa2b931 ("fix: no paragraph split on pages with an invisible OCR text layer") and 118d00a ("fix: apply-outline finds a missed heading named on the wrong page"). Builds on the earlier extract and outline work in this area.

## Starting point (2026-11-20)

Three failures from batch 3. The batch directories `/tmp/pdf_SGSC_Literatur_<stem>/` were never modified. All experiments ran under `/tmp/b3/`.

| PDF | failure |
|---|---|
| Baumol 1991, `BaumolPerfectMarketsEasyVirtue_1991` (14 pages) | `extract FAILED (paragraph_start_not_found): page 10: indented line 'tribute most effectively toward that goal not by attempts to' not found in the converter text` |
| Schelling 1981, `SchellingEconomicReasoningEthicsPolicy_1981` (25 pages) | `extract FAILED (paragraph_start_not_found): page 1: indented line 'Discomfort also arises when, intent on speeding toward an ever-' not found in the converter text` |
| Brennan 2012, `BrennanForProfitBusinessCivicVirtue_2012` (12 pages) | `apply-outline FAILED (missed_heading_not_found): page 3: the line 'Open Questions About Civic Virtue' occurs 0 times in pages/p3.md, it must occur once` |

## What the two scans contain

Both PDFs are scans with an OCR text layer from an older tool. pymupdf4llm did not OCR them (`ocr_pages=0`), because a text layer exists.
- Baumol: creator `Acrobat 5.0 Scan Plug-in`, producer `Adobe Acrobat 8.13 Paper Capture Plug-in`, font `HiddenHorzOCR` on most pages. Every page has one image covering the whole page.
- Schelling: producer `Pdf-It version 6.2`. Every page has one image covering the whole page.
- In both, every text trace on every page has `type` 3 in `page.get_texttrace()`, which means invisible text.

Survey of `get_texttrace()` types over all 39 SGSC PDFs in `rag-cli/data/pdf/wise2627/`:
- Only type 3: Baumol (14 of 14 pages), Schelling (25 of 25), Collins 1994 (8 of 8, not yet run).
- Types 0 and 3: Boatright 1999, 9 pages. These pages stay on the split path.
- Every born-digital PDF has only types 0 and 1, including Scholtens, Wright, Contreras, Heilmayr, Meyerstein and Brennan.
- Hayek has no text layer at all.

### Schelling page 1: markup inside words
The row `Discomfort also arises when, ...` (x 53 against the left edge 42/43) is a real paragraph start. The text layer sets nearly every `o` in Times-Bold and some commas in Times-Italic. The converter therefore writes `Disc **o** mf **o** rt als **o** arises when _,_ intent`. `locate_row` allows markup only between words, so the needle `Discomfort also arises` was not found.

### Baumol page 10: specks of the OCR layer move the left edge
- The text box `[104, 320, 392, 531]` has rows at x 117.7 to 118.8. On the row of `institute a voluntary program ...` there is a separate 8 pt line `\,` at x 104.5, a speck of the scan. The row x is the minimum of its parts, so the left edge became 104.5 and every normal row looked indented by about 14 pt. The mid-paragraph row `tribute ...` (after `can con-`) was taken as a paragraph start, and the converter has `contribute`.
- The same page shows a second instance, glued into a word span. In the right column, `.petitive disadvantage.` starts at x 503.3, against 507.x for the other rows. With the code before this change it produced a silent wrong split: `... for it puts` / `the firm that makes the ostensible contribution at no com.petitive disadvantage.` No tripwire fires for it, because the row is found.
- Row x jitter on this scan (117.7 to 118.8 within one box) is larger than the 1 pt `LEFT_TOLERANCE_PT`.

## Decision: no paragraph split on a page whose whole text layer is invisible

Rule built (extract.py, `invisible_text_layer`): a page whose text traces are all of type 3 gets no paragraph split. These pages are handled like the pages the converter OCRs itself. Everything else still runs on them: coverage check, rotated-table and column-table steps, regions, headings. The summary line has a new field `invisible_text_pages=N`, so the path taken is visible per run.

Alternative tried and rejected: two narrow fixes.
1. Allow markup inside a needle word (`(?:\s*[*_]+\s*)?` between characters).
2. Ignore row parts without a word character when computing the row x.

Simulated over the cached converter output, with these results:
- Schelling: 47 splits, all of which looked right.
- Baumol: 5 splits. One of them was the silent wrong `the firm that makes ...` split, because a speck glued into a word span cannot be told apart by part.
- The four regression PDFs: identical.

Making the row x come from the first word character instead would shift rows that start with `(` or a quote on born-digital PDFs by a few pt. That is the Heilmayr `(Di,t)` situation, and those rows would become false paragraph starts. Rejected because an OCR layer from a scan gives geometry that is not reliable enough at a 1 to 3 pt scale (specks, jitter), and wrong splits there are silent.

Cost of the decision: Schelling's converter boxes do glue paragraphs (page 1: `... more than a sense of direction. Discomfort also arises ...`). They stay glued in `pages/p<N>.md`, as on Hayek. The page worker sees the image, and its prompt says paragraphs stay separate where the image shows a new one. Whether Haiku splits them is not verified. A glued new paragraph at the top of a page can be carried onto the previous page by the page join (the original Scholtens page 3 problem). If the user wants Schelling's 47 splits back, alternative 1 alone is enough for Schelling (0 failures over 25 pages), and it could be enabled for invisible layers. Baumol would then need the skip or stop at a tripwire.

## Brennan: what the line and the page are

- `pages/p3.md` does not contain the line. `pages/p4.md` line 9 is exactly `Open Questions About Civic Virtue` (no trailing space, no markup). The worker's `line` matches character for character, and only its `page` is wrong.
- `bookmarks.json` lists `Open Questions About Civic Virtue` on page 4. The worker still wrote `"page": 3`. A plausible reason, not verified: the heading follows `The Definition of ‘‘Civic Virtue’’` (h3_2 on page 3) in the outline, and the worker took the page from that.

Decision: the fix goes into apply-outline, not into the prompt.
- The page is a fact that the tool can look up deterministically.
- A prompt change cannot be verified without a worker run.
- Only a tool fix lets the existing `headings_fixed.json` pass.
- The prompt is unchanged, so `prompt_sha` and the config hash stay the same.

Rule built (apply_outline.py, `missed_row`):
1. Exactly one match on the named page is used, as before.
2. If the named page has no match, the line must occur exactly once in all other page files, and that page is used.
3. Otherwise the run fails with `missed_heading_not_found`. Examples: several matches on the named page, no match anywhere, several matches elsewhere. The message is `page 3: the line '...' occurs 0 times in pages/p3.md and 0 times in the other page files, it must occur once in pages/p3.md or, absent there, once in the other page files`.

The match is still the trailing-space-stripped line. Every relocation is printed: `missed headings found on another page than named: 'Open Questions About Civic Virtue' named page 3, found on page 4`, or `none`. Missed entries are still applied one after another, so a second entry for an already marked line finds nothing, as before. A named page that does not exist still fails with `missed heading on page N, which does not exist`.

## Verification (2026-11-20)

Commands ran through `cli.py` with the normal conversion log, into fresh directories under `/tmp/b3/verify/`.
- Baumol: `extract ok`, `pages=14 ocr_pages=0 tables=0 figures=5 formulas=0 headings=8 paragraph_starts_split=0 invisible_text_pages=14`.
- Schelling: `extract ok`, `pages=25 ocr_pages=0 tables=0 figures=0 formulas=0 headings=8 paragraph_starts_split=0 invisible_text_pages=25`.
- Brennan, on a copy of the batch with the worker's `headings_fixed.json`: `apply-outline ok: 18 headings, 1 set to level 0, 1 missed headings added`, plus the relocation line above. `p4_outlined.md` line 9 is `### Open Questions About Civic Virtue`, and the outline equals the bookmarks.
- Regression: Scholtens, Wright, Contreras and Heilmayr were extracted with the new code. They were also extracted with the old code (`git archive HEAD src config cli.py`, run from `/tmp/b3/oldtest` with a separate conversion log `/tmp/b3/old_conversions.jsonl`). All `pages/p<N>.md`, the region directories and `headings.json` are identical between new and old. The page files are also identical to the original batches. Summaries are the same except for the new field `invisible_text_pages=0`.
- Tests: 3 new tests.
    - `test_pdf_extract.py`: one test parametrized `schelling` / `baumol`, on generated pages with `render_mode=3` text and the observed converter spans.
    - `test_pdf_apply_outline.py`: one test.
  Each fails on the old code (old `src` beside the new tests in `/tmp/b3/oldtest`), with exactly the observed messages: the two `paragraph_start_not_found` lines and `occurs 0 times in pages/p1.md`. Full `run_strands.sh`: 91 strands, 1 skipped, 0 failed.
- Not verified: no worker has run on the new Baumol and Schelling batches.

## Hypotheses, not observed, nothing built

- A page that mixes a visible and an invisible text layer (Boatright, types 0 and 3) is still split. Its OCR part could hit the same speck or markup problems. If it does, the tripwire `paragraph_start_not_found` stops it.
- A missed heading named on the wrong page, whose line also occurs once on yet another page while missing on the named one, would be placed on that one page, even if that is the wrong occurrence.
- A born-digital PDF that draws its whole text invisibly over a vector rendering would lose the paragraph split.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- "Paragraph split at indented lines ..., only inside `text` boxes and only on pages not OCR'd": pages whose text layer is entirely invisible are not split either.
- "A missed heading must match exactly one line of `pages/p<N>.md` ...; zero or several matches fail": zero matches on the named page now fall back to exactly one match in the other page files.
- The orchestrator record in this area names Schelling and Boatright as scans with an older OCR text layer. Baumol 1991 is one too (14 of 14 pages invisible text over a full-page image), and so is Collins 1994 by its text traces.

## How the work ran, what to reuse, what went wrong

Order:
1. Read everything.
2. Classified the PDFs (images, fonts, text trace types).
3. Cached the converter output of six PDFs (`/tmp/b3/tools/cache.py`, all in parallel, a few seconds).
4. Probed the failing boxes (`probe.py`: rows, starts, span) and the line geometry (`lines.py`).
5. Surveyed every start (`survey.py`) and simulated `build_page` plus `require_coverage` old against new (`simulate.py`).
6. Built, tested, verified, recapped.

Reuse:
- `page.get_texttrace()` type 3 identifies invisible OCR text, and a survey over all PDFs of a folder takes seconds (`/tmp/b3/tools/traces.py`).
- Read the output of every split in the simulation, not only the reported failure. The silent wrong Baumol split was found only by reading the page 10 text.

Mistakes:
- A script named `inspect.py` in `/tmp/b3/tools/` shadowed the standard library module that pymupdf imports. The run died with a circular import. Do not name dev scripts after stdlib modules.
- The narrow fixes were built first and reverted after the Baumol simulation output showed the second speck.
- `grep -r` without `--include` is blocked by a hook here.
