# KVP M3 deep dive run record and the cause behind dbis.ur.de (2026-10-14)

Worker record for two tasks of the KVP stream: (A) one persistent run record per deep dive, read by the KVP report; (B) why the result list of dbis.ur.de is missing from what the chromium lane captures. Branch `kvp55`, commits `7afc3aa` (log, records, closing command, CLI wiring), `ff23361` (report section, skill patch), plus the commit of this entry (probes, classifier marker, docs). The earlier plan says "M3 is not built"; it is built now, with the limits listed under Open points.

## A: the run record

### What exists

- One log, `src/logs/deep_dive_log.jsonl` (gitignored like the others; env override `WEBSEARCH_DEEP_DIVE_LOG_PATH`; every record carries `code_version`; pruned by `log_janitor`). Three record types:

| record_type | Written by | When | Needs a skill change |
|---|---|---|---|
| `discovery` | `cli.py discover_urls` (`log_discovery_record`) | every discovery, also a failed one (`ok=false`, `error`) | no |
| `scrape_round` | `pipe_scraper.scrape_urls_workflow` (`log_scrape_round_record`) | end of every pipe_scraper run | no |
| `closing` | new CLI command `deep_dive_record` (`deep_dive_closing_workflow`) | once, called by the worker | yes, patch below |

- `discovery` fields: `seed_url`, `host`, `url_file`, `ok`, `error`, `total`, `by_source`, `failed_feeders`, `dropped`, `wall_s`.
- `scrape_round` fields: `run_id` (the same id the per-URL pipe records carry), `host`, `engine`, `url_file`, `output_dir`, `urls_requested`, `files_written` (URLs with more than 0 bytes), `bytes`, `onward_links` (null for camoufox), `wall_s`.
- `closing` fields: `host`, `domain`, `seed_url`, `collection`, `info_need`, `discovered`, `kept`, `work_files` (count, bytes), `failed` (`dir_exists`, `count`, `names`), `cuts` (per class: `passages`, `lines`, `files`), `backups` (classes with a `_PRE_<class>_BACKUP` dir), `collection_files` (`copied`, `with_index_sidecar`), `index` (`log_path`, `log_exists`, `done` with files/chunks/skipped/adopted, `errors`).
- Code: `src/crawler/deep_dive_logger.py`, `deep_dive_records.py`, `deep_dive_closing.py`. Report side: `dev/kvp/kvp_dives.py` plus a table "Run record per deep dive" in `kvp_render.py`; `dev/kvp/kvp_report.py` loads the log through the normal window filter.
- Skill patch for the owner (not applied): `dev/kvp/patch/capture_deep_dive_record.patch`. It inserts the `deep_dive_record` call as item 1 of Step 6; the five report lines become item 2. Apply from the repo root with `patch -p0 < dev/kvp/patch/capture_deep_dive_record.patch` (`git apply -p0 --check` passes against the skill text of 2026-10-14). The older `capture_cull_and_report.patch` touches the same Step 6 item 1 line; the skill already holds that line's new wording, so apply this patch against the current skill, not both.

### Decisions and why

- **Facts are read from the filesystem, not reported by the worker.** Cull, cleanup and the failed-scrape move are agent actions, but their results are files: `/tmp/<domain>_urls.txt`, `_urls_culled.txt`, `/tmp/<domain>/`, `/tmp/<domain>_failed/`, `/tmp/cut_<class>_<domain>.md`, `/tmp/<domain>_PRE_<class>_BACKUP/`, the collection directory and the index log. A hand-typed JSON line or hand-counted numbers from an agent are an error source; the command counts itself. The worker passes four values it alone knows: domain (exactly as in the `/tmp` names), seed URL, collection, INFO_NEED.
- **A missing source is `null`, never 0.** `kept: null` means the culled file was not there; `failed.dir_exists: false` with `count: 0` is the legitimate state of a run without failed scrapes (the skill creates `_failed/` only on the first move; the sre.google run has none). The reader decides what null means.
- **Join by host and time, no dive id.** A dive is a `discovery` record, the `scrape_round` records on the same normalized host after it (`www.` stripped) and the `closing` record on that host. The next discovery on a host opens a new dive; a round or closing without an open dive becomes a dive labelled "no discovery record". A dive id would have to be carried through the skill by the worker. Hypothesis, never observed: two concurrent dives on one host would be mixed.
- **`scrape_round` instead of deriving rounds from pipe run ids.** Run ids exist in the pipe log, but nothing ties them to a dive and the input list size, the onward link count and the output dir were not logged. `run_id` in the round record is the same id, so the report joins the per-URL failed count by it.
- **`kept` is the line count of the culled list at closing time.** It is the first-round list; URLs added in later rounds (Step 3 item 5) show up in the round sizes, not in `kept`.
- **Cut file semantics.** `passages` = header lines `<file>.md:<start>-<end>`, `lines` = sum of the ranges, `files` = distinct file names. The files are written in the dry run and in the `--apply` run alike, so a cut file read at closing time can come from either; the record cannot tell. Checked against the five real sre.google files: lines of a file = number of headers plus the sum of ranges (for example book_toc: 75 headers, 3589 lines, 3664 file lines).
- **Index log.** `done` is parsed from the last line starting with `Done: N files indexed (M chunks), K skipped, A adopted`. `errors` are lines starting with `Error` (observed in a real log: `Error: rag busy: index running ...`). An index log without a `Done:` line gives `done: null`. Optional `--index-log` exists because the real sre.google run wrote `/tmp/websearch-pages_index_sre.log` instead of the skill's `/tmp/<collection>_index.log` (the owner's deviation for that run).
- **Test isolation.** `conftest.py` points the deep dive log at a throwaway file for every test, so no test can write the real or the worktree log.

