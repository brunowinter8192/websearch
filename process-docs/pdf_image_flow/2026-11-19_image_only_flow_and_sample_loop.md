# 2026-11-19 - Image-only PDF flow: split, resplit, merge, sample loop, publish

Area: pdf_image_flow. Worker branch `pdf-image-flow`, base `integration`, not pushed. Replaces the text mode of the area pdf_workflow and the scan mode with control worker of the area pdf_scan. The form rules of the area pdf_form stay unchanged in the transcription prompt.

## User decisions (2026-11-19, translated from German, fixed)

1. The fast text extraction (liteparse anchors, the `pdftotext` mode decision) is removed completely. "It brings nothing." Most PDFs the user works with are scans.
2. The orchestrator splits the PDF into pieces without reading a page. Every worker gets a piece. At the end the pieces are merged.
3. The content check in `assemble` goes ("horseshit").
4. After the merge one worker takes samples. The orchestrator checks its findings against the PDF to see whether they are real.
5. A piece blocked by `API Error: Output blocked by content filtering policy` is split into smaller pieces for Haiku workers: 20 pages, then 10, then 5. Transcription always stays with workers.
6. Skill and code follow these decisions.
7. (given after the first proposal) The sampling worker corrects a mistake it finds itself and reports it. Then a further sample of 10 percent of new pages follows. This repeats until one sample run finds nothing.

Answers of the user to open points: 10 percent per run is the user's number; the Read tool on a PDF is used as it is (no rendering with `pdftoppm`, no prompt rule against other text tools); `outline.md` stays as an orchestrator step after the split; that smaller pieces avoid the block is the user's decision and a hypothesis (see below).

## Facts observed on 2026-11-19 that motivated the change

- Twelve articles of 9 to 34 pages, one batch each (eleven text mode, one scan). The old `assemble` reported ok for all ten that produced a batch file; lowest batch recall values 0.952, 0.963, 0.980, 0.989, 0.992, 0.992, 0.994, 0.997, 0.998, 1.000.
- A per-page comparison against `pdftotext` (character multiset, more than 8 % of a page missing) flagged eight pages in five of those articles. Pies 2009 (batch recall 0.992): page 17 has 4061 characters in the PDF and 1248 in the Markdown, footnotes 8 and 9 missing entirely (about 2800 characters); page 22 missing 966. Jensen 2001 (0.963): page 5 missing 565, page 9 missing 1373 (partly a pull quote repeated from page 7), page 17 missing 236 (running footer). Brennan 2012 page 1 missing 768, Clark and Lee 2015 page 28 missing 758 (not inspected). Hahn and Sunstein 2005 page 10 missing 106 (dropped header and footer, intended). So the batch-level check passed books that lost whole footnotes.
- Schelling 1981 (25 pages, text mode) and Hayek 1939 (23 pages, scan mode) never produced a batch file. Each was spawned three times (once Haiku, twice without `MODEL_SELECTION_FILE`); all six replies were only the content-filter error, no part file in any attempt.

## Hypothesis (not observed): smaller pieces get past the content filter

All six blocked attempts hit the first write with every model tried. Nothing shows that a piece of 20, 10 or 5 pages of the same article is not blocked. The ladder is the user's decision. If a piece of 5 pages or fewer is blocked, `resplit` refuses (`piece_minimal`) and the PDF is not indexed.

## Command flow as built

```
pdf split --pdf <PDF> --batch-dir /tmp/pdf_<STEM>/      page count via pdfinfo, 50-page pieces, prompt_<a>-<b>.md, manifest, start record
  workers write piece_<a>-<b>.md (part files per 20 pages as before)
pdf resplit --batch-dir ... --piece <a>-<b>             blocked piece -> pieces of the next size
pdf merge --batch-dir ...                               all piece files present -> BATCH_DIR/<STEM>.md (no paragraph split)
loop:
  pdf sample --batch-dir ...                            run k: draw, excerpts, run.json, prompt.md in samples/run_<k>/
  sampling worker edits excerpts, writes findings.md
  pdf sample-report --batch-dir ...                     report.md: pages, findings, every correction before/after
  orchestrator checks each correction against the PDF page
  pdf sample-close --batch-dir ... [--reject N ...]     accepted corrections into BATCH_DIR/<STEM>.md, loop state
pdf publish --batch-dir ... --out-dir <OUTPUT_DIR>      only after the loop ended: paragraph split, atomic write, ok end record
```

