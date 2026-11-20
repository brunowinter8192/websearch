# 2026-11-20 - Formula worker, new box classes, row and split fixes, clean page images, page join ambiguity

Area: pdf_repair_flow. Worker branch `pdf-formulas`, base `integration` (9a2f67b). Commits b651378 (formulas, classes, row and split fixes), a819280 (page join), 6b6c2ad (clean images). Builds on the text layer repair flow recorded earlier in this area.

## Starting point (2026-11-20)

`extract` ran on five SGSC PDFs from `rag-cli/data/pdf/wise2627/`. Hayek and Moura Chaddad passed and their workers were running. Three stopped at a tripwire:

- Conley & Williams 2011: `unknown_box_class: page 1: box class 'title' was never observed`
- Contreras, Bos & Kleimeier 2019: `unknown_box_class: page 1: box class 'footnote' was never observed`
- Heilmayr 2020: `paragraph_start_not_found: page 9: indented line 'Gi,g,t , and indirect exposure through a local market' not found in the converter text`

User decision: formulas get their own worker that reads every formula as an image. Before this, the page worker wrote formulas as LaTeX from the 150 dpi page image.

## What the PDFs contain (probed with `to_markdown(page_chunks=True)`, dumps were `/tmp/fprobe_*.json`)

Box class inventory:

| PDF | pages | OCR pages | classes beyond the earlier set |
|---|---|---|---|
| Conley 2011 | 34 | none | `title` (1), `footnote` (1) |
| Contreras 2019 | 19 | none | `footnote` (12), `formula` (2) |
| Heilmayr 2020 | 16 | 1, 4, 8, 11, 12 | `formula` (4) |
| Scholtens 2007 | 22 | 22 | none |
| Hayek 1939 | 23 | all | `formula` (3) |
| Moura Chaddad 2012 | 12 | none | none |

- `title`, Conley page 1, is the paper title. The text layer holds two hidden 1-pt spans, `lapo_348` and `542..575` (TimesNRMT-Bold size 1.0, publisher tags). The converter wording is `# **Global Banks as Global Sustainability 542..575 Regulators?: The Equator Principleslapo_348**`.
- `footnote` boxes carry a leading `> ` from the converter. Contreras page 2: footnote 1's first line is a `text` box (`> 1 Since the Basel II accord ...`) and the rest is a `footnote` box.

Display formulas, every observed shape:

| PDF, eq | page | formula body | equation number |
|---|---|---|---|
| Heilmayr (1) | 7 | `formula` box | inside the box |
| Heilmayr (2), (3), (4) | 9 | `formula` boxes | inside the box |
| Contreras (1) | 5 | `formula` box | inside the box |
| Contreras (2) | 5 | `text` box `Peer Pressure ¼ EPj � Concentrationji;` | separate `formula` box `ð2Þ`, same row |
| Contreras (3) | 6 | `section-header` `Susceptibility ¼ EPj � Concentrationij` | separate `page-footer` box `ð3Þ`, same row |
| Contreras (4) | 7 | `section-header` `External Pressure ¼ ... Market Share; ð4Þ` | inside the box |
| Scholtens | 13 | `section-header` `Ri ¼ a þ bRm þ error:` | none |

- Hayek's three `formula` boxes (page 18 `[31]`, page 21 `[36]` and `[37]`) are scan page numbers, not formulas.
- The fonts of Contreras and Scholtens encode `=` as `¼`, `+` as `þ`, and `(`/`)` as `ð`/`Þ`. Heilmayr's converter text uses real `=` and `∑`.
- Inline math in running text (Heilmayr D_{i,t}, P̂_{i,t}) cannot be cut out. It stays with the page worker as `$...$`.

## Decisions and why

### `title` and `footnote`
- `title` is handled exactly like `section-header`: it goes into `headings.json` and the outline worker sets its level.
- `footnote` is plain text like `list-item` and `caption`, with no paragraph split. The page worker writes `[^N]: ...`.

