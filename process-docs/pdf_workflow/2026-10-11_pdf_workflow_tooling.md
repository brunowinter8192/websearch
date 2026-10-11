# 2026-10-11 - PDF workflow tooling (`cli.py pdf extract|assemble|stats`)

Builds the tooling the `websearch-pdf` skill calls. Evidence and the method decision come from the area pdf_conversion_qa in the monitor-cc project (liteparse as default converter, Haiku batch transcription, content check against the PDF text layer, JSONL conversion log). This file records how the tooling was built and why the numbers are what they are. Worker branch `pdfwf`, not pushed, not published.

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

## Worker limit

`workers = max(1, min(20, batch_count, floor(available_gb - 8)))` with 1.0 GB per worker. The trial measured about 0.8 GB per worker with 20-page contexts; 40-page contexts are larger, so 1.0. 8 GB reserve for the rest of the machine. 20 is the highest parallelism actually run in the trial. Examples (test table): 17.2 GB free and 25 batches gives 9; 40 GB and 25 batches gives 20; 6 GB gives 1. Real runs: 23.9 GB free, Basner 2 batches gives 2, Kuepper 17 batches gives 15.

## Output cap (why part files)

A 40-page batch is roughly 30 to 45k output tokens in one Write call; the proxy cap for Haiku is 64 000 max tokens and adaptive thinking counts against it. Dense books are close (Kuepper: 2 495 alphanumeric characters per page). The prompt for batches over 20 pages therefore has two Read calls (the Read tool returns at most 20 PDF pages per call), a part file after each, and one Bash command that concatenates and deletes the parts. Side effect used on purpose: `batch_<from>-<to>.md` appears atomically, so the skill's "file exists = done" signal cannot fire while the worker is still busy. Batches of 20 pages or fewer use one Read and one Write. A single-page last batch uses the bare number (`"41"`) as pages parameter, not `"41-41"` (hypothesis: the Read tool may reject a one-page range; not observed).

Open risk, not decidable offline: about 5 000 tokens per page means about 200k tokens per 40-page worker. If `[1m]` does not take effect for Haiku, workers hit the context limit. It is visible in the tmux status line of the first real worker.

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

`dev/tests/test_pdf_*.py` plus `_pdf_fakes.py`, all offline. PDFs are generated by a small raw-PDF writer in the helper (Helvetica text pages, optional blank pages); liteparse and poppler run for real on them. Free RAM is injected by patching `src.pdf.extract.current_available_bytes`, the log path by env var, directories by `tmp_path`. Cases come from observed situations: blank page inside a batch, a page marker missing with complete content, a batch that lost about 15 percent (fails) against one that lost about 5 percent (passes), books over 1 000 pages, stale batch files, retry of the same run. The full suite (77 files) was run in parallel with `dev/tests/run_strands.sh` and passed.

Running one file: `venv/bin/python -m pytest -x -q dev/tests/test_pdf_extract.py`. The venv of the main checkout is used from worktrees (`../../../venv` relative to the worktree).

## Verification state (2026-10-11)

Real `extract` run through `cli.py` from the worktree on two PDFs of `rag-cli/data/pdf/wise2627/`:

- `BasnerMcGuireNoiseAndSleepReview2018.pdf`: 45 pages, 2 batches (1-40, 41-45), 2 workers, into `/tmp/pdf_BasnerMcGuireNoiseAndSleepReview2018/`. Run time 1.5 s.
- `KuepperControlling_2024.pdf`: 658 pages, 17 batches, 15 workers, into `/tmp/pdf_KuepperControlling_2024/`. Run time 3.4 s. Only batch 241-280 is to be spawned; the other 16 batches act as the missing-batch case for `assemble`.

The log of these runs is `src/logs/conversions.jsonl` inside the worktree (`PROJECT_ROOT` follows the checkout). `assemble` and `stats` must run from the same checkout, or with `WEBSEARCH_CONVERSION_LOG_PATH` set, otherwise `stats` does not see the runs. Worker verification (Haiku output, `assemble`, `stats`) is the orchestrator's step and not done at the time of this entry.

## For a successor

- Do not edit the threshold or the worker formula without new measurements from real 40-page Haiku batches. The recall values above are from 20-page batches written with the old prompt.
- The prompt template set is hashed into the logged config (`prompt_sha`), so a prompt change shows up as a new `config_hash` in `stats`.
- The skill file `skills/websearch-pdf/SKILL.md` is user-owned and was not touched. It still names `src/pdf/workflow.py` and `WEBSEARCH/logs/conversions.jsonl`; both differ from what was built (see decisions).
