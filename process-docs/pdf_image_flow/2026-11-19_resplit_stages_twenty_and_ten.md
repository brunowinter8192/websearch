# 2026-11-19 - Resplit stages 20 and 10 only

Area: pdf_image_flow. Worker branch `pdf-stages`, base `integration`, not pushed.

## Stages 20 and 10, nothing below (2026-11-19, user decision, fixed)

### Decision

- A blocked piece is split into pieces of 20 pages, then 10 pages. There is no stage below 10 pages.
- A blocked piece of 10 pages or fewer is refused by `resplit` with `piece_minimal`. The PDF is then not indexed. A PDF is indexed completely or not at all; there is no partial book.
- Only Haiku workers transcribe. No other model is used as a last attempt.

This supersedes, in the earlier process-docs of this area, the ladders 20, 10, 5 (decision 5), 20, 10, 5, 2 (section "Two-page stage") and 20, 10, 5, 2, 1 (section "One-page stage"), together with every example there that splits a piece of 10 pages or fewer (10 -> 5/5, 8 -> 5/3, 81-85 -> 81-82/83-84/85, Jensen 16-17 -> 16/17, Schelling 21-25 -> 21-22/23-24/25, Hayek 21-23 -> 21-22/23).

### Facts observed on 2026-11-19 with the stages 20, 10, 5, 2, 1 (relayed by the orchestrator)

- Schelling 1981 (25 pages): blocked with Haiku in pieces of 25, 20, 10, 5 and 2 pages. Blocked with Opus 5-5 as one piece of 25 pages (twice, old prompt) and in all twelve pieces of 2 pages (1-2 to 23-24). Page 25 alone passed with Haiku.
- Jensen 2001 (17 pages): no piece passed. Blocked with Haiku in pieces of 17, 10, 7, 5 and 2 pages and as the single pages 10, 11 and 15.
- Brennan 2012 (12 pages): 10 of the 12 pages passed in pieces of 1 and 2 pages. Page 5 was blocked as a single page with Haiku and with Opus 5-5, page 7 as a single page with Haiku.
- Hayek 1939 (23 pages): pages 22 and 23 passed as single pages, page 21 was blocked as a single page, piece 1-20 was blocked.
- Pies 2009 and Clark and Lee 2015 (34 pages each) passed as one piece without a block.
- No PDF became complete through pieces smaller than 10 pages.

What this says about the hypothesis "smaller pieces get past the content filter" (earlier sections of this area): small pieces let single pages through (Schelling 25, Brennan 10 of 12, Hayek 22 and 23), but in every blocked article at least one page stayed blocked even alone or with Opus, so none of them could be indexed completely. Under "complete or nothing" the stages below 10 only cost worker runs. The model attempt with Opus did not unblock anything Haiku could not do, hence Haiku only.

### What changed

- `RESPLIT_PIECE_PAGES = (20, 10)` in `src/config.py`. The rule in `resplit.py` is unchanged: the largest stage strictly smaller than the blocked piece. So a piece of 11 to 20 pages becomes 10 plus the rest, a piece of 21 or more becomes pieces of 20 plus the rest, and a piece of 10 pages or fewer has no smaller stage and is refused. No new code path was needed for the refusal.
- Examples from the tests: 50 -> 20, 20, 10; 20 -> 10, 10; 18 -> 10, 8 and 8 refused; book piece 51-85 -> 51-70, 71-85 -> 71-80, 81-85, both refused. The four observed articles under the new stages: Schelling 1-25 -> 1-20, 21-25 -> 1-10, 11-20, 21-25; Jensen 1-17 -> 1-10, 11-17; Brennan 1-12 -> 1-10, 11-12; Hayek 1-23 -> 1-20, 21-23 -> 1-10, 11-20, 21-23. Every one of those end pieces is refused, and a refusal leaves the manifest and the prompt of the piece unchanged.
- The `resplit` output always says "pages" now; the singular "page" for size 1 had become unreachable and was removed.
- Logged config field `resplit_piece_pages` is `[20, 10]`, so runs from this build get a new `config_hash`.
- `resplit` CLI help: "20, then 10 pages; 10 pages or fewer is final".
- Tests: `test_pdf_resplit.py` rewritten for the two stages (the removed tests asserted the 5, 2 and 1 stages); `test_pdf_merge.py` mixed-size merge no longer resplits a 10-page piece (pieces 1-20 21-30 31-40 41-50 51-85); `test_pdf_split.py` expects the new config list.

### Not changed

- No file under `skills/` was touched (task instruction). At commit e42a9b5 the skill sentences that named the stages and the `piece_minimal` size still described the older ladders, as did the three patch files in `dev/pdf_image_flow/patch/`; see the section "Skill text and the removed patch files" below.
- The model choice is not in this code: `split` writes the worker model from `config/pdf_models.json` into the manifest, which was already Haiku (`claude-haiku-5-5[1m]`).

### Verification

All `dev/tests/test_pdf_*.py` (11 files) and `dev/tests/test_cli_bootstrap.py` run in parallel, one pytest per file with its own `--basetemp`: 87 tests pass. The first run failed in `test_pdf_merge.py` only, because its mixed-size case resplit the 10-page piece 21-30, which is now refused as minimal; the test was adjusted, not the code.

## Skill text and the removed patch files (2026-11-19)

### Where the skill text lives

The skill text is `skills/websearch-pdf/SKILL.md`, committed by the user on `integration` as 9356d06 ("docs: pdf skill for image-only flow, stages 20 and 10"), after the merge of e42a9b5 into integration as a83d146. That file is the only source of the skill text; agents never write it (a hook blocks every write under `skills/`). Checked on 2026-11-19 by reading the file in full, it describes:
- the image-only flow `split`, `status`, `resplit`, `merge`, `sample`, `sample-report`, `sample-close`, `publish`, with the done rule "idle and `status` says `complete`";
- the stages "20 Seiten, dann 10 Seiten. Kleiner wird nie geteilt", refusal with `piece_minimal` at 10 pages or fewer;
- "Ein PDF wird ganz oder gar nicht indexiert";
- Haiku for every worker via `MODEL_SELECTION_FILE`, never another model, not even as a last attempt.

### Removed

`dev/pdf_image_flow/patch/` with its three files `websearch-pdf_SKILL.patch`, `websearch-pdf_SKILL_incomplete_pieces.patch` and `websearch-pdf_SKILL_two_page_stage.patch`. They were diffs against earlier skill texts (the chain started at the unpatched skill on integration ea634f4) and do not apply to the file of 9356d06; their content is superseded by that file. That was the only content of `dev/pdf_image_flow/`, so the directory is gone and `pdf_image_flow` was removed from the list of area subdirectories in `dev/DOCS.md`. No other DOCS.md named the patch files.

Statements in the earlier process-docs file of this area that no longer hold (not edited there): every instruction to apply the patches ("Apply from the repo root with `patch -p1 < ...`", "A real run of the skill has to apply ... first"), "the skill on the branch still describes `extract`, `assemble`, the control worker", and "The skill on integration at ea634f4 still had neither patch applied" as a description of the skill today.

Not removed, outside this task: `dev/pdf_scan/patch/websearch-pdf_SKILL.patch`, which area pdf_image_flow already recorded as describing the removed scan flow and as not to be applied. It does not apply to 9356d06 either.
