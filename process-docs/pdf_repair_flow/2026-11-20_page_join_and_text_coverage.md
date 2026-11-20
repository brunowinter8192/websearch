# 2026-11-20 - Page join failures, text coverage tripwire, rotated tables, missing region words

Area: pdf_repair_flow. Worker branch `pdf-join`, base `integration` (15342eb). Commits 14ce6fb (page join), 1b34a62 (coverage tripwire, rotated table recovery, list marker), 4e37922 (missing region words for workers, checked in assemble). Builds on the formula worker and text layer repair flow recorded earlier in this area.

## Starting point (2026-11-20)

Five SGSC PDFs went through the whole repair flow with Haiku workers, no worker blocked. Batches `/tmp/pdf_SGSC_Literatur_<stem>/` (never modified, every experiment ran on copies in `/tmp/pjoin/`).

| PDF | assemble before | problem |
|---|---|---|
| Heilmayr 2020 | ok, 67 joins | reference list of pages 15 and 16 chained onto item `[6]` of page 14 |
| Contreras 2019 | ok, 17 joins | `Table 2` labels and the wrong paragraphs joined around tables |
| Hayek 1939 (scan, two book pages per PDF page) | FAILED `ambiguous_page_join` page 11 | body and footnote 11 both run on, both really continue |
| Heilmayr 2020 | - | title `#` twice (cover sheet on page 1 plus article on page 2) |
| Conley 2011, Moura Chaddad 2012 | ok, 22 and 6 joins | to keep working |

## Page join rules (assemble), each from an observed case

How the cases were found: a script that lists, per page boundary, the end of the last body paragraph and last footnote (open or not), the first paragraphs of the next page and the paragraph before its first footnote. That overview showed more wrong joins than the four reported. Reproduce it before changing join rules; reading only the reported cases misses half.

1. List item: an open list item (`- `) is not continued by a paragraph that is itself a list item. Heilmayr page 14 ends `- [6] Jayachandran ... _Science_ **357** 267–73`, page 15 starts `- [7] ...`. A list item continued by a non-list paragraph still joins (Moura 9->10 `- _Congruence ... and other` + `third party appropriators`, Heilmayr 7->8 `- Local markets: ... certified` + `in year $t$`).
2. Continuation that starts with `- ` but whose target is not a list item: the marker is dropped when joining. Conley 30->31: footnote `[^10]: ... to sue` + worker-written `- corporations for human rights abuses ...` now reads `to sue corporations`.
3. Caption label paragraph is skippable: `Table N`, `Fig. N`, `Figure N`, optionally bold, alone or followed by `.`, `—`, `*` or ` (`. Observed: `Table 2`, `Table 8 (continued)`, `Table 1. Descriptive statistics`, `Table 1—continued`, `**Table 1.** Channels`, `**Table 1. (Continued.)**`, `Fig. 1. Baseline`, `**Figure 1.** Conceptual`. Body text `Table 7 presents ...`, `Fig. 5 summarizes`, `Fig. 4(a)` does not match.
4. The paragraph right after a bare label is its title and skippable: Contreras `Table 2` / `Regional distribution of adopters of the Equator Principles.` / TABLE.
5. The old rule "paragraph directly before a TABLE is a caption" was removed. Contreras page 16: `some light to our findings. ...` (the continuation of page 15) stands directly before TABLE p16_0, whose caption `Table 9 Correlation table.` is inside the rotated table crop. The old rule skipped it and joined `To determine ...` instead.
6. Table note: a paragraph directly after a TABLE is skippable only when it starts with an uppercase letter or `(`. Observed notes: `This distribution ...`, `Unit of observation ...`, `Mean differences ...`, `Exponentiated coefficients ...`, Scholtens `Source: ...`, `(continued on next page)`. Observed body text after tables: `estate, greater exposure ...` (Heilmayr page 10, was a missed 9->10 join), `$\text{Concentration}_{ji}$ is the share ...` (Contreras page 6). `Table 7 presents ...` after TABLE p16_0 counts as a note; harmless, it is never a continuation there.
7. `;` no longer ends a paragraph. Only one page end with `;` was observed: Contreras page 5 `... and zero otherwise;`, continued in print on page 6 after Table 1. Now joined.
8. Body and footnote both open: the body continuation is the first paragraph of the next page, the footnote continuation is the paragraph directly before the first footnote definition of that page, and it must stand after the body continuation and be body text. Hayek page 12 holds `until it becomes ...`, `## III`, body, `[19]`, `that are to be satisfied. ...`, `[^12]: ...`; same on Hayek 13->14 (`equality provides no serviceable guide` before `[^14]`). Every other layout still raises `ambiguous_page_join` with the old message. A single open footnote keeps the old rule (first paragraph of the next page): Conley 30->31 and Scholtens 16->17 depend on it, and Conley page 31 has a reference before its first footnote definition, so "paragraph before the first footnote" would be wrong there.
9. Page numbers in picture-text markup are page numbers: `<!-- Start of picture text -->\n[31]<br><!-- End of picture text -->` (Hayek pages 18, 21, from formula boxes holding a scan page number). Before, they were the join target (`[31] pensable instrument ...`).
10. Imprint lines are skippable: a paragraph starting with `>` (converter footnote box), a paragraph entirely in square brackets without `^` (Hayek page 22 `[PRINTED IN USA]`), a paragraph containing `ISSN`, `©` or `downloaded from IP address`. All observed on page 1 except the bracket line. They caused Conley 1->2 to join onto `ISSN 0265–8240` instead of `... they did not understand,`, Heilmayr 1->2 to join the cover sheet stamp to `Environmental Research Letters`, and Hayek 22->23 to join `[PRINTED IN USA]` to the back cover list.

