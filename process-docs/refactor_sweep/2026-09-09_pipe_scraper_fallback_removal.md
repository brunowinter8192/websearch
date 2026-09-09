# Removal of both curl_cffi fallback paths from pipe_scraper (2026-09-09)

Phase 4 of the refactor sweep: a control-flow integrity scan over `src/` (textual grep for
fallback/legacy/dedup/gated names, an AST pass over every `except` handler returning non-`None`
without re-raising, and a manual cross-module read for duplicated/diverging logic) surfaced two
`except` handlers in `src/crawler/pipe_scraper_acquisition.py` and `pipe_scraper_config.py` that
produced output by re-fetching the same URL a second way via `curl_cffi` when the primary browser
fetch failed. The user classified both as fallbacks — "a branch that produces alternative output
by a second method is a fallback, and a fallback is eliminated" — and ordered their removal.

## What existed and what replaced it

Path (a) was crawl4ai's own `fallback_fetch_function` config hook, wired in `_build_configs`
to `_fallback_fetch` (a `curl_cffi` GET). Path (b) was `_own_fallback_rescue`, called from
`_scrape_one`'s `except Exception` block: it re-fetched the URL via `curl_cffi` directly, then fed
the resulting HTML back through crawl4ai's own `raw:<html>` conversion to get markdown out of it.
Both were removed along with their shared low-level primitive `_curl_cffi_get`, the
`FALLBACK_FETCH_TIMEOUT_S` constant, the `fallback_armed` config-stamp key, and the
`pipe_fallback_used`/`pipe_fallback_resolved` JSONL log fields. `_landed_url_from_result`'s
`crawl4ai_fallback_fetch_used` short-circuit (which returned `None` specifically on path a, since
crawl4ai hardcoded `redirected_url=url` on that route) was removed with path (a); the function
was then a one-liner (`getattr(result, "redirected_url", None)`) and was inlined at its one call
site rather than kept as a wrapper.

`_scrape_one`'s `except Exception` block is now the tripwire the rule set requires: it logs
`status=None, bytes=0` (no field invented — `diagnosis={}` and `landed_url` stay at whatever they
already defaulted to) and returns the same dict shape as the success path minus `'links'`; the
run's `asyncio.gather` moves on to the next URL. `crawl4ai_fallback_fetch_used` itself stays in
the log — it is read off crawl4ai's own `crawl_stats`, an observation of the library's internal
behavior, not of pipe_scraper's own removed mechanism, so it does not fall under "output by a
second method."

## Caller check

A repo-wide grep for `_curl_cffi_get`, `_fallback_fetch`, `_own_fallback_rescue`,
`FALLBACK_FETCH_TIMEOUT_S`, `fallback_armed`, `pipe_fallback_used`, `pipe_fallback_resolved`, and
`_landed_url_from_result` across `src/`, `cli.py`, and `dev/` found hits only in the four
`pipe_scraper*.py` files being edited and in `dev/tests/test_pipe_scraper.py` — no other caller
anywhere in the project. `curl_cffi` remains a project dependency regardless, since
`src/news/engine/proxy_pool/fetch.py` uses it independently for the proxy-pool engine's own
primary (not fallback) HTTP fetch.

## Tests

14 tests whose sole subject was the removed mechanism were deleted from
`dev/tests/test_pipe_scraper.py`: `test_extract_pipe_config_stamp_reads_fallback_armed_off_real_object`,
`test_build_configs_wires_fallback_fetch_function`, `test_is_blocked_flags_crossref_shaped_failures`
(its only purpose was framing which crawl4ai `is_blocked` branch would decide whether path a/b
fired — moot with neither path left), four `test_fallback_fetch_*` tests plus their
`_FakeCurlResponse`/`_FakeCurlSession` fixtures, three `test_own_fallback_rescue_*` tests plus
their `_FakeHardFailureCrawler`/`_FakeUrlsplitRescueCrawler` fixtures,
`test_crawl4ai_own_fallback_surfaces_in_log_distinctly_from_pipe_fallback` plus its
`_FakeCrawl4aiOwnFallbackCrawler` fixture, and `test_landed_url_null_on_crawl4ai_own_fallback`
(its premise was the now-removed short-circuit; the fake result's own `redirected_url` default
already made the assertion vacuous once the short-circuit was gone). Two surviving tests were
adapted rather than deleted: `test_scrape_all_records_carry_config_hash_and_config` dropped its
`fallback_armed` assertion, and `test_scrape_all_camoufox_record_shape_engine_specific_fields`
dropped `pipe_fallback_used`/`pipe_fallback_resolved` from its list of chromium-only keys expected
absent from a camoufox record.

One new test, `test_scrape_one_exception_becomes_tripwire_record`, proves the replacement
behavior by reusing the existing `_FakeCrawler` fixture (already raises on any URL containing
`"fail"` — no new fixture needed): the failing URL's result carries `status_code=None`/`bytes=0`,
no `.md` file is written for it, the sibling non-failing URL in the same run still succeeds
(`status_code=200`, proving the run continues past the failure), and the failing URL's JSONL log
record carries neither `pipe_fallback_used` nor `pipe_fallback_resolved` at all.

Net test count: 378 (baseline) − 14 (deleted) + 1 (added) = 365, confirmed by
`./venv/bin/python -m pytest -q`.

## Docs

`src/crawler/DOCS.md`'s Purpose/Writes/Calls-out lines for `pipe_scraper_acquisition.py`,
`pipe_scraper_config.py`, `pipe_scraper_constants.py`, and `pipe_scraper_records.py` were updated
to drop every reference to the removed mechanism. Five Gotcha bullets that were substantively
about paths (a)/(b) (`max_retries`'s fallback-protection rationale, the `http_status=200`-always
bullet, the `landed_url`-null-on-path-a bullet, an open question about path (b)'s reachability,
and the "raw: conversion links not extracted" bullet) were rewritten into short "REMOVED
2026-09-09" notes pointing back to one new anchor Gotcha that documents the full removal — per
this project's rule against deleting history silently. Two other bullets (`same_target` removal,
`outcome`-field removal) that referenced `pipe_fallback_used`/`_own_fallback_rescue` only in
passing got a one-clause in-place fix instead of a full rewrite, since their own subject was
unrelated to the fallback mechanism itself. `dev/tests/DOCS.md`'s `test_pipe_scraper.py` entry and
LOC were updated to match.
