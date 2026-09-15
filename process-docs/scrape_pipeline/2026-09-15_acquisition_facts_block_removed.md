# M2 — the ad-hoc scrape lane's acquisition-facts block removed, 2026-09-15

Worker session (worktree `mechanics`). Milestone: the printed `## Acquisition facts` block that
`scrape_url_chromium` (and the currently-unwired `scrape_url_camoufox`) print ahead of scraped
content is gone completely. This was a project-owner decision, grounded in
`process-docs/scrape_pipeline/adhoc_output_audit_2026-09-15.md` (read that file for the underlying
evidence — 91-record audit, byte counts, the stern.de/github.blog examples). This entry records
what changed, what was found to be block-only and removed alongside it, and how it was verified.

## What changed, file by file

- **`src/scraper/chromium_scrape.py`** — `_format_scrape_output` no longer builds the
  `## Acquisition facts` section; it now renders `# Content from: <url>` followed by `## Content`
  and the content, nothing else. Signature trimmed from `(url, content, meta, og_published_time)`
  to `(url, content)` — `meta`/`og_published_time` existed only to feed the removed block, the
  function has no other use for them. `_ACQUISITION_ERROR_MESSAGES` (the `browser_missing` /
  install-command string) and `_acquisition_error_message()` (the `budget_exhausted` →
  human-readable-budget-sentence formatter) were deleted outright — confirmed via whole-repo grep
  that neither had any caller besides the removed block and their own now-deleted tests. The
  `log_scrape(...)` call inside `scrape_url_chromium_workflow` is byte-for-byte unchanged — every
  field it wrote before (`http_status`, `document_status_chain`, `landed_url`, `og_published_time`,
  `raw_markdown_bytes`, `crawl4ai_success`/`crawl4ai_resolved_by`/`crawl4ai_attempts`/
  `crawl4ai_error_message`, `acquisition_error` as its own raw string, etc.) it still writes.