Rejected: treating converter headings set to level 0 as join stops. In Hayek, level 0 entries include prose (`system than under the older schemes ...`, OCR noise), and OCR'd wording does not match the fixed pages.

Results on copies (every join checked at its join point): Heilmayr 9, Contreras 12, Hayek 23, Conley 22, Moura 6, all right. Scholtens (earlier batch) kept exactly its 9 documented joins. Hayek 13->14 has a second body join because the page worker split one paragraph at the book page break inside PDF page 14 (`That there are` / `questions which ...`); the repeated join pass rejoins it correctly.

## Case 4: the doubled title (outline prompt)

Heilmayr page 1 is the IOP download cover sheet (`PURPOSE-LED PUBLISHING`, `To cite this article`, `You may also like`, `This content was downloaded from IP address ...`) repeating the title. The outline prompt said "title of the work 1", so the worker set both occurrences to level 1. Added rule: a cover sheet put in front of the work by a publisher or download service is not part of the work; every entry on it gets level 0, also the title; the title gets level 1 where the work begins. Not verified with a worker run: workers cannot use worker-cli (a guard answers `worker-cli --help`). Hayek's pamphlet cover title (page 1, level 1) and the essay title on page 3 (level 2) are a different case and were fine.

## Text coverage tripwire (extract, `src/pdf/coverage.py`)

Requirement: on every non-OCR page every word of the text layer (`page.get_text("words")` on the converted document) appears in the page output (page md, region `_current.md`, heading texts). Calibrated on the six distinct PDFs the batches come from (Conley, Contreras, Hayek, Heilmayr, Moura Chaddad, Scholtens). There were six, not the seven the request named.

