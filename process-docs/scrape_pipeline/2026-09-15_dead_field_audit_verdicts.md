# M0 — the three dead fields from the 2026-09-15 audit, verdicts and source trace

Worker session (worktree `mechanics`). Milestone: `process-docs/scrape_pipeline/
adhoc_output_audit_2026-09-15.md` (read that file first — it is not edited here, it is historical
and frozen) measured three fields in `src/logs/scrape_log.jsonl` that were empty/constant in 91 of
91 records over a 14-day window: `content_type`, `og_published_time`, `crawl4ai_fallback_fetch_used`.
This is a pure code-reading task: for each field, is it structurally reachable on the path this
project actually takes, verified against the installed crawl4ai 0.9.2 source
(`venv/lib/python3.14/site-packages/crawl4ai/`), not documentation, not expectation. No browser was
launched — every check below is either a source read or an offline `CrawlResult(...)` construction
(pure Python, no network, no browser), consistent with the standing rule.

## Field 1 — `content_type`: DEFECTIVE, fixed

`src/scraper/chromium_scrape.py::_acquire_scrape` read:
```python
if hasattr(result, "headers") and result.headers:
    ct = result.headers.get("content-type") or result.headers.get("Content-Type")
```
`crawl4ai.models.CrawlResult` (a pydantic `BaseModel`) has no `headers` field at all — the real
field is `response_headers` (`models.py:148`). Confirmed live, no browser, no network:
```python
>>> from crawl4ai.models import CrawlResult
>>> r = CrawlResult(url='https://x.test', html='<html></html>', success=True,
...                  response_headers={'content-type': 'text/html; charset=utf-8'})
>>> hasattr(r, 'headers')
False
>>> hasattr(r, 'response_headers')
True
>>> r.response_headers
{'content-type': 'text/html; charset=utf-8'}
```
`hasattr(result, "headers")` is `False` on every real `CrawlResult` object. The `if` branch has
therefore NEVER executed once, on any scrape this project has ever run — `content_type` was never
empty, it was unreachable. This is categorically different from "legitimately empty": the field
carries a real, populated value inside crawl4ai's own result object, this project's own code just
never looked at the right attribute.

**Where `response_headers` actually gets populated**, traced to confirm it is real and reaches this
project's exact acquisition path (`browser_mode="custom"`, `cdp_url=...`, `AsyncPlaywrightCrawlerStrategy`):
`async_crawler_strategy.py:800`, inside `_crawl_web` (the one method `AsyncPlaywrightCrawlerStrategy
.crawl()` calls regardless of how the browser was launched/connected — the CDP-vs-normal-launch
distinction is resolved earlier, in `BrowserManager`, not in this method) —
`response_headers = first_resp.headers`, read off the real Playwright `Response` object returned by
`page.goto()`. This flows into `AsyncCrawlResponse` and then `async_webcrawler.py:491`
(`crawl_result.response_headers = async_response.response_headers`) onto the final `CrawlResult`.
Separately confirmed via Playwright's own source (`playwright/_impl/_network.py:1028`,
`RawHeaders.__init__`/`.headers()`) that header dict keys are ALWAYS lowercased
(`header["name"].lower()`), which is why the old code's own `.get("Content-Type")` fallback was
ALSO dead — it could never have matched even if `.headers` had existed.

**Fix:** `ct = result.response_headers.get("content-type")` (the mixed-case fallback dropped, since
it is provably unreachable). Regression-guarded:
`dev/tests/test_chromium_scrape.py::test_try_scrape_extracts_content_type_from_response_headers`
(real value extracted from a fake `response_headers` dict) and
`::test_try_scrape_content_type_none_when_response_headers_empty` (graceful `None` when absent,
locking in the same neutral outcome the old, buggy code accidentally also produced — for the same
underlying reason, empty headers, not a new one).

**What is NOT yet shown, and is explicitly not claimed here:** that a REAL live scrape now writes a
real `content_type` value into `scrape_log.jsonl`. The standing no-live-browser rule means this
worker cannot produce that proof — only a fake-result-driven unit test. The project owner will run
one live scrape after merge and report what lands in the log. Until that report exists, treat the
fix as source-verified and unit-tested, not yet operationally confirmed.

