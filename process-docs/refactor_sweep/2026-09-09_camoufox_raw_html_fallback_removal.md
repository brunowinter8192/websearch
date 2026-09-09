# Removal of the raw-HTML-as-content fallback in camoufox_scrape.py (2026-09-09)

Fourth Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal, the proxy_riding abort stub removal, and the engine search() wrapper removal for
the three before it). `_convert_camoufox_html` returned the captured HTML as `content` with
`content_is_raw_html=True` whenever crawl4ai's `raw:` markdown conversion failed — a second way to
produce content for the same page. The user classified this as a fallback with no supporting
observation: the only real historical trigger was the `raw://` (double-slash) urlsplit bug, fixed
2026-08-07 by the switch to `raw:`; the production log carried 112 camoufox records since that fix
with zero `content_is_raw_html=True` occurrences. Ordered removal.

## What changed

On a conversion failure, `content` is now `""`; `markdown_conversion_error` (already existing)
remains the fact. `content_is_raw_html` was removed entirely — the meta key, the
`_format_camoufox_output` "Content format: RAW HTML" line, and the JSONL log field in
`src/crawler/pipe_scraper_records.py::_log_pipe_camoufox_record` (the only real external consumer
found; `pipe_scraper_acquisition.py::_scrape_one_camoufox` itself was checked and confirmed to
never read the key directly, only forward the whole `meta` dict onward). The camoufox sidecar
`mode` is now always `"markdown"` (chromium's own lane is unaffected, still passing `"filtered"` —
the two lanes were never required to share one mode value, they just each collapsed to their own
single constant).

## Reachability finding

`_convert_camoufox_html`'s own outer `try/except` around its call to `_html_to_markdown` was
confirmed unreachable by reading `_html_to_markdown` in full: it already wraps its own
`AsyncWebCrawler` construction/`arun()` call in `try/except Exception as e: return "", str(e)`, and
its post-try code only touches a well-formed crawl4ai `CrawlResult.markdown` attribute that cannot
raise under any documented library behavior. No code path in the current implementation could ever
reach that outer handler — it was dead defensive code with zero observed trigger, consistent with
the 112-records/0-occurrences evidence. Removed. With both the raw-HTML branch and the dead
`except` gone, `_convert_camoufox_html` reduced to a two-statement body (delegate to
`_html_to_markdown`, log a warning on failure) and was inlined directly into `_acquire_camoufox`,
which stays at 24 body lines, well under the project's 50-LOC split threshold. `content` and the
former `raw_markdown` variable collapsed into one value in the process, since after the removal
they were always identical (success: the real markdown; failure: `""` either way).

## Tests

In `dev/tests/test_camoufox_scrape.py`, four tests tied to the removed mechanism were deleted:
`test_try_scrape_camoufox_preserves_html_when_markdown_conversion_raises`,
`test_try_scrape_camoufox_preserves_html_when_crawl4ai_swallows_conversion_error` (both fed the old
"Invalid IPv6 URL" failure text and asserted the HTML-preservation behavior),
`test_scrape_url_camoufox_workflow_mode_reflects_raw_html_fallback` (asserted `mode="raw_html"`),
and `test_format_camoufox_output_raw_html_shape_states_it_plainly` (exercised the now-removed
`_format_camoufox_output` block). One new test,
`test_try_scrape_camoufox_conversion_failure_yields_empty_content`, replaces all four: with
`_html_to_markdown` monkeypatched to return `("", "simulated conversion failure")`, it asserts
`content == ""`, `markdown_conversion_error` carries the fact, `acquisition_error is None`, and
`content_is_raw_html` is absent from `meta` entirely. The `_meta()`/`_camoufox_meta()` fixture
helpers in both `test_camoufox_scrape.py` and `dev/tests/test_pipe_scraper.py` dropped the key
from their default dicts; two `test_pipe_scraper.py` tests
(`test_scrape_all_camoufox_record_shape_engine_specific_fields`,
`test_scrape_all_chromium_record_shape_camoufox_fields_absent`) had their overrides/assertions/
docstrings adjusted to drop the now-nonexistent key rather than testing its absence as if it were
still a real (if camoufox-only) field. Net delta: 367 (baseline) − 4 + 1 = 364, confirmed by
`./venv/bin/python -m pytest -q`.

## Docs

`src/scraper/DOCS.md` gained a new Gotcha bullet placed directly after the existing `raw://` bug
bullet, documenting the full removal (what existed, the evidence, what replaced it) plus the
reachability finding and the inlining decision; `camoufox_scrape.py`'s LOC was updated (270→247).
`src/crawler/DOCS.md` reworded `pipe_scraper_acquisition.py`'s Writes line (dropped "OR raw HTML,
see `content_is_raw_html`") and updated `pipe_scraper_records.py`'s LOC (38→37). `dev/tests/
DOCS.md` updated both touched test files' entries and LOC.

**Noted, not fixed (out of scope for this task):** while editing `src/scraper/DOCS.md`, the
pre-existing Gotcha bullet on the `raw://` bug (directly above the new one) was found to still name
`src/crawler/pipe_scraper.py`'s `_own_fallback_rescue` as a sibling fix site — that function was
itself removed in the earlier pipe_scraper curl_cffi fallback removal (see this folder's own entry
on that task). This drift predates the current task and wasn't part of its deliverables, so it was
left untouched and flagged to Main rather than corrected silently.
