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

## Milestone: `index_scrapes` CLI subcommand (M2, 2026-09-20)

### Why

This is the mechanism the previous milestone's handoff note said was "not built yet": a user
reads an ad-hoc `scrape_url_chromium` result in chat, then decides — after reading, never before —
that it should be persisted into a RAG collection. `websearch index_scrapes <collection> <url>
[<url> ...]` is the CLI surface for that decision. The agent naming URLs must not need to know
where a sidecar lives or where the collection directory lives — the tool resolves both, keeping
the agent's context small.

### What got built

New module `src/scraper/index_scrapes.py` (92 LOC), `index_scrapes_workflow(collection, urls) ->
IndexScrapesResult`, one new `cli.py` subcommand. Per URL, in order: resolve its sidecar, strip
the sidecar's own header, rewrite in the `rag-cli` collection convention, write into the
collection directory, shell out to `rag-cli index --collection <collection> --document
<filename>`. Indexing happens per file, not batched at the end — `rag-cli index` only ever takes
one `--document` per call, so batching would just move the same loop later with strictly worse
failure isolation.

Tripwire: if `RAG_CLI_COLLECTIONS_ROOT / collection` is not a directory, the WHOLE run aborts
before any URL is touched (`IndexScrapesResult.ok=False`), and the directory is never created.
`RAG_CLI_COLLECTIONS_ROOT` is a hardcoded absolute path (a separate project's data directory,
given directly by the project owner as an external fact) — no env override was added; none was
requested and there is no observed need for one, unlike `WEBSEARCH_SCRAPE_LOG_PATH`, which already
had a real, pre-existing override mechanism this module reuses as-is for locating the sidecar dir.

### URL -> sidecar resolution: recompute the slug, latest filename wins

`scrape_logger.write_sidecar` names each sidecar `<sanitized-ts>_<url-slug-with-dashes>.md`. To
resolve a URL back to its sidecar, `_find_sidecar` recomputes `scrape_logger._url_slug(url)` (the
exact function `write_sidecar` itself uses — imported, not reimplemented) and globs
`sidecar_dir.glob(f"*_{slug}.md")`. Filenames sort lexically = chronologically, because the
timestamp prefix (`YYYY-MM-DDTHH-MM-SS.mmmZ`, colons already sanitized to dashes) has fixed field
widths and one separator throughout. **The lexically-last (= most recent) match wins, unconditionally.**

This was checked against real production data, not assumed. `WEBSEARCH_SCRAPE_LOG_PATH` pointed at
the main checkout's real `src/logs/scrape_content/` (80 real sidecars at the time) turned up this
exact case for `https://www.mojeek.com/search?q=python+asyncio+tutorial`:

```
2026-09-17T16-41-00.707Z_..._python-asyncio-tutorial.md   364 bytes  (block page: "Verification required")
2026-09-17T16-43-11.214Z_..._python-asyncio-tutorial.md  7845 bytes  (real content)
2026-09-17T16-44-09.595Z_..._python-asyncio-tutorial.md   364 bytes  (block)
2026-09-17T16-44-48.629Z_..._python-asyncio-tutorial.md   364 bytes  (block)
2026-09-17T16-45-48.430Z_..._python-asyncio-tutorial.md   364 bytes  (block)
2026-09-17T16-53-41.001Z_..._python-asyncio-tutorial.md  8912 bytes  (real content, second-to-last)
2026-09-17T16-54-15.360Z_..._python-asyncio-tutorial.md   364 bytes  (block — THIS is the latest one)
```

Seven sidecars for that one exact URL (not five — I recounted from the real files; the number
given in the task framing this milestone started from was off, doesn't matter, the real count is
what's recorded here). The literal latest-by-timestamp sidecar for this URL **is** a 364-byte
block page, with a real 8912-byte content sidecar sitting one scrape earlier. "Latest wins" picks
the block page here. This was a deliberate choice, not an oversight: recency is the only
non-content-inspecting tie-break available, and this project has repeatedly removed content
judgment from the scrape path on user decision (`process-docs/scrape_pipeline/`) — searching
backwards past the latest match for a "better" one would be exactly that judgment, reintroduced
one layer up. If a successor is ever asked to change this tie-break, re-read this real example
first; it is the concrete case any change has to justify itself against, not a hypothetical.

### The byte-count requirement this milestone added, and why it exists

The project owner's own reaction to the block-page finding above: print the written byte count on
every `indexed:` line (`indexed: <url> -> <filename> (<n> bytes)`), acted on by nothing. This
makes a 364-byte result visible in the CLI output at a glance without anyone opening the file — a
reported fact sitting next to the URL, not a threshold, not a skip, not a warning. `byte_count` is
computed from the actual bytes written to the collection file (source-comment line + blank line +
content, UTF-8-encoded length), not copied from the sidecar's own `bytes:` header line (that
header is dropped entirely — see below — and in any case would measure different bytes, since it
covers only the sidecar's raw scraped content, not the collection file's own header-replaced
shape).

### The sidecar header: dropped, not carried over

`write_sidecar`'s own header (`url`/`ts`/`bytes`/`mode`/`engine`, five HTML-comment lines) is
stripped entirely and replaced with the fixed `rag-cli` collection convention: one line,
`<!-- source: <url> -->`, blank line, then content. This is not a new decision — it matches what
`src/crawler/pipe_scraper_acquisition.py`'s own batch-pipeline `_scrape_one` already writes for
every collection file that pipeline produces, confirmed by reading a real file in the
`websearch-reference` collection directory. Nothing is lost: the sidecar itself is read-only to
this module and stays on disk untouched (retention now 90 days, see the milestone above), so
`ts`/`bytes`/`mode`/`engine` remain recoverable there if ever needed. `_sidecar_content` isolates
the content by splitting the sidecar's raw text on the first `"\n\n"` — always exactly the
header/content boundary, because `write_sidecar` always writes `header + "\n" + content` and the
header string itself already ends in one `\n`, giving exactly one blank line before content
starts, every time, for every one of the 80 real sidecars inspected.