### Formula detection in extract (deterministic, one rule per observed shape)
1. A `formula` box is a formula, unless its content without the `<!-- Start/End of picture text -->` and `<br>` markup is a bare page number (Hayek) or only an equation number. A page-number formula box keeps the earlier behaviour: its raw span stays as text.
2. A `section-header` containing `¼` is a formula. This covers Scholtens and Contreras (3) and (4). No other heading in the six PDFs contains `¼`. A plain `=` in a heading was never observed and is not a rule.
3. A box whose markup-free content fully matches `ð\d+Þ` is an equation number, whatever its class (observed: `formula`, `page-footer`). Its partner is found and becomes a formula:
   - candidates are boxes whose vertical range contains the number's vertical centre and whose right edge is left of the number;
   - the partner is the candidate with the largest right edge;
   - the crop is the union of both bboxes, so the number is in the image;
   - `_current.md` holds both spans joined by a space.
   - Contreras page 5: the left-column text box [32,663,284,724] also contains the number's centre 724. The nearest-right-edge rule picks the formula text [301,719,447,729] instead.
   - Contreras page 6: the page-footer number is consumed before the running-box drop, so it is not lost.
4. Tripwire `equation_number_alone`: no box to the left, or a partner of a class other than `text`, `section-header` or `formula`.

- Formula headings no longer reach `headings.json`, so the outline worker never sees them. Scholtens: 16 headings became 15.
- Alternative rejected: let the outline worker mark formula headings and crop them in apply-outline. That needs the crop after outline and a manifest change in apply-outline. apply-outline would also have to render from the PDF, where pymupdf4llm's `remove_rotation` coordinates differ on landscape pages.

### Cut out, written, put back
- Placeholder `<!-- FORMULA p<page>_<k> -->` as its own paragraph.
- Files `formulas/<id>.png` (200 dpi, same as tables) and `<id>_current.md`.
- Worker `formulas` with `prompt_formulas.md` from template `formulas_prompt.md`. It is in the manifest only when formulas exist and starts in Step 2 with `tables` and `figures`, because all crops are known at extract.
- Output: one line `$$<LaTeX>$$`, with the equation number written as `\tag{N}`.
- `assemble` replaces FORMULA placeholders like tables and figures, and the placeholder check covers FORMULA. A FORMULA placeholder is skippable for the page join like every placeholder. The paragraph after a formula is not treated as a caption (only TABLE and FIGURE neighbours are).
- Old batches without a `formulas` manifest key (Hayek, Moura, extracted before this change) still assemble: the summary reads `manifest.get("formulas", [])`.

### Row fix (Heilmayr page 9)
- Cause: the line reads "(G_{i,g,t}), and indirect ...". The large brackets are CMEX10 glyphs; pymupdf gives them a bbox 140.5–150.5 with baseline 148.5, against 149.5–159.8 and baseline 156.6 for the letters. Grouping by bottom y within 2 pt therefore built an own row `( )`. The real row then started at `G` (x 346.5, 4.6 pt right of the edge 341.9), looked indented, became a paragraph start and was not found in the converter text.
- Fix: a row without any `\w` character is merged into the following row, with the minimum x of both.
- Checked with a script on the real converter output before building: Heilmayr page 9 passes, and the splits of Scholtens (2), Heilmayr (1) and the prose of Contreras are unchanged.

### Hanging-indent references (Contreras page 18)
- Several references sit glued in one `text` box: first line at the left edge, continuation lines 11.9 pt in. The old rule (indented row followed by a left-edge row) split before the last line of a reference. Examples: "institutionalism in organizational analysis (pp. 1–38).", "# 9-214-083..", "themselves? Transnational Corporations, ...".
- New rule: a box is hanging when its first row is at the left edge and it has at least as many indented rows as left-edge rows. In a hanging box a paragraph starts at every left-edge row whose previous row is indented. Prose boxes are mostly left-edge rows and keep the old rule.
- Result on page 18: splits before DiMaggio 1983, Esty & Sesia 2005, Godlewski 2012, Kolk 1999 and Lenox 2006.
- A box whose first row is indented is never hanging: a 2-row paragraph [indented, left] must not split.