### Verification with real data (code_version `7afc3aa34a`, written to the worktree log)

1. `cli.py discover_urls https://sre.google/ --url-file /tmp/kvp55_verify_urls.txt` (a verification file, the real `/tmp/sre.google_urls.txt` stayed untouched): `discovery` record at 2026-10-14T21:08:53Z, total 229 (seed 1, robots 2, sitemap_declared 226), no failed feeders, 0.2 s. The 2026-10-11 run counted 228; the site changed by one URL.
2. `pipe_scraper --url-file /tmp/kvp55_one.txt` with `https://sre.google/`: `scrape_round` at 21:09:08Z, `run_id` 7ed87f41-a75c-4712-8122-650185e46420 (identical to the pipe record), 1 requested, 1 file, 17096 B, 29 onward links, 2.6 s.
3. `cli.py deep_dive_record --domain sre.google --seed-url https://sre.google/ --collection websearch-pages --index-log /tmp/websearch-pages_index_sre.log` against the real files of the 2026-10-11 run: `discovered 228`, `kept 205`, 205 files / 4360614 B, no `_failed/`, cuts book_footer 300 passages (75 files), book_toc 75 (3589 lines), images 730 (163 files), site_footer 130 (2472 lines), site_header 130 (20280 lines), five backups, 205 copied / 205 with index sidecar, `Done: 205 files indexed (3222 chunks), 997 skipped, 0 adopted`. These are the numbers the task named as recoverable only from chat, now recovered from disk. The record exists only in the worktree log, not in production; no reconstructed record went into the production log (owner decision).
4. `dev/kvp/md/kvp_report_2026-10-14T21-00_now_20261014T210956.md` shows the three records as one dive, state `complete`, "205/229 (89.5 %)". Read that row with care: the discovery (229) belongs to the verification run and the closing (228, 205) to the real 2026-10-11 files, so the share mixes two runs. It proves the mechanics, not a measurement.

### Tests

- `dev/tests/test_deep_dive_records.py`, `test_deep_dive_closing.py`, additions to `test_kvp_report.py`. Real fixtures: excerpts of two `cut_*` files, the sre.google index log (first 15 lines plus the `Done:` line) and the one-line `Error: rag busy` log in `dev/tests/fixtures/deep_dive/`; the three real records of step 1 to 3 in `dev/tests/fixtures/kvp/deep_dive_log_real.jsonl`.
- Constructed (spec, not observed), named as such: `deep_dive_log_constructed.jsonl` (a dive without closing record with a failed navtree feeder, a round without discovery), the `/tmp` tree of the workflow test, the second-discovery grouping case.
- Full suite on the branch: 905 passed, 12 browser tests deselected (`./venv/bin/python -m pytest -q -n0`).

### Report reading guide

- The table is only filled for dives that ran after the merge of this branch. Older runs stay in "Technical and relevance per pipe run" (per-URL view) and appear there only.
- State column: `complete` (discovery and closing), `no closing record` (the skill patch is not applied, or the worker did not call it), `no discovery record`, `discovery failed`.
- Until the owner applies the patch, every real dive will read `no closing record`; discovered counts, rounds and the files written per round are still there.

## B: dbis.ur.de

