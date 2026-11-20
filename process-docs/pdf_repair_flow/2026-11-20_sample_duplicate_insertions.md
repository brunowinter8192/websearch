# 2026-11-20 - Sample loop: insertions that repeat text joined onto an earlier page

Area: pdf_repair_flow. Worker branch `pdf-sampledup`, base `integration` (142aa5b). Code commit 8f1be8b ("fix: sample-close rejects insertions repeating earlier joined text"). Builds on the page join work recorded earlier in this area and on the sample loop of the area pdf_image_flow.

## Problem (observed 2026-11-20)

assemble joins a paragraph that runs over a page boundary onto the page where it begins, also across whole table or figure pages. `sample` cuts an excerpt for page N from the marker of page N-1 to the marker of page N+1. When page N-1 holds only a table or figures, the paragraph that continues on N stands under page N-2 or earlier, outside the excerpt. The sampling worker sees the continuation printed at the top of page N, does not find it in the excerpt and inserts it. Accepting that correction would put the text into the book twice. Before this change the main agent found each one with grep and passed `--reject`.

Observed cases, batches read-only, all experiments on copies under `/tmp/sdup/verify/`:

| batch, run, page | join | finding of the worker | inserted text | where it already stands |
|---|---|---|---|---|
| Heilmayr 2020, run 1, page 9 | 7->9 over figure page 8 | `missing_text: opening sentence of page (the mill was certified ... using equation (2)) missing` | `the mill was certified ( $I_{cert_{m,t}=1}$ ). We then calculated the certified proportion of the point's local market ( $L_{i,t}$ ) using equation (2).`, directly after `<!-- page 9 -->` | end of the list item `- Local markets: ...` on page 7, written `( $I_{cert_{m,t}}=1$ )` and `point’s` |
| Scholtens 2007, run 2, page 10 | 8->10 over table page 9 | `missing_text: two-column body text below Table 1 continuation missing, added` | the paragraph `finding that almost all the size-related ... (Gunningham & Sinclair, 2002).`, after the `Source:` note of Table 1 (continued) | end of the paragraph `The hypotheses we want to test ...` on page 8, character for character |