### Heading lines (user decision after the plan)
- Page workers may correct the characters after the `#` marks against the image. Examples: hidden tags like `lapo_348`, and the `**` bold markers Moura headings carry (`## **1. Introduction**`).
- They must never change the number of `#`. `assemble` enforces this: the sequence of `#` runs at line starts must be equal in `p<N>_outlined.md` and `p<N>_fixed.md`, otherwise `heading_marks_changed`. apply-outline still writes the converter wording; the correction happens only in the page worker's output.

### Page join ambiguity (Moura Chaddad, observed during the review)
- `assemble FAILED (ambiguous_page_join): page 1`. Page 1 ends with the body paragraphs `_ISSN 1569-1829 print, ... DOI 10.3920/JCNS2012.x002_` and `_13_`, then footnotes `[^1]`, `[^2]`: author addresses ending in an e-mail address without a full stop. Page 2 starts with `## **2. Literature review**`.
- Two causes:
  - `_13_` was not a bare page number because of the underscores;
  - the ambiguity was raised before looking for a continuation, although a heading on page 2 means nothing is joined.
- Fix:
  - `ambiguous_page_join` is raised only when a continuation exists;
  - `*`/`_` are stripped before the bare-page-number test.
- On a copy of the batch: `assemble ok`, joins 3->4, 6->7, 7->8, 8->9, 9->10, 10->11, each checked at its join point ("end users and" + "civil society) ...").

### Page images and crops from the unmodified PDF (observed during the review)
- pymupdf4llm mutates the document it gets: `page.remove_rotation()` on every page, and on OCR pages `exec_ocr_interface` writes the OCR text with `page.insert_text` (visible). extract rendered `page_png/` and every crop from that same document.
- Observed consequence on Hayek page 17: OCR text drawn over the scan in a second font. The superscript `16` after "economic matters." became unreadable, the page worker wrote `[^1]` and the sample worker reported no finding.
- Fix: rendering uses a freshly opened copy of the PDF on which only `remove_rotation()` is applied. That call doesn't change the rendered appearance, but it puts the copy in the converter's coordinates, which landscape pages need (Scholtens pages 11 and 21).
- Paragraph-split detection still reads the converted document. It never runs on OCR pages, where the inserted text is.
- Batches extracted before 6b6c2ad have contaminated images on every OCR page: Hayek all 23 pages, Heilmayr pages 1, 4, 8, 11, 12, Scholtens page 22.

## Verification

Commands ran through `cli.py pdf extract` into fresh directories with the normal conversion log.

| PDF | summary | formulas |
|---|---|---|
| Conley 2011 | `pages=34 ocr_pages=0 tables=0 figures=1 formulas=0 headings=22 paragraph_starts_split=0` | none |
| Contreras 2019 | `pages=19 ocr_pages=0 tables=11 figures=8 formulas=4 headings=23 paragraph_starts_split=7` | p5_0 (1), p5_1 (2), p6_0 (3), p7_0 (4) |
| Heilmayr 2020 | `pages=16 ocr_pages=5 tables=3 figures=6 formulas=4 headings=35 paragraph_starts_split=1` | p7_0 (1), p9_0 (2), p9_1 (3), p9_2 (4) |
| Scholtens 2007 | `pages=22 ocr_pages=1 tables=9 figures=6 formulas=1 headings=15 paragraph_starts_split=2` | p13_0 |
| Hayek 1939 (after 6b6c2ad) | `pages=23 ocr_pages=23 tables=0 figures=1 formulas=0 headings=16 paragraph_starts_split=0` | none |