## Field 2 — `og_published_time`: LEGITIMATELY EMPTY, no change

Full mechanism trace, recorded here so a future agent looking at another 91-null window does not
re-read this same source:

1. `chromium_scrape.py::_acquire_scrape` reads `(getattr(result, "metadata", None) or
   {}).get("og:published_time")` — the exact key, colon included.
2. `result.metadata` is populated by `extract_metadata_using_lxml(html, doc=None)`
   (`crawl4ai/utils.py:1497`) — for every `<meta property="og:...">` tag in `<head>`, it stores
   `metadata[property_name] = content` where `property_name` is the tag's OWN declared property
   string verbatim (`utils.py:1556-1562`, `og_tags = head.xpath('.//meta[starts-with(@property,
   "og:")]')`) — so a page declaring `<meta property="og:published_time" content="...">` produces
   exactly the key `"og:published_time"` this project reads.
3. This function is called from `content_scraping_strategy.py:698`
   (`meta = extract_metadata_using_lxml("", doc)`), inside `LXMLWebScrapingStrategy._scrap` — the
   scraping-strategy class' own `scrap()` entry point wraps it and returns it as
   `ScrapingResult.metadata` (`content_scraping_strategy.py:179`, `metadata=raw_result.get
   ("metadata", {})`).
4. `LXMLWebScrapingStrategy` is the DEFAULT `scraping_strategy` — `CrawlerRunConfig.__init__`
   (`async_configs.py:1726`) sets `self.scraping_strategy = scraping_strategy or
   LXMLWebScrapingStrategy()` when the caller passes none. `chromium_scrape.py::_build_run_config`
   never passes one, so the default applies unconditionally on this project's own configuration.
5. `async_webcrawler.py:965` (`metadata=metadata` inside the final `CrawlResult(...)` construction)
   carries it through to the object this project actually reads from.

Every link in this chain is real and unconditional on this project's own config — the mechanism is
correctly wired end to end, confirmed by reading each hop, not assumed from one.

The empirical side: the project owner's own live check (recorded in the audit this entry follows)
fetched `https://www.anthropic.com/news/claude-3-7-sonnet` directly with curl and read its `<head>`
— it declares `og:title`, `og:description`, `og:image`, `og:type`, and genuinely no
`og:published_time`. Combined with the correctly-wired mechanism above, 91/91 null reads as "the
sampled pages mostly don't use this specific OpenGraph extension," not as broken plumbing.
**No code change.** If a future window shows a real, known date-stamped article page (a blog/news
platform that is known to declare this tag) still coming through null, that would be the first
actual counter-evidence and would warrant re-opening this — nothing observed so far is that.

## Field 3 — `crawl4ai_fallback_fetch_used`: REMOVABLE, removed from the ad-hoc lane only

`async_webcrawler.py:553-565`:
```python
_fallback_fn = getattr(config, "fallback_fetch_function", None)
if _fallback_fn and not _done and not _is_raw_url:
    ...
    _crawl_stats["fallback_fetch_used"] = True
```
This is the ONLY place `fallback_fetch_used` is ever set `True` anywhere in the installed crawl4ai.
`chromium_scrape.py::_build_run_config`/its `BrowserConfig` never set `fallback_fetch_function` —
confirmed by reading the whole file, no such parameter appears anywhere. `_fallback_fn` is
therefore always `None` on this project's own configuration, the branch is structurally
unreachable, and the field is always `False` for every scrape this lane can ever produce — the same
class of dead field this project has already removed elsewhere (`outcome`, the `EMPTY_*`
sub-statuses): a constant that carries zero per-call information, not a real observation.

**Removed** from `chromium_scrape.py::scrape_url_chromium_workflow`'s own final `log_scrape({...})`
dict, and from `try_scrape`'s `_empty_meta` seed dict (the only two places in the ad-hoc lane that
referenced it). Regression-guarded:
`dev/tests/test_chromium_scrape.py::test_scrape_url_chromium_workflow_log_record_has_no_fallback_fetch_used_field`.