The worker's insertion differs from the book text in markup and quote glyphs (Heilmayr: `=1}$` against `}=1$`, `'` against `’`). An exact string comparison misses it.

The task named "two similar reports from the earlier hand run (Scholtens page 3, sample of 2026-11-20 morning)". The only file found is `/tmp/pdfx_run/sample/findings.md` with one page 3 finding: the paragraph `The history of the EP is described by Esty, ...` was reported missing from `excerpt_p3.md`. It stood glued into a page 2 paragraph, outside the excerpt (the hand-run excerpt held page 3 only). That was a real misplacement, later fixed by the paragraph split in extract (recorded earlier in this area), and the hand-run worker did not edit any excerpt. It shares the mechanism "text the worker sees is in the book before the excerpt", but it is not a duplicate of a join and is not handled by this change. A second report from that run was not found.

## Decision: detect the duplicate at report and close, reject it automatically

Chosen because it works on the existing batches and on exactly the corrections the workers wrote, whatever the worker does. Rule, in `src/pdf/sample_duplicates.py`:
- The changed excerpt is compared line by line with its original (difflib, the same comparison as the report).
- A change is a duplicate insertion when it is a pure insertion and every inserted text block (non-blank lines between blank lines) is, after `normalized` from `coverage.py` (NFKC, casefold, alphanumerics only), a proper suffix of the normalized text of a paragraph in the book before the excerpt's start. Proper suffix: a join makes the earlier paragraph "head + continuation", so the continuation is its tail and the paragraph is longer. The source page is the marker section of the nearest such paragraph.
- Excerpt kinds: `correction` (no duplicate insertion), `duplicate` (every change is a duplicate insertion), `mixed` (both).

Behaviour:
- `sample-report`: a `duplicate` excerpt gets the line `DUPLICATE: the inserted text already ends a paragraph on page 7, before this excerpt. sample-close rejects this correction.` under its heading. The summary has two new lines: `duplicates of earlier text, rejected at close: <files or none>` and `duplicates mixed with other changes, close refuses: <files or none>`.
- `sample-close`: a `duplicate` excerpt is never applied. It is listed in `rejected` and in the new run field `duplicates`; the summary line is `rejected as duplicate of earlier text: <files or none>`. It does not count as an applied correction, so a run whose only correction is a duplicate ends the loop (`loop ended: run 1 applied no correction`), the same result as the hand rejection before.
- Tripwire `duplicate_mixed`: a `mixed` excerpt that the main agent did not `--reject` stops `sample-close` with the files named. Never observed. The report marks it with a WARNING line so the main agent sees it before closing.
- The book sha check (`book_changed`) now runs before the judgement in `sample-close`, because the judgement reads the book. Same failure class and message.

Rejected alternative, not built: let assemble record its joins and let `sample` start an excerpt at the page where a joined paragraph begins. That would prevent the insertion, but the existing batches have no join record, the worker could still insert the text, and the two observed corrections could not be replayed.

## Survey before building (2026-11-20)

`/tmp/sdup/tools/survey.py` ran the rule over every changed excerpt of every batch under `/tmp/pdf_*/samples/` (book before the excerpt taken from the current book at the excerpt's position). 10 changed excerpts in 6 batches. Flagged `duplicate`: exactly Heilmayr run 1 `excerpt_9.md` (source page 7) and Scholtens run 2 `excerpt_10.md` (source page 8). Not flagged: the 7 applied corrections (Clark & Lee 20, 5, 11; Meyerstein 77-78; Pies 25; ResponsibleSteel 34; Scholtens 21) and Clark & Lee run 3 `excerpt_12-13.md` (rejected by hand for another reason, a footnote added from the image). Scholtens run 1 page 21 added `(continued next page)`; the book has `(continued on next page)` on page 9, which is not a suffix match after normalization, and it is a whole paragraph there, not a tail.

## Verification (2026-11-20)

Copies `/tmp/sdup/verify/heil` and `/tmp/sdup/verify/scho` of the two batches. In each the run was reopened: `status` set to `open`, `applied` and `rejected` removed from `run.json`; excerpt files and `findings.md` are the worker's originals. The book sha256 equals the run's `book_sha256` in both (neither run had applied anything). Then `cli.py pdf sample-report` and `cli.py pdf sample-close` without `--reject`.

Heilmayr run 1:
```
corrected excerpts: 1 (pages 9)
duplicates of earlier text, rejected at close: excerpt_9.md
DUPLICATE: the inserted text already ends a paragraph on page 7, before this excerpt. sample-close rejects this correction.
sample run 1 closed: corrections applied 0, rejected 1
rejected as duplicate of earlier text: excerpt_9.md
loop ended: run 1 applied no correction
```
Scholtens run 2: the same with `excerpt_10.md`, `page 8`, `run 2`, `pages sampled: 6 of 22`.

`the mill was certified` occurs once in the Heilmayr book afterwards and `finding that almost all the size-related` once in the Scholtens book. The same replay with the code of 142aa5b (`git archive HEAD src config cli.py` into `/tmp/sdup/old`) on second copies applied both (`corrections applied 1, rejected 0`, `loop continues`) and left each sentence twice in its book.

Tests: `dev/tests/test_pdf_sample_duplicates.py`, 2 tests parametrized over the two observed shapes (Scholtens: continuation after a table `Source:` note, identical text; Heilmayr: continuation right after the marker, with the formula markup and apostrophe variants). Report marks the duplicate with page N-2; close rejects it, the book is unchanged, the loop ends. All 4 fail on 142aa5b (checked with the old `src` next to the new tests in `/tmp/sdup/oldtest`); the failure messages show the missing summary line and `corrections applied 1, rejected 0`. Full `run_strands.sh`: 91 strands, 1 skipped, 0 failed.

## Skill lines (skills/websearch-pdf/SKILL.md, integration at 247bdd3; user-owned, not edited)

- After line 153 a new bullet: ``   - Eine Korrektur, die der Bericht mit `DUPLICATE` kennzeichnet, prüfst du nicht. `sample-close` verwirft sie selbst.``
- Optional, for the tripwire: ``   - Steht bei einer Korrektur `WARNING: an inserted text already ends a paragraph`, lass den Worker den eingefügten Text entfernen oder nenne die Seite mit `--reject`.``
- Line 165 (step 8) can stay: the close output lists duplicates under `rejected` as well.

## Hypotheses, not observed, nothing built

- A real missing text whose normalized form happens to be the tail of a longer earlier paragraph would be rejected as a duplicate.
- A continuation in the middle of a paragraph that runs over three pages (not its tail) is not recognised.
- A worker inserting a continuation whose joined paragraph lies inside the excerpt (page N-1) is not checked; only text before the excerpt counts.
- A worker that replaces neighbouring lines while inserting the continuation (a `replace` hunk, not an `insert`) is not recognised.

## Statements elsewhere that no longer hold (recorded here, not edited there)

- `src/pdf/prompts/sample_prompt.md` said an excerpt begins with the page before the checked page because a paragraph that continues on the checked page stands completely there. Both observed cases contradict it: with a table or figure page between, the paragraph stands two pages before. Corrected after review, see the next section.
- Area pdf_image_flow: "That covers the text of page N that stands in page N-1's section under the paragraph rule". It does not cover text joined over a whole table or figure page.

## Follow-up after review: sampling prompt corrected (2026-11-20, user request)

Commit b41fa7d ("fix: sampling prompt on continuations from several pages earlier"), `src/pdf/prompts/sample_prompt.md` only:
- Intro, before: "An excerpt begins with the page before the page you check, because a paragraph that begins on that page and continues on the checked page stands completely on the page where it begins."
- Intro, after: "An excerpt begins with the page before the page you check. A paragraph that continues on the checked page stands completely on the page where it begins. That page can be several pages earlier when table or figure pages lie between, and then the paragraph is not in the excerpt. Continuation text at the top of a checked page that is missing from the excerpt for this reason is not a finding: do not add it."
- "Not findings" bullet, before: "text of a checked page that stands before its line <!-- page N --> because its paragraph began on the page before"; after: "... stands before its line <!-- page N --> or before the excerpt, because its paragraph began on an earlier page".

Prevention and safety net together: the prompt should keep the worker from inserting the continuation; if it still does, `sample-close` rejects the insertion as before. Whether Haiku follows the new sentence is not verified, because no sampling worker ran with it. The prompt files are hashed into `prompt_sha` of the extract start record, so the next extract has a new `config_hash`. Existing batches keep their already written `samples/run_<k>/prompt.md`; only runs opened after this commit get the new text. Tests: `test_pdf_sample.py` 11, `test_pdf_sample_loop.py` 8, `test_pdf_extract.py` 20 passed.

## How the work ran, what to reuse

- Replay a closed run: copy the batch, set `status` to `open` in `run.json`, drop `applied` and `rejected`, check that the book sha256 still equals `book_sha256` (true when the run applied nothing), then run `sample-report` and `sample-close`. The worker's excerpt files are still in the run directory.
- Old code side by side: `git archive HEAD src config cli.py` into a scratch directory; run `cli.py` from there with the worktree's venv python.
- Pick test pages deterministically: `draw_sample_pages({'pages': n, 'pdf_sha256': 'a'*64}, [])` gives `[8]` for 9 and 10 pages; the test book is built around page 8.
- zsh: `echo =====` aborts the call; use quotes.
