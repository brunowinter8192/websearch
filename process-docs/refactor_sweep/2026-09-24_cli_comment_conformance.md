# cli.py comment conformance and root DOCS.md drift (2026-09-24)

Baseline: 476 passed before, 476 passed after. `cli.py --help` and `--help` of all 5 subcommands
exit 2 and print the fixed skill-pointer text (the NoHelpParser design, unchanged).

## Comment triage (about 20 comment lines removed)

- `sys.path` insert comment: not covered anywhere; added as a Gotcha to root DOCS.md.
- Logging block comments (daily rotation, no StreamHandler, before `src.*` imports, `basicConfig`
  with explicit `handlers=` never installs the default StreamHandler): the ordering rule and
  "no stderr handler" were already in root DOCS.md. The `handlers=` detail is recorded here only:
  passing `handlers=` explicitly is why no default StreamHandler appears.
- NoHelpParser comment: covered by the root Gotcha on disabled help.
- `_log_drilldown` comment: `search_key` correlation is covered in `src/search/DOCS.md`. Fail-soft
  posture comes from `log_query` itself. The comment's pointer to a `query_logger.py` schema
  comment was already dead (removed in the search comment sweep).
- `_write_discovery_output` block: fully covered by the root Gotcha on `discover_urls`.
- Five `# -- name --` dividers: self-evident, deleted.

## Structure

The file now carries INFRASTRUCTURE / ORCHESTRATOR (`main`) / FUNCTIONS. No side-effecting
statement moved: the `sys.path` insert, the logging block, and every `src.*` import keep their
original relative order inside INFRASTRUCTURE. Only function definitions were reordered (stepdown
from `main`), which has no import-time effect. `if __name__ == "__main__"` sits at file end
because it must follow all definitions.

Residual non-conformance, deliberately not fixed (scope: zero behavior change, comments only):
`main` still contains inline logic (the `.pdf` path check via `urlparse`, `result[0].text`, and
`asyncio.run` calls). A strict Humble Object orchestrator would extract these into functions.

## Drift fixes

- Root DOCS.md said `search_web` and `search_engine_drilldown` take mutex `--books`/`--pdf`/`--docs`
  flags. The parser has only `query` (and required `--engine` for drilldown). Corrected.
- `search_web` help string said "7 engines"; `_DEFAULT_ENGINES` in `src/search/search_web.py`
  has 8. String corrected to "8 engines" (the only text change in the file).
- LOC heading updated 230 -> 213 (`wc -l`).

## Follow-up: pure orchestrator (2026-09-24)

The residual noted above was fixed after review. `main` is now a pure if/elif over `args.cmd`,
one dispatcher call per branch: `_dispatch_search_web`, `_dispatch_search_engine_drilldown`,
`_dispatch_scrape_url_chromium`, `_dispatch_discover_urls`, `_dispatch_index_scrapes`. The PDF
check lives in `_dispatch_scrape_url_chromium` as an early return before the workflow call (no
sentinel, no shared `result` variable). `_write_discovery_output` moved below its caller for
stepdown order. LOC heading 213 -> 218. Tests: 476 passed; all `--help` checks unchanged.

## Recap (2026-09-24)

Files changed versus `integration`: `cli.py`, `DOCS.md` (root), this file. Final state verified:
cli.py 218 LOC (matches the DOCS.md heading), 476 tests passed before and after, `--help` of the CLI
and all 5 subcommands exit 2 with the skill-pointer text.

Lessons for a successor:
- `sed -i` with BSD sed on macOS needs an explicit backup-suffix argument; a failed sed inside a
  `;` chain does not stop the commit that follows. Use Edit for DOCS.md changes and check each
  segment's own output.
- A section-marker restructure of a file with import-time side effects is safe as long as only
  function definitions move; the `sys.path` insert, logging setup and `src.*` imports stay in
  their original order in INFRASTRUCTURE.
- The orchestrator (`main`) must contain no logic at all: even a `urlparse` check or
  `print(result[0].text)` belongs in a per-command dispatcher, with early returns instead of
  sentinels.
- Root DOCS.md is a real drift source for CLI flags: check the argparse wiring, not older DOCS text.

# Phase 2 dev comment sweep (2026-09-24)

