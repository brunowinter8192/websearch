# 2026-10-11 - PDF workflow tooling (`cli.py pdf extract|assemble|stats`)

Builds the tooling the `websearch-pdf` skill calls. Evidence and the method decision come from the area pdf_conversion_qa in the monitor-cc project (liteparse as default converter, Haiku batch transcription, content check against the PDF text layer, JSONL conversion log). This file records how the tooling was built and why the numbers are what they are. Worker branch `pdfwf`, not pushed, not published.

## Update 2026-10-11 (later the same day): spec change, supersedes the sections marked "superseded"

The user changed four points after the first build. Everything below is implemented and tested; the sections "Worker limit", "Output cap" and "Verification state" describe the earlier 40-page build and are superseded where they contradict this section.

1. **Batch size is fixed at 50 pages** (was 40). Goal: a book of up to 1 000 pages runs in one wave. 1 000 pages give exactly 20 batches; 1 001 pages give 21 and need a second wave. Books over 1 000 pages are rare, a second wave is accepted. A test pins the boundary.
2. **Parallel workers are fixed at 20**, written to the manifest and the logged config, independent of free RAM and of the batch count (a 2-batch book also gets 20). The RAM-derived formula (`worker_limit`, reserve, 1.0 GB per worker) is removed.
3. **Worker prompt is generalised: one Read and one part file per 20 pages.** A 50-page batch reads 1-20, 21-40, 41-50, writes `part1_`, `part2_`, `part3_<span>.md`, then runs one Bash command that concatenates them in order (with an empty line between) into `batch_<from>-<to>.md` and deletes the parts. Batches of 20 pages or fewer keep one Read and a direct Write. A chunk of one page uses the bare number as pages parameter (`"21"`, 21-page batch). The manifest entry lists the part file names (`parts`, empty for single-chunk batches). Templates: `worker_prompt.md`, `steps_single.md`, `steps_split.md`, `chunk_steps.md`; the step numbers and the concatenation command are generated in `extract.py`. Observed example of the rendered prompt for pages 51-100: 9 steps, three Read/Write pairs, step 8 is the `cat` command.
4. **Tripwire instead of the formula: `extract` stops with failure class `low_ram` (and an end record) when free RAM is below 16.0 GB.**
   - Derivation: observed on 2026-10-11, 20 parallel Haiku workers ran fine with about 21 GB available at start; measured about 0.8 GB per worker with 6 workers. 20 workers times 0.8 GB is 16.0 GB, the measured demand of all workers alone. "Clearly less than the observed condition" is implemented as "less than that measured demand": below 16.0 GB the workers cannot fit by the measurement. Between 16.0 and 21 GB is less than observed but not clearly less; it passes.
   - Code: `PARALLEL_WORKERS = 20`, `WORKER_RAM_GB = 0.8`, `MIN_AVAILABLE_GB = PARALLEL_WORKERS * WORKER_RAM_GB` in `extract.py`; the check runs first in the extract steps, after the start record, so the refusal is in the log (start has `available_gb`, end has `low_ram`). Free RAM is `psutil.virtual_memory().available`, compared after rounding to 0.1 GB.
   - Observed free RAM on this machine on 2026-10-11: 17.2 GB (probe) and 23.9 GB (real extract runs); the tripwire would have passed both.
   - Caveat (hypothesis): the 0.8 GB comes from 6 workers with 20-page contexts. A 50-page worker holds about 300k tokens of context (see next point), memory per worker at that size is not measured.
5. **Context observation from today (reported by the user, not measured here):** Basner batch 1-40 finished with 76 percent context left on `claude-haiku-5-5[1m]`, which is about 240k tokens for 40 pages, roughly 6 000 tokens per page. The 1M window is effective for Haiku. A 50-page batch is therefore expected at about 300k tokens.

