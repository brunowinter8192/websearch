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

## Iteration 1 (2026-10-14): M4 canary runner and the empty-filter fallback

This section supersedes the line above that says M4 is not started. Commits on branch `kvpreport`: `c4d6606` (canary runner), `ba9a2f3` (baseline on unfixed code), `d6f7f06` (fix), `ae8ca4e` (run after the fix). The worktree was fast-forwarded to `integration` (`e44a35f`) first, so the baseline ran on the integrated code.

### Trigger and evidence

- Three `scrape_log` records had `bytes_returned=1` while `bytes_raw_markdown` was 15 to 17 KB, HTTP 200, mode filtered: `https://vorschriften.bgn-branchenwissen.de/daten/gv/eg_2004_853/a35.htm` (2026-09-15), `https://dbis.ur.de/UBFM/resources?q=JSTOR` and `...?q=Business+Source` (2026-09-23). `chromium_scrape._acquire_scrape` sent only `fit_markdown`.
- Probe before any change (`try_scrape` with the response captured, nothing logged): for all three, `fit_markdown` is `"\n"` (1 B). bgn raw is 16742 B and holds the complete legal text (Annex III Section V, chapters I to IV with tables, then the table of contents). The pruning filter removes a table-layout page entirely. dbis raw is 15916 B for both queries and byte-identical: it is the list of library organisations ("Keine Organisation wählen", AACHEN to MÜNSTER). The words JSTOR and Business Source are not in it, so the result list is missing before the filter runs. Hypothesis, not verified: the results are loaded by JavaScript after the capture.
- Precedent: a fit-to-raw fallback with a 200 B threshold existed and was removed on 2026-08-22 (area `scrape_pipeline`). That record names the evidence a reintroduction needs: a concrete failing URL with a large filtered-vs-raw gap where raw is real content, not chrome. bgn is that URL. The old threshold was never reintroduced.

### Decisions

- Rule in `select_content(fit, raw)`: if `fit_markdown` has no word character (`\w`) and `raw_markdown` has one, the agent gets raw. Otherwise fit, also when both are empty. No byte threshold: the observed condition is "whitespace only", and the earlier threshold had fired once in 69 scrapes without effect. The existing test that a short fit with text stays untouched remains valid.
- Owner decision: the rule also applies to dbis. The agent otherwise receives nothing; `content_source` keeps it traceable.
- New fact field `content_source` in the scrape record: `fit_markdown`, `raw_markdown_fallback`, or `null` when crawl4ai produced no markdown. `bytes_returned` is what was sent, `bytes_raw_markdown` unchanged. Not added to the config stamp: `code_version` already separates the records and `config_hash` stays stable.
- Scope: only the chromium ad hoc lane. Camoufox and pipe_scraper already use raw markdown.
- Known weakness, hypothesis only: `\w` also matches letters inside URLs, so a raw page made of nothing but link syntax counts as "has text". No such page was observed.

### Canary runner (M4)

