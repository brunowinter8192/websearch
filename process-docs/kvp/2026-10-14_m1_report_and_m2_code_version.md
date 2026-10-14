# KVP M1 report script and M2 code version per record (2026-10-14)

Worker record for milestones M1 and M2 of the KVP plan. Branch `kvpreport`, commits `959270d` (M2), `b9e7132` (M1), `c0aabea` (orchestrator refactor). M3 (deep dive run record) and M4 (canary set) are not started.

## What exists after this work

- `src/code_version.py` and a `code_version` field in every record of `query_log.jsonl` (all three record types), `scrape_log.jsonl` (chromium and camoufox) and `pipe_scrape_log.jsonl` (both engines).
- `dev/kvp/`: `kvp_report.py` (entry), `kvp_config.py`, `kvp_load.py`, `kvp_classify.py`, `kvp_indicators.py`, `kvp_render.py`. Run from the repo root: `./venv/bin/python -m dev.kvp.kvp_report --since 2026-10-15 --until 2026-10-20`. Output `dev/kvp/md/kvp_report_<since>_<until>_<timestamp>.md`.
- Tests: `dev/tests/test_code_version.py`, `test_kvp_classify.py`, `test_kvp_report.py`, fixtures in `dev/tests/fixtures/kvp/`.
- First report on the whole window: `dev/kvp/md/kvp_report_start_now_20261014T165908.md`.

## M2 decisions

- The stamp is a short SHA of 10 characters. `+dirty` is appended when tracked files differ from HEAD (`git status --porcelain --untracked-files=no`). Untracked files are ignored on purpose, otherwise the main checkout with its untracked dev files would always read dirty (owner decision). On any git failure the value is `unknown`; a logging helper must never abort a scrape or a search.
- The stamp is written inside the three `log_*` functions, not in the record builders, so no future record type can forget it.
- The production CLI (`~/.local/bin/websearch`) runs the main checkout. Records carry the commit only after this branch is merged. Until then every real record in the main logs reads `unversioned` in the report.
- Verification records (all `code_version` `959270d339`, written from the worktree through the main venv): query_log `engine_run` and `workflow_summary` at 2026-10-14T16:52:44Z, scrape_log `https://example.com/` at 16:52:53Z, pipe_scrape_log run `cd4ca1cc` for `https://example.com/` at 16:53:11Z.

## M1 verdict rules (derived offline, never logged)

Scrape, first matching rule wins. Sizes are `bytes_returned` of the record, markers are searched in the sidecar body.

