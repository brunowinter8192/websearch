# 2026-11-20 - Second batch: drop cap, table box over the text column, hidden text, bottom footnote continuations

Area: pdf_repair_flow. Worker branch `pdf-batch2`, base `integration` (44e3701). Code commit 68ab230 ("fix: drop caps, column tables, hidden text and bottom footnote joins"). Builds on the page join and text coverage work recorded earlier in this area.

## Starting point (2026-11-20)

A second batch of five SGSC PDFs ran with the code of 44e3701. Batch directories are `/tmp/pdf_SGSC_Literatur_<stem>/`. They were never modified, and every experiment ran on copies under `/tmp/b2/`. Three of the five failed:

| PDF | failure |
|---|---|
| Wright & Rwabizambuga 2006 (29 pages) | `extract FAILED (paragraph_start_not_found): page 1: indented line 'a wide variety of public interest concerns into their corporate' not found` |
| Schouten & Glasbergen 2011 (9 pages) | `assemble FAILED (region_word_missing): tables/p9_0_fixed.md lacks ... companies. Relations. Routledge, University englisch/news.php?id=1070, Summary Assembly:` |
| Schrage & Ewing 2005 (14 pages) | `assemble FAILED (ambiguous_page_join): page 4: its last paragraph and its last footnote both run on` |

## Wright page 1: drop cap (extract, `text_rows`)

What the PDF contains: the first paragraph opens with a drop cap `I`. It is BASRBookman-Light at 48.5 pt, with line bbox `[54.2, 262.4, 70.6, 309.0]`. The three rows beside it start at x 70.6, and the rows below start at x 54.1. Row grouping by bottom y made the `I` its own row at the left edge (bottom 309.0). The row before it ("a wide variety ...", x 70.6) therefore looked indented with a left-edge row after it, so it was taken as a paragraph start. The converter text holds `integrating Ia wide variety`, so the row was not found.

Rule built: a line whose vertical extent contains the bottoms of at least two other rows is a drop cap. Here "another row" means a bottom strictly between the line's top and its bottom minus the 2 pt row tolerance. A drop cap is not a row. Every row whose bottom lies in the cap's vertical range takes the cap's left x as its own x.
- Survey over every `text` box of all nine PDFs, non-OCR pages: exactly two lines match, Wright page 1 `I` (3 rows) and Schrage page 2 `R` (4 rows). The Heilmayr CMEX10 brackets span no row bottom.
- A first survey counted every line with a bottom inside the extent. It hit every justified row, because the word pieces share one bottom. Count distinct row bottoms below the line's own bottom.
- The page output still reads `integrating Ia wide variety`. The page worker repairs it from the image.

## Wright, after the drop cap: two more coverage stops

With the drop cap fixed, `text_not_covered` stopped extract twice:
1. Page 1, `1Original BASR`: the text layer holds ten overlapping Helvetica spans at 2.0 pt, white (color 16777215), all at bbox y 70.4–72.3. They are publisher metadata: `Blackwell Publishing Ltd`, `BASR`, `0045-3609`, `1Original Article`, `WRIGHT AND RWABIZAMBUGA`, and others. The converter mixed them into the title (`# WRIGHT AND RWABIZAMBUGA0045-3609 **1OB** © 2006 Ce10UAusiness alackwell ...`). Rule: words whose centre lies in a span smaller than 3 pt are not checked by coverage. Conley's hidden tags (1 pt) fall under the same rule. They passed before only because the converter printed them.
2. Page 6, `cues.21`: the text layer glues the superscript note 21 (6 pt span) to `cues.`, and the converter wrote `informational 21 cues.`. Rule: a word of letters followed by digits is covered when both parts occur anywhere in the page output.

Result: `extract ok`, 29 pages, 5 tables, 2 figures, 12 headings, 1 paragraph split (page 27, endnote `45.` after `... policy statement.`), no region words missing.

## Schouten page 9: table box over the reference column (extract, `split_column_tables`)