**`extract_crawl4ai_diagnosis` (the function that actually reads `stats.get("fallback_fetch_used")`)
is UNCHANGED, deliberately.** It is shared — `src/crawler/pipe_scraper_acquisition.py`'s own
`_scrape_one` calls it too, and `src/crawler/pipe_scraper_records.py::_log_pipe_record` reads
`diagnosis.get("crawl4ai_fallback_fetch_used")` off that SAME shared function's output for the
BATCH lane's own log record. Stripping the key out of `extract_crawl4ai_diagnosis` itself would
have silently changed the batch lane's log schema too — exactly what this milestone was told not to
do without saying so.

**Stated fact, not acted on: the batch lane has the identical dead-field condition.** Checked
`src/crawler/pipe_scraper_config.py::_build_configs` — it also never sets
`fallback_fetch_function` (this was already removed project-wide on 2026-09-09, per
`src/crawler/DOCS.md`'s own Gotcha on the curl_cffi fallback removal). So
`crawl4ai_fallback_fetch_used` is structurally always `False` in `pipe_scrape_log.jsonl` too, by
the exact same reasoning. This milestone's scope was explicitly "only these three fields" in the
context of the ad-hoc lane's own audit — the batch lane's log was not itself audited here, and
removing a field from a log nobody has measured in this session would be a different, unscoped
decision. Left alone, deliberately, with this fact on record for whoever does audit the batch log
next.

## Verification performed

`dev/tests/`: 377 passed (374 baseline + 3 new: 2 on `content_type` extraction, 1 on
`crawl4ai_fallback_fetch_used`'s absence from the logged record), plus the existing full-field-set
test updated to drop the removed key from its own expected set. `_FakeResult`'s `headers` attribute
was renamed to `response_headers` (matching the real `CrawlResult` field) — checked, not assumed,
that no existing test in the file asserted on `.headers`/`content_type` via that fixture before this
change (grep confirmed only the `_meta()` helper and the full-field-set key list referenced
`content_type`, neither via `_FakeResult`-driven extraction), so no existing test started passing
for a different reason than before — the empty-default case (`response_headers={}`) produces the
identical `content_type=None` outcome the old buggy code also produced, for the same reason (no
headers present), not a new one.

**Outstanding, not claimed here:** a real live scrape has not yet been run to confirm `content_type`
actually lands correctly in a real `scrape_log.jsonl` record. That is the project owner's own
verification step, per the standing no-live-browser rule — this entry stops at what a fake-result
unit test and a source trace can show.

## Recap — 2026-09-15, same day, live confirmation closes the outstanding item

The project owner ran a real scrape of `https://example.com/` from this worktree and read the
`scrape_log.jsonl` record it wrote: `content_type: "text/html"` — a real, non-null value, the first
one this field has ever carried across the entire 14-day window that produced this milestone.
`http_status` 200, field count down from 22 to 21 (`crawl4ai_fallback_fetch_used` confirmed absent),
suite re-run at 377 green. The outstanding item this entry named above is closed, in the fix's
favor: it works against a real `CrawlResult` from a real navigation, not only against the fake this
worker's own tests were limited to under the standing no-live-browser rule.

**The lesson, stated plainly because it is the real point of this milestone, not a footnote to it:**
this field sat null in 91 consecutive records and read as "empty" to everyone who looked at the
log, including the project owner earlier the same day. It was not empty. It was unreachable. A field
guarded by `hasattr(result, "headers")` against an attribute name that does not exist on the object
at all fails silently, forever, with no signal anywhere in the data that distinguishes "this is
genuinely absent" from "this code path can never run." The audit that started this milestone
(`adhoc_output_audit_2026-09-15.md`) could not have told the two apart by looking at the log alone —
91 nulls looks identical either way. The only way to tell them apart was to read the actual class
the code was checking `hasattr` against, which is the whole reason this milestone was scoped as a
code-reading task and not a further measurement pass. A future agent staring at a field that is
constant across an entire retention window should treat "structurally unreachable" as at least as
likely as "genuinely empty," and check the former by reading the object's real shape before trusting
the latter.

`dev/tests/`: 377 passed, unchanged from before this recap (a docs-only addition).