| Order | Label | Rule | Observed cases it catches |
|---|---|---|---|
| 1 | `no_content` | `acquisition_error` set or `bytes_returned == 0` | deal-magazin.com and uni-frankfurt.de (crawl4ai exception, 0 B), tk.de (`budget_exhausted`) |
| 2 | `filtered_to_nothing` | `bytes_returned <= 1` while `bytes_raw_markdown` is larger | vorschriften.bgn-branchenwissen.de (1 of 16742 B), dbis.ur.de x2 (1 of 15774 B) |
| 3 | `http_error_page` | final `http_status` 404 or 410 | github.blog 158 B, techcrunch.com 3921 B, ub.uni-frankfurt.de x5 |
| 4 | `login_wall` | `landed_url` differs from `url` in host or path, the landed host+path matches a login word (idp, saml, login, signin, sso, auth as whole words), the requested URL does not | ub.uni-frankfurt.de/formulare/* landed on idp.ub.uni-frankfurt.de SAML SSO, 482 B |
| 5 | `blocked` | final status in 401, 403, 429, 503 and `bytes_returned < 2000` | cosdna.com 506 B, stern.de 121 B, forums.raspberrypi.com 522 B |
| 6 | `challenge_or_interstitial` | `bytes_returned < 1000` and the body holds one of: "sicherheitsüberprüfung", "access denied", "verification required", "klicke auf die schaltfläche" | mojeek 185 B (six records), amazon.de 374 B |
| 7 | `usable` | everything else | |

- `crawl4ai_success` is not an input. It is wrong in both directions: stackoverflow.com x2, superuser.com, eclecticlight.co and trustpilot.com carry `false` with real bodies of 8 to 21 KB, and the status in the record is the final one (200 after a 403 in the chain).
- Silent = labels 2 to 6 (exit 0, success-shaped output, unusable body). `no_content` is counted separately because stdout says "(no content returned)".
- A 403 with a long body and no marker stays `usable`. That is the only reason the size limit of rule 5 exists.
- The planned rule 7 "stub" (HTTP 200, body under 200 B, no marker) was dropped: the smallest scrape classified `usable` has 1031 B (developer.apple.com).
- The marker list holds only markers seen in real bodies. Adding "just a moment" or "cloudflare" would be a guess.
- Reddit URLs with `js_challenge=1` in `landed_url` are `usable` because the login pattern looks at host and path only, never the query.
- iz.de 1683 B (article cut mid-word) is `usable`; paywall truncation is not detectable with these rules.

Engine run (`workflow_summary.engines[*]`): `OK`; `ERROR_*` and `TIMEOUT_*` are `transport_error`; `RATE_SKIP`; `EMPTY` is `blocked` when the diagnosis has at least one of `marker`, `challenge_triggered`, `challenge_widget`, `pow_link`, `http_status` 403 or 429, or a `showcaptcha` URL, otherwise `empty_no_signal`. `empty_no_signal` is not a claim that the engine truly had no results: google has 115 of them; the earlier inventory places almost all of them in 2026-09-06..2026-09-18 (not re-checked here), cause still unverified.

Pipe record: `no_content` (error or 0 bytes), `http_error_page` (status 400 or higher), else `usable`. All 363 records are `usable`; the log cannot show a failure in the retained window.

Collection file (`websearch-pages`, state at report time, not windowed): `placeholder` (5 or more bare `Loading...` lines), `title_only` (100 B or less after the source line), `duplicate` (same body hash as an alphabetically earlier file).

## Indicators as implemented

- Searches with at least 3 engines `OK`, searches with at least one `blocked` engine, block rate per engine and per engine per code version. Source is `workflow_summary`; `engine_run` is a duplicate of it.
- Usable-body rate and silent-failure rate of scrapes, label counts per code version.
- Relevance click data: a scrape is attributed to a drilldown when its normalized URL is in that drilldown's `urls` and the scrape happened within 3 hours after it. A search "leads to a scrape" when any of its drilldowns has such a scrape. Rank is the position in the latest matching drilldown. Scrapes are loaded up to `until` plus 3 hours so late scrapes of an in-window search count.
- Deep dive per `run_id`: URLs, failed, zero-byte, status histogram, median wall time, survival (pipe URL or landed URL found as `<!-- source: URL -->` in the collection). Discovered, kept, rounds and cleanup counts are printed as not recorded; they need M3.
- Deep dive usefulness: indexed documents (a `.json` sibling exists) of `websearch-pages` that appear in a `hits` entry of rag-cli `search.jsonl` within the window, per domain. With zero searches the report says undefined, never 0 %.
- Version split: every table has an "all" row and one row per `code_version`; records without the field are `unversioned`.

## Result on the whole window (generated 2026-10-14)

- Scrapes: 156, usable 130, silent 23 (14.7 %: blocked 3, challenge_or_interstitial 7, filtered_to_nothing 3, http_error_page 7, login_wall 3), no_content 3. The five inverse cases appear in the counter-check table as `usable`.
- Searches: 265, at least 3 engines OK 251 (94.7 %), at least one blocked engine 176 (66.4 %). Blocked runs: yandex 142 of 265, brave 75 of 265, openalex 10 of 265, mojeek 10 of 149.
- Searches leading to a scrape: 80 of 265. Rank of the scraped URL: 1:39, 2:13, 3:19, 4:8, 5:1, 6:5, 7:5, 8:8, 9:3, 10:1.
- Deep dive: 10 runs, 0 failed, run 67554e80 survival 17 of 50. Collection: 1189 files, all indexed, 4 duplicates, 1 title-only, 0 placeholders. rag-cli: 3 searches on `websearch-pages`, 12 of 1189 indexed documents retrieved.

## Differences to the inventory numbers

- The logs kept growing after 2026-10-11 (265 searches instead of 262, 361 rag-cli searches instead of 290), so counts are not comparable one to one.
- Yandex blocks are 142, the inventory counted 126: 13 yandex runs carry only the `showcaptcha` URL without `marker`, and the report counts them as blocked.
- Rank 3 shows 19 and attributed scrapes 102, the inventory had 18 and 101. Cause not investigated (hypothesis: window or tie handling in the attribution).
- The 13 platform.claude.com "Loading..." files were deleted from the collection after the move of 2026-10-11, so the placeholder rule found nothing in real data.

## Tests

- Scrape and engine cases are real records copied into `dev/tests/fixtures/kvp/` with their `source_ts`; bodies are cut to 1500 characters (the classifier takes sizes from the record). 24 scrape cases (13 expected silent or no content, 11 expected usable), 21 engine cases, a title-only file, a normal page, a real duplicate pair (bodies cut to 800 characters).
- The placeholder fixture is constructed from the documented shape (51 bare `Loading...` lines between navigation lines), because no real exemplar exists any more. The threshold of 5 lines is an assumption.
- The attribution test uses constructed records (spec, not observation): a scrape after 1 h is attributed with rank 2, a scrape after 4.5 h is not.
- `test_kvp_report.py` runs `main()` on a temporary log directory built from the fixtures, so loader, window filter and renderer are covered together.

## Gotchas for a successor

- `cli.py` prints no help; it says to invoke the skills. Commands: `search_web "<query>"`, `scrape_url_chromium <url>`, and `python -m src.crawler.pipe_scraper --url-file F --output-dir D`.
- Hook behaviour seen on 2026-10-14: `scrape_url_chromium` run through `$M/venv/bin/python cli.py ...` was blocked both with and without output redirect; `python -m src.crawler.pipe_scraper` must be alone in its Bash call; reading a redirected CLI output file back in the same call is blocked. What worked: a wrapper `/tmp/wt_ws` that execs the worktree's `cli.py`, called as `/tmp/wt_ws scrape_url_chromium <url>` without redirect.
- A worktree has no `venv`. A symlink `venv` to the main checkout's venv works and is gitignored.
- A global commit-msg hook rejects any commit whose author name is not the owner's. Tests that commit in a throwaway repo must pass `-c core.hooksPath=<empty dir>`.
- The pipe URL file for a verification run must exist before the call; a chained call that was blocked earlier had never created it and the first pipe run failed with FileNotFoundError.
- Full suite: `./venv/bin/python -m pytest -q -n0` gave 841 passed, 12 browser tests deselected.
- The orchestrator `main()` of `kvp_report.py` must only call functions; the split of query records into summaries and drilldowns sits in `split_query_records` for that reason.

## Open points

- Thresholds `BLOCK_BODY_MAX_BYTES` 2000, `INTERSTITIAL_BODY_MAX_BYTES` 1000 and the 5-line placeholder limit are tuned to the 156 observed scrapes. Re-check them when the first report on a new window shows records in the counter-check table or in the silent list that a human judges differently.
- Collection-based numbers (survival, flagged files, usefulness) are the state at report time. For a before/after comparison they change between runs even with an identical window.
- Next in the plan: M3 (run record for deep dives) and M4 (canary set).