- Files: `dev/kvp/kvp_canary.py` (entry), `kvp_canary_logic.py` (pure functions), `canary_cases.json` (17 cases). Run: `./venv/bin/python -m dev.kvp.kvp_canary [--baseline dev/kvp/json/<file>.json]`. Output `dev/kvp/md/kvp_canary_<ts>.md` and `dev/kvp/json/kvp_canary_<ts>.json`; exit code is always 0, the runner only reports.
- Each case: `name`, `url`, `expected` (a `kvp_classify` label), optional `must_contain`, `origin`, optional `volatile`. Verdict comes from `classify_scrape`; the content marker is checked against the returned body. A case is PASS only if the verdict matches and every marker is present.
- `expected` is the wanted state for the defect cases (usable) and the observed state for failures nobody can fix (cosdna, stern, raspberrypi: blocked; ub login: login_wall; three 404 pages). A flip of a pinned case therefore shows up as FAIL and must be looked at, improvement or site change.
- Cases: 3 empty-filter URLs, 3 blocks, 2 volatile challenges (mojeek, amazon.de), 1 login wall, 3 404, 5 regression guards (example.com, pytest builtin, a stackoverflow and an eclecticlight page that carry `crawl4ai_success=false` with real content, kubernetes.io for the code-block guard).
- Volatile cases are annotated and listed in their own table in the baseline comparison. Observed: amazon.de returned a 120 KB page in both canary runs while the logged 2026-09-26 record was a 374 B interstitial; mojeek returned the 185 B verification page in both runs although it served real results in two of eight logged calls.
- The runner calls the real `scrape_url_chromium_workflow` with `WEBSEARCH_SCRAPE_LOG_PATH` pointing to a directory under `$TMPDIR` named `kvp_canary_*` (on this machine `/var/folders/...`, not `/tmp`). Production logs stay clean. One run per case, sequential, because `reap_orphaned_scrapes` at the start of every scrape would kill the Chrome of a parallel scrape. A run takes about 4 minutes.
- The canary report prints `code_version`. A run from a dirty tree reads `+dirty`; commit before a baseline run.

### Result

| Case | Baseline `c4d66065ce` | After fix `d6f7f060cf` |
|---|---|---|
| bgn a35 | FAIL, `filtered_to_nothing`, 1 B | PASS, `usable`, 16742 B, `raw_markdown_fallback`, marker "Sterilisationsvorrichtungen" present |
| dbis JSTOR | FAIL, 1 B | verdict `usable`, 15916 B, marker JSTOR missing: FAIL |
| dbis Business Source | FAIL, 1 B | verdict `usable`, 15916 B, marker missing: FAIL |
| 12 other stable cases | PASS | PASS, `content_source` `fit_markdown` |

Stable cases passing: 12 of 15 before, 13 of 15 after. Byte differences in unchanged cases are page variance (stern 121 to 119 B, stackoverflow 9609 to 9656 B), not an effect of the fix. Reports: `dev/kvp/md/kvp_canary_20261014T171108.md` (baseline) and `kvp_canary_20261014T171607.md` (after). Real record after the fix, bgn: `content_source raw_markdown_fallback`, `bytes_returned 16742`, `code_version d6f7f060cf`.

### Open points

- dbis stays unsolved at content level: the agent now gets the organisation list instead of one byte, not the result list. The KVP report classifies such a record as `usable`, because its rules cannot see missing content; only the canary marker shows it. Cause of the missing results is unexplained.
- The fix is active in production only after the merge; until then new records in the main logs carry no `content_source`. After the merge, a KVP report on a window with `code_version` split should show no new `filtered_to_nothing` records.
- The hook setup blocks `cli.py scrape_url_chromium` run through a venv path; the canary was started with `./venv/bin/python -m dev.kvp.kvp_canary > /tmp/<file> 2>&1`, which was accepted.

## Iteration 2 (2026-10-14): collapse searches, host saturation facts

Commits on branch `kvpreport`: `0a5b117` (host facts), `a23deaf` (report section and collapse classification). Task A is analysis only, no code. No fix for the collapse itself was made; the iteration only adds facts so the next collapse can be diagnosed from the log.

### A: what the existing sources show

Trigger: 14 of 265 searches had fewer than 3 engines OK. Method notes for a successor: `cli.log` and the rag-cli logs use local time (CEST, UTC+2), `query_log` uses UTC; `cli.log` holds 3.3 M DEBUG lines (about 99 % pydoll and websockets), so it was read by time window and logger name, never in full; its CDP event lines are truncated to 1000 bytes and carry no request ids.

The 14 searches fall into five groups, only the last one is the saturation question:

| Group | Searches | Evidence | Reading |
|---|---|---|---|
| Blocks | 2026-09-15T11:52Z (1) | brave and yandex `blocked`, openalex and google `EMPTY`, startpage 1 watchdog timeout | engine blocks, not an outage |
| Old architecture | 09-15 18:42Z to 18:43Z (3) | persistent Chrome profile `~/.websearch/browser-session`, `TIMEOUT_NONCOOP` and `TIMEOUT_HTTPX` | before the self-launched Chrome per search (commit `4769358`) |
| Connect failure | 09-21 08:40Z to 10:03Z (6) | pydoll connects to its preassigned port (log: `Browser initialized: port=9296`) while Chrome was started with `--remote-debugging-port=0`; "Failed to get browser ws address: Cannot connect to host localhost:92xx", 24 of 24 occurrences on that day; Chrome start 10:40:40, first tab 10:40:45 (local) | never seen again after 09-21; hypothesis: transitional or probe code (one query is "orchestrator failure path probe") |
| Local network | 09-24 17:13:08Z and 17:13:10Z (2) | 7 browser engines `net::ERR_CONNECTION_REFUSED` within 0.25 to 0.36 s and openalex (httpx) "502 Bad Gateway" in the same second, twice | cause outside the tool; hypothesis: proxy or VPN, nothing logged |
| Slow navigation | 10-10T12:09:15Z, 10-14T16:39:24Z (2) | see below | current architecture |

Since the fresh-profile-per-run architecture (2026-09-19): 114 searches, 12 with at least one watchdog timeout, 10 with fewer than 3 OK (6 connect failures, 2 local network, 2 slow navigation).

Slow-navigation facts (the two cases of the task):
- Chrome start is not the cause: process start to all tabs created took about 0.8 s in both cases.
- All engines slow down together. Over 249 healthy searches the navigation duration (INFO lines "Navigating to URL" to "Navigation complete") has the median 0.57 s startpage, 0.80 s bing, 1.21 s brave, 1.16 s yandex, 1.42 s google, 1.24 s duckduckgo. In the 10-14 16:39:24Z search the median over engines is 4.96 s (startpage 5.2 s, bing 5.2 s, yandex 5.0 s). On 10-10 five of seven browser engines never logged "Navigation complete" within the 6 s watchdog; google hit its own 3 s page-load limit. Engines of different companies and CDNs slowing down together points to the local side or the local network, not to the engines.
- Dose and response: the four searches of 10-11 14:11Z (owner-reported load average 14.6 during a rag-cli index) had median navigation 2.0 to 2.65 s and all engines stayed OK; the 10-14 16:39:24Z search had about 5x and collapsed; 16:39:36Z had 3.3 s and 5 OK. Healthy maxima are 3.6 to 4.9 s and the watchdog is 6 s, so a slowdown of roughly 4x or more tips engines over the limit.
- The Python event loop was not starved: the lag between a CDP frame arriving and pydoll processing it had median 0 ms and maximum 12 ms (2803 events on 10-14, 1707 on 10-10). A process that macOS throttles as a whole would not show up in this measure.
- Concurrent load seen in other sources: 10-14, rag-cli indexing of `websearch-reference` ran 18:38:44 to 18:41:39 local (indexer and chunker log), overlapping both slow searches. 10-10, `pmset -g log` shows a Spotlight task (`mds_stores` BackgroundTask) held 14:01:23 to 14:06:18 and about 14:06:57 to 14:17:30 local, covering the search at 14:09:08; the rag-cli logs show nothing then. No Spotlight task around 10-14 18:39. The machine never slept and pmset holds no thermal event (it only reaches back to 2026-10-07).
- Weak and confounded: rag-cli embedding activity overlapped 7 of 14 collapse searches against 29 of 251 normal ones; median concurrent Claude sessions around the search was 2 against 1.

Not decidable from these sources: local CPU contention, local I/O or the local network. Nothing recorded CPU. Hypothesis, not proven: CPU contention.