Log consequences: the logged `config` now contains `batch_pages` 50, `workers` 20 and `min_available_gb` 16.0, so the 50-page runs form a new `config_hash`; the start record no longer has a top-level `workers`; new failure class `low_ram`. The two start records written earlier today by the 40-page build stay in the append-only log with the old hash.

## Decisions taken with the user (2026-10-11)

| Topic | Decision |
|---|---|
| Entry point | `python cli.py pdf` with the nested subparsers extract, assemble and stats, not `src/pdf/workflow.py`. A script under `src/pdf/` cannot use `from src...` imports without a path hack, and the repo has a test that forbids path hacks. The skill's `WORKFLOW` becomes `WEBSEARCH/venv/bin/python WEBSEARCH/cli.py pdf`. |
| Log | `src/logs/conversions.jsonl` (`LOG_DIR`), gitignored by the existing `src/logs/` rule. Not pruned: `log_janitor` is deliberately not called. Env `WEBSEARCH_CONVERSION_LOG_PATH` redirects it (tests). |
| `assemble` | All-or-nothing. Any failed batch: exit 1, failed batches named, nothing written to `--out-dir`. Reason: a book with holes in `OUTPUT_DIR` would be indexed by `rag-cli index`. |
| `extract` on an existing batch dir | Deletes only its own file patterns (`anchor_*.md`, `prompt_*.md`, `batch_*.md`, `part*_*.md`, `manifest.json`), keeps foreign files, starts a new run. Reason: stale `batch_*.md` from an earlier run must never be assembled into a new run. |
| Content check threshold | 0.90 alphanumeric recall per batch (derivation below). |
| Worker write protocol | Part files, then one Bash `cat` creates `batch_<from>-<to>.md`. Reason: see "Output cap" below. |
| Page markers | `<!-- page N -->` stay in the final markdown, as in the trial run. |
| `cli.py` exit hook | Unchanged. `kill_own_chrome_atexit` only acts on browser state of its own process, which a pdf run never creates, so it is harmless there; changing the registration order would have broken `test_main_configures_logging_before_parsing_arguments`. |

## Layout

`src/pdf/`: `extract.py`, `assemble.py`, `stats.py` (one orchestrator each), `conversion_log.py`, `pdf_text.py`, `report.py`, `prompts/` (three template files). `config/pdf_models.json` holds `main` and `worker`; `extract` reads `worker` for the log config and the manifest. Shared constants in `src/config.py`: `MANIFEST_FILE_NAME`, `CONTENT_CHECK_THRESHOLD`. `liteparse` added to `requirements.txt` and installed into `venv/` (2.15.1, Python 3.14.7 works, the wheel is abi3).

## Observed facts that shaped the code

- liteparse parses Coenenberg (993 pages) in one call in 2.8 s at 0.67 GB. `result.pages[i].markdown` is per page. The tooling therefore parses the PDF once and slices anchors, instead of one `target_pages` call per batch as in the trial; header/footer removal then sees the whole document. `max_pages` is set to the real page count (default is 1000, books over 1000 pages must work). Page count comes from `pdfinfo`; pypdf is not needed.
- Text layer in wise2627: all 21 PDFs. Lowest mean is 879 alphanumeric characters per page (TelekomPibMagentaZuhauseL, 1 page). The gate stops a PDF below 100 per page. No PDF without a text layer has been observed, the gate is a tripwire.
- Trial batches re-measured (50 batches of 20 pages, Coenenberg, alphanumeric multiset recall of the Haiku output against `pdftotext -f -l`): median 0.982, minimum 0.890 (batch 841-860, the diagram labels dropped by the old prompt), next lowest 0.934, then 0.949. Merged to 25 batches of 40 pages: median 0.983, minimum 0.927 (841-880).
- Batch 661-680 of the trial had 19 page markers for 20 pages (marker 675 missing) while recall was 0.9935 and character totals were equal: content complete, marker lost. Page 667 is blank in the PDF (0 characters). Consequences: markers are not a pass/fail criterion; a blank page inside a batch must not fail it.
- Free RAM on the development machine at the time of the real extract runs: 23.9 GB (`psutil.virtual_memory().available`), 17.2 GB in the earlier probe.