Normal converter changes that must pass, each observed:
- NFKC (ligatures `ﬁ`, `ﬀ`), case, all non-alphanumerics dropped, markup removed (`<br>` to space, other tags removed, HTML comments removed). Modifier letters (category Lm) are dropped: Heilmayr page 9 `ˆPi,t.` comes out as `_P_<sup>ˆ</sup> _i,t_ .`; Python counts `ˆ` as alphanumeric.
- Line-end hyphenation: a word ending letter+`-` first tries the joined form with the next word (`communi-` + `ties` = `communities`). Without this, a fragment such as `communi` was consumed inside a free `community` and `munity,` was reported missing (Conley page 7).
- Matching order: exact tokens with counts first; the rest by substring in the unused output in its original order, longest first; the rest is accepted if it occurs anywhere in the whole output stream. That last step covers words glued in the PDF: `staﬀas`, `staﬀfrom` (Scholtens), `the—major` (Conley), `Carlson3,4and` (Heilmayr).
- Words inside dropped running boxes are ignored, and so is any PDF line that repeats the text of a running box dropped anywhere in the document. Scholtens page 21 has its vertical running head `BANKING ON THE EQUATOR. ARE BANKS THAT ADOPTED THE EQUATOR PRINCIPLES?` as a `text` box with an empty span.
- Formula regions: every character of the word must occur in the region text, because the converter scrambles formulas (`∑ Ss = g 1` for Σ_{s=1}^{S_g}, Heilmayr pages 7 and 9).
- Table and figure regions: presence in the region `_current.md`, no counts. Words missing there do not stop extract (next section).

A first version with the tag pattern `<[^>]+>` removed the text between `p < 0.10` and the next `>`, and reported hundreds of missing words on Contreras pages 10 to 15. The tag pattern is `</?[a-zA-Z][^<>]*>`.

Results with the final code (2026-11-20): all six PDFs pass; Heilmayr lists `p6_0=2` (next section). Without the rotated-table fix (call removed temporarily) Contreras stops: `text_not_covered: page 16: 11 words ... instead practices Correlation Concentrationij(%) ...`. Moura Chaddad (already published) lost no text.

## Rotated table swallowing a column (Contreras page 16, extract)

The converter's table box was `[75,75,563,756]`, almost the whole page. The table is printed rotated in the left part; the right body column had converter text boxes only for `some light ...`, `Table 7 presents ...` and `To determine ...`. `6.2. Sub-sample analyses`, `When discussing Hypothesis 4 ...`, `Table 8 provides ...`, `6.3. Out-of-sample analyses`, `7. Conclusion` and `The Equator Principles are a form ...` existed only inside the table span, partly garbled (`sure wt measures or proitaty an sze nstea o wt a`). The page worker never saw them; page 17 of the book started mid-sentence.

Rule: a table box in which rotated lines (direction not (1, 0)) are more than half of its lines is a rotated table. Contreras page 16 has 169 rotated against 60 horizontal; Scholtens page 21 (2 rotated margin lines against more than 137 horizontal) stays untouched. For a rotated table:
- the region becomes the union of the rotated lines (the crop shows the table with caption and note);
- `_current.md` becomes the text of the rotated lines, one per line (the converter span was the garbled mix);
- every text block whose horizontal lines all lie inside the old box, outside the new box and outside every other converter box becomes a text paragraph; line-end hyphens are joined like the converter does (`out-of-` + `sample` = `out-ofsample`); each is inserted before the first later box in the same column that starts lower, otherwise at the end.
Only `pages/p16.md` and `tables/p16_0_current.md` changed in Contreras; the other five PDFs produce identical files. Recovered headings arrive as plain lines; the outline worker can add them as missed headings.

## Missing words inside table and figure regions (user decision)

First version: missing region words stopped extract, and Heilmayr stopped on page 6 (`during droughts`). The converter clips cell text in Heilmayr tables: page 5 `sup-` + `ply bases` became `l b`, and the page 6 cell `... or in neighboring areas` / `during droughts` ends at `neighboring area`. The table worker repaired both from the crop in the existing batch.

Correction of a statement in this session's own report: I said `p6_0_fixed.md` lacks `drought`. That was wrong; the grep needed 60 characters after the match and the words stand at the end of the line. The worker wrote `... neighboring areas<br>during droughts|`.