### Real discrepancy found: `_url_to_filename` does not match one pre-existing file, and that's fine

The task's own worked example named `src/crawler/pipe_scraper_acquisition.py`'s `_url_to_filename`
as already producing the collection convention, pointing at the real file
`api_semanticscholar_org_graph_v1_swagger.md` (source
`https://api.semanticscholar.org/graph/v1/swagger.json`) as the model to match. Calling the real,
installed function on that exact URL does NOT reproduce that filename:

```
>>> _url_to_filename("https://api.semanticscholar.org/graph/v1/swagger.json")
'api_semanticscholar_org_graph_v1_swagger_json.md'
```

The real file on disk has no `_json` suffix; the function's regex (`re.sub(r'[^a-zA-Z0-9]', '_',
...)`) slugs the `.` in `.json` like any other non-alphanumeric character, it does not treat a
trailing extension specially. I sampled ~40 other real files in `websearch-reference` (all
`api.stackexchange.com/docs/...` URLs, none with a path extension) and every one of those matches
`_url_to_filename`'s real output exactly. Conclusion recorded, not just assumed: the one
`swagger.md` file predates this function or this milestone and was produced some other way — it is
the outlier, not evidence of a different current convention. `index_scrapes.py` follows
`_url_to_filename` exactly as written, reused via import (not reimplemented, not patched to strip
extensions) — the function is shared with the batch pipeline, so a local special-case here would
silently NOT apply to that pipeline's own files, producing a new, second inconsistency instead of
fixing the old one. If a successor wants to close this gap, it has to be done in
`pipe_scraper_acquisition.py` itself, deliberately, with its own reason — not chased from here.

### Test count

`./venv/bin/python -m pytest dev/tests/` — 454 passed before this milestone (unchanged from the
retention milestone's own "after" count), 463 passed after (9 new, `dev/tests/test_index_scrapes.py`,
none removed or changed elsewhere).

### Verification (real command, real data, real collection, then undone)

`WEBSEARCH_SCRAPE_LOG_PATH` pointed at the main checkout's real `src/logs/scrape_log.jsonl` (the
worktree's own `src/logs/` is empty — sidecars are gitignored, per-worktree). Picked the real
Claude Opus 4.5 Anthropic sidecar (18300 bytes of real content, confirmed non-block beforehand,
confirmed as the only sidecar for that exact URL, confirmed not already present in the collection):

```
$ WEBSEARCH_SCRAPE_LOG_PATH=.../src/logs/scrape_log.jsonl ./venv/bin/python cli.py index_scrapes websearch-reference "https://www.anthropic.com/news/claude-opus-4-5"
indexed: https://www.anthropic.com/news/claude-opus-4-5 -> www_anthropic_com_news_claude_opus_4_5.md (18365 bytes)
```

Resulting file in the real collection directory, name + first 3 lines:

```
www_anthropic_com_news_claude_opus_4_5.md
<!-- source: https://www.anthropic.com/news/claude-opus-4-5 -->

Announcements
```

`rag-cli`'s own `.json` sidecar (its business, not this module's) confirmed the real index call
ran: `"collection": "websearch-reference"`, `"document":
"www_anthropic_com_news_claude_opus_4_5.md"`, 12 real content chunks.

Undone, run alone (this environment enforces that `rag-cli index`/`rag-cli delete` run with
nothing else chained in the same Bash call):

```
$ rag-cli delete --collection websearch-reference --document www_anthropic_com_news_claude_opus_4_5.md
Deleted 12 chunks
```

Both the `.md` and rag-cli's own `.json` confirmed gone from the collection directory afterward.
The original sidecar in `websearch`'s own `src/logs/scrape_content/` was confirmed untouched
(`head -1` still showed its original `url:` header line) — this module never writes to a sidecar,
only reads it.

### For whoever picks up the next `adhoc_persistence` milestone

- The previous milestone's handoff note ("the read-back mechanism is not built yet") is resolved
  by this one. What's still open: `index_scrapes` is a manual CLI call an agent has to remember to
  make after reading a scrape — nothing in the skill layer (`skills/websearch-web-research/` etc.)
  yet tells an agent when or why to reach for it. That's a skill-doc question, out of scope for
  this module itself.
- The block-page-can-win-by-recency fact is real and load-bearing for how this tool is meant to be
  used: it reports what happened, it does not protect anyone from naming a bad URL. Do not "fix"
  this by adding a size/content check later without a fresh, explicit user decision to do so — see
  the tie-break section above for the full reasoning and the real mojeek numbers to re-check
  against if that decision ever gets made.
- The `_url_to_filename`/`swagger.md` mismatch is unresolved and deliberately left that way. If it
  ever needs closing, it belongs in `src/crawler/pipe_scraper_acquisition.py` (the function's real
  home, shared with the batch pipeline), not patched locally in `index_scrapes.py`.
- `RAG_CLI_COLLECTIONS_ROOT` (`src/scraper/index_scrapes.py`) is this machine's real, hardcoded
  path into a sibling project's data directory. It has no test/env override by design. Any test
  touching it monkeypatches the module attribute directly (`monkeypatch.setattr(index_scrapes,
  "RAG_CLI_COLLECTIONS_ROOT", tmp_path)`), the same pattern already used elsewhere in this test
  suite for module-level constants (e.g. `test_mojeek_engine.py`'s `WAIT_INTERVAL`).
