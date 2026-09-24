# Phase 5 fixes in src/ and cli.py: fallbacks made traceable or turned into tripwires (2026-09-24)

Follows a scan-only pass over `src/` and `cli.py` (findings P-01 .. P-33) and a review that confirmed most of them. This entry records
what was changed, why each fallback was kept or removed, and what a successor must know. Baseline before: 517 tests passed
(brave/yandex real-browser files excluded); after: 626 passed including them.

## Decision rule that was applied

For every "unobserved fallback": look in git log and process-docs for an entry that recorded the triggering condition. Recorded
condition -> keep the path and make it traceable (log / record field). No record -> remove the second path so the condition aborts.
Observation sources used: `process-docs/`, `git log -S`, and the production logs of the main checkout (`src/logs/cli.log*`,
`query_log.jsonl`: e.g. 0 lines for `Google consent`, `Could not set LSUIElement`, `dropping unparseable`, `... write failed`).

## Changes by finding

Crawler (`src/crawler`, `cli.py`):
- P-01 `_scrape_all` no longer uses `return_exceptions=True`; a raising executor aborts the run. Before, the exception object was replaced
  by a `{'status_code': None, ...}` row and vanished (camoufox executor has no inner handler).
- P-02 `_scrape_one` still records `status=None, bytes=0` on an exception, and now also `error: "<Type>: <message>"` in the JSONL record
  (key `error`; it must not be called `acquisition_error`, a test asserts that key is camoufox-only).
- P-12 sitemap `FeederResult.source` is `sitemap_declared` (robots `Sitemap:` present) or `sitemap_conventional` (`/sitemap.xml`, `/sitemap_index.xml`).
  The fixture ground truth (`dev/url_discovery/_fixture_site_content.py`) expects `sitemap_declared`.
- P-13 `ABSENT_STATUSES = (404, 410)` in `seed_feeders_constants.py`; robots, sitemap and navtree fetchers return `None` only for these, every other
  non-200 raises `RuntimeError("unexpected status ...")` so the feeder reports `ok=False` (already surfaced by `discovery` in `failed_feeders`).
  A version page that is absent in the navtree is logged (`seed_feeders_navtree` logger) and skipped.
- P-15 `scope_and_dedup` returns `(urls, dropped)`; `FeederResult.dropped`, `DiscoveryResult.dropped`, printed by `cli.py` as `dropped_malformed_urls`.

News (`src/news`):
- P-03 `fetch_url` returns `(status, content, reason)` and catches only `curl_cffi.requests.exceptions.RequestException`
  (reason = class name); `_validate` supplies `http_<code>` / `content_marker_missing`. Any other exception propagates (a bug no longer burns the proxy pool).
  `AcquireLogger.record_attempt(..., reason)` writes `reason`; loop and theblock discover unpack three values.
- P-27/P-28 `_try_source` stores `error = type(exc).__name__`; `record_pool_source(..., error)` writes it.
- P-29 `_collect_manifest` and `return_exceptions=True` deleted in `engine/scrape.py` (`_fetch_one` already catches everything).
- P-32 `_run_clean_pass` raises `FileNotFoundError` on a missing raw file.
- P-06/P-07 theblock discover: module logger; failed direct fetch logs status + xml-marker + URL; each served sitemap logs `direct` or the proxy;
  a sub-sitemap that fails direct + proxy raises `RuntimeError` like the index. The parameter `logger` (an `AcquireLogger`) of `discover`/`_fetch_xml`
  was renamed `acquire_logger`; the platform method `TheBlockPlatform.discover(logger=...)` keeps its name and maps it.
- P-08 coindesk `cleanup` returns `""` when there is no `# ` heading (counts as body-less in `clean_pass`), and logs the `NONE` end-anchor case.
- P-09 `parse_articles` reads `_id`, `pathname`, `articleDates.displayDate` with `[]` (KeyError otherwise); `storyType` and `title` stay `.get`.
  The list-or-dict container detection stays because no document records the container shape. Consequence: an article without `articleDates`
  now aborts discovery; before it was dropped silently by `_build_entry`.
- P-10 `coindesk/browser._extract_value` has no handler any more (dev copy had it removed on 2026-09-24 already).
- P-11 `load_discover_filtered` raises `FileNotFoundError` for a missing directory or year shard.

Scraper (`src/scraper`, log writers):
- P-04 `_resolve_system_locale` = `defaults read -g AppleLocale` only; empty output raises `RuntimeError`; `import locale` gone.
- P-24 `_ensure_no_focus_steal` has no try/except; the early returns for non-darwin / no executable / no `.app` stay (input shape).
- P-23 `chromium_process._get_frontmost_app` / `_activate_app` log one warning per process (`_osascript_warned` set) on non-zero exit or empty output.
- P-16 `scrape_logger.log_scrape`, `write_sidecar`, `pipe_scrape_logger.log_pipe_scrape`, `query_logger.log_query` no longer catch write failures.
  `write_sidecar` still returns `None` for empty content only. A consequence: a broken log path now aborts the surrounding workflow after the scrape.