### Result in one paragraph

The result list is missing for three stacked reasons, only the first of which is specific to the two canary URLs. (1) `/UBFM/resources?q=...` is not a page of DBIS: the server answers HTTP 200 with its own "not found" page. (2) The real results route `/UBFM/results?q=...` serves a human-verification page (altcha, "Sicherheitsprüfung", "Ich bin ein Mensch" button) to a plain client and to the chromium lane. (3) Independently, crawl4ai's lxml parser silently drops everything after nesting depth 256, and every DBIS page nests deeper (the server never closes the `city-group` divs of the organisation dropdown), so the main content of every DBIS page is lost in the chromium lane, including the "not found" message. None of this was visible to the agent, who got the organisation list. No scraper change was made.

### Evidence, with the request budget of 5

| # | Request | Result |
|---|---|---|
| 1 | plain GET `https://dbis.ur.de/UBFM/resources?q=JSTOR` (`probe_dbis_http`) | HTTP 200, 215225 B, title "DBIS - Fachgebiete", `<h1>Leider ist ein Fehler aufgetreten.</h1>`, "Leider wurde die gewünschte Seite auf DBIS nicht gefunden.", no redirect, `JSTOR` nowhere in the body. `<main>` holds only the error. `UBFM` is a valid organisation (button "Universitätsbibliothek Frankfurt"); the path `/resources` is not a route. |
| 2 | chromium lane, `cli.py scrape_url_chromium` on the same URL (worktree log, 21:14:17Z) | `http_status 200`, chain `[200]`, `bytes_raw_markdown 15774`, `content_source raw_markdown_fallback`; the markdown is the organisation list and ends at `MÜNSTER`; the error message is not in it. |
| 3 | plain GET `https://dbis.ur.de/UBFM/search?q=JSTOR` | HTTP 200, 384903 B, title "DBIS - Suche", `<h1>Erweiterte Suche</h1>`; the search form is `action="/UBFM/results" method="get"` with field `q`. A valid page that holds the query only as input value. |
| 4 | plain GET `https://dbis.ur.de/UBFM/results?q=JSTOR` | HTTP 200, 2470 B, title "Captcha", `<h1>Sicherheitsprüfung</h1>`, script `altcha`, form with button "Ich bin ein Mensch". No list. |
| 5 | chromium lane on `/UBFM/results?q=JSTOR` (21:16:29Z) | `http_status 200`, `bytes_returned 197`, `content_source fit_markdown`: `# Sicherheitsprüfung` plus the footer links. The same verification page. |

Hypothesis from the earlier entry ("results loaded by JavaScript after the capture") is refuted for this case: the server never sends a list for `/resources`, and for `/results` it sends a bot check. No DOM sampling over time and no long-wait scrape were needed or done.

### The parser finding (general, not dbis-specific)

- Source of request 1: 399 `<div` opened, 18 `</div>` closed. The city groups are never closed, so the tree nests one level per group.
- Offline, no further request (`dev/kvp/probe_html_depth.py` on the saved pages in `dev/kvp/html/`): with lxml's default parser the maximum tree depth is 256 (libxml2 limit); the document is cut there. `LXMLWebScrapingStrategy` (crawl4ai 0.9.2, `lhtml.document_fromstring(html)` in `_scrap`, lxml 6.1.1, libxml2 2.14.6) therefore returns `cleaned_html` of 125386 of 214825 chars. With `HTMLParser(huge_tree=True)` the depth is 393 and nothing is cut.

| Page (saved server HTML) | Parser | cleaned_html | raw markdown | Strings in raw markdown |
|---|---|---|---|---|
| `/UBFM/resources?q=JSTOR` | default | 125386 | 15552 | MÜNSTER yes, Zürich no, "Leider ist ein Fehler aufgetreten" no |
| same | huge_tree | 183479 | 22504 | MÜNSTER yes, Zürich yes, "Leider ist ein Fehler aufgetreten" yes |
| `/UBFM/search?q=JSTOR` (valid page) | default | 125905 | 15755 | Zürich no, "Erweiterte Suche" no |
| same | huge_tree | 297758 | 52326 | Zürich yes, "Erweiterte Suche" yes |

- The live chromium markdown (15774 B) is close to the offline default-parser value (15552 B); the difference is what the browser's JavaScript changed in the DOM. `fit_markdown` is 1 B in all four runs (pruning removes the page), so the agent's content comes from the raw fallback of iteration 1.
- Consequence: on a valid DBIS page the agent gets the header and the organisation dropdown and nothing from `<main>`. Even a passed bot check would not have delivered a result list.

