# 2026-11-20 - Wright 2006: table notes written as footnotes, text after tables and figures (assemble)

Area: pdf_repair_flow. Worker branch `pdf-wright-fix`, base `integration` (5cee415). Code commit 9db477b ("fix: table notes, uppercase captions and text after tables and figures"). Builds on the page join work recorded earlier in this area (rule numbers below refer to the Meyerstein follow-up there).

## Starting point (2026-11-20)

The batch `/tmp/pdf_SGSC_Literatur_WrightRwabizambugaVoluntaryCodesEquatorPrinciples_2006/` (29 pages, all 9 workers complete) failed:
`assemble FAILED (ambiguous_page_join): page 13: its last footnote runs on, but page 14 has no text before its first footnote`.
The batch was never modified. Every run used copies under `/tmp/wfix/copies/<stem>/` with `samples/` removed.

## What pages 13 and 14 contain

- `page_png/p13.png`: TABLE 1 with caption above, then the table notes `* Equator bank as of June 30, 2004.` and `Notes: Data based on ...` in small type, then body text. The body ends `... on the environment and` (open).
- `page_png/p14.png`: TABLE 2 with caption above, then the notes `* Equator bank ... **Not formally an Equator bank, ...`, then the body `sustainable development, 72 percent ...`, which continues page 13.
- The page worker wrote both notes as `[^*]:` and `[^**]:`, and `Notes:` as `_Notes_:`. The captions are `**TABLE 1** ...` (upper case).

Why it failed: `[^*]:` started a footnote area, so on page 13 every following paragraph (the body included) belonged to that "footnote". The body ending became a footnote target. On page 14 the paragraph before the first `[^...]:` is the TABLE placeholder, so the tripwire fired.

## Decision: `[^*]` next to a table is a table note

Survey over all ten batches (Wright, Scholtens, Hayek, Conley, Contreras, Heilmayr, Moura, Schrage, Schouten, Meyerstein) of every footnote definition directly after a TABLE placeholder:

| batch, page | definition | what the print shows |
|---|---|---|
| Wright 13, 14, 15 | `[^*]`, `[^**]` | table notes |
| Meyerstein 155 | `[^*]: three banks selected both responses.` | table note (page_png/p155.png) |
| Scholtens 19 | `[^a]`, `[^b]` | table notes |
| Meyerstein 22, 141, 156 | `[^26]`, `[^170]`, `[^178]` | real page footnotes placed after a table at the page bottom |

Rule built: a footnote definition whose mark contains no digit (`[^*]`, `[^**]`, `[^a]`) is a table note when it stands directly after a TABLE placeholder, or directly after such a table note. A table note is skippable and is not a footnote definition: it starts no footnote area and it does not count as "first footnote" of a page. A numbered definition after a table stays a footnote. The Schrage page-1 note `[^*]: Original research ...` is not after a table and is unaffected.

The label paragraph `_Notes_: ...` after a symbol table note is also a table note. Its form is a label in `*`/`_` emphasis followed by `:` (`_Notes_:`, Wright page 13; `_Sources_:`, Wright page 20 directly after TABLE 5).

## Three more join faults that showed once 13->14 passed

The first fix (table notes only) let assemble run through, and the full join list then showed more wrong joins in Wright. Read the whole join list after every change.

1. Upper-case captions. `CAPTION_LABEL` only knew `Table`, `Fig.`, `Figure`. `**TABLE 1**` and `**FIGURE 1**` (Wright pages 13 to 20) were body text. The old trace before the crash had `12->13` joined onto `**TABLE 1** Top 10 ...` and chained 12->14, 12->15. `TABLE` and `FIGURE` were added to the caption label.
2. Body text after a figure. Every paragraph directly after a FIGURE placeholder was skipped as a caption. Wright prints the caption above the figure. Page 17 `and rapid uptake ...` continues page 16 (`... shed light on the wide`). Page 19 `book runners, managers, ...` continues page 18 (`... as arrangers, providers,`). Both were skipped. Then the wrong next paragraph was joined (`These governance conditions ...`), or page 19 counted as a footnote-only page and 18->21 joined `providers,` + `Principles were ...`. Rule: the paragraph after a FIGURE is skipped only if it does not start lower case (`runs_on`).
3. Upper-case body text after a table. Page 15 holds TABLE 3, `[^*]`, TABLE 4, then `Africa and the Middle East includes ...` (continuation of page 14, `... the regional league table covering`), then `These distributions suggest ... to adopt` (open, continued on page 16). The rule "a paragraph directly after a TABLE starting with an upper-case letter or `(` is a table note" skipped `Africa ...`, and 14->15 joined `These distributions ...`.

