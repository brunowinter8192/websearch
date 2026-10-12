# 2026-10-11/12 — Orchestrator record: PDF workflow rebuild, wise2627 conversion, side fixes

Orchestrator-side record of the cycle that replaced MinerU with liteparse + Haiku workers and converted the wise2627 semester PDFs. The tooling itself is documented by worker pdfwf in this area; this file holds what only the chat with the user carried: decisions, observed failures, and their resolution. Builds on area pdf_conversion_qa in monitor-cc (measurements, proposal, Coenenberg trial).

## User decisions (in order)

| Decision | Detail |
|---|---|
| MinerU deleted from disk | Repo `~/Documents/ai/Mineru` (2.3 GB incl. venv), HF models MinerU2.5-2509-1.2B and PDF-Extract-Kit-1.0 (5.7 GB), `~/mineru.json`, `~/magic-pdf.json`, `~/.mineru-locks`. GitHub remote MineruProcess stays as backup. All local branches were verified to be contained in the remote before deletion (`git log --branches --not --remotes` empty). RAG collection mineru-docs: deletion attempted twice, both times blocked by a running index of websearch-pages; not deleted at time of writing. |
| Tooling location | websearch repo, next to the skill, as `cli.py pdf extract|assemble|stats` (worker proposal; `src/pdf/workflow.py` would have needed an import hack). |
| Batch size and parallelism | First 40 pages, then 50 pages with a fixed 20 parallel workers. User goal: a book up to 1000 pages in exactly one wave. No RAM measurement, no RAM tripwire at all (user explicitly rejected a 16 GB tripwire). |
| Paragraph splitting | Moved into `assemble` (limit 900 UTF-8 bytes) after the orchestrator had to split 409 over-long paragraphs of Coenenberg by script. |
| Failed batch handling | Orchestrator analyses the failure itself (compare batch md with PDF pages), never blindly respawns. If the worker really lost content, the orchestrator repairs the batch file; if that fails, the PDF is not indexed. |
| Anthropic content-filter block | Skill text (user-applied): orchestrator takes over the batch; decides whether to transcribe 1:1; otherwise builds the batch from `pdftotext` with page markers and corrects recognition errors, headings, quotes and figure descriptions against the page images by targeted replacement. |
| Skill runs without user questions after Step 0 | Ends with a short report (pattern of websearch-capture-and-index). |
| Shefrin | `ShefrinBehavioralRiskManagement_2016.md` (MinerU-era md from 2026-10-04) and its PDF deleted; not semester literature. |
| Indexing | Only on explicit user order, once for all md files at the end. |

## Observed during the wise2627 run (2026-10-11)

- Collection wise2627-reference: 11 md files (Coenenberg, Ewert, Küpper, Grundei, Welge, Boatright, Bosch-Badia, Collins, Friedman, Pies, Prakash), 4 175 pages. Lowest batch recall per book between 0.946 (Küpper 651-658: every page carries a library licence footer that the worker drops as running footer) and 1.000.
- `stats` at 2026-10-12: 12 runs, 11 ok, 1 unfinished (the first Coenenberg extract that was redone), mean 355.6 pages.
- Context per Haiku worker on 50-page batches: 21-33 % of the 1M window used (Coenenberg). The `[1m]` window is effective for Haiku: a 40-page Basner batch left 76 % free, about 240k tokens used.
- One 20-worker wave of Coenenberg (993 pages) took about 8 minutes for 19 batches.

### Parallel spawns break workers (do not repeat)

The orchestrator first spawned 20 workers with `&` in parallel. Result: 19 of 20 worker proxies exited at startup (`proxy_errors_worker_*_pdf-coka-*.log`: "Error logged during startup, exiting..."), and the prompts were swapped between workers (worker pdf-coka-1 worked on anchor_501-550, pdf-coka-301 on 701-750). Cause of the proxy failure not proven (hypothesis: port race). All 20 were killed, extract rerun, and spawned sequentially: all proxies up, mapping correct. After the switch, 0 proxy start errors across 73 sequential Haiku spawns. The skill now forbids parallel spawns in Step 2.1. worker-cli itself does not guard against it.

### Anthropic content filter

`API Error: Output blocked by content filtering policy` is the whole worker reply; no partial file. Observed on 4 worker runs: Coenenberg 601-650 (retry ok), Ewert 551-600 (retry ok), Collins 1-8 (blocked three times, including a test worker on 2026-10-11 evening). Collins was then built from `pdftotext` and corrected by 150 targeted replacements against the page images (scanned 1994 article, OCR layer with errors like "clysfunctional", "3s 3 constraint", page 6 nearly unreadable). liteparse's anchor for Collins was unusable (multi-column page read as broken pipe tables with repeated headers), so `pdftotext` is the right base for this fallback.

Mistake to avoid: the orchestrator first presented the raw `pdftotext` text as "clean" after reading only the start of page 1. It was not; always check the whole text against the images before calling a fallback good.

### Worker pdf-coka-601b write errors

Not the content filter: Haiku called Write with Edit parameters (`old_string`/`new_string`, InputValidationError), assumed the write had succeeded, then made five Edit calls on a missing file before rewriting with an absolute path. Hypothesis: Haiku receives no tool descriptions at all (the proxy empties descriptions for every family, and drops the shared rules for haiku), so it confuses Write and Edit.

## Side fixes done in this cycle (details in the named areas)

- Worker viewer windows open in the background via a shim-injected Ghostty copy (iterative-dev, area worker_spawn). Upstream Ghostty issue #11457 is open; removal steps are documented there.
- Menubar finds viewer-app windows; worker row clicks resolve the tmux session at click time; menubar log is UTF-8 (monitor-cc, area menubar). The menubar runs from the py2app bundle in `~/Applications/monitor-cc-menubar.app`: a launchctl restart alone does not load new code; rebuild with `./venv/bin/python setup_py2app.py py2app` from the monitor-cc root.
- Proxy strips tools with prefix `mcp__claude_ai_` (claude.ai account connectors: Gmail, Google Drive, Claude Code Remote, Claude Docs listed in `~/.claude.json` `claudeAiMcpEverConnected`) and a trailing `<total_tokens>` line on system messages (monitor-cc, area proxy_tool_stripping). Verified live with a fresh Haiku worker: only Bash, Edit, Read, Skill, Write reach the model.

## What Haiku PDF workers receive (measured 2026-10-11, pdf-kuepper-1 and striptest)

System prompt replaced by "." except the billing header; 5 tools without descriptions; Claude Code reminders replaced by "."; the worker prompt (about 3 300 characters); then the anchor file and page images it reads itself.

## Open at the end of the cycle

- Indexing of wise2627-reference was started by the orchestrator on 2026-10-11 evening and killed by the tool timeout at 352/1705 chunks of Coenenberg; on 2026-10-12 another session was running `rag-cli index --collection wise2627-reference` (265 chunks in the collection at that moment).
- mineru-docs RAG collection still to delete.