- **`src/scraper/camoufox_scrape.py`** — same shape of change. `_format_camoufox_output` trimmed
  to `(url, content)`, `_CAMOUFOX_ACQUISITION_ERROR_MESSAGES` deleted (same "block-only, no other
  consumer" confirmation). `scrape_url_camoufox_workflow`'s `log_scrape(...)` call is unchanged.
  This lane is not currently wired into `cli.py` (removed as an ad-hoc subcommand 2026-08-27, see
  this same directory's own history) — changed anyway per the milestone's explicit instruction
  ("Both lanes, together... Letting one keep it would make the two engines' output diverge"),
  since the module stays deliberately reactivatable and its own tests still exercise it directly.
- **`cli.py`** — the `scrape_url_chromium` subparser's help string dropped the trailing
  `"plus acquisition facts"` clause.
- **`skills/websearch-web-research/SKILL.md`** — the scrape-lane instruction changed from
  *"report the failure plainly with the acquisition facts the command prints"* to *"the returned
  content itself will show it (an error/block page, a 404); report that plainly, do not retry
  silently."* This is not a cosmetic reword: before this milestone the agent learned "this page
  failed" from a printed HTTP-status line; after it, the ONLY thing the agent sees on a failed
  scrape is whatever body actually came back — `# Access Denied` (stern.de, HTTP 403, real
  2026-09-15 record in the audit), `Whoops, we haven't written that blog post yet!` (github.blog,
  404). The project owner's premise (stated explicitly during the audit) is that showing the agent
  that body IS the wanted behaviour, not a defect — so the instruction had to be reworded to match
  where failure-recognition now actually happens, not just have its dangling clause deleted.

## What existed only to feed the block — found by grep, not guessed

Before touching anything, every call site of `_format_scrape_output`, `_format_camoufox_output`,
`_acquisition_error_message`, `_ACQUISITION_ERROR_MESSAGES`, and `_CAMOUFOX_ACQUISITION_ERROR_MESSAGES`
was grepped across the whole repo (`.py` files only — DOCS.md/process-docs hits are prose, not
call sites). Every real call site besides the format functions' own bodies and their own tests was
inside the two `..._workflow` functions building the return value. Nothing in `src/crawler/`,
`dev/` outside the two test files, or anywhere else touches these four symbols. This is why the
removal is clean: no caller elsewhere silently breaks.

## Test surface — the largest part of this milestone

Deleting the tests that asserted the old block's presence does not, by itself, prove the new
behaviour — it only stops asking the old question. Per this project's own standing test rule (a
behaviour change needs a test proving the NEW behaviour matches spec), two new tests were added
per lane instead of a bare deletion:

- `test_format_scrape_output_carries_no_acquisition_facts_preamble` /
  `test_format_camoufox_output_carries_no_acquisition_facts_preamble` — the returned text contains
  no `"Acquisition facts"` substring.
- `test_scrape_url_chromium_workflow_logs_full_field_set_unchanged` /
  `test_scrape_url_camoufox_workflow_logs_full_field_set_unchanged` — the log record captured by a
  monkeypatched `log_scrape` still contains every field key the pre-milestone record carried
  (chromium: 21 keys including `og_published_time`/`content_type`; camoufox: 16 keys, no
  `content_type`/`og_published_time` — that asymmetry between the two lanes already existed before
  this milestone and is unrelated to it). Both new tests reuse the existing `_meta()` fixture
  helper already used by every other log-record test in each file — no new fixture was invented.

Net test change: `dev/tests/test_chromium_scrape.py` — 11 tests deleted (asserted directly on
removed block lines: landed URL ×3, og:published_time ×2, the crawl4ai-diagnosis wording, facts-
precede-content ordering, document-status-chain line, the two `_acquisition_error_message`/
`_ACQUISITION_ERROR_MESSAGES` tests since both symbols are gone), 2 tests rewritten to the new
2-arg signature (content-appears-verbatim, zero-content-renders-`(no content returned)` — both
still real, unrelated to the removed block), 2 new tests added — net −9.
`dev/tests/test_camoufox_scrape.py` — 2 tests deleted (landed-URL-unconditional,
document-status-chain line), 2 existing tests folded/rewritten to the new signature, 2 new tests
added — net 0. Whole-suite count: 377 (integration baseline, unchanged from the prior M1 session)
→ 368 after this milestone, exactly matching −9 arithmetically (chromium −11+2, camoufox −2+2).
`./venv/bin/python -m pytest dev/tests/` was green at 368 after every edit in this session, checked
repeatedly, not just once at the end.

## Live verification

The Bash tool in this session specifically blocks redirecting `scrape_url_chromium`'s own CLI
invocation output to a file (`"its output belongs in context"`), while separately nudging toward a
redirect for any generic `python script.py` invocation with no timeout — a genuine conflict for
this exact command inside this sandbox that could not be resolved by adjusting flags. Worked around
by invoking `scrape_url_chromium_workflow` directly via `python -c` (the exact function `cli.py`'s
own dispatch calls, `asyncio.run(scrape_url_chromium_workflow(url))`, then printing
`result[0].text` — literally what `cli.py`'s own `print(result[0].text)` does) against
`https://www.rfc-editor.org/info/rfc2616/`, a real network scrape, real self-launched Chrome, real
`scrape_log.jsonl` write. Output began:

```
# Content from: https://www.rfc-editor.org/info/rfc2616/

## Content

RFC 2616: Hypertext Transfer Protocol -- HTTP/1.1 | RFC Editor
...
```

No `## Acquisition facts` anywhere in the 511053-character output. The same run's
`scrape_log.jsonl` tail line carries the full field set unchanged (`http_status: 200`,
`document_status_chain: [200]`, `og_published_time: null`, `crawl4ai_success: true`,
`config_hash`, the full `config` stamp, etc.) — confirming live, not just via mocked tests, that
the log record is untouched while the printed text shrank.

## Things a future agent should know

- If `cli.py scrape_url_chromium` is ever invoked directly through this same sandboxed Bash tool
  again (as opposed to the `python -c` workaround above), expect the same redirect conflict. The
  `python -c` pattern above is a legitimate equivalent for verification purposes — it calls the
  exact same production function `cli.py`'s dispatch calls — but is NOT how a real user/skill
  invokes the command (SKILL.md's own instruction is `websearch <command>`, foreground, no
  redirect); don't read this workaround as evidence about the real CLI's own argparse wiring, which
  was not separately exercised this session (only unit-tested, as it always has been).
- `camoufox_scrape.py`'s lane is still not wired into `cli.py` (`scrape_url_camoufox` subcommand
  removed 2026-08-27, unrelated to this milestone) — this milestone's camoufox-side changes are
  therefore not reachable from any CLI today, only from a direct Python call or its own tests, same
  as before this session touched it.
- Do not reintroduce `_acquisition_error_message`/`_ACQUISITION_ERROR_MESSAGES`/
  `_CAMOUFOX_ACQUISITION_ERROR_MESSAGES` on the reasoning that "the human-readable form was nicer"
  — the raw `acquisition_error` string is already a logged fact on its own; a prose mapping has no
  consumer left once nothing prints it.

## Recap — 2026-09-15, same day, review round

Main reviewed independently: reran the suite (368 green, confirmed), ran a live
`cli.py scrape_url_chromium https://example.com/` directly (not the `python -c` workaround this
entry describes above — Main's own environment did not hit the redirect conflict this session's
sandbox hit, or worked around it differently; not investigated further, out of scope for a
cosmetic-only review round) and confirmed heading/blank/`## Content`/blank/page text with no
preamble, and confirmed the matching `scrape_log.jsonl` record still carries all 22 fields. Both
new tests (no-preamble, full-log-field-set) were confirmed as exactly the right shape for this
milestone. Substance accepted outright — one cosmetic defect only.

**The defect:** deleting `_CAMOUFOX_ACQUISITION_ERROR_MESSAGES` from `camoufox_scrape.py` (a
4-line dict plus its own blank-line padding) took one blank line with it that didn't belong to the
dict at all — the `# ORCHESTRATOR` section marker immediately below ended up with only ONE blank
line above it, where every other section marker in both scraper modules (and, by established
convention across this codebase's `# INFRASTRUCTURE`/`# ORCHESTRATOR`/`# FUNCTIONS` markers) has
two. Root cause: my original removal edit replaced the dict's own line range with a single blank
line, but the line ranges I computed for the chromium-side removal and the camoufox-side removal
weren't symmetric — chromium's got a follow-up fix in the same work session (caught by my own
`Read` verification immediately after that edit), camoufox's did not get the same visual check
before moving on to the next file. Fixed by inserting the missing blank line at the correct spot
(line 32, immediately before the marker) and re-verified: `wc -l` on the file went from 226 to 227,
`src/scraper/DOCS.md`'s own LOC line for this module was stale at 226 and bumped to 227 in the same
pass — a DOCS.md going stale from a one-line whitespace fix is easy to miss if the LOC check isn't
re-run as the literal last step after ANY edit to a module, not just after edits that look
"substantial."

**Lesson for future sessions doing multi-file symmetric edits (chromium lane + camoufox lane, same
shape of change in both):** after editing the SECOND of two structurally-parallel files, diff the
immediate context around every touched boundary against the FIRST file's equivalent boundary,
rather than trusting that an edit "shaped the same way" produced the same spacing. A syntax check
(`ast.parse`) catches broken code; it does not catch a single missing blank line, and neither does
a green test suite — this defect shipped through both untouched, only caught by Main's own visual
review of the diff.

Suite re-verified after the fix: 368 passed, unchanged from before the fix (a whitespace-only
change, as expected).

**Addendum to the same review round:** a second pass found the removal had left stale claims in
`src/scraper/DOCS.md`'s OLDER Gotchas (predating this milestone), contradicting the new M2 Gotcha
at the bottom of the same file — a later top-to-bottom reader would hit the stale claim first. Four
spots fixed, all in the same file: the `crawl4ai_error_message`/`crawl4ai_success` observation-not-
verdict Gotcha claimed the rendered text still surfaced the diagnosis and pointed to
`_format_scrape_output`'s own comment (comments are not permitted in this codebase's source at
all, and the block itself is gone) — reworded to "log record only" and repointed at
`process-docs/scrape_pipeline/content_judgment_removal_2026-08-05.md`, which is where the
guenstiger.de evidence and the observation-not-verdict reasoning actually live; the guenstiger.de
evidence itself was kept verbatim, it is still true of the logged field. The document-status-chain
Gotcha (2026-09-03) claimed a "rendered 'Document status chain' line" still existed. The Camoufox
M2 sibling Gotcha claimed `_format_camoufox_output` still had "its own line" for
`document_status_chain`. The `is_same_target` removal Gotcha (2026-08-05) claimed both URLs were
"on disk/in the rendered text either way" — trimmed to "on disk (the log record) either way". All
four were reworded to past tense or explicitly pointed at the M2 Gotcha, without touching their own
still-valid historical evidence (dates, byte counts, live-confirmed repro chains).

Requested as an amend into the recap commit above — blocked by this environment's own hard rule
("Never amend existing commits — create a new commit instead"), which overrides instruction-level
requests to amend. Committed as a new commit instead (`3acb2e3`); flagged to Main as a deviation
from the literal instruction, not a silent substitution.