Scope: 35 `.py` files (every `.py` in the six directories carried at least one violation) in
`dev/scrape_pipeline/` (22 files, incl. `03_cleanup/`, `04_overview_sweep/`, `05_paper_mode/`,
`browser_eval/`, `filter_eval/`, `garbage_eval/`), `dev/agentic_discovery/` (7), `dev/logging/` (3),
`dev/pipe_scraper_hardening/` (1), `dev/camoufox_lane/` (1), `dev/engine_reduction/` (1).
Measured before: 15 + 25 + 2 + 0 + 1 + 1 = 44 docstrings, 218 + 181 + 22 + 17 + 8 + 8 = 454
comments. After: an AST + tokenize scan (shebang and the three markers exempt) prints nothing.

## Method and proof of zero behavior change

- Removal was done by one tokenize/AST script, not by hand-editing 35 files: it deletes
  standalone comment lines and docstring statements, cuts trailing comments, and collapses only
  blank-line runs that a deletion created. It never touches string literals.
- Proof: for every touched file, `ast.dump` of the new module equals `ast.dump` of the
  pre-change module after both have their docstring statements removed. 35/35 equal. The three
  `__doc__` files are equal after mapping the new `DESCRIPTION` constant back to `__doc__`.
- `__doc__` landmine: only three files used it, all as `argparse.ArgumentParser(description=__doc__)`:
  `03_cleanup/clean.py`, `04_overview_sweep/sweep.py`, `04_overview_sweep/analyze.py`. Each now has a
  `DESCRIPTION = """..."""` constant in INFRASTRUCTURE with byte-identical text (the script asserts
  the constant equals the old docstring) and `description=DESCRIPTION`.
- `--help` diff (captured before and after, `diff -r`): identical for the 9 argparse scripts that
  parse before doing any work (`01_dual_mode_smoke`, `02_raw_smoke`, `06_cloudflare_md_adoption`,
  `07_pipe_scrape_eval`, `filter_eval/06_content_source`, `sweep`, `analyze`, `clean`, `download`).
  Not run, on purpose: `filter_eval/04_filtering.py` and `browser_eval/03_browser.py` read
  `sys.argv` as URLs without argparse (`--help` would be scraped as a URL); `filter_eval/05_filter_debug.py`
  imports `src.scraper.*` modules that no longer exist and dies at import; the seven
  `agentic_discovery` scripts and the other probes take no argparse and mutate external files or
  hit live services.
- Every touched file passes `py_compile`. Test suite: 488 passed before and after (one earlier run
  of the same suite before any edit showed 1 failed / 487 passed and passed on the immediate rerun,
  so treat that one test as flaky, unrelated to dev/ scripts).
- The three files that import `src.*` inside `dev/` (`browser_eval/01_baseline.py`,
  `filter_eval/05_filter_debug.py`, `garbage_eval/08_garbage_edge_cases.py`) were rewritten by the
  script without a hook refusal. No import was added or changed.
- `/tmp` is shared with other workers: a file named `/tmp/scan.py` written by this session was
  overwritten by another agent's scanner mid-session, which made one verification print another
  area's files. Use a session-unique directory under `/tmp` for helper scripts.

## Triage counts per file

Columns: total = docstring items + comment lines. a = deleted, substance already in a DOCS.md or
process-docs. b = deleted, substance recorded in this file (below). c = self-evident or restating
the adjacent code (includes def-heading comments, `# noqa`, section dividers). Counted per comment
line / docstring item at block granularity; a block whose facts are summarised below counts as b.

