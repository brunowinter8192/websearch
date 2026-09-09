# Comment-rule conformance for src/news/ + src/death_pipe.py + src/log_janitor.py (2026-09-07)

Fourth pass of the comment-rule conformance sweep (`src/scraper/`, `src/search/`, `src/crawler/`
covered earlier, see those areas' own entries in this same folder). Every comment line and
docstring in `src/news/**/*.py` (39 files across the root, `engine/`, `engine/proxy_pool/`,
`engine/proxy_riding/`, `platforms/coindesk/`, `platforms/theblock/`) plus the two root utility
modules `src/death_pipe.py` and `src/log_janitor.py` was removed except the three allowed section
markers. Pure deletion: no code line changed, no reformatting, zero behavior change — 378 passed
before and after.

## Triage and the one correction from Main

Same shape as the `src/crawler/` pass: "every hit is DELETE," confirmed by reading all 40 files
end-to-end against their package DOCS.md (`src/news/DOCS.md`, `engine/DOCS.md`,
`engine/proxy_pool/DOCS.md`, `engine/proxy_riding/DOCS.md`, `platforms/DOCS.md`,
`platforms/coindesk/DOCS.md`, `platforms/theblock/DOCS.md`, `src/DOCS.md`). Every comment's
substance traced to something already stated in the relevant DOCS.md's Modules or Gotchas
sections — none required a process-docs read.

The scan surfaced one item beyond Main's named list: `src/death_pipe.py` line 1, the
`#!/usr/bin/env python3` shebang, flagged by the AST scan as a non-marker comment line. Proposed
deleting it on the grounds that the file is not executable (`chmod +x` absent) and is always
invoked as `[sys.executable, path, ...]`, never run directly — so the shebang appeared to carry no
runtime role. Main corrected this before Go: the comment rule exempts a shebang explicitly, and it
stayed. The AST scan script itself was adjusted with a one-file exemption (`src/death_pipe.py`
line 1) so subsequent scan runs correctly treat the shebang as allowed rather than flagging it.

## Bundled fix: src/DOCS.md's death_pipe.py "Called by" drift

Main also flagged, independent of the comment-deletion task, that `src/DOCS.md`'s death_pipe.py
entry still named `src/scraper/chromium_scrape.py` as the caller of `_terminate_then_kill`. Grep
against `src/scraper/*.py` confirmed `_kill_by_profile` and `_reap_orphaned_scrapes` (the two
callers of `death_pipe._terminate_then_kill`) are defined in `chromium_process.py`, not
`chromium_scrape.py` — `chromium_scrape.py` only calls `spawn_watchdog`. The "Called by" line was
corrected to attribute each function to its actual caller module.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count. The AST-based scan script (module
docstrings, function/class docstrings, any comment line other than the three markers, and inline
trailing comments outside string literals — with the one shebang exemption noted above) printed
nothing for the whole `src/` tree after the edit pass. All 40 touched `.py` files' `wc -l` values
were verified programmatically against their respective DOCS.md module headings across all seven
touched DOCS.md files — zero mismatches, checked in one pass rather than file-by-file spot check.