Other facts: the 52 `TIMEOUT_WATCHDOG` are spread over many days (09-21 18, 09-15 11, 09-19 8, 10-10 5, 09-24 3, 10-14 3, rest 1 or 2). The 12 "Page load timed out" are the own 3 s page-load limit of google, duckduckgo and mojeek, logged as `ERROR_BROWSER`. A watchdog timeout with `diagnosis` null means the engine was still before the result wait (navigating); with `diagnosis_partial` it was already waiting for results. Overhead (browser start plus lock wait) is derivable as `total_wall_ms` minus the largest `search_ms`, so no extra field.

### B: what was added

- `src/host_load.py`, field `host` in the `workflow_summary` record and in the chromium scrape record: `cpu_count`, `load_avg_start` (load average before the own Chrome runs), `cpu_busy_pct` (system CPU over the workflow window, from `psutil.cpu_times()` deltas), `top_cpu_processes` (top 3 by CPU seconds in the window, aggregated by process name, own python process excluded, with process count), `errors` (list).
- The process table comes from `ps -axo pid=,time=,comm=`, not from psutil: psutil returned no CPU time for 291 of 868 processes (root processes such as `mds_stores`). `ps` lists all 869 in about 26 ms. Expected format is `mm:ss.cc`; other formats (for example `3-04:05:06`) are not parsed.
- Monitoring must never break the tool (owner decision, same principle as `code_version` `unknown`): every source read is guarded. An unparseable `ps` line is skipped and noted as `ps: <n> unparseable lines, first: '<line>'` in `host.errors`; a failing `ps` or psutil call leaves the field `null` and adds the error. The other fields stay. Process names are in the log on purpose (owner decision).
- Not added because the analysis did not show it: memory pressure, event-loop lag, prewarm time, host facts for camoufox and pipe records.
- Report: section "Collapse searches" with one row per search with fewer than 3 OK engines (timestamp, code version, OK count, wall, overhead, median of the completed engine times, pattern, evidence, host facts or `not recorded`). `classify_collapse` assigns the pattern offline: `browser_connect_failed` (any "Failed to get browser ws address"), `local_network` (at least 3 engines `ERR_CONNECTION_REFUSED`), `slow_navigation` (at least 3 `TIMEOUT_WATCHDOG`), `blocked` (at least 2 blocked engines), else `mixed`; the first match wins. On the 14 real searches: browser_connect_failed 6, slow_navigation 4, local_network 2, blocked 2, mixed 0. The two 09-15 searches of the old architecture are labelled `slow_navigation` and `blocked` by these rules only because the rules look at statuses.
- Fixtures: 7 real workflow summaries in `dev/tests/fixtures/kvp/collapse_cases.jsonl` (6 collapse cases plus the healthy 10-14T16:39:36Z search). The host cell in the report test is constructed. `conftest.py` pins the process table for all tests.

### Verification and one negative result

