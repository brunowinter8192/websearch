# Main session 2026-09-24/25 — iterative-dev-refactor over websearch

Orchestrator-level record of one Main agent running the refactor-scan skill (Phases 0-6) autonomously over websearch, in parallel with monitor-cc and trading. Worker entries of this area dated 2026-09-24/25 hold the details.

## Phase 0 decision

Excluded: `skills/` (published plugin interface) and `dev/news_pipeline/theblock/jhao104/upstream/` (vendored third-party code). `output/` was not scanned.

## Starting state, measured 2026-09-24

- `.py`: 0 files over 400 LOC, 0 functions at or over 50 lines; one file with comments/docstrings (the jhao104 validator overlay under `patches/`).
- `docs-drift-check`: 550 findings (528 rule violations).
- `.gitignore` lacked `debug/`.

## Ending state, measured 2026-09-25

- Scanner and `docs-drift-check`: 0 findings in every category.
- Default suite: 664 passed, browser-marked tests deselected; `dev/tests/run_strands.sh` runs one fail-fast pytest per file in parallel, skips browser-only modules explicitly and treats exit code 5 as a failure.

## What changed

- Phase 3: autouse conftest redirects the temp dir per test and traps `osascript`; watchdog tests no longer write into `src/logs/cli.log` (observed: a pytest tmp path had been written into the production log on 2026-09-24 20:45:45); pytest-xdist and pytest-timeout added; real-Chrome tests marked `browser`; the two pydoll core scripts renamed to `verify_*`.
- Phase 5: 32 findings; decision rule as in the monitor-cc refactoring area (recorded observation -> keep and trace, otherwise tripwire). The coindesk timeline parser keeps only the recorded field shape; the Google consent branch was removed (0 consent lines in `cli.log*`, SOCS cookie path 30/30); selector alternations were NOT removed, the hit index goes into the diagnosis only; `src/spawn/tmux_spawn.sh` deleted (no caller).
- Phase 4: all DOCS.md rewritten at module level; "Calls out" lists external packages only.
- Phase 6: `Platform` protocol declares its optional attributes (plus `supports_scrape_only`); `proxy_status_log.json` untracked (it had been force-added via `.gitignore` negation lines, now removed).

## Decisions taken autonomously

- Module-layout findings from the four-eyes review (section markers missing in about 70 test files, multiple orchestrators per module, stepdown order, shared constants without a config module) are outside the skill's Phase 2 and were left for a separate issue.
- Shebang lines stay.

## Hazard seen

- A worker's sandbox command `cd /tmp/x && rm -rf *` resolved statically to the worktree; rejected. Always use `mktemp -d`.
- Two timeout tests flipped their classification under CPU load (2 of 10 load repeats); fixed by a tick-counter `perf_counter`. The repetition count 10 was fixed before measuring.
