# adhoc_persistence session log (started 2026-09-20)

This file is extended in place across the whole session, one `## Milestone` section per
increment, oldest first. Do not split later milestones of this same session into new files.

## Area context

`adhoc_persistence` covers the work that lets a single ad-hoc `scrape_url_chromium` result —
today only readable once, in chat, then only recoverable from its on-disk sidecar under
`src/logs/scrape_content/` — become something a user can decide, after reading it, to persist
into a RAG collection. It builds on two existing areas:

- `process-docs/scrape_pipeline/` — the sidecar/JSONL logging mechanism this work reads back
  (`write_sidecar` in `src/scraper/scrape_logger.py`), and the fact-not-verdict contract that
  governs what a sidecar contains.
- `process-docs/agentic_discovery/` — the wider pattern of an agent making a judgment call after
  reading real content, rather than a mechanism pre-deciding for it.

## Milestone: default log retention raised 14 -> 90 days (2026-09-20)

### Why

The project owner's framing (given directly, not inferred): a later, not-yet-built piece of work
will let a user decide — after reading a scrape in chat — that the scraped page should go into a
RAG collection. That decision reads the sidecar back off disk
(`src/logs/scrape_content/<ts>_<slug>.md`). 14 days was too short a runway between "scrape
happened" and "user decides to index it" for that read-back to reliably still find the file.
90 days was the number given, not derived by me.

### Mechanism

`get_retention_days()` in `src/log_janitor.py` is the single source of truth: reads
`WEBSEARCH_LOG_RETENTION_DAYS`, falls back to a literal (was `14`, is now `90`). Both
`_prune_jsonl` (JSONL line filter, `scrape_log.jsonl`/`query_log.jsonl`/etc.) and
`_prune_sidecars` (mtime-based `.md` unlink under `scrape_content/`) call it. `cli.py` also calls
it directly, at module-load time, for `TimedRotatingFileHandler(backupCount=...)` on `cli.log`.
The env var is set nowhere in the repo, so the literal is the effective value everywhere it is
read.

### What moved with the literal, and why each one did

Grep for the literal `14` plus the word "retention" across the whole repo, then judged each hit
individually — not every "14" found is this retention value (dates like `2026-09-14`, unrelated
"14 tests total" counts, and an unrelated "chrome retention" phrase in a diff-scoring docstring
all showed up and were excluded).

Changed:
- `src/log_janitor.py` — the literal itself.
- `dev/tests/test_log_janitor.py` — the one test asserting the default; renamed
  `test_get_retention_days_defaults_to_14_when_unset` ->
  `test_get_retention_days_defaults_to_90_when_unset`, assertion `== 14` -> `== 90`. The sibling
  `ValueError`-on-unparsable test is unrelated to the literal and untouched.
- `src/DOCS.md` — `log_janitor.py`'s Purpose line opened with "14-day log retention janitor.",
  now "90-day".
- `src/search/DOCS.md` — one line describing `maybe_prune_jsonl`'s cutoff as "the 14-day
  retention window", now "90-day". This is a present-tense behavioral claim about production
  code, not a historical record, so it had to track the change.
- `dev/tests/test_query_logger.py`, `dev/tests/_pipe_scraper_fakes.py` — one comment each,
  explaining to a test author why a fixture's `ts` must be current ("...older than the 14-day
  retention window..."). Both updated to 90-day. Comments are permitted in `dev/tests/` under the
  existing style there (this is not `src/`); they were in scope because they state the number as
  a fact about production behavior, not because comments in general are fair game to edit.
- `dev/tests/DOCS.md` — the `test_log_janitor.py` entry. Kept the existing "As of 2026-09-09:
  raises ValueError..." sentence (still true, still dated correctly) and added a new, separately
  dated sentence for the 2026-09-20 default change, rather than overwriting the old one in place.

Deliberately NOT changed:
- `cli.py` — already calls `get_retention_days()` for `backupCount=`, no literal to move. Checked
  directly, not assumed.
- `dev/logging/p1_log_janitor.py`, `dev/logging/01_prune_test.py`, `dev/logging/DOCS.md` — a
  standalone "dev-isolated" mirror of the pruning algorithm, not the same env var
  (`SEARXNG_LOG_RETENTION_DAYS`, pre-project-rename name), and it still carries the
  swallow-on-unparsable fallback that was removed from `src/log_janitor.py` on 2026-09-09 —
  concrete proof it was never kept in sync with `src/log_janitor.py` and isn't expected to be.
  `process-docs/refactor_sweep/2026-09-09_log_janitor_retention_fallback_removal.md` already
  states this file is "explicitly out of scope" for changes to the real module — that was treated
  as binding precedent, not re-litigated.
- `process-docs/logging/logging.md` — opens with "*Snapshot as of 2026-06 — historical process
  record; the live current state is the source code, not this file.*" and separately states
  "14-day uniform retention" as part of that snapshot. Explicitly marked historical; left as-is
  per the standing rule that a past-dated record of what a value WAS is not rewritten.

### Test count

`./venv/bin/python -m pytest dev/tests/` — 454 passed before, 454 passed after. Same count: one
assertion value and one test name changed, nothing added or removed.

### Verification (real filesystem, not source-reading)

Ran `maybe_prune_sidecars` for real against a real `tempfile.mkdtemp()` directory (not `tmp_path`,
not mocked), three files backdated via `os.utime` to 91, 14, and 89 days old:

```
get_retention_days() = 90
before prune: ['old_14d.md', 'old_91d.md', 'recent_89d.md']
after prune:  ['old_14d.md', 'recent_89d.md']
```

The 91-day file was deleted, the 89- and 14-day files were kept — confirms the live cutoff sits
at 90 days on real `mtime` comparisons, not just in the source text. A 14-day-old file surviving
is itself the sharpest single data point against the old default still being in effect.

### For whoever picks up the next `adhoc_persistence` milestone

- The actual read-back mechanism (a user deciding, after reading a sidecar in chat, to index it
  into RAG) is NOT built yet as of this entry — this milestone only widened the runway the
  sidecar has on disk before that later mechanism can read it back.
- `write_sidecar` (`src/scraper/scrape_logger.py`) is the only writer of
  `src/logs/scrape_content/*.md`; its header format (`url`/`ts`/`bytes`/`mode`/`engine` HTML
  comments) is already stable and documented in `src/scraper/DOCS.md` — read that before adding a
  reader for it.
- `maybe_prune_sidecars` is mtime-based, not ts-in-content-based — if a sidecar file is ever
  touched/rewritten after creation, its retention clock resets. Not currently a problem (each
  sidecar is written once, never rewritten), but worth knowing before building anything that
  might re-save a sidecar in place.