## Threshold 0.90

All trial batches except one are at or above 0.934. The one below, 0.890, really lost content (the old prompt said to drop image placeholders). 0.90 flags exactly that batch and no good one. With the new prompt (figure descriptions) the figure labels are in the output, so legitimate batches should sit higher. Limit of the check: it sees a loss of about 10 percent of a batch, 4 pages of 40. A single lost page (2.5 percent) passes. A per-page check was rejected because the markers are not reliable (batch 661-680). If real runs show a different distribution, the number is `CONTENT_CHECK_THRESHOLD` in `src/config.py`; it is part of the logged config, so statistics separate the configurations.

Metric: NFKC, lowercased, only alphanumeric characters below U+0250 (Latin). Greek letters are alphanumeric in pdftotext but become `\alpha` in LaTeX output; restricting to Latin avoids false failures on formula papers. This is a hypothesis: no formula-dense paper went through the Haiku path yet. Precision (extra text) is not checked, because figure descriptions legitimately add text. A batch with fewer than 200 reference characters is "unjudged" and passes.

## Worker limit (superseded by the update above)

First build: `workers = max(1, min(20, batch_count, floor(available_gb - 8)))` at 1.0 GB per worker. Replaced by the fixed 20 and the 16.0 GB tripwire.

## Output cap (why part files; batch size 40 in this section is superseded by 50)

A 40-page batch is roughly 30 to 45k output tokens in one Write call; the proxy cap for Haiku is 64 000 max tokens and adaptive thinking counts against it. Dense books are close (Kuepper: 2 495 alphanumeric characters per page). The prompt for batches over 20 pages therefore has two Read calls (the Read tool returns at most 20 PDF pages per call), a part file after each, and one Bash command that concatenates and deletes the parts. Side effect used on purpose: `batch_<from>-<to>.md` appears atomically, so the skill's "file exists = done" signal cannot fire while the worker is still busy. Batches of 20 pages or fewer use one Read and one Write. A one-page chunk uses the bare number as pages parameter, not `"41-41"` (hypothesis: the Read tool may reject a one-page range; not observed).

The open risk of this section (whether `[1m]` takes effect for Haiku) is answered by the update above: it does.

## Log design as built

Two record types in one file, linked by `run_id`.

- start (written by `extract` before any conversion work): `run_id`, `ts_start`, `pdf`, `pdf_sha256`, `pages`, `converter`, `converter_version`, `config_hash`, `config` (`batch_pages`, `ocr`, `worker_model`, `prompt_sha`, `threshold`, `min_text_chars_per_page`), `attempt` (count of earlier starts with the same sha256, plus one), `available_gb`, `workers`.
- end (written by `extract` on failure, by `assemble` on every invocation): `run_id`, `ts_end`, `outcome` (`ok`, `failed`, `content_check_failed`), `failure_class`, `wall_s` (from `ts_start` to `ts_end`), plus `failed_batches` (`from`, `to`, `reason`, `recall`), `chars_out`, `chars_ref`, `char_ratio`, `md` or `error`.
- Failure classes: `no_text_layer`, `extract_error`, `page_count_mismatch`, `missing_batch`, `low_recall`, `assemble_error`, `unreadable_pdf`. A missing PDF file or a missing manifest raises before any record exists and is not logged.
- `assemble` runs once per attempt, so one run can have several end records (failed first, ok after the retry). `stats` takes the last end record as the outcome of the run and counts runs with more than one end and a final ok as "recovered by retry".
- `wall_s` includes every pause between extract, the workers and assemble, including waiting for the user. It is not the compute time. The tooling cannot see token cost or worker memory, so the proposal's `peak_mem_gb` and `min_available_gb` do not exist.
- A start without an end is "unfinished": crash, kill, or the flow was abandoned.
- `stats` output is plain text: runs, ok, failed, unfinished, recovered by retry, failures by reason, mean pages, mean duration in minutes, runs per `config_hash` (ordered by time, so the last line is the current production config). `--since YYYY-MM-DD` filters on `ts_start`.

