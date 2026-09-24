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