Rule for 3: a paragraph directly after a TABLE that starts with an upper-case letter is body text, not a note, when it is the last paragraph of the page or when the next paragraph is body text that also starts with an upper-case letter. A `(` start is always a note (Scholtens page 9 `(continued on next page)`, the last paragraph there).
- The "last paragraph" part is needed because of the join mechanics: after `Africa ...` is popped into page 14, `These distributions ...` stands directly after TABLE 4 as the last paragraph of page 15. It must stay a body target so that 15->16 joins.
- Observed notes that keep their status: Contreras `This distribution ...` (followed by `Table 3`), `Unit of observation ...` (followed by `Table 4`), `Mean differences ...` (followed by `(%) for adopters ...`), `Exponentiated coefficients ...` (followed by lower-case text or `Table 8`), Scholtens `Source: Bankscope ...` (followed by `finding that ...`), `Source: Datastream.` (followed by `[^*]`).
- `continuation()` was traced on all ten batches for a found continuation preceded on its page by a skipped upper-case table note. Only three cases had an upper-case continuation: Wright page 15 and Contreras page 6 (both wrong before), and Meyerstein page 101, where the candidate was `(Watchman 2007).` and nothing was joined.

## Verification (2026-11-20)

`cli.py pdf assemble` on the fresh copy `/tmp/wfix/verify/wright`: `assemble ok`, 20 joins. Each one was checked at its join point, against page_png where a table or figure stands between:

| join | end of page | start of next | judgement |
|---|---|---|---|
| 1->2 | `how financial institutions should consider environmental and` | `social issues in their project finance operations. The paper` | right |
| 2->3 | `tal and social record, or even a commitment to these issues,` | `it is false to assume that this is always the case.[^8] In t` | right |
| 3->4 | `ection will discuss the emergence of the Equator Principles,` | `and the fifth section will provide a regional analysis of ad` | right |
| 6->7 | `tored by a civil society group may face greater reputational` | `risks from irresponsible corporate practices than firms that` | right |
| 7->8 | `a public relations war with critics over the appropriateness` | `of corporate practices, adopting a voluntary code of conduct` | right |
| 8->9 | `rge-scale, capital-intensive investment projects financed by` | `public and private multinational and regional financial inst` | right |
| 9->10 | `ed to displace more than 1 million people and feared by some` | `to cause widespread environmental damage. While the World Ba` | right |
| 10->11 | `linked to the emergence of the Equator Principles, which has` | `produced expectations that investment projects financed by p` | right |
| 12->13 | ` finance market has been profound, and is likely to increase` | `as more financial institutions adopt them, and implementatio` | right, over TABLE 1 and its notes |
| 13->14 | `) statement by financial institutions on the environment and` | `sustainable development, 72 percent are from Europe, 12 perc` | right, the reported failure |
| 14->15 | `uator banks. For example, the regional league table covering` | `Africa and the Middle East includes only five Western Europe` | right |
| 15->16 | `ts produce different strategic incentives for firms to adopt` | `voluntary codes of conduct. Furthermore, the high uptake of ` | right |
| 16->17 | `gic incentives they produce for firms shed light on the wide` | `and rapid uptake of the Equator Principles among financial i` | right, over FIGURE 1 |
| 18->19 | `ent, and often multiple capacities, as arrangers, providers,` | `book runners, managers, financial advisers, and legal advise` | right, over FIGURE 2 |
| 18->21 | `ich is not surprising, considering the fact that the Equator` | `Principles were primarily devised as a framework to diffuse ` | right; page 19's paragraph now sits on page 18, page 20 is TABLE 5 with `_Sources_:` only |
| 21->22 | `itutional environments shaped by targeted advocacy campaigns` | `organized by civil society groups and strong regulatory syst` | right |
| 22->23 footnote | `ley Act into law, intended to protect investors by improving` | `the accuracy and reliability of corporate disclosures. The a` | right |
| 23->24 footnote | `d anniversary Equator Principles implementation assessment,”` | `prepared by Michelle Chan-Fishel, (Friends of the Earth, U.S` | right |
| 26->27 | `; environmental assessment (OP 4.01, October, 1998), natural` | `habitat (OP 4.04, November 1998), pest management (OP 4.09, ` | right |
| 27->28 | ` and Society Review_ 109(2004): 449–477). found that British` | `firms, in particular, “have, or attempt to have, a distinct ` | right (the `). found` is in the worker text) |