What the PDF contains: page 9 has two columns. The left column (x 42–294) holds `Appendix A (continued)` with the interview table, rows 11 to 22. The right column (x 310–562) holds references. The converter's table box was `[48, 69, 562, 610]`, and the crop showed the table on the left and references on the right. The references from `Bitzer, V., ... 2008` to `RSPO, 2007 ... accessed: August 10, 2009.` existed only inside the table span. The converter had text boxes only for the right-column lines above (`[310, 56, 562, 87]`, Biermann 2007 and Biermann & Gupta 2011) and below (`[310, 606, 520, 613]`, RSPO 2008).

Answers to the questions in the request:
- Were the listed words present in the page output outside the region? No for `companies. Relations. Routledge, University englisch/news.php?id=1070, Summary`. The table worker correctly wrote only the table, and the page worker never saw the references, so 23 references were lost from the book. `Assembly:` belongs to `RSPO, 2008. Minutes of the 5th General Assembly`, a line that is inside both the table box and the lower text box. It was present in the page.
- Should the crop and `_current.md` cover the right column? No.

Rule built: a table box crossed by a converter `text` box with a non-empty span (positive intersection area) is cut at that box's left x, the "edge".
- The table keeps the text-layer lines whose right end is at or left of the edge. The region becomes their union, and `_current.md` becomes their texts, one per line.
- The lines starting at or right of the edge, and not inside any other converter box, become one `text` box with hyphenated line ends joined. It is inserted like an orphan of a rotated table: before the first later box in the same column that starts lower. On Schouten that is right before `RSPO, 2008`.
- That text box goes through the normal paragraph split. The references have a hanging indent (310.5 vs 322.5), so 23 splits came out. Consecutive one-line references (`RSPO, 2002 ... RSPO, 2004b`) stay glued, because the hanging rule only splits after an indented row. The page worker separates them from the image.
- Tripwire `table_column_unclear`: a line inside the table box crosses the edge, or one side is empty.
- Survey of all nine PDFs, every non-OCR table box after the rotated-table step, any other box intersecting it:
    - Scholtens page 21: an empty-span `text` box `[644, 53, 653, 417]` (the rotated running head) and a picture with a 1 pt overlap. Both are ignored because of the class and empty-span conditions.
    - Schouten page 9: the two right-column text boxes.
    - Nothing else.

Results:
- Fresh extract of Schouten: `pages=9 tables=3 figures=3 headings=28 paragraph_starts_split=24`, region words missing `none`.
- `pages/p1.md` to `p8.md`, `tables/p1_0_current.md`, `p8_0_current.md` and `headings.json` are byte-identical to the batch. Only `p9.md` and the `p9_0` files differ.
- The new `tables/p9_0.png` shows only the table, rows 11 to 22.

## Schrage page 4 to 5: footnote continuation in a converter footnote box (assemble)

What the PDF contains (page_png/p5.png): the footnote area at the bottom of page 5 starts with the unnumbered line `persons’ the minimum age is 18 years also; ILO C138, art. 2. ...`. That line continues footnote 14 of page 4, and footnote 15 follows it. In `pages/p5_fixed.md` it stands as `> persons’ the minimum age ...` directly before `[^15]:`. The `> ` comes from the converter's `footnote` box. Page 4 ends with body `... Growing cocoa involves` (open) and `[^14]: ... morals of young` (open). Page 5 starts with `long hours in the sun ...`.

Cause: the both-open rule takes the paragraph directly before the first footnote definition. That paragraph must be body text, and a paragraph starting with `>` is an imprint (skippable), so the rule raised.

Rule built: the footnote continuation may also be a `>` paragraph, and the join drops the leading `> ` like it drops `- `.

## Schrage, observed after the fix: open footnote continued at the bottom of the next page (assemble)

`p5_fixed.md` ends with `[^18]: ... however, all anti-trafficking law` (open), and its body is terminated (`... kidnapping of children.[^18]`). Page 6 starts with `## Response of the global cocoa industry`. Its continuation `enforcement efforts in Côte d’Ivoire have ceased ... (USDOS 2003).` stands directly before `[^19]:`, without `>` (the worker removed it there). Two effects under the old rules:
- Footnote 18 was not joined, because a heading starts page 6.
- The body join 6->7 was missed, because the footnote continuation was the last body paragraph of page 6 and is terminated. The real last body paragraph `... announced an initiative ‘to` continues on page 7 with `address the workers’ rights issues ...`.