## Tests

`dev/tests/test_pdf_*.py` plus `_pdf_fakes.py`, all offline. PDFs are generated by a small raw-PDF writer in the helper (Helvetica text pages, optional blank pages); liteparse and poppler run for real on them. Free RAM is injected by patching `src.pdf.extract.current_available_bytes`, the log path by env var, directories by `tmp_path`. Cases come from observed situations: blank page inside a batch, a page marker missing with complete content, a batch that lost about 15 percent (fails) against one that lost about 5 percent (passes), books over 1 000 pages, stale batch files, retry of the same run. The full suite (77 files) was run in parallel with `dev/tests/run_strands.sh` and passed for the 40-page build; for the 50-page build the six pdf test files pass (38 tests) and the full suite (77 files) passed again in parallel.

Running one file: `venv/bin/python -m pytest -x -q dev/tests/test_pdf_extract.py`. The venv of the main checkout is used from worktrees (`../../../venv` relative to the worktree).

## Verification state of the 40-page build (superseded as a plan, the directories exist)

Real `extract` run through `cli.py` from the worktree on two PDFs of `rag-cli/data/pdf/wise2627/`:

- `BasnerMcGuireNoiseAndSleepReview2018.pdf`: 45 pages, 2 batches (1-40, 41-45), 2 workers, into `/tmp/pdf_BasnerMcGuireNoiseAndSleepReview2018/`. Run time 1.5 s.
- `KuepperControlling_2024.pdf`: 658 pages, 17 batches, 15 workers, into `/tmp/pdf_KuepperControlling_2024/`. Run time 3.4 s. Only batch 241-280 is to be spawned; the other 16 batches act as the missing-batch case for `assemble`.

The log of these runs is `src/logs/conversions.jsonl` inside the worktree (`PROJECT_ROOT` follows the checkout). `assemble` and `stats` must run from the same checkout, or with `WEBSEARCH_CONVERSION_LOG_PATH` set, otherwise `stats` does not see the runs. Worker verification (Haiku output, `assemble`, `stats`) is the orchestrator's step. The two directories were created with the 40-page prompts and were not touched by the 50-page change; they are assembled as they are. No `extract` with the 50-page build has been run on a real PDF yet.

## For a successor

- Do not edit the threshold or the worker formula without new measurements from real 40-page Haiku batches. The recall values above are from 20-page batches written with the old prompt.
- The prompt template set is hashed into the logged config (`prompt_sha`), so a prompt change shows up as a new `config_hash` in `stats`.
- The skill file `skills/websearch-pdf/SKILL.md` is user-owned and was not touched. It still names `src/pdf/workflow.py` and `WEBSEARCH/logs/conversions.jsonl`; both differ from what was built (see decisions).

## Verification part 1 (2026-10-11): assemble and stats on the 40-page directories

Both directories were built by the 40-page build (commit 3a24944) and assembled with the current code; the manifest keys `from`, `to`, `output` are the same in both builds. Run from the worktree, so the log is the worktree's `src/logs/conversions.jsonl`.

| Directory | Result | Detail |
|---|---|---|
| Basner (45 pages) | `assemble` FAILED, `low_recall`, nothing written | batch 1-40 recall 0.638 (false failure, see below); batch 41-45 recall 0.9995 |
| Kuepper (658 pages) | `assemble` FAILED, `missing_batch`, nothing written | 16 batches named, as intended; batch 241-280 exists and has recall 0.9909 (ref 98 234, out 100 854 characters) |