| File | total | a | b | c |
|---|---|---|---|---|
| scrape_pipeline/01_dual_mode_smoke.py | 24 | 0 | 4 | 20 |
| scrape_pipeline/02_raw_smoke.py | 9 | 1 | 2 | 6 |
| scrape_pipeline/03_cleanup/clean.py | 66 | 1 | 53 | 12 |
| scrape_pipeline/04_overview_sweep/analyze.py | 24 | 1 | 4 | 19 |
| scrape_pipeline/04_overview_sweep/sweep.py | 11 | 1 | 3 | 7 |
| scrape_pipeline/05_paper_mode/download.py | 6 | 1 | 0 | 5 |
| scrape_pipeline/06_cloudflare_md_adoption.py | 9 | 3 | 0 | 6 |
| scrape_pipeline/07_pipe_scrape_eval.py | 8 | 0 | 0 | 8 |
| scrape_pipeline/_pipe_scrape_eval_common.py | 3 | 0 | 0 | 3 |
| scrape_pipeline/_pipe_scrape_eval_phase1.py | 3 | 0 | 0 | 3 |
| scrape_pipeline/_pipe_scrape_eval_phase2.py | 5 | 1 | 1 | 3 |
| scrape_pipeline/_pipe_scrape_eval_phase3.py | 10 | 1 | 3 | 6 |
| scrape_pipeline/p1_pipe_scraper.py | 4 | 1 | 1 | 2 |
| scrape_pipeline/browser_eval/ (3 files) | 15 | 0 | 0 | 15 |
| scrape_pipeline/filter_eval/ (3 files) | 24 | 0 | 0 | 24 |
| scrape_pipeline/garbage_eval/ (3 files) | 12 | 0 | 0 | 12 |
| agentic_discovery/clean_web_Playwright.py | 11 | 1 | 0 | 10 |
| agentic_discovery/clean_web_anthropic.py | 14 | 1 | 0 | 13 |
| agentic_discovery/clean_web_cookieyes.py | 37 | 0 | 3 | 34 |
| agentic_discovery/clean_web_onetrust.py | 32 | 1 | 3 | 28 |
| agentic_discovery/clean_web_rag_docs.py | 47 | 1 | 4 | 42 |
| agentic_discovery/clean_web_searxng.py | 52 | 1 | 8 | 43 |
| agentic_discovery/clean_web_tor.py | 13 | 1 | 2 | 10 |
| logging/01_audit.py | 12 | 1 | 0 | 11 |
| logging/01_prune_test.py | 5 | 1 | 0 | 4 |
| logging/p1_log_janitor.py | 7 | 2 | 1 | 4 |
| pipe_scraper_hardening/01_stealth_concurrency_probe.py | 17 | 1 | 3 | 13 |
| camoufox_lane/01_launch_timeout_probe.py | 9 | 0 | 5 | 4 |
| engine_reduction/openalex_pdf_probe.py | 9 | 2 | 1 | 6 |

Per-directory sums equal the measured totals (scrape_pipeline 233, agentic_discovery 206, logging 24,
pipe_scraper_hardening 17, camoufox_lane 9, engine_reduction 9).

## Facts moved here (b), grouped by module

### scrape_pipeline/01_dual_mode_smoke.py
- crawl4ai prints `[FETCH]`/`[SCRAPE]`/`[COMPLETE]` progress lines to stdout BEFORE the CLI's own
  output. The result parsers therefore use `re.search(..., MULTILINE)` / `str.find` on the whole
  stdout, never `startswith`. Observed in the saved data under `01_dual_mode_data/20260505_185247/`.
- `FAILURE_SIGNALS` is ordered by specificity, first substring match wins in `detect_failure_type`.
  The signal strings are messages of the retired production garbage classifier (`is_garbage_content`,
  removed 2026-09-09); a run today would label every failure `unknown_error`.
- Finding (not fixed, out of scope): Mode 1 shells out to `cli.py scrape_url_raw`. The current
  `cli.py` parser has 5 subcommands and no `scrape_url_raw`, so Mode 1 cannot succeed. Added as a
  Gotcha to `dev/scrape_pipeline/DOCS.md`.

### scrape_pipeline/02_raw_smoke.py
- `arun_many` returns results in dispatch order, not input order, so results are indexed by URL.
- The `(PDF)` / `(plugin-domain: github)` suffix on an `empty` status is an informational hint, not
  routing logic (plugin domains hard-coded: github.com, arxiv.org, reddit.com).

### scrape_pipeline/03_cleanup/clean.py (all patterns are URL-spanning heuristics)
Order in `clean_markdown`: HN top nav, GitHub chrome (site-specific, establish the content anchor),
then pre-h1 chrome, no-h1 fallback, skip links, sphinx anchors, tail chrome, blank-line collapse.
Where each pattern was first seen:
- GitHub chrome: `github.com/adbar/trafilatura/issues/25`. Issue/PR pages carry ~150 lines of
  nav/search/sponsor/repo chrome; the title is `# <text> #<N>` with N from the source URL path.
- Pre-h1 chrome: `seirdy.one` (simple) and `github.com` (cluster of chrome h1s). The title h1 is
  the first h1 whose gap to the next h1 holds at least `MIN_TITLE_PROSE_CHARS=200` chars of
  substantive prose (lines over 60 chars that are not link-only, table rows or headings); else the
  first h1. Stale wording removed: the old comment said "MIN_TITLE_GAP lines", the constant is chars.
- No-h1 fallback: `adrien.barbaresi.eu` and the ACL Anthology page (`doi.org/10.18653/v1/...`).
  Strip pure-link nav until the first substantive line (heading, or over 60 visible chars after
  removing image-in-link wrappers, images, links, bare URLs, emphasis marks). Robust against nested
  `[![ACL Logo](url)ACL Anthology](url2)`.
