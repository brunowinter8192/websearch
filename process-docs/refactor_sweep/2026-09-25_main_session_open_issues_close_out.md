# Main session 2026-09-25 (afternoon): websearch module layout close-out

Orchestrator record for websearch. Worker entries of this area dated 2026-09-25 (wssrc, wsdev) hold the details; the cross-project record is in the monitor-cc area refactoring.

## Decisions taken by Main

- Classification rule given to every worker: a module run as a script or with an entry workflow gets exactly one ORCHESTRATOR that only calls functions; pure library modules and pytest modules get only INFRASTRUCTURE and FUNCTIONS; the `__main__` guard stays at file end.
- Path-run dev scripts keep `sys.path.insert` plus bare sibling imports. Reason: digit-leading module names and hyphenated area names cannot be imported absolutely without turning dev/ into packages. Recorded as a documented exception, not as conformance.
- Statements after FUNCTIONS (before the guard) were rejected; values needed at import time are computed in INFRASTRUCTURE without same-file functions, or lazily.
- Search engines became modules (`name` plus one `search_with_reason` orchestrator); `ENGINES` maps names to modules, no engine object exists at import; rate limits come from one table read lazily by `get_limiter`.
- Tracked generated reports under `dev/*/md/` keep their glyphs as historical artifacts; only the producing scripts were changed.

## Verification

- Real `websearch search_web "python datetime fromisoformat"` after the merge: all 8 engines returned URLs (google 10, duckduckgo 9, mojeek 10, openalex 6, startpage 10, brave 10, bing 10, yandex 10).
- Default suite after the follow-ups: `run_strands.sh` strands=71 skipped=1 failed=0.

## Pitfall

`dev/tests/run_strands.sh` writes to a fixed `/tmp/websearch_strands` unless `STRAND_OUT_DIR` is set; two workers running it at once overwrite each other.