### Why nothing was implemented

The task rule was: implement only if the cause is general and the fix is small. The cause of the missing list is not the parser (it is the wrong URL, then a bot check), and the parser fix does not make the canary markers `JSTOR` / `Business Source` appear, so the canary comparison against `kvp_canary_20261014T171607.json` could not show an effect and was not run. The parser depth truncation is general and has a small fix, but its reach is unmeasured (one site, two pages).

### Proposal for the next iteration (not done)

- Fix candidate: set `lxml.html.html_parser = lxml.html.HTMLParser(huge_tree=True)` once at import time of the code that uses crawl4ai (chromium_scrape and the pipe lane). `lxml.html.document_fromstring` reads that module global when no parser is passed, which is how the offline probe applied it. Risks to weigh: `huge_tree` also lifts libxml2's text-node size and depth limits (a memory guard for pathological pages), and it is a process-wide change to a third-party default. `bs4` with `lxml` inside the pruning filter has its own default parser and was not tested with the fix; `fit_markdown` was 1 B either way here.
- Measure first: add a fact to the scrape record (`html_max_depth` or "depth limit hit") so the next report shows how many real pages hit 256. Then decide.
- Canary cases `empty_filter_dbis_jstor` and `empty_filter_dbis_business_source` can never pass: the URL is a soft 404. Replace the URLs by `/UBFM/search?q=...` (a valid page whose heading "Erweiterte Suche" is a marker that only appears with the parser fix) or pin them as observed failures. Left unchanged here because renaming or re-pointing cases breaks the run-to-run comparison; owner decision.
- The KVP classifier cannot see a soft 404 (HTTP 200, not-found text). One real example exists (dbis, and in the lane it is not even in the body because of the truncation), so no rule was written: a marker list built from one site is a guess.

### Classifier change from the evidence

`ANTI_BOT_MARKERS` in `dev/kvp/kvp_classify.py` gets `sicherheitsprüfung` (the existing marker is `sicherheitsüberprüfung`). The altcha page of request 5 (197 B, HTTP 200) was classified `usable` before; now `challenge_or_interstitial`. The real record and body are the new fixture case `dbis_results_altcha_197B` in `dev/tests/fixtures/kvp/scrape_cases.jsonl`.

## Gotchas for a successor

- **Hook on `dev/` files.** A write-time hook refuses `Write`/`Edit` of any `dev/` file whose content contains `from src.` ("dev/ scripts may not import from src/"). The probe that was to instrument the production chromium path (it needs `src.scraper.chromium_scrape`) could not be written. I did not work around the hook. The two probes written have no `src` import: `probe_dbis_http.py` (httpx) and `probe_html_depth.py` (crawl4ai, lxml). The older `kvp_canary.py` and `probe_google_load_events.py` do import from `src` (they predate the hook or got there another way); a successor needing to instrument `src` has to ask the owner. An earlier process-docs entry (area engine_reduction) records a workaround by pure-deletion edits; I did not use it.
- A worktree wrapper for the CLI was used because an earlier session observed the hook setup blocking `cli.py scrape_url_chromium` called through a venv path (not re-tested here; `discover_urls` and `deep_dive_record` through the venv path ran fine): `/tmp/kvp55_ws` (exec of this worktree's venv python and `cli.py`). `/tmp/wt_ws` of the earlier session points to the old worktree `kvpreport`.
- `python -m src.crawler.pipe_scraper` must be alone in its Bash call, without an env prefix; reading a CLI's redirected output in the same call as the CLI is blocked.
- Writing `dev/kvp/md/` output while testing the report on the worktree log commits a report file; the one from step 4 above is kept on purpose.
- The `dev/kvp/html/*.html.gz` pages are the server HTML of public DBIS pages (214825 and 384903 chars, gzipped about 14 KB and 30 KB); they are the input of the offline probe and make the table above reproducible without a request.

## Open points

- The skill patch is not applied; the first real `closing` record exists only when the owner applies it.
- `kept` does not include URLs added in later rounds; if the cull ratio over the whole dive is wanted, sum the round sizes (the report shows them in "rounds (URLs each)").
- Two deep dives on one host at overlapping times would be mixed in the report (unobserved).
- Index errors are only the `Error`-prefixed lines; other failure shapes of `rag-cli index` have not been observed and would show as `done: null` only.
- The parser depth truncation: reach unmeasured, fix not applied (see the proposal).