Missed, not fixed: 25->26. Page 25 ends with the note `... “Pollution reduction preferences of U.S.`, and page 26 starts `environmental managers: Applying Ajzen’s theory ...`. The abbreviation `U.S.` ends in a full stop, so the note counts as closed. The continuation stays as its own paragraph on page 26. No wrong join results.

The book holds the three Wright table notes as `[^*]:` lines on pages 13, 14 and 15, so the same definition label occurs three times. assemble does not rename marks.

Regression: `assemble_workflow` on copies of the ten batches with `samples/` removed, traced with the code of 5cee415 (`git archive HEAD src config` into `/tmp/wfix/old`) and with the new code. The trace lists every join with 60 characters on both sides.
- Identical: Scholtens 9, Hayek 23, Conley 22, Heilmayr 9, Moura 6, Schrage 8, Schouten 6.
- Contreras 13 joins. 5->6 changed its tail from `The second key variable to our analysis is Susceptibility.` to `Concentrationji is the share of syndicated project finance l...`. page_png/p6.png shows `Concentration_ji is the share ...` as the first text under Table 1, continuing `... and zero otherwise;` of page 5. The old join was wrong (rule 3).
- Meyerstein 148 joins instead of 147. New: 131->132 `... on individual reputation disagree or disagreed` + `strongly with the possibility of having a collective reputat...`. page_png/p131.png shows `As Table 7.1 illustrates, ...` under the table, running on to page 132. Before, this last paragraph after a table was treated as a note, and the join was missed (rule 3, last paragraph).
- So the request "same joins as with the current code" is not met literally for Contreras and Meyerstein. Both differences are corrections confirmed on the page images.

Tests: 4 new in `test_pdf_assemble.py`: symbol and label table notes with an upper-case caption, upper-case text after a table followed by body text, upper-case last paragraph after a table, lower-case text after a figure. Each fails on 5cee415, checked with the old `src` next to the new tests in `/tmp/wfix/oldtest`. The first fails with the observed `ambiguous_page_join` message. The figure test first joined onto `**FIGURE 1** ...`. Full `run_strands.sh`: 90 strands, 1 skipped, 0 failed. The tripwire test (non-text paragraph before the next page's first footnote) is unchanged and passes.

## Hypotheses, not observed, nothing built

- A real page footnote with a symbol mark (`[^*]`) placed by a worker directly after a table would be taken as a table note.
- A table note that starts with an upper-case letter and is followed by an upper-case body paragraph, or that is the last paragraph of its page, would be taken as body text. All observed last-paragraph notes are terminated, so as body they are no join target.
- A real figure caption under a figure that starts lower case would be taken as body text.
- An abbreviation with a full stop at a page end (`U.S.`) closes the paragraph (observed once, Wright 25->26, not fixed).

## How the work ran, what to reuse

- Tools in `/tmp/wfix/tools/` (temporary): `trace.py` (join list with 60 characters each side, wraps `planned_joins`), `run.sh <code_root> <label>` (all ten copies in parallel, output in `/tmp/wfix/out/<label>_<stem>.txt`), `survey.py` and `survey2.py` (paragraphs directly after TABLE/FIGURE placeholders and footnote definitions after tables), `skipped_notes.py` (continuations found after a skipped upper-case table note), `leftover.py` (open targets left after joining).
- The survey of every paragraph after a TABLE or FIGURE across all batches decided the rules. Without it, the rule "symbol mark" (versus Meyerstein's numbered footnotes after tables) and "upper-case followed by upper-case body" would have been guesses.
- Mistake: the first rule chained every upper-case paragraph after a table note. Meyerstein page 155 `It is important ...` (body after `[^*]`) would have become a note. The chain is limited to symbol notes and labels.

## Statements elsewhere in this area that no longer hold (recorded here, not edited there)

- "Table note: a paragraph directly after a TABLE is skippable only when it starts with an uppercase letter or `(`". An upper-case paragraph is now body when it is the last paragraph or is followed by upper-case body text. Symbol-mark definitions and emphasis labels are also notes.
- "A figure caption directly after a figure placeholder is also skippable". Not when the paragraph starts lower case.
- "Footnote area: every paragraph after a footnote definition ... belongs to that footnote". This no longer holds when the definition is a table note.
- Caption label list: upper-case `TABLE N` and `FIGURE N` are added.
- The page join and text coverage record of this area says that Contreras page 6 joins `$\text{Concentration}_{ji}$ is the share ...`. In the batch `/tmp/pdf_SGSC_Literatur_ContrerasBosKleimeierSelfRegulationEquatorPrinciples_2019/`, the paragraph is `Concentrationji is the share ...` with an upper-case start, and up to 5cee415 the join took `The second key variable ...` instead.