- Skip-to-content links: `seirdy.one`. Sphinx/Furo permalink anchors `[#](url "Link to this heading")`
  and `[¶](url "Permalink to ...")`: `trafilatura.readthedocs.io`.
- Tail chrome (earliest marker wins): `## Continue reading` from `seirdy.one`, expanded with
  Related posts/articles, Comments, Webmentions, Replies, `You are here:`, `Copyright <year>`.
- HN: the page is nested markdown tables; the story starts at the first row containing a
  `vote?id=` link (present on story rows and comment-permalink rows alike), everything before it
  (logo plus new/past/comments/ask/show/jobs/submit/login row) is nav.
- `MIN_CONTENT_BYTES=500`: raw files below this (PDFs etc.) are skipped, not cleaned.

### scrape_pipeline/04_overview_sweep/analyze.py, sweep.py
- `SHAPE_MAP` is a manual classification of the Q24 URL set. `trafilatura.readthedocs.io` is filed
  as `Blog` because of its blog-like single-h1 structure although it is technical docs;
  `adrien.barbaresi.eu` is `Index-Aggregator` because it is a tag page. `webscraping.fyi`
  (scrape failure), `downloads.webis.de` and `searchstudies.org` (PDFs) are excluded so they do not
  pollute metrics.
- sweep: `CacheMode.BYPASS` per config keeps results comparable (fresh fetch each time); for the
  `none` filter the `content_source` still varies (markdown generation sees different HTML); the
  smoke-report parsing block is a deliberate copy of `02_raw_smoke.py` so each dev script stays
  self-contained.

### scrape_pipeline/_pipe_scrape_eval_phase2.py, _phase3.py, p1_pipe_scraper.py
- Phase 2 plateau rule falls back to the highest tested delay when no adjacent pair gains 5% or less.
- Phase 3 pacing constants: `PHASE3_BATCH_SIZE=30` matches the WAF burst window seen in Phase 1;
  `PHASE3_INTER_BATCH_S=30.0` is a conservative recovery pause; `PHASE3_RETRY_COOLDOWN_S=60.0` is the
  wait before the single retry pass over 429 URLs.
- `p1_pipe_scraper.EMPTY_THRESHOLD_BYTES=100`: below this a page counts as `empty`. The production
  constant of the same name was removed with the `outcome` verdict; this dev copy keeps it.

### agentic_discovery (site chrome facts, one-shot scripts that rewrite RAG files in place)
Do not run these to check anything: they overwrite files in the sibling RAG project.
- Playwright (Docusaurus): content is the span from the first `# ` heading to the first
  `[Previous ` / `[Next ` link; a bare `Learn`/`Community`/`More` header followed by a list item marks
  the site footer when no pagination link exists.
- `clean_web_rag_docs.py`: Docusaurus heading anchors are `[<U+200B>](URL "Direct link to ...")`, the
  link text is a zero-width space; MkDocs (crawl4ai) has standalone `Copy` lines after code blocks,
  a mobile close button rendered as `×`, and a footer starting at `#### On this page`, `> Feedback`,
  `xClose`, `Type to start searching` or `[ Ask AI ]`; Sphinx (trafilatura) has `[#](URL "Link to
  this heading")` anchors and a footer of `[ previous X ][ next Y ]`, `On this page`, `### This Page`.
- `clean_web_searxng.py` footer markers per prefix: searxng `[ ![Logo of SearXNG]`, crawl4ai
  `Page Copy`/`ESC to close`, playwright `[Previous `, tor `[Edit this page](`, anthropic icon-only
  links plus `### Solutions|Partners|Company|Learn|...`, trafilatura logo line or copyright line,
  onetrust `Getting Started` / `Did this page help you?`, cookieyes `## Have more questions?` /
  `## CookieYes`; other prefixes fall back to a copyright line.
- cookieyes: category index pages (`cookieyes__category__*.md`) are a list of child links and that
  list IS their content; the helpfulness footer can also appear inline as a ` Was this article
  helpful? Yes No` suffix on a content line; the skip-icon plus `Jump to` anchor block follows a
  `Last updated on` line on some pages. "Skip to content" links were never seen in the samples.
- onetrust: split headings (`# ` alone, text on the next line) are merged; trailing `* * *`
  separators are stripped only when nothing meaningful follows them (changelog case).