- Formula crops were viewed for Contreras (1)–(4), Heilmayr (1), (3), (4) and Scholtens p13. Each shows the complete formula with its number.
- Hayek `page_png/p17.png` is pixel-identical to a rendering of the freshly opened PDF. Scholtens pages 11, 21, 22 are 1447x1016; the table crops on pages 11 and 21 cover their tables.
- Tests: 9 new across `test_pdf_extract.py` and `test_pdf_assemble.py`; full `run_strands.sh` 90 strands, 1 skipped, 0 failed. The bracket-row, hanging-indent, italic page number, heading-before-continuation and clean-image tests were run against the code before each fix and failed there.
- Not verified: no worker has run `formulas_prompt.md` or the changed `pages_prompt.md`. Whether Haiku writes `\tag{N}`, keeps FORMULA lines and corrects heading characters without changing `#` is unknown.

## Skill lines the user edits himself (skills/websearch-pdf/SKILL.md as of 9a2f67b)

- After line 62: ``   - `formulas` — `BATCH_DIR/prompt_formulas.md`, fehlt, wenn das PDF keine Formel hat.``
- Line 66: `### Step 2 — Tabellen, Abbildungen und Gliederung` becomes `### Step 2 — Tabellen, Abbildungen, Formeln und Gliederung`.
- Line 68: ``1. Starte die Worker `tables`, `figures` und `outline` direkt nacheinander.`` becomes ``1. Starte die Worker `tables`, `figures`, `formulas` und `outline` direkt nacheinander.``

## Hypotheses, not observed, nothing built

- A page ending with an open sentence whose continuation follows a formula on the next page: the formula is skipped like a table, so the text after it would be joined onto the previous page, before the formula.
- A heading that is a formula but contains neither `¼` nor an equation number: it stays a heading. The outline worker would set level 0 and the page worker would write `$$...$$` as before.
- A reference box mixing single-line and multi-line references ([left, left, indented]) falls back to the prose rule.

## How the work ran, what to reuse, what went wrong

Order: read everything, probe all six PDFs once, first reply with plan, go (plus the two heading and hanging-indent fixes), code, simulation script against real converter output, tests, verification. Then two observed bugs from the running batches (Moura join, Hayek images), each fixed the same way.

What to reuse:
- `text_rows`, `paragraph_starts` and `locate_row` can be imported and run per text box over a real conversion, to list every split and failure of a PDF in seconds before touching extract.
- For glyph geometry, dump `page.get_text("dict", clip=..., flags=ROW_FLAGS)` spans with `bbox`, `origin`, `font` and `size`. That is how the CMEX10 brackets and the 1-pt hidden title tags were found.
- A test that must fail on the old code: `git stash push <file>`, run the test with `-k`, `git stash pop`.
- Set `WEBSEARCH_CONVERSION_LOG_PATH` to a file in `/tmp` for experimental extract runs, so the conversion log only holds real runs.

Mistakes:
- `/tmp/src.py` exists on this machine. A script under `/tmp` that does `from src.pdf ...` imports it instead of the repo package. Put dev scripts in a subdirectory such as `/tmp/fdev/` and run them with `PYTHONPATH=.` from the worktree.
- A hook blocks a Bash call that redirects a CLI's output and reads the file back in the same call, and then the whole call does not run, including file edits chained before it. Read the output file in a separate call.
- A test first asserted the exact crop width 700 px; pymupdf rounds to 701. Compare crops to each other or to a fresh rendering instead of a computed pixel count.
- The first assemble test for formulas codified a join across a formula, which reorders text. It was replaced by a test of the replacement only, and the join case is recorded as a hypothesis above.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- "`formula` is kept as plain text for the page worker": only a formula box holding a bare page number is; other formula boxes become FORMULA placeholders.
- "Crops and page images are rendered afterwards from that same document": they come from a fresh copy of the PDF since 6b6c2ad. The reason given there (rotation agreement) is kept by applying `remove_rotation()` to the copy.
- "Lines starting with # stay exactly as they are" (page prompt): characters may now be corrected; the number of `#` is enforced by `assemble`.
- "Both open fails with `ambiguous_page_join`": only when a continuation exists.
- Hypothesis "A page ending with a display formula `$$...$$` counts as open": cut-out formulas are placeholders now and are skipped for the join.