Rule built: when only the footnote is open, the paragraph directly before the next page's first footnote definition continues it, if that paragraph is body text or a `>` paragraph and starts with a lowercase letter (after an optional `> `). Otherwise the old rule applies (the first paragraph of the next page). The continuation is popped from page 6 while page 5 is joined, so page 6's open body paragraph becomes its target and joins page 7.
- Conley 30->31 is unaffected: the paragraph before the first footnote of page 31 is a reference with an uppercase start.
- Scholtens 16->17 is unaffected: there that paragraph is the first paragraph itself.

## Rejected during the work

Restricting the body target to paragraphs before the page's first footnote definition, meant to stop the Schrage page 1 footer from being a target. Contreras page 3 is two-column with footnotes 2 to 5 at the bottom of the left column and body text after them in the right column. The 3->4 join (`... voluntary pro-` + `grams work by ...`) was lost. Reverted.

## Verification (2026-11-20)

Tests: 6 new tests in `test_pdf_extract.py` and `test_pdf_assemble.py`, one per rule: drop cap, column table, tiny hidden text, moved note mark, `>` footnote continuation, bottom footnote continuation. Each fails on the code of 44e3701. That was checked by running them against `git archive HEAD src` in `/tmp/b2/old`, and each failure message was the observed one. Full `run_strands.sh`: 90 strands, 1 skipped, 0 failed.

Wright: `cli.py pdf extract` into the fresh `/tmp/b2/wright_fresh` gave `extract ok`.

Schouten: fresh extract into `/tmp/b2/schouten_fresh`. All worker outputs of the original batch were copied in, then `apply-outline` ran (28 headings, outline identical). `p9_fixed.md` is a stand-in made by me, not by a worker: the original `p9_fixed.md` with the 24 returned reference paragraphs of the new `p9_outlined.md` inserted after `<!-- TABLE p9_0 -->`. No page worker has run on the new page 9. Result: `assemble ok`, 6 joins, all right:

| join | end of page | start of next |
|---|---|---|
| 1->2 | `orest and marine stewardship councils (FSC and MSC) that are` | `based on the same kind of model. Following Cashore and Berns` |
| 2->3 | `an interconnected whole. Second, they need to create a basic` | `understanding and common belief related to what they are try` |
| 4->5 | `n 2005, which led to the adoption of a Code of Conduct and a` | `Grievance Procedure. This conflict regards the workers of a ` |
| 5->6 | `e initiative was to ensure the long term supply of palm oil,` | `while retailers Migros and Safeway pointed out that they joi` |
| 6->7 | `nd by now the premium for certified sustainable palm oil has` | `declined. The low uptake of certified sustainable palm oil i` |
| 7->8 | `es a niche market for certified palm oil. The opportunity to` | `change the market as a whole will depend, in particular, on ` |

No join at 3->4 (page 3 ends with the caption `**Timeline of the RSPO**`, page 4 starts with a heading) and none at 8->9 (page 8 ends with `... (NWO) for funding this research.`). Both are right.

Schrage, copy of the batch: `assemble ok`, 9 joins:

| join | end of page | start of next | judgement |
|---|---|---|---|
| 1->2 body | `**JCC 18** _Summer 2005_` | `Reports of slave labour on cocoa farms surfaced as early as ` | wrong |
| 4->5 body | `ld labour under this Convention.[^14] Growing cocoa involves` | `long hours in the sun performing physically demanding work. ` | right |
| 4->5 footnote | ` ‘likely to jeopardize the health, safety or morals of young` | `> persons’ the minimum age is 18 years also; ILO C138, art. ` | right, `> ` dropped |
| 5->6 footnote | ` children rescued in 2002; however, all anti-trafficking law` | `enforcement efforts in Côte d’Ivoire have ceased since the c` | right |
| 6->7 body | ` legislation, the cocoa industry announced an initiative ‘to` | `address the workers’ rights issues recently identified by th` | right |
| 7->8 body | `the importance of eliminating all forced labour, in addition` | `to the worst forms of child labour, and referenced ILO Conve` | right |
| 8->9 body | `lication, clearing underbrush with a machete, carrying heavy` | `loads, and using a machete to open the cocoa pods. According` | right |
| 9->10 body | `adopted a Declaration and Plan of Action against Trafficking` | `in Persons calling on member states to criminalise trafficki` | right |
| 12->13 body | `ake local law the default minimum standard (Ewing 2004). The` | `CIP participants represent substantial leverage within the g` | right |