Search (`src/search`):
- P-05 `browser_lock`: warning with holder pid / age / budget before `_break_lock`; `_read_sidecar` returns `None` only for `FileNotFoundError`, a corrupt
  sidecar raises; `_write_sidecar` writes a tmp file and `os.replace`s it so a waiter can never read a half-written sidecar (this was needed because
  corrupt now raises).
- P-23 same once-only osascript warning in `browser._get_frontmost_pid` / `_activate_pid`.
- P-20 google consent branch removed (`CONSENT_DOMAIN`, `_JS_CONSENT`, `_has_inline_consent`, `_handle_consent`). History: added in the stealth port
  (`stealth_inventory.md`: 30/30 with the SOCS cookie), no consent occurrence ever recorded. A consent page now shows up in the no-containers diagnosis (`url`).
- P-21 `_select_engines(engines) -> dict`, raises `ValueError` on an unknown name; `all_excluded` plumbing and the `engines_excluded` query-log field removed
  (it was `{}` in 210 of 210 records). The `engines` parameter of `search_web_workflow` stays because callers pass it positionally.
- P-19 selector alternatives stay; the parse JS of google (anchor 0-4, snippet 0-2), bing (caption 0-1), brave (title 0-1, snippet 0-1), yandex (snippet 0-1)
  returns `sel` per item. `_parse_results` returns `(results, hits)`; `src/search/selector_hits.py::collect_selector_hits` aggregates to
  `{"snippet": {"0": 8, "1": 2}}`; the success branch puts it in the diagnosis as `selector_hits`. `_build_results` ignores `sel`, so `SearchResult` and the CLI
  output are byte-identical. On the empty-results branches no `selector_hits` is attached.

Misc:
- P-17 `_prune_jsonl` keeps unparseable lines (still warns). P-18 `_log_intervention` has no handler; `dir_removed = not Path(cleanup_dir).exists()` after the rmtree.
- P-33 `src/spawn/tmux_spawn.sh` deleted; its shell-parameter names removed from `.drift-whitelist.txt`.

## Proof

- Selector JS: `dev/search_pipeline/selector_js_equivalence_check.py` loads the pre-change engine source via `git show b6fab1d:...` (constant `BASE_REV`),
  runs old and new `_JS_PARSE` in headless Chrome on synthetic HTML covering every alternative, compares items minus `sel`: `VERDICT PASS` for all four
  engines (report in `dev/search_pipeline/md/`). Observed indexes on the fixture: google `{'anchor': 0..4, 'snippet': 0..2}`, bing `caption 0/1`, brave `title/snippet 0/1`, yandex `snippet 0/1`.
- Every new raise or log line has a provoking test in `dev/tests` (new files: `test_coindesk_cleanup_and_shards.py`, `test_proxy_pool_fetch.py`,
  `test_selector_hits.py`, `test_search_web_select_engines.py`, `test_browser_lock_tripwires.py`, `test_browser_osascript.py`, `test_death_pipe_tripwires.py`;
  extended: sitemap/robots/navtree/scope/discovery, `test_pipe_scraper.py`, `test_scrape_logger.py`, `test_query_logger.py`, `test_log_janitor.py`,
  `test_coindesk_timeline.py`, `test_theblock_discover.py`, `test_theblock_clean_pass.py`, `test_proxy_pool_retry.py`, `test_proxy_pool_sources.py`,
  `test_chromium_process.py`, camoufox focus/output tests). Adapted for the changed contracts: fail-soft tests became "raises" tests, `fetch_url` mocks return three values,
  `_parse_results` mocks return `(results, hits)`, brave/yandex diagnosis assertions include `selector_hits`, `FakeCompletedProcess` in `test_browser.py` got `returncode`/`stderr`.
- Comment/docstring scan (tokenize + ast) over all `.py` files changed in the six commits: 0 hits.

## Notes for a successor

- The real-browser tests (`test_brave_engine.py`, `test_yandex_engine.py`) run in the default suite and need Chrome; `test_stuck_challenge_cancelled_mid_loop_leaves_partial_facts_behind`
  (timeout 0.3 s) and `test_engine_with_timing_timeout*` in `test_query_logger.py` failed intermittently under load in this session; not touched here (Phase 3 topic).
- When an engine's DOM changes, read `selector_hits` in `query_log.jsonl` (`diagnosis.selector_hits`) to see which alternative still matches before deleting any selector.
- If a coindesk article without `articleDates` is ever observed, the right fix is a logged skip for that specific shape, not a return to the `or` chains.
- Hypotheses not observed: a half-written sidecar race in `browser_lock` (prevented by the atomic write), a raised non-`RequestException` from curl_cffi in `fetch_url`.
- Rejected in the review (no change made): P-14, P-22, P-25, P-26, P-31 and the env-variable log-path seams.