`/tmp/pdfwf_out` was not created by either run (all-or-nothing works). `stats` afterwards: runs 2, ok 0, failed 2 (`low_recall` 1, `missing_batch` 1), unfinished 0, mean pages 351.5, mean duration 31.8 min (the wall time from `extract` to `assemble`, which includes the spawning and the waiting for the workers), one config hash with 2 runs. `assemble` prints only the failed batches and the lowest recall on success; the per-batch recall above was computed with `check_batch` in a throwaway script.

### Finding 1: the content check false-fails Basner 1-40 because the text layer of that PDF is superimposed

- The Haiku output of Basner 1-40 looks correct in the two pages read: 40 page markers; page 6 has the final text once and matches the readable lines of the `-layout` text; page 37 is a clean pipe table (Table 13, Summary of findings). Not every page was read. The reference is what is wrong.
- Per page, 33 of 40 pages have recall 0.97 to 1.0. Page 37 has a pdftotext layer of 67 082 alphanumeric characters against 2 822 in the output (recall 0.042); the typical page has 3 000 to 4 000. That one page is 35 percent of the reference of the batch. Seven more pages (3, 6, 10, 11, 12, 21, 22) have recall 0.60 to 0.79.
- Cause, observed on page 6 with `pdftotext -layout`: the PDF carries two superimposed text layers, the final article (header "6 of 45") and the peer-review draft (header "Int. J. Environ. Res. Public Health 2018, 15, x FOR PEER REVIEW ... 6 of 43"), so the same sentences appear twice, and on page 37 about twenty times (words like "However, However, However, we we we downgraded downgraded"). The liteparse anchor is affected the same way (page 37 anchor: 15 090 characters).
- Recall of the batch with page 37 removed from reference and output: 0.9598, above the threshold.
- A word-set recall instead of the character multiset was tested and does not help: Basner 1-40 0.869 (overlay creates merged garbage tokens such as "ofAlthough"), Coenenberg trial batches median 0.933 and minimum 0.800 (841-860), and a simulated 15 percent line loss still gives 0.92 or less there, so the separation is worse than with characters. Not recommended.
- Candidate rule (not implemented, pending the user): exclude a reference page from the judgement when its character count exceeds 5 times the median page of its batch, and name it in the output and in the end record as unjudged. Evidence for the factor: the largest page-to-median ratio inside any 50-page window is 19.7 (Basner p37) against 2.7 (Kuepper p652), 2.1, 1.9, 1.7, 1.7, 1.5, 1.5, 1.4 in the eight other measured PDFs (about 4 400 pages in total); any factor between 3 and 19 separates them. With the rule Basner 1-40 would pass at 0.960. Limit: a PDF with many superimposed pages (here 7 of 40 pages sit at 0.6 to 0.8) can still fall below 0.90; this was observed only once, in one PDF of 21.
- The all-or-nothing `assemble` offers no override today. A failed batch that is correct after inspection can only be fixed by changing the rule.

### Finding 2: hyphenation at a batch boundary

- Kuepper 241-280 ends with "...in Vorgaben fuer Organisationseinheiten umgesetzt wer-" and page 281 (first page of the next batch) starts "den. Hierzu sind ...". In the text layer the pair is the same (page 280 ends with "wer-", page 281 starts with the running header and then "den.").
- Frequency at batch seams, text layer of the last two lines of the seam page ending in a letter plus hyphen: Kuepper with 40-page batches 4 of 16 seams (pages 240, 280, 440, 520), with 50-page batches 1 of 13 (page 450); Coenenberg 1 of 24 (page 840) and 0 of 19. So zero to four split words per book.
- The same defect happens inside a batch: in Kuepper 241-280, page 257 ends in "beein-" and page 258 starts (after the running header) with "flusst werden sollen"; the worker joined other page-end hyphens (243, 249, 251, 263) but not this one. A repair in `assemble` therefore would not make the output hyphen-free.
- Judgement: no handling in `assemble`. A join would edit worker content with a heuristic (a line-end hyphen followed by a lowercase word can also be a suspended hyphen such as "Personal- und Sachkosten" or a real compound hyphen), the damage is one split word per seam, and the embedding is not affected in a measurable way.
- If the user wants visibility: a grep for lines ending in a letter plus hyphen in the skill's sample step, counting the leftovers, no repair.