## Decisions taken in this session, with reasons

- **One flow, no mode.** `MODE_TEXT`, `MODE_SCAN`, `decide_mode`, liteparse, the anchor files and `pdftotext` are gone. The former scan prompt is the only transcription prompt; its wording "This PDF has no text layer" became "There is no anchor text", because PDFs with a text layer now take the same path. The `[?]` and "check numbers twice" rules of the scan prompt therefore apply to every PDF.
- **Pieces are page ranges of the original PDF**, not separate PDF files. Workers read the original with the pages parameter as before. Splitting into files (qpdf) would add a step without evidence that it changes the block.
- **Names.** Every piece, whatever its size: `prompt_<a>-<b>.md`, `piece_<a>-<b>.md`, `part<n>_<a>-<b>.md`. Worker names `pdf-<stem>-<a>-<b>`, because a sub-piece starts on the same page as its parent and the old `pdf-<stem>-<von>` would collide.
- **Next piece size** = the largest of 20, 10, 5 strictly smaller than the blocked piece. Examples tested: 50 -> 20/20/10, 20 -> 10/10, 10 -> 5/5, 18 -> 10/8, 8 -> 5/3, 85-page book piece 51-85 -> 51-70/71-85 -> 71-80/81-85, then 81-85 refused. `resplit` refuses a piece whose `piece_<a>-<b>.md` exists (`piece_finished`), so a finished piece is never redone or deleted; it removes only the prompt of the replaced piece. Leftover part files of a blocked piece are not touched (none were observed).
- **`resplit` writes no log record.** The ok end record of `publish` lists the final pieces (`pieces`), so blocks are visible afterwards. A PDF abandoned at `piece_minimal` stays "unfinished" in `stats`.
- **`merge` checks only presence** (`missing_piece`, end record outcome `failed`, nothing written) and a coverage tripwire (`manifest_corrupt`). It writes no end record on success; the ok end record belongs to `publish`. It refuses once a sample run exists (`sampling_started`), because a new merge would discard the corrections.
- **Corrections go into excerpt files, not into the book.** Reasons: the orchestrator must see each correction before it lands and must be able to discard one that is not real; the Edit tool on a 1 000-page book file is not workable (a book was observed at 993 pages). `sample` cuts per sampled page the text from the marker of the nearest earlier page to the marker of the nearest later page. That covers the text of page N that stands in page N-1's section under the paragraph rule, and a missing marker (observed before, area pdf_workflow) widens the excerpt instead of breaking it. Overlapping excerpts (neighbouring pages) are merged into one file `excerpt_<a>-<b>.md`. `sample-close` splices the edited excerpts back by the offsets recorded at `sample`, after checking the book's sha256 (`book_changed` tripwire) and that the marker lines of every accepted excerpt are unchanged (`excerpt_markers_changed`; the orchestrator can reject that page instead).
- **The orchestrator drives the loop with the CLI; the sampling worker only checks, corrects excerpts and writes `findings.md`.** The fact that the worker could run the CLI itself was not used, because the judgement of each correction has to come between the worker's edit and the write-back. For run 2 and later the orchestrator sends the worker `Read <run_dir>/prompt.md completely and follow it.`
- **What "a run finds nothing" means:** a run in which `sample-close` applies no correction. A correction rejected by the orchestrator does not count, and a line in `findings.md` without a correction does not count either (the skill tells the orchestrator to send such a finding back to the worker before closing). The loop also ends when every page has been sampled once, even if the last run applied a correction.
- **Draw:** per 50-page block of the whole PDF `ceil(0.10 * block pages)` pages among pages of that block never sampled before, `random.Random("<pdf_sha256>:<run number>")`. Independent of how the pieces were split. 85 pages: 5 + 4 per run; 9 pages: 1 per run, 9 runs at most; 23 pages: 3 per run. `pdf_sha256` is now in the manifest.
- **Report format** (`samples/run_<k>/report.md`): sampled pages, `findings.md` verbatim, and for every changed excerpt the changed lines before and after with 2 unchanged lines of context in four-backtick fences, plus a warning when marker lines changed.
- **Paragraph splitting moved from merge to publish.** The Pies footnotes are about 2800 characters, more than three times the 900-byte limit; text inserted by the sample loop has to pass the split. A test inserts a 2900-byte footnote through the loop and requires every published paragraph to be at most 900 bytes.
- **`publish` is the only way into OUTPUT_DIR** and refuses without a run (`sampling_missing`), with an open run (`run_open`) or before the loop ended (`loop_not_ended`).
- **Sampling worker model: Haiku** via `MODEL_SELECTION_FILE`, chosen by me, not by the user. The old skill said to set the variable only for transcription workers but also used it for the control worker; the new skill sets it for every spawn.
- **Log.** Start record without `mode`, `converter`, `converter_version`; config fields `piece_pages`, `resplit_piece_pages`, `workers`, `worker_model`, `prompt_sha`, `sample_share`, `paragraph_limit_bytes`. New config hash. Failure classes that no longer occur: `low_recall`, `control_*`, `page_count_mismatch`, `content_check_failed` as outcome. `stats` unchanged.

