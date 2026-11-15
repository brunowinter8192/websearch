# 2026-11-15 - Orchestrator cycle: scan flow for the websearch-pdf skill

Orchestrator view of the cycle that added the scan flow. The code and its design are described in the worker file of this area; the text-mode tooling is described in the area pdf_workflow. This file holds what only the chat with the user contained.

## What the user ordered

The user supplied a written flow for pages without a text layer and asked to implement it in the skill and in the tooling:

1. Transcription: `extract` splits into 50-page batches as before, one worker per batch reads only the page images, no anchor text.
2. Control on a sample: after transcription one single control worker for the whole PDF checks 10 % of the pages, drawn at random over all batches, by comparing the page image with the text of the first worker.
3. Finding: the control worker reports per checked page whether the text is correct and names every deviation (missing paragraphs, misread numbers, invented text, broken tables).
4. Decision: `assemble` writes the file only when the sample has no grave finding; otherwise it names the pages with findings and the PDF is not indexed.

The user's own arithmetic example mentioned 40 pages for a 200-page scan (20 %); the stated share is 10 % and 10 % was built.

## Decisions taken by the orchestrator and reported to the user (2026-11-15)

- Per PDF, not per page. The user's text left open whether a mixed PDF (single scanned pages inside a normal PDF) gets the scan flow only for those pages. Decided per PDF: the existing criterion already works per PDF, and no mixed PDF has been observed. Hypothesis, unhandled: a mixed PDF with an average at or above 100 characters per page runs in text mode, and its scanned pages lower the batch recall.
- The control worker classifies every deviation as grave or not grave itself; one grave finding fails `assemble`.
- A failed scan is not repaired by hand; the PDF is not indexed. Text mode keeps its repair step.
- The share of 10 % is a constant in the tooling, not a setting.
- The names `mode`, `control_pages`, `prompt_control.md`, `control.json` were chosen by the orchestrator in the skill draft and given to the worker as a fixed interface.
- Accepted from the worker without change: `ceil(10 %)` per batch, draw seeded with the sha256 of the PDF, simple control read.

## Skill state on 2026-11-15

- The orchestrator wrote the new skill text to `/tmp` and opened it as a patch; the user applied it himself (commit `0f1a18b` on integration, 37 insertions, 0 deletions).
- Observed after the user's edit: all new lines are in `skills/websearch-pdf/SKILL.md`, but seven superseded lines were not removed. Step 1 still says that `extract` aborts on a PDF without a text layer, Step 2 has two headings, Step 3 carries the old bullets of the content check and the old points 2 and 3 next to the new ones.
- The remaining removal is stored as `dev/pdf_scan/patch/websearch-pdf_SKILL.patch` (diff -u of the live file against the intended text). The skill is user-owned; the orchestrator did not edit it.

## Verification on the real scan (2026-11-15)

- PDF: the Kley article from the LÜAG folder of wise2627, copied to `/tmp/KleyScanVerify_2023.pdf`, 9 pages, no text layer.
- `extract` and `assemble` were run from the worker's worktree with `WEBSEARCH_CONVERSION_LOG_PATH` pointing at the log of the main checkout, so run `36fa6e3a3425` is in `src/logs/conversions.jsonl` of the main checkout.
- Haiku workers were spawned as the skill says (`MODEL_SELECTION_FILE`), one for batch 1-9, then one control worker. Transcription worker: batch file after about 1 minute. Control worker: `control.json` with page 5, `correct: true`, no findings.
- `assemble` wrote `/tmp/pdf_scan_verify_out/KleyScanVerify_2023.md` (not indexed). Pages 1, 2, 3, 5 and 8 were compared with the page images by the orchestrator: text, headings, numbers and names match; the web page controls of the print-out (menu, search bar, footer links) are left out.
- Observed property of this PDF, not a defect of the transcription: the print-out cuts text at page breaks (page 2 ends with "nach einem zeitaufwendigen", page 3 starts with "damit einhergehenden"), so sentences are incomplete in the source itself.
- Not verified with real workers: the path with a grave finding. It ran only in the hermetic tests, because the Kley sample had no finding.

## Tool observation: `worker-cli wait` from a directory outside the project

The session ran in `/Users/brunowinter2000/Documents/wise2627` (not a git repository); workers were spawned with `PROXY_PROJECT_PATH` set to the websearch checkout. `worker-cli wait` accepts no prefix and no `cd`, so it ran from the wise2627 directory. Observed: the first wait ended with `timeout` although the worker had been idle for a long time. Hypothesis (not checked): `wait` looks for workers of the current directory's project and does not see the websearch workers. Workaround used: `worker-cli wait --timeout <seconds>` with a short limit, then `worker-cli status <name>`.