### Worker reports of this verification (relayed by the user)

- Basner 1-40: low-resolution figures were described approximately and marked with `[?]` (5 `[?]` in the batch file, 0 in Kuepper 241-280).
- Kuepper 241-280: the anchor misses the opening sentence of page 268 and is sparse for Abb. 7-2 on page 264; the worker took both from the image. Finished with 69 percent context left at 40 dense pages, about 7 800 tokens per page including output; 50 dense pages would stay near 400k of the 1M window.

## Update 3 (2026-10-11): outlier-page rule in assemble, RAM tripwire removed by user decision

Three decisions of the user after verification part 1.

1. **Outlier-page rule (implemented).** In the content check, a reference page whose character count is more than 5 times the median page of its batch is left out of the reference, and the batch is judged on the remaining pages. Constants: `OUTLIER_PAGE_FACTOR = 5` in `src/config.py` (shared by `extract`, which logs it in the config, and `assemble`). Details that are easy to get wrong:
   - "More than": exactly 5 times is not an outlier (test: sizes 100, 100, 100, 500 keep all four; 501 drops the fourth).
   - A batch whose median page has 0 characters gets no exclusion (test: sizes 0, 0, 0, 900).
   - Only the reference loses the page. The output text of that page stays in the output multiset, which cannot raise recall beyond what the other pages' reference allows because recall counts the minimum of both.
   - Excluded pages are named in the `assemble` output (`unjudged pages (text layer over 5x the median page of the batch): 37`) on success and on failure, and in the end record as `unjudged_pages` (list of page numbers). `chars_ref` and `char_ratio` use the judged reference.
   - The rule does not hide real loss: a fixture with one superimposed page (20 layers, shifted 3 pt each, the page-37 case) plus 15 percent lost lines on the other pages still fails with `low_recall` and names the page. Without the rule the same fixture gives recall 0.728 and fails although the output is complete.
   - Pages like Basner 3, 6, 10, 11, 12, 21, 22 (recall 0.60 to 0.79, text layer roughly doubled) are not excluded; they only lower the batch recall.
2. **No hyphen handling in `assemble`** (user agrees with the judgement in verification part 1).
3. **The RAM tripwire is removed completely (user decision).** `extract` makes no RAM measurement at all: no `psutil` call, no `available_gb` in the start record or the manifest, no `min_available_gb` in the config, no `low_ram` failure class, no abort. Parallel workers are fixed at 20 (`PARALLEL_WORKERS`, logged in the config as `workers`, written to the manifest). This supersedes point 4 of "Update 2026-10-11 (later the same day)" and every RAM statement in that section and in "Worker limit". A test patches `psutil.virtual_memory` to raise and requires `extract` to succeed and to log no RAM field. Records written before this change (the two start records of the 40-page build) still carry `available_gb` and `workers`; they stay in the append-only log.

Result of the rerun on the Basner directory (the 40-page build, unchanged on disk): `assemble` now exits 0 and writes `/tmp/pdfwf_out/BasnerMcGuireNoiseAndSleepReview2018.md` (184 600 characters, 45 page markers). Batch 1-40 recall 0.9789 with page 37 unjudged, batch 41-45 recall 0.9995. The end record has `outcome` ok, `chars_ref` 140 572, `char_ratio` 0.991, `unjudged_pages` [37]. `stats` then reports 2 runs, 1 ok, 1 failed (`missing_batch`, the Kuepper run), "recovered by retry: 1" (the Basner run: its first end record was the false `low_recall`, the second is ok; this retry was a code change, not a worker retry), mean duration 37.8 minutes (wall time from `extract` to the last `assemble`, mostly waiting). Both runs belong to config hash `ef02c8db4356d4f2` (the 40-page build); the 50-page build with the new config has not been run on a real PDF yet.