## Removed

`src/pdf/extract.py`, `assemble.py`, `pdf_text.py` (only `pdf_page_count` survived, moved into `split.py`), prompts `control_prompt.md`, `control_page_steps.md` and the text-mode templates, constants `CONTENT_CHECK_THRESHOLD`, `OUTLIER_PAGE_FACTOR`, `MODE_TEXT`, `MODE_SCAN`, `CONTROL_FILE_NAME`, `CONTROL_PROMPT_NAME`, `MIN_TEXT_CHARS_PER_PAGE`, `MIN_REFERENCE_CHARS`, `CONTROL_SHARE`, `liteparse` from `requirements.txt` (still installed in the main checkout's venv, not uninstalled), tests `test_pdf_extract.py`, `test_pdf_assemble.py`, `test_pdf_assemble_scan.py`, `test_pdf_control_draw.py`, `test_pdf_scan_prompt.py`, and the superimposed-layer support in `_pdf_fakes.py`.

## Skill

`skills/websearch-pdf/SKILL.md` is user-owned; a hook blocked the write ("rules and skills are user-owned"). The intended German text is stored as a unified diff in `dev/pdf_image_flow/patch/websearch-pdf_SKILL.patch` against the skill on `integration` at 8644fda. It was checked to apply cleanly with `patch` and to reproduce the intended file byte for byte. Apply from the repo root with `patch -p1 < dev/pdf_image_flow/patch/websearch-pdf_SKILL.patch`. Until it is applied, the skill on the branch still describes `extract`, `assemble`, the control worker and the manual piece procedure, none of which exists any more.

## Statements in other areas that no longer hold (recorded here, not edited there)

- Area pdf_form: "the orchestrator checks the batch files before `assemble`" and the footnote rationale "the digit stays in the text, so the character count of `assemble` still sees it" - there is no `assemble` and no character count. The Formkontrolle now runs on `piece_*.md` before `merge`.
- Area pdf_form: "The skill has a rule for a blocked worker in mode text only" - superseded by `resplit`.
- Area pdf_scan: the stored skill patch `dev/pdf_scan/patch/websearch-pdf_SKILL.patch` describes the removed scan flow and must not be applied.
- Area pdf_workflow: threshold, outlier rule, anchors, the 2026-10-12 fallback of building a blocked batch from `pdftotext` - all removed by user decision.

## Verification state on 2026-11-19

- Hermetic tests: eleven `dev/tests/test_pdf_*.py` files plus `test_cli_bootstrap.py` pass; full suite `PYTHON=../../../venv/bin/python bash dev/tests/run_strands.sh` from the worktree: 91 strands, 1 skipped (browser), 0 failed.
- CLI smoke on a generated 23-page PDF with a scratch log (`WEBSEARCH_CONVERSION_LOG_PATH`): split 1 piece; resplit 1-23 -> 1-20, 21-23; resplit 21-23 refused with `piece_minimal`; merge with no piece files failed and named both; after writing simulated piece files merge ok; sample run 1 drew pages 9 10 20 (excerpts `excerpt_9-10.md`, `excerpt_20.md`); an appended footnote showed in `report.md`; publish refused with `run_open`; close applied 1 and said "loop continues"; run 2 drew 3 6 16, closed with no correction, "loop ended"; publish wrote the book; `stats` showed 1 run ok, "recovered by retry: 1" (the failed merge record followed by the ok publish record).
- Not verified: no real worker has run any of the new prompts. Open questions for the first real run: whether Haiku edits excerpt files with the Edit tool without breaking marker lines, whether it writes `findings.md` in the given line format, and whether the content filter also blocks the sampling worker (not observed, unhandled).

## Review fix (2026-11-19)

The orchestrator's review found one violation: `NEW_PARAGRAPH = "\n\n"` was defined in both `merge.py` (join of pieces) and `publish.py` (join of split paragraph chunks). It moved to `src/config.py` and both modules import it. A scan of all upper-case module constants in `src/pdf/` found no other name defined twice. The PDF tests and `test_cli_bootstrap.py` pass after the change (78 tests in 11 files). The skill patch was left unchanged; the orchestrator applies it.

## Recap (2026-11-19): how the work ran, what to reuse, what went wrong

Order of work: (1) read every file named in the task and answered with a plan before touching anything; (2) the orchestrator answered with decision 7 (the sampling worker corrects and the loop repeats) and replies to the open gaps; (3) built code, then tests, then a CLI smoke; (4) DOCS.md, process-docs, the skill patch; (5) the review fix above.

What to reuse:
- Running the PDF tests in parallel from the worktree: one `../../../venv/bin/python -m pytest -x -q -p no:cacheprovider --basetemp=/tmp/<dir>/<name> <file> &` per file, then `wait`. The parent of `--basetemp` must exist; without it every file fails with `FileNotFoundError` in the conftest fixture `deepdivelog`, which looks like a code failure but is not.
- Full suite: `PYTHON=../../../venv/bin/python STRAND_OUT_DIR=/tmp/<dir> bash dev/tests/run_strands.sh` (91 files, about a minute).
- CLI smoke without workers: generate a PDF with `write_pdf` and `numbered_pages` from `dev/tests/_pdf_fakes.py`, write the piece files with `worker_output`, simulate the sampling worker by appending to an excerpt file and writing `findings.md`, and point `WEBSEARCH_CONVERSION_LOG_PATH` at a scratch log.
- A real run of the skill has to apply `dev/pdf_image_flow/patch/websearch-pdf_SKILL.patch` first; the skill on the branch describes the removed flow.

Mistakes made, so that they are not repeated:
- Hooks on this machine block two kinds of Write: a `dev/` helper module (`_pdf_fakes.py`) that imports from `src/` ("dev/ scripts may not import from src/"), and any edit of `skills/` ("rules and skills are user-owned"). Test files `test_*.py` under `dev/tests/` may import from `src/`. Therefore the split runner moved from `_pdf_fakes.py` into each test file, and the skill change is a patch.
- The shell is zsh: a command stored in a variable (`W="python cli.py pdf"; $W split ...`) is not word-split and fails with "no such file or directory". Use a shell function.
- A constant used by two modules was first defined twice (the review finding). Before committing, list the module constants of the package and look for duplicates: `grep -h -E "^[A-Z_]+ = " src/pdf/*.py | awk -F' = ' '{print $1}' | sort | uniq -d`.
- One test expectation was computed wrongly the first time (the number of pieces after three resplits, 6 not 7); the code was right.
- The first excerpt diff in `report.md` showed an empty "before" for a pure insertion; context lines were added so that the place of an insertion is visible.

## Incomplete piece files (2026-11-19, after the merge into integration)

### Observed in the first real run (relayed by the orchestrator)

- Brennan 2012, piece 1-12, single-read prompt. The Haiku worker wrote `piece_1-12.md` with one Write call, then kept changing it with Edit calls (adding footnotes page by page), and was then blocked with `API Error: Output blocked by content filtering policy`. The file left behind: 17 074 bytes, page markers 1 to 5 only, page 5 holds 37 characters, pages 6 to 12 absent. An earlier conversion of the same 12 pages had about 60 000 bytes.
- Consequences in the code of the first build: the skill's rule "finished = idle and the file exists" called the piece finished; `resplit` refused it with `piece_finished` until the orchestrator moved the file away by hand; `merge` would have joined it, because it only checked that the file exists.
- A blocked worker of piece 1-23 (split prompt) left `part1_1-23.md` behind. This contradicts the first build's statement above that no part file was observed after a block; that statement held for the six blocked attempts before the first real run.
- The statement "a block hits the first write" (area pdf_form) does not hold in general: in Brennan the block came after a Write and several Edits.

### What was built

- **Completeness of a piece file = the line `<!-- page N -->` is present for every page N of the piece.** Computed from the worker's Markdown only, never from the PDF. `piece_state` in `pieces.py` returns `complete`, `incomplete` with the pages whose marker is missing, or `missing`. Order, duplicates and extra markers are not checked (not observed). Brennan's file is `incomplete` with pages 6 to 12.
- **New command `pdf status --batch-dir`**: one line per piece in page order plus `pieces complete: X of Y`. It replaces "the file exists" as the done signal in the skill.
- **`merge` requires every piece complete.** Failure class `missing_piece` if any file is absent, otherwise `incomplete_piece`; the end record carries `missing_pieces` and `incomplete_pieces` (`from`, `to`, `missing_pages`); nothing is written.
- **`resplit` refuses only a complete piece** (`piece_finished`). For an incomplete or missing piece it splits as before and then moves the piece file and every part file named in the manifest entry (`part<n>_<a>-<b>.md`) into `BATCH_DIR/blocked/`, keeping their names; the output line `set aside:` lists them. Nothing is deleted, so the evidence of a block survives. `split` removes `blocked/` together with its other stale files. `BLOCKED_DIR_NAME` sits in `src/config.py` (used by `split.py` and `resplit.py`). The page-marker regex and `page_markers` moved from `sample_runs.py` to `pieces.py`, because the completeness check needs them too; `sample_runs.py` and `sample.py` import them from there.
- No command or flag to force a resplit of a complete piece was added: not needed for anything observed.

### Trade-off of the marker criterion, recorded so it is not rediscovered

Area pdf_workflow observed on 2026-10-11 a batch with complete content and one lost marker (batch 661-680, marker 675 missing, old prompt). Under the new rule such a piece is `incomplete`. The skill tells the orchestrator to send the missing pages to the living worker (it adds the marker or the text) or, if the worker is gone, to resplit the piece, which redoes correct work. That costs a re-transcription, never a silent gap in the book. A stricter content criterion would need the PDF and is ruled out by decision 1.

### Not changed, open

- The transcription prompt still allows Edit calls after the Write. Whether forbidding them would have avoided the Brennan truncation is unknown (hypothesis); no prompt change was requested.
- A worker that is still running while its file is incomplete is also reported `incomplete`. The skill's done rule needs both idle and `complete`; `resplit` must only follow the kill of the worker (skill step 1 of the block procedure).

### Skill

The changed sentences are in a second patch `dev/pdf_image_flow/patch/websearch-pdf_SKILL_incomplete_pieces.patch`, made against the skill text produced by the first patch `dev/pdf_image_flow/patch/websearch-pdf_SKILL.patch`. Checked: applying both patches in order to the skill on integration (ea634f4) reproduces the intended text byte for byte. The skill on integration at ea634f4 still had neither patch applied.

### Verification

Hermetic tests from the two observed cases: a 12-page piece file holding pages 1 to 4 plus the start of page 5 (status, merge refusal with the end record, resplit to 1-10 and 11-12 with the file kept in `blocked/`); a 23-page piece with only `part1_1-23.md` left (resplit sets it aside, pieces 1-20 and 21-23); a blank page with its marker counts as complete. PDF and CLI tests: 12 files (11 `test_pdf_*.py` plus `test_cli_bootstrap.py`), 84 tests; full suite 92 strands, 1 skipped, 0 failed. CLI smoke of the Brennan case through `cli.py` with a scratch log: status `incomplete (no page marker for pages 6 7 8 9 10 11 12)`, merge `FAILED (incomplete_piece)`, resplit `set aside: blocked/piece_1-12.md`, status afterwards `1-10 missing`, `11-12 missing`.

## Two-page stage (2026-11-19, user decision)

### Decision

Blocked pieces are also split into pieces of 2 pages. The stages are 20, then 10, then 5, then 2 pages. This supersedes the ladder "20, 10, 5" in decision 5 and every statement above that a piece of 5 pages or fewer is final.

### Observed in the real run on 2026-11-19 (relayed by the orchestrator)

- Blocked at the first write and refused by `resplit` with `piece_minimal` under the old ladder: Schelling 21-25 (5 pages), Hayek 21-23 (3 pages), Jensen 11-15 (5 pages), Jensen 16-17 (2 pages).
- Also blocked, at larger sizes: Jensen 1-10, Schelling 1-20.
- Passed after a block: Brennan 11-12 (2 pages), after Brennan 1-12 had been blocked.
- So the hypothesis "smaller pieces get past the filter" has one supporting case (Brennan 11-12) and one case against it at the new floor (Jensen 16-17, 2 pages, blocked). Under the new ladder Jensen 16-17 is still refused with `piece_minimal`, and Jensen is still not indexed unless that piece passes on another attempt. Nothing shows that a 1-page piece would pass; 1 page is not a stage by decision.

### What changed

- `RESPLIT_PIECE_PAGES = (20, 10, 5, 2)` in `src/config.py`. The rule is unchanged: the largest stage strictly smaller than the blocked piece. Consequences: 5 pages -> 2, 2, 1 (Schelling 21-25 -> 21-22, 23-24, 25); 3 pages -> 2, 1 (Hayek 21-23 -> 21-22, 23); 4 pages -> 2, 2. A blocked piece of 2 pages or 1 page (a remainder such as 25 or 23) is refused with `piece_minimal`.
- The logged config field `resplit_piece_pages` is now `[20, 10, 5, 2]`, so runs from this build have a new `config_hash`.
- The `resplit` CLI help names the four stages.
- Tests: the two refused 2026-11-19 cases (5 and 3 pages) as a parametrized test, the step from 5 to 2, 2, 1 with the refusal at 2 pages, the remainder 81-85 -> 81-82, 83-84, 85 with the refusal at the 1-page piece 85. 12 test files, 86 tests pass.

### Skill

Third patch `dev/pdf_image_flow/patch/websearch-pdf_SKILL_two_page_stage.patch` against the text after the second patch. Checked: the three patches applied in order to the skill on integration (ea634f4, still unpatched) reproduce the intended text byte for byte.

## One-page stage (2026-11-19, user decision)

### Decision

The smallest stage is always one page. The stages are 20, then 10, then 5, then 2, then 1 page. A blocked piece of one page is the only piece `resplit` refuses as minimal. This supersedes the section "Two-page stage" wherever it says that a piece of 2 pages is refused, and the statement there that 1 page is not a stage.

### What changed

- `RESPLIT_PIECE_PAGES = (20, 10, 5, 2, 1)` in `src/config.py`. The rule stays the largest stage strictly smaller than the blocked piece, so a 2-page piece becomes two 1-page pieces and only a 1-page piece has no smaller stage (`piece_minimal`). No code path besides the constant was needed for the refusal.
- The case that motivated it: Jensen 16-17 (2 pages, blocked at the first write on 2026-11-19, refused under the two-page ladder) now resplits into 16 and 17. Whether a single page gets past the content filter is not observed (hypothesis).
- Logged config `resplit_piece_pages` is `[20, 10, 5, 2, 1]`, a new `config_hash`. The `resplit` CLI help names the five stages. The `resplit` output says "page" for size 1 ("into 2 pieces of at most 1 page").
- Tests: 5 -> 2, 2, 1 then 1-2 -> 1, 2 and refusal of 1-1; the remainder 81-85 down to single pages with refusal of 83-83 and 85-85; the observed Jensen chain 1-17 -> 1-10, 11-17 -> 11-15, 16-17 -> 16, 17. 12 test files, 87 tests pass.
- No skill patch this time: the orchestrator writes the skill text. The skill sentences that depend on this constant are the stage line ("in vier Stufen ... dann 2 Seiten"), the examples line and the `piece_minimal` line ("2 Seiten oder weniger") of the third patch in `dev/pdf_image_flow/patch/`; those three patch files were left unchanged.