- tor: the footer starts at the `Jobs` link, English or localized
  (`/de/about/jobs/` style prefix); a `View for:` widget line also consumes the OS-label line after it.
- anthropic: card navigation at end of file is a single line of concatenated `[ text ](url)` links.

### logging
- `01_prune_test.py` docstring named `dev/log_janitor/01_prune_test.py`; the real path is
  `dev/logging/01_prune_test.py` (directory was renamed). The test sets
  `SEARXNG_LOG_RETENTION_DAYS=14` and uses a fast-path marker window of one hour
  (`_MARKER_MAX_AGE_SECS=3600`, the stale-marker scenario backdates the marker by 3700 s).

### pipe_scraper_hardening/01_stealth_concurrency_probe.py
- The script mirrors `src/crawler/pipe_scraper.py`'s per-domain pacing model verbatim as a dev-local
  copy (dev scripts may not import `src/`). The only additions are the `enable_stealth` toggle on
  `BrowserConfig` and verbatim exception-message capture for the crash log, because production
  `_scrape_one` discards the exception text. `GAP_SECONDS=300` between the baseline and stealth run
  exists because WAF budget recovery takes minutes (the measurement is in the
  `pipe_scraper_hardening` and `pipe_scraper` process-docs).

### camoufox_lane/01_launch_timeout_probe.py
- Purpose: send a 1 ms launch timeout through the same chain production uses (kwargs ->
  `camoufox.launch_options` -> `AsyncCamoufox(from_options=...)`) to learn whether the timeout kwarg
  is enforced or silently ignored, with a second run at the production default (30000 ms) as a
  control through the identical probe path. `PROD_TIMEOUT_MS` and `PROD_KWARGS`
  (`headless=False, os="macos", block_images=False`) are literal copies of what
  `src/scraper/camoufox_scrape.py` builds; they are kept in sync by inspection, not by import, so a
  change there is not detected here.

### engine_reduction/openalex_pdf_probe.py
- The 7 queries are real agent queries from the query log, 2026-08-20 to 2026-09-03. Eyeball
  listings cover queries 3 and 6 (1-indexed). Vendor facts the probe relied on, captured
  2026-09-03: no `mailto` parameter (ignored since 2026-02), no API key, keyless budget $0.10/day
  at $0.001 per call, so 7 calls fit comfortably.

## Findings noticed, not touched (out of scope)
- `dev/scrape_pipeline/filter_eval/DOCS.md` says `04_filtering.py` writes to `04_reports/`; the code
  writes to `03_filter_comparison/`. Pre-existing drift.
- `browser_eval/02_regression.py` prints "Run run_baseline.py first"; the script is `01_baseline.py`.
  The text is a string literal, so it stays.
- DOCS.md LOC headings for every touched file that has a DOCS entry were updated to the new
  `wc -l` values (the `pipe_scraper_hardening` and `camoufox_lane` directories have no DOCS.md and
  none was created).

## Recap, Phase 2 (2026-09-24)

Files changed versus `integration`: 35 `.py` files in `dev/scrape_pipeline/`, `dev/agentic_discovery/`,
`dev/logging/`, `dev/pipe_scraper_hardening/`, `dev/camoufox_lane/`, `dev/engine_reduction/`; nine
`DOCS.md` files (`dev/scrape_pipeline/` and its subdirectories `03_cleanup`, `04_overview_sweep`,
`05_paper_mode`, `browser_eval`, `filter_eval`, `garbage_eval`, plus `dev/agentic_discovery`,
`dev/logging`, `dev/engine_reduction`); this file. Every `### <module>.py (N LOC)` heading in those
DOCS.md files was re-checked against `wc -l` at recap time: no mismatch.

Lessons for a successor:
- A tokenize/AST stripper plus an `ast.dump` equality check (docstrings removed on both sides) proves
  zero behavior change for a comment sweep far more cheaply than reviewing 35 diffs by eye.
- Before removing docstrings, grep for `__doc__`; here it fed `argparse(description=...)` in three
  scripts. Capture `--help` before and after and diff it, but only for scripts that parse arguments
  before doing any work.
- Do not put helper scripts at fixed names in `/tmp`; another worker overwrote one mid-session.
- Facts worth keeping in these dev scripts sit in a few places: site-chrome patterns in
  `agentic_discovery`, pattern-discovery URLs in `03_cleanup/clean.py`, and the mirrors of production
  constants in the probes. Read the "Facts moved here" section above before touching them.