Not handled, unobserved: `format_success` takes the minimum recall over judged batches and would fail on a book in which every batch is unjudged (fewer than 200 reference characters each); a one-page PDF with 100 to 199 text characters passes the text-layer gate and would hit this.

## Recap (2026-10-11): how the work ran, what to reuse, what went wrong

Order of work: (1) read the skill draft, the monitor-cc process-docs of the area pdf_conversion_qa, the trial driver and the websearch conventions, and answer with gaps and a plan before any code; (2) throwaway probes in `/tmp/pdfwf_probe` outside the worktree (liteparse in a scratch venv, recall of the 50 trial batches against pdftotext, text-layer statistics of the 21 PDFs of wise2627) which set the entry point, the threshold and the batch protocol; (3) build with tests; (4) three spec changes from the user (50-page batches with 20 fixed workers and a RAM tripwire, then removal of the tripwire, then the outlier-page rule after a false failure found by verification); (5) verification on real Haiku output. Every number in the code has its origin in a section above.

What to reuse:
- Running tests from the worktree: `PYTHON=<main checkout>/venv/bin/python bash dev/tests/run_strands.sh` runs one fail-fast pytest per file in parallel (77 files, about 1 minute). One file: `<main checkout>/venv/bin/python -m pytest -x -q -p no:cacheprovider dev/tests/test_pdf_extract.py`. A worktree has no `venv/`; `liteparse` was installed into the main checkout's `venv/` (gitignored).
- Generated PDFs: `dev/tests/_pdf_fakes.py` writes a raw PDF with Helvetica text, blank pages and superimposed layers (same text drawn N times, shifted 3 pt per layer, which poppler does not merge). It is the shortest way to a hermetic fixture; no PDF library is installed.
- Diagnosing a failing content check: compute recall per page, not per batch, with `latin_char_counts` and `pdftotext_pages` from `src/pdf/pdf_text.py`; one page with 20 times the normal character count explained the 0.638 of Basner 1-40.
- The log of real runs lives in the checkout that ran them (`src/logs/conversions.jsonl` below `PROJECT_ROOT`); run `assemble` and `stats` from the same checkout.
- The real verification directories are `/tmp/pdf_BasnerMcGuireNoiseAndSleepReview2018/` and `/tmp/pdf_KuepperControlling_2024/` (40-page build, Haiku output of Basner 1-40, 41-45 and Kuepper 241-280). `/tmp` is not persistent.

Mistakes made, so that they are not repeated:
- BSD `sed -i` on macOS needs `-i ''`; two edits failed with "extra characters at the end of d command" and were redone with the Edit tool or a Python replace.
- The shell resets its working directory after every call; every command begins with `cd <worktree>`.
- Two test expectations were computed wrongly the first time (the mean duration in the stats fixture, and a character ratio above 1.0 because the output carries page markers); the code was right, the tests were corrected.
- A process-docs sentence claimed that page 37 of the Basner output had been compared against the layer; only its first 900 characters (a clean pipe table) had been read. The claim was corrected in this file. Write what was actually read.
- The first threshold reasoning used trial batches of 20 pages with the old prompt; real 40-page Haiku batches then showed a failure mode (superimposed text layer) that those data could not contain.

Open at the end of this session:
- The 50-page build (`extract` with 50-page batches, the three-chunk prompt) has been exercised only by tests and by rendering a prompt, not by a real `extract` and not by real Haiku workers.
- `skills/websearch-pdf/SKILL.md` still describes the earlier design (script path, log path, 40 pages, RAM-derived parallelism); it is user-owned and was not touched.
- The unjudged-everything case in `format_success` (see Update 3) and the hypothesis that the Read tool may reject a one-page range such as `"21-21"` are unobserved and unhandled or guarded only by the bare-number form.
