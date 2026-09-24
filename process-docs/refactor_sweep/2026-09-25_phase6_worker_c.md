# Phase 6 worker C (websearch), 2026-09-25

Scope: the confirmed Phase 6 findings assigned to worker C. Rejected items (module layout, P2-01 shebang, P3-02/03/05, P5-03..06 and others) were not touched. The wsdoc-a process-docs cleanup was explicitly excluded by Main because wsdoc-a did it itself.

## Decisions and why

### P2-08 dead function
`fetch_search_results` had zero references in all tracked .py files. Deleted. `src/search/DOCS.md` also claimed "a sync wrapper for dev scripts"; that claim referred to this function and was removed. AST comparison against HEAD: only this function differs, all other function bodies identical.

### P4-09 emoji
Only one emoji existed in production code: the warning sign in `browser_reporter.py` (`  <sign> **REGWALL ABORT**` in the Regwall table cell). Removed the glyph, the text stays. Em-dashes and ellipses in that file are not emoji and stay. Proof: report written by old and new module on identical frozen records; unified diff shows the glyph line plus the backfill-hours line (wall-clock dependent, differs between any two runs).

### P4-01 tracked log
The file was force-added through negation rules in `.gitignore` (`!dev/news_pipeline/theblock/logs/`, `!.../proxy_status_log.json`). `git rm --cached` alone would have left the file showing as untracked, so the two negation lines and their comment were removed too. The local file is kept. The old comment called the file "institutional data"; the Code-Standards rule (logs/ is never in version control) wins per the task.

### P5-02 Platform protocol
- Direct attribute reads replaced `getattr`/`hasattr` in `pipeline.py` (three sites) and `__main__.py`.
- `Platform` now declares defaults: `timeframe = "delta"`, `uses_master_list = False`, `supports_scrape_only = False`, `riding_scrape_config = None`, plus a default `load_scrape_entries` that raises `NotImplementedError`.
- Defaults only exist for classes that subclass the protocol explicitly, so `CoinDeskPlatform` and `TheBlockPlatform` now subclass `Platform`.
- `supports_scrape_only` is new. It replaces `hasattr(platform, "load_scrape_entries")`, which cannot be expressed as a direct read once the protocol declares the method. CoinDesk sets it True (it overrides `load_scrape_entries`), TheBlock keeps the default False.
- `RidingScrapeConfig` is imported under `TYPE_CHECKING` only, to avoid a circular import through `engine/proxy_riding`. The pipeline keeps `platform.riding_scrape_config or RidingScrapeConfig()` because None is now a declared value, not a missing attribute.
- Equivalence proof: on the two registered platforms, the values old code obtained through getattr/hasattr are identical to the new direct reads (uses_master_list False/True, load support True/False, riding config object/None, timeframe present on both).

### P5-01 silent drops
| Site | Change | Reason |
|---|---|---|
| camoufox and chromium document-status listener, `request.frame` raising | `logger.debug` with response URL and exception | Playwright raises for responses without a frame (service worker); this was observed and documented in the scrape_pipeline area, so the drop stays but becomes traceable |
| `box_lock.cleanup_stale`, unreadable sidecar | raises (`json.JSONDecodeError` / `OSError`) | User decision: raise unless an observation is recorded; search of the process-docs found only a design statement ("treated as held") and no observed unreadable sidecar |
| `box_lock.cleanup_stale`, `PermissionError` on `os.kill` | warning log, sidecar kept | Recorded design (live pid of another user is treated as held); now traceable |
| `box_lock._busy_message`, blanket `except Exception` | removed, errors propagate | Same rule as the sidecar case; the busy message therefore raises instead of returning a fixed text when the sidecar is unreadable |
| `_onward_link_identity`, `ValueError` from `urlsplit` | warning log with URL and error | Hostless URLs (mailto, javascript) stay silent, they are normal and covered by an existing test; only malformed URLs are logged (example: `http://[bad`) |
| `_extract_rsc_stream_payloads`, non-JSON rows | counted, one debug line per call | Non-JSON rows are normal in RSC streams (text rows such as `2:T5,hello`); the count makes the drop visible |
| theblock `_find_news_article`, malformed JSON-LD | stderr line with URL, `_find_news_article` takes `url` | The module already reports through stderr prints; narrowed `(JSONDecodeError, ValueError)` to `JSONDecodeError` |

The dev copy `acquire_pipe/box_lock.py` got the same three edits, since it is a line-for-line variant of the src module.

