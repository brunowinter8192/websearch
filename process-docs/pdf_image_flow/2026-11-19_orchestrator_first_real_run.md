# Orchestrator record: first real run of the image-only PDF flow (2026-11-19)

Area: pdf_image_flow. Builds on the areas pdf_workflow, pdf_scan and pdf_form.

This file holds what only the orchestrator saw: the user's decisions in the order they were taken, and the results of the first real run with Haiku and Opus workers. The code decisions are in the worker files of this area.

## Decisions of the user on 2026-11-19, in order

1. Remove the fast text extraction (liteparse anchor text) and the character check of `assemble` from the process. Reason given: most PDFs are scans, and the check reported ok for files with missing text.
2. Split the PDF without reading a page, one worker per piece, merge at the end, then a sampling worker.
3. The sampling worker corrects what it finds, reports it, and draws a further 10 percent of new pages until one run finds nothing. The orchestrator checks its findings against the PDF.
4. Blocked pieces are split smaller. The stages changed three times during the evening: 20/10/5, then 20/10/5/2, then 20/10/5/2/1 with Opus 5-5 as a last attempt on single pages.
5. Final decision after the results below: stages 20 and 10 only, Haiku only, a PDF is indexed completely or not at all.

## What triggered decision 1

Ten articles converted with the old flow (anchor text plus character check) all passed `assemble` with batch recall between 0.952 and 1.000. A page-by-page comparison against `pdftotext` then showed missing text in four of them: Pies 2009 page 17 (footnotes 8 and 9 absent, 2813 of 4061 characters missing) and page 22, Jensen 2001 pages 5 and 9, Brennan 2012 page 1, Clark and Lee 2015 page 28. The batch-level count had been offset by added text such as figure descriptions.

## Results of the real run, image-only flow

Six articles were converted with the new flow, all with the Haiku model unless stated.

| Article | Pages | Result |
|---|---|---|
| Pies 2009 (German) | 34 | passed as one piece, no block |
| Clark and Lee 2015 (German and English on facing pages) | 34 | passed as one piece, no block |
| Brennan 2012 | 12 | 10 pages passed in pieces of 1 and 2 pages; page 5 blocked as a single page with Haiku and with Opus 5-5; page 7 blocked as a single page with Haiku |
| Jensen 2001 | 17 | no piece passed; blocked in pieces of 17, 10, 7, 5 and 2 pages and as single pages 10, 11 and 15 |
| Schelling 1981 | 25 | page 25 passed alone; pages 1 to 24 blocked with Haiku in pieces of 25, 20, 10, 5 and 2 pages and with Opus 5-5 in all twelve 2-page pieces |
| Hayek 1939 (scan) | 23 | pages 22 and 23 passed alone; page 21 blocked alone; piece 1-20 blocked |

Every block was the reply `API Error: Output blocked by content filtering policy`.

Observed, not explained:

- Jensen and Brennan had passed the same evening in the old flow, where the worker also got the anchor text. In the image-only flow Jensen passed with no piece. Two cases; the cause is unknown.
- The two articles that passed without a block are largely German.
- Smaller pieces did not make any article complete. Within Brennan the block sat on two specific pages and not on the size of the piece: page 6 passed alone after piece 6-7 had been blocked.
- Hypothesis, not verified: the filter reacts to verbatim reproduction of protected text. The error message names no reason.

A worker can be blocked after it has written its file. The Brennan worker for piece 1-12 wrote the file, then edited footnotes into it page by page and was blocked during those edits; the file held pages 1 to 5 of 12. This case led to the `status` command and the completeness check of `merge`.

## Sample loop, first real use

Both passing articles went through merge, sample, sample-report, sample-close and publish. The filter did not block a sampling worker.

- Pies 2009: 2 runs, 8 of 34 pages, 1 correction applied.
    - Run 1, page 25: footnote 15 held the placeholder `[?]`. The sampling worker replaced it with "eine Replik". The page reads "als Kritik". The orchestrator sent the finding back, the worker corrected its excerpt.
    - Run 2: no finding.
- Clark and Lee 2015: 3 runs, 12 of 34 pages, 3 corrections applied, 1 rejected.
    - Run 1, page 20: "also" was missing (real, corrected). In the same paragraph the transcription said "dieser Beteiligten" where the page reads "derer"; the sampling worker had not reported it, the orchestrator found it while checking the first correction.
    - Run 2: page 5 "Cratchit" against printed "Cratchet", page 11 "nur nicht" missing. Both real.
    - Run 3, page 13: the worker added the tail of footnote 6 as a new footnote. The footnote was already complete in the Markdown. Rejected with `--reject 13`; the loop ended.

What this shows:

- The sampling worker was wrong in three of five runs: one invented word, one missed deviation, one duplicate. Each was only visible because the orchestrator read the PDF page. The orchestrator's check against the page is necessary.
- Haiku transcribing from images replaces single words. Four word-level deviations on twelve sampled pages of Clark and Lee.
- The loop ends after a small share of the pages. 22 of 34 pages of Clark and Lee were never sampled.
- In the bilingual layout of Clark and Lee the page markers do not always sit at the page boundary; text of a page can stand under the neighbouring marker. A whole-document character comparison against `pdftotext` showed no missing text (Pies 0.9975, Clark and Lee 0.9886).

## State in RAG after the run

Collection wise2627-reference, prefix SGSC: 14 articles and 4 slide decks. The four versions with known gaps from the old flow (Jensen, Brennan, Pies, Clark and Lee) were deleted; Pies and Clark and Lee were indexed again from the new flow. Jensen, Brennan, Schelling and Hayek are not indexed.

## Not done

- Two spawns failed with "CC did not reach input-ready state within 30s" and left a worktree and a branch that `worker-cli` does not know: `pdf-sgsc-hayek-21-22` and `pdf-sgsc-jensen-16-16`. A hook blocks removing them by hand.
- `dev/pdf_scan/patch/websearch-pdf_SKILL.patch` is a stale skill patch.
- Nothing on `main`, nothing pushed, plugin not published as of the end of the run. All commits of this area are on `integration`.