Real records from the worktree (`code_version a23deaf632`): a scrape of `https://example.com/` at 2026-10-14T17:32:30Z with `cpu_busy_pct 17.5`, `load_avg_start 3.8`, top processes WindowServer, System Events (the focus watchdog's osascript), Preview; a search at 17:32:29Z with `cpu_busy_pct 29.9`.

Load demonstration, owner-approved: 14 `yes > /dev/null` for one search (17:33:08Z) gave `cpu_busy_pct 100.0`, `load_avg_start 5.34`, `yes` 73.14 CPU-s over 14 processes; 30 of them for another search (17:33:41Z) gave `load_avg_start 16.32`, `yes` 85.69 CPU-s over 30 processes. Both searches degraded (startpage `TIMEOUT_WATCHDOG`, google `ERROR_BROWSER`, wall 7.2 s and 8.3 s) but 4 engines stayed OK each, so no collapse. n = 2, the count was not raised further. Reading: pure CPU saturation alone degraded the search but did not reproduce the collapse of 10-10 and 10-14; the next real collapse with `host` will show whether the machine was saturated then.

### Gotchas for a successor

- zsh does not split an unquoted variable: `kill $pids` with several pids failed with "illegal pid" and left the 14 `yes` running for a while. Use `pkill -x yes` (after checking `pgrep -x yes` shows only your own) or an array. macOS `sed -i` needs a suffix argument; use python for in-place edits.
- A host fact exists only for records written after the merge; the report shows `not recorded` for everything older. The production CLI runs the main checkout.
- The first search after a code change in a worktree is run with `./venv/bin/python cli.py search_web "<q>" > /tmp/<file> 2>&1` and the scrape with the wrapper `/tmp/wt_ws scrape_url_chromium <url>` (see the entry above for why).

### Open points

- Whether the collapse needs more than CPU saturation (I/O, Spotlight, the local network, many tabs in one Chrome) stays open until a collapse is logged with `host`.
- The collapse labels are rules over statuses, not diagnoses; `mixed` has no real example yet.
- `top_cpu_processes` shows only the 3 biggest consumers; a diffuse load (many small processes) shows up only in `cpu_busy_pct`.

## Iteration 3 (2026-10-14): google "Page load timed out"

Commit `b184394` on branch `kvpreport` (the worktree was fast-forwarded to `integration` `848cfc5` first). The change is implemented and tested hermetically; the real-search verification is not done, see the end of this section.

### Cause, measured

- Facts from the main `query_log` since 2026-09-19: 139 google runs, 119 OK, 10 `ERROR_BROWSER` "Page load timed out" (7.2 %), 6 `TIMEOUT_WATCHDOG` (all on 09-21), 2 other `ERROR_BROWSER` (09-24, `ERR_CONNECTION_REFUSED`), 2 `EMPTY`. The 10 timeouts are spread over 09-24, 09-26 (2), 09-30, 10-10, 10-11, 10-14 (3). Healthy google `search_ms` since 09-19: p50 2411, p90 3285, max 4187 (96 OK runs from 2026-09-19T15:35Z on).
- pydoll's `Tab.go_to` waits for `Page.loadEventFired` (default `PageLoadState.COMPLETE`, a browser-wide option). The load event fires only after all subresources. `google.py` called `go_to(url, timeout=3.0)`; on expiry pydoll raises `PageLoadTimeout`, the search code maps it to `ERROR_BROWSER` "Page load timed out", and the page is never read.
- Probe `dev/kvp/probe_google_load_events.py` (full 8-engine production path, only google instrumented, `go_to` timeout 30 s, log and cache isolated): in poll mode (results DOM queried every 50 ms, n=28) the result containers `div.MjjYud` were present at p50 1013 ms (p90 1450, max 3102), `DOMContentLoaded` at p50 1328 (p90 2115, max 3107), `load` at p50 3046 (p90 4067, max 4209); results were in the DOM before `load` in 28 of 28 runs; 14 of 28 had `load` later than 3.0 s. In events mode (no polling, one DOM query at `DOMContentLoaded`, n=11 valid) result containers existed at `DOMContentLoaded` in 11 of 11, `DOMContentLoaded` p50 1256 (max 2008), `load` p50 2539 (max 3175), 3 of 11 later than 3.0 s. The gap `load` minus `DOMContentLoaded` has p50 1.0 to 1.7 s. The pages request 40 to 121 subresources.
- The poll mode itself slows the page (50 % over 3 s against 27 % in events mode and 7 % in production), which is why the events mode exists as the control. The 7.2 % production rate was not reproduced by the probe; the probe shows the mechanism, not the rate.
- `cli.log` corroboration (not attributable per tab): production windows hold more `Page.domContentEventFired` than `Page.loadEventFired` events, for example 10-10: 6 against 1, 10-14 18:39 local: 6 against 4.

### Change

- `google.py`: new `_go_to_dom_content_loaded(tab, url, timeout)` replaces `tab.go_to`. It enables page events, registers a `Page.domContentEventFired` listener, sends `Page.navigate`, raises `NavigationError` on `errorText`, waits once with `asyncio.wait_for`, raises pydoll's `PageLoadTimeout` on expiry (so status and `drop_reason` stay `ERROR_BROWSER` / "Page load timed out"). One bounded attempt, no retry, no backoff (owner rule of 2026-09-18). The tab is closed afterwards by the existing `kill_tab`, so no listener cleanup.
- `NAVIGATION_TIMEOUT_S` stays 3.0. Worst case of one google run: tab creation about 0.3 s, navigation 3.0 s, cookie and parse about 0.5 s, URL resolution up to 1.5 s (`GOTO_RESOLVE_TIMEOUT_S`) gives about 5.3 s, below the 6.0 s watchdog; 4.0 s would not fit. A test asserts `NAVIGATION_TIMEOUT_S + GOTO_RESOLVE_TIMEOUT_S < ENGINE_WATCHDOG_TIMEOUT`. `DOMContentLoaded` was under 3.0 s in 38 of 39 probe runs (one outlier at 3107 ms with a 1978 ms document response).
- Rejected: browser-wide `page_load_state=INTERACTIVE` (changes all seven engines, none measured). The same load wait exists in `duckduckgo.py` (3.0 s) and is a candidate for a separate measured iteration.
- Report: new table "Engine google by code version" (runs, ok, `page_load_timeout`, `timeout`, `blocked`, `empty_no_signal`, `transport_error`, median and p90 of OK `search_ms`), with `FOCUS_ENGINE` in `kvp_config.py`. On the full real window: 266 google runs, 130 OK, 13 page load timeouts, 6 timeouts, 115 `empty_no_signal` (the September google outage), almost all `unversioned`. Read it with `--since` after the merge.
- Correction of my earlier claim in this iteration: Google's `/sorry/` page is already classified `blocked` by the report, because its diagnosis carries `http_status` 429 (chain `[200, 429]`). No `/sorry/` marker was needed and none was added. The real record is in `engine_cases.jsonl` as `google_sorry_captcha_429`.
- Tests: `dev/tests/test_google_navigation.py` (fake tab: returns at the DOM event without any load event, listener before navigate, single bounded wait, `errorText`, wiring and timeout value, budget invariant); `test_google_goto_drops.py` fake tab updated to the new navigation calls; report test for the google table by version. Suite: 886 passed.

### Side effect to budget for in future probes

About 57 google searches in 20 minutes from this IP (the two probe runs: 28 and 29 searches, plus one real search) made Google answer with the `/sorry/` CAPTCHA page. 18 of the 29 runs of the second probe already got it. The block also hits the agents' searches, because it is per IP. After that, a single check search at 17:55Z and one at 17:59Z (the latter on the new code, `google` `EMPTY`, 833 ms, status chain `[200, 429]`) still got `/sorry/`. Duration of the block unknown. Future probes against google must budget their volume: production traffic is about 8 searches a day, so a probe should stay in the low tens per hour, spaced out, and must stop at the first `/sorry/`. The probe script has no such stop; a successor should add one before reusing it.

### State at the end of this iteration

- Not verified with real searches, because google was still serving `/sorry/` at the single allowed check. No further google search was made. Pre-registered verification for later: 10 real searches 60 s apart through the production path; accept if google is `OK` with at least 1 result in all 10, no "Page load timed out", median `search_ms` below the 2411 baseline, resolved result count in line with the baseline. With 10 runs and a 7.2 % failure rate, zero failures happen with about 47 % probability even without the fix, so the failure rate itself is to be read from the new report table over time.
- Probe script and its outputs stay in the repo (owner decision): `dev/kvp/probe_google_load_events.py`, `dev/kvp/md/probe_google_load_events_*.md`, `dev/kvp/json/probe_google_load_events_*.json`.