1->2 is wrong and not fixed. Page 1 ends, after `[^*]:`, with the page-1 footer `**JCC 18** _Summer 2005_`, which extract keeps because running boxes on page 1 are kept unless they are a bare page number. Page 2 starts a new section with the drop cap `R`. Without the footer, the target would still be wrong: the body paragraph before the footnote is `! aewing@law.columbia.edu`, an author address without a full stop. Possible rules, none built:
- A paragraph ending in an e-mail address is closed. Observed twice: here, and in the Moura page 1 footnotes.
- Mark page-1 running boxes so that assemble can skip them, for example their texts in the manifest, compared after `normalized`.

Regression, assemble on copies with `samples/` removed: Scholtens 9, Hayek 23, Conley 22, Contreras 13, Heilmayr 9 and Moura 6 joins. The join list and the joined text of every join (60 characters each side) are identical before (code of 44e3701) and after. The extract side was simulated over a cached converter output of all nine PDFs (`build_page` plus `require_coverage`). All page texts, regions, headings and missing-word lists are identical for Scholtens, Hayek, Conley, Contreras, Heilmayr, Moura and Schrage. Only Schouten page 9 changed, and Wright now passes.

## Hypotheses, not observed, nothing built

- A converter text box crossing a table from the left (a text column left of the table) hits the `table_column_unclear` tripwire.
- A drop cap of two rows' height (one spanned bottom) is not recognised.
- In the Schrage layout, a footnote continuation that starts with an uppercase letter, or a terminated body before it, falls back to the first paragraph of the next page.
- A word of letters plus digits that the converter really lost passes coverage when both parts occur elsewhere on the page.

## How the work ran, what to reuse, what went wrong

Order:
1. Read everything.
2. Cached the converter output for all nine PDFs as JSON under `/tmp/b2/cache/` (about 30 s for all, run in parallel).
3. Probed boxes, rows and text-layer blocks per failing page.
4. Surveyed each rule candidate over all nine PDFs before building it.
5. Simulated extract over the caches before and after the change.
6. Traced assemble joins on copies with the old code (`git archive HEAD src | tar -x -C /tmp/b2/old`, run with `PYTHONPATH=/tmp/b2/old`) and the new code.

Reuse:
- Old code side by side: `git archive HEAD src` plus a copy of `dev/tests`, `config` and `pytest.ini` into a scratch directory proves "fails on the old code" for new tests without stashing.
- The join overview script (per page: last body and last footnote, open or not, first paragraphs of the next page, paragraph before its first footnote) found the two missed Schrage joins that the reported failure did not show.

Mistakes:
- zsh treats `echo =====` as `=` command expansion and aborts the call. Use quotes.
- A hook blocks reading a CLI's redirected output in the same Bash call. Run the CLI, then read the file in a second call.
- A test for the column split first used a reference block with more left-edge rows than indented rows. The prose rule then split inside a reference. Test data has to reproduce the observed hanging indent (more indented rows than left-edge rows).

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- "A single open footnote keeps the old rule (first paragraph of the next page)": a lowercase body or `>` paragraph directly before the next page's first footnote definition now comes first.
- Imprint rule "a paragraph starting with `>` (converter footnote box)" is skippable: it still is for body joins, but such a paragraph can now be a footnote continuation.
- The hypothesis "A footnote continuation on the next page while the body is terminated, in a layout like Hayek ... would take the first paragraph of the page" was observed (Schrage 5->6) and is handled for lowercase starts.
- Duplicate constant names `HYPHENATED_END` (extract.py, assemble.py) and `PICTURE_TEXT_MARKUP` (extract.py, assemble.py) were already present on 44e3701 and were left as they are.
