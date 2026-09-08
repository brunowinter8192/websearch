# Shortening camoufox_scrape.py's _acquire_camoufox (2026-09-07)

`src/scraper/camoufox_scrape.py`'s `_acquire_camoufox` was 51 LOC, over the 50-LOC function
threshold. Pure extraction inside the same file — no new module, zero behavior change: 378 passed
before and after.

## One extraction sufficed

Unlike several other functions shortened earlier in this `refactor_sweep` area (`cursor_loop`,
`run_loop`, `_run_slot`, `discover_urls_playwright`), which each needed two rounds of extraction to
clear the 50-LOC line with margin, `_acquire_camoufox` needed only one: `_convert_camoufox_html(url,
html) -> tuple[str, bool, str, str | None]` — the markdown-conversion-with-fallback-to-raw-html
block (the `_html_to_markdown` try/except, the conversion-failure warning log, and the
`content`/`content_is_raw_html` selection), taken from the task's own first suggested candidate.
This single cut took the function from 51 to 42 LOC. The task's second candidate (the in-browser
navigation block: goto, render wait, landed_url, status resolution) was not needed and was left
untouched.

## No patch-target risk, verified before editing

Every monkeypatch in `dev/tests/test_camoufox_scrape.py` was read and confirmed to target
`camoufox_scrape.<name>` module attributes directly (`launch_options`, `AsyncCamoufox`,
`AsyncWebCrawler`, `CAMOUFOX_RENDER_WAIT_S`, `TOTAL_CAMOUFOX_BUDGET_S`, `_html_to_markdown`,
`try_scrape_camoufox`, `write_sidecar`, `log_scrape`, `sys.platform`) — none patch `_acquire_camoufox`
itself, and the one test that patches `_html_to_markdown` to a raising fake
(`_raising_html_to_markdown`) continues to intercept correctly after the extraction, since
`_convert_camoufox_html`'s own `_html_to_markdown()` call resolves via `camoufox_scrape.py`'s own
module globals — same module, same interception guarantee this sweep's earlier same-module
extractions (`rider.py`, `loop.py`) already relied on.

## Verification

`./venv/bin/python -m pytest -q`: 378 passed, unchanged count.