User decision, built:
- extract writes `<dir>/<id>_missing.txt` (one word per line, no duplicates) for table and figure regions whose `_current.md` lacks printed words; extract does not stop for them. The summary line reads `region words missing from the converter text: p6_0=2` or `none`.
- The tables and figures prompts name the ids that have such a file (`Tables with a missing-words file: p6_0`) and say every listed word is printed there and must appear in `<id>_fixed.md` where the image shows it.
- assemble stops with `region_word_missing` naming the fixed file, the list file and the absent words. On a copy of the Heilmayr batch with the new list file: `assemble ok`; with `<br>during droughts` deleted from the copy's `p6_0_fixed.md`: `assemble FAILED (region_word_missing): tables/p6_0_fixed.md lacks words printed in the region and listed in tables/p6_0_missing.txt: during droughts`.
- Words missing outside regions still stop extract, and so do words missing inside formula regions (the decision named tables and figures; no formula miss was observed).
- Batches extracted before 4e37922 have no list files and are not checked.

## Tests

- assemble: list item, caption labels and table-only page, text before a captionless table, lowercase after a table, semicolon over a captioned table, paragraph and footnote both open, picture-text page number, three imprint variants, listed region words; the list item test also checks the dropped marker.
- extract: coverage (normal changes pass, a lost sentence stops with the exact message), rotated table, words missing inside a table listed for its worker.
- Each new or changed test failed on the code before its commit (checked with `git stash push <files>`). Three existing extract tests had fake converter output that did not cover their generated PDF; the fixtures were aligned (page texts the chunks contain; the scan test's converter now reports page 1 as OCR).
- Full `run_strands.sh`: 90 strands, 1 skipped, 0 failed.

## Hypotheses, not observed, nothing built

- A rotated table whose orphan blocks belong to two columns: insertion assumes one column below the table box.
- A body paragraph that genuinely starts with `Table N.` would be skipped as a caption label.
- A footnote continuation on the next page while the body is terminated, in a layout like Hayek (continuation at the bottom of the page): it would take the first paragraph of the page.
- A missing region word that is a substring of another word of the fixed region passes the assemble check (presence by substring).

## How the work ran, what to reuse, what went wrong

Reuse:
- Cache the converter once per PDF (`convert` plus a JSON of `text` and `page_boxes`, about 30 s for Hayek, seconds for the rest) and run `build_page` over the cache with the PDF reopened and `remove_rotation()` applied; coverage rules can then be tried on all PDFs in seconds.
- Trace joins by monkeypatching `assemble.joined` and pairing the recorded calls with the summary. For a page where body and footnote both join, the code runs the footnote join first; swap the pair when printing.
- To show that a fix is needed, remove just its call in a temporary copy of the code and run the real command, then restore and check the restore with grep.

Mistakes:
- A glob that matched its own output file (`for f in final_*.txt ... > final_all.txt`) grew without end; kill the shell and the `cat` by PID (a hook blocks `pkill -f`).
- Scripts under a path containing `dev/` that import `src` are blocked by a hook; throwaway scripts went to `/tmp/pjoin/tools/`.
- `git stash push` with an untracked file only errors and stashes nothing; an older unrelated stash `beads-backup pre-dev-switch` exists in this repo and must not be popped.
- zsh aborts a whole command when one glob has no match (`ls a/*.txt b/*.txt`).
- grep with a fixed-width context (`.{60}word.{60}`) misses matches near line ends; it produced the wrong `during droughts` statement above.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- "Skippable: ... a paragraph directly before a TABLE placeholder (caption), directly after a TABLE or FIGURE placeholder (note, figure caption)": before-TABLE is gone; after-TABLE only for uppercase or `(` starts; labels and titles after a bare label are new.
- "Open = not ending in `. ! ? : ;`": `;` no longer ends a paragraph.
- "`ambiguous_page_join` is raised only when a continuation exists": also not when the footnote continuation stands before the next page's first footnote definition.
- The hypothesis "A body paragraph directly before a table would be treated as a caption and skipped" was observed (Contreras page 16) and is fixed.
- extract stops on more than the earlier tripwires: `text_not_covered`.