Proof: `dev/tests/test_drop_reporting.py` has 12 tests. Run against the pre-change src tree (stash of src and dev/news_pipeline), 8 fail (the provoked conditions) and 4 pass (unchanged behaviour: main-frame status recorded, dead pid cleanup, holder message, hostless link silent). Against the changed tree all 12 pass.

### P3-04 run_strands.sh
- Modules containing a line `pytestmark = pytest.mark.browser` are skipped with a printed `SKIP <name> (browser-only module)`; the summary line shows `skipped=N`.
- Any nonzero exit, including 5, is a failure. Before, exit 5 was silently a pass.
- Only `test_brave_engine.py` matches the skip rule. `test_yandex_engine.py` has function-level browser marks plus normal tests, so it exits 0.
- Proof in a fresh `mktemp -d` sandbox with stub test files: a module-marked browser file is skipped (exit 0 overall); a file whose only test is browser-marked at function level yields exit 5 and is reported FAIL (exit 1).
- Consequence: passing `-m browser` to the script no longer runs module-marked browser files; use pytest directly for that.

### P3-01 real-Chrome files
Renamed with `git mv` to `verify_brave_pydoll_core.py` and `verify_mojeek_pydoll_core.py`. No Python file imported them, only the two DOCS.md files referred to the old names. Their DOCS.md now says verification, run by explicit path. Explicit-path collection still works (2 of 20 tests selected without `-m browser`; the rest carry the browser marker).

### P4-02 new DOCS.md
`dev/camoufox_lane`, `dev/pipe_scraper_hardening`, `dev/news_pipeline/theblock/jhao104/patches/helper`. `dev/DOCS.md` area list and the theblock DOCS.md sentence about the vendored jhao104 directory were updated. The pipe_scraper_hardening probe reads a URL list from `dev/explore_pipeline/` that does not exist in the repo; the DOCS says the file is not tracked (docs-drift-check flagged the literal path).

### P4-03 Calls out
Scripted rewrite (script kept in /tmp only): every `Calls out` line was split into items; items matching an allowlist of external packages and OS tools were kept, everything else (project modules, sibling groups, `src.*` imports, stdlib names such as `statistics`, `http.server`) was dropped. 169 lines changed, empty result becomes `none.`. Two mistakes of the script were caught by diffing old against new and fixed by hand: a lost `matplotlib (lazy)` and a lost `psutil; no project-internal imports on purpose`. `macOS open, pgrep and osascript` was truncated by the comma split and restored in two files.
Internal dependencies that carried information moved into the Flow paragraph of 18 directories (one sentence each), for example the `src/search/` reuse in the search_pipeline probe folders and the `src/scraper/` reuse in `src/crawler`.

### P4-04 Called by
Verified by grepping the import graph:
- `pipe_scraper_constants.py`: importers are `pipe_scraper.py` and `pipe_scraper_config.py`; `pipe_scraper_acquisition.py` removed.
- `proxy_pool/logger.py`: importers `pipeline.py`, `loop.py`, `scrape.py`.
- `proxy_riding/cooldown.py`: importers `rider.py`, `scrape.py`, `state.py`; `reporter.py` removed.
- theblock `cleanup.py`: imported by the platform `__init__.py` only.
- coindesk `cleanup.py`: not dead code by import (`coindesk/__init__.py` wraps it as the platform's cleanup method). The only call site of `platform.cleanup` is `clean_pass.py`, which `pipeline.py` runs on the proxy-pool path only, so no coindesk run reaches it. The entry states exactly that.
- `chromium_scrape.py`: `camoufox_scrape.py` added.

### P4-05
Shortened the 33-word Purpose to 22 words. My own `run_strands.sh` entry was 27 words after the first edit and was shortened as well; a scripted check over all tracked DOCS.md found no other Purpose above 25 words.

## Verification summary
- Full default suite after the last src change: 664 passed, 12 deselected.
- `docs-drift-check`: 0 path, 0 LOC, 0 rule findings.
- Nothing was run against live sites, real Chrome, or the production lock directory; lock tests use a per-test `tmp_path` as `LOCK_DIR`.

## Notes for a successor
- The sandbox shell in this environment is zsh: a `grep --include=*.py` without quotes fails with "no matches found" and aborts the rest of a chained command. Quote the glob.
- Never `rm -rf` with a relative glob after a `cd` in a sandbox; use `mktemp -d` and absolute paths.
- The `Calls out` rule is "external packages only". OS tools (macOS open, osascript, pgrep) and subprocess CLIs (rag-cli) were kept as external.
- Open judgement: `TheBlockPlatform` still carries an unused `dedup_mode` attribute; not in scope.
