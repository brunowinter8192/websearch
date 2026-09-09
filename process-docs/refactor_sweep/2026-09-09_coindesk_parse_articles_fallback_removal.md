# Removal of the parse-failure fallback in coindesk's parse_articles (2026-09-09)

Eighth Phase 4 control-flow removal (see this same folder's entries on the pipe_scraper curl_cffi
fallback removal, the proxy_riding abort stub removal, the engine `search()` wrapper removal, the
camoufox raw-HTML fallback removal, the engine `_parse_results` JSON-handler removal, the bing
`_clean_url` decode-fallback removal, and the log_janitor retention-fallback removal for the seven
before it). `timeline.py::parse_articles` wrapped `json.loads(body)` in `except Exception: return
[]`, and `discover.py::cursor_loop` then logged "Empty response — reached API bottom or parse
failure. Stopping." on either outcome — the message itself admitted the two could not be told
apart. The user ordered removal: no process-docs entry documents a real parse failure of the
CoinDesk timeline API ever occurring.

## What changed

`parse_articles` now does a bare `data = json.loads(body)`; `import json` moved from a local
import inside the removed `try:` block to `timeline.py`'s module-level INFRASTRUCTURE imports. A
non-JSON body now raises `json.JSONDecodeError` straight out of the function. The later `if not
articles: return []` (a valid JSON payload that simply carries no article list) was kept
untouched — that is the real, now-unambiguous "API bottom" shape. `cursor_loop`'s stop message was
rewritten to "Empty response — reached API bottom. Stopping." since a parse failure can no longer
reach that line at all.

## Propagation path (confirmed by reading cursor_loop in full)

`articles = parse_articles(body)` sits inside `cursor_loop`'s own `try: ... finally:
_close_year_files(year_files)` block, with no `except` clause. A raised `json.JSONDecodeError`
therefore still triggers the `finally` (year-shard file handles close cleanly) before propagating
up through `cursor_loop` and then `discover()` (no try/except around that call either), ending the
run with a traceback instead of a silent stop. `try_rewarm`/`fetch_feedpage` do not call
`parse_articles` and were left untouched.

## Caller check

`grep -rn "parse_articles" src dev cli.py`: the only real caller is `discover.py::cursor_loop`.
`dev/news_pipeline/exploration/{05,06}_*.py` each carry their own independent, differently-scoped
standalone `parse_articles` (one even has its own copy of the old stop-message string) — dev-only
exploratory duplicates, not imported from `src/`, left untouched.

## Tests

`src/news/platforms/coindesk/` had zero test coverage under `dev/tests/` before this task
(confirmed by grep — the package's only prior mention there was a pointer to the unrelated
`dev/news_pipeline/coindesk_proxy_riding/` dev-script area). New file
`dev/tests/test_coindesk_timeline.py` (20 LOC) adds the package's first `dev/tests/` coverage: one
test confirms `parse_articles(b"not json")` raises `json.JSONDecodeError`, one confirms
`parse_articles(b'{"foo": 1}')` still returns `[]` (the real-bottom shape, now unambiguous). Full
suite: 367 (baseline) + 2 = 369, confirmed by `./venv/bin/python -m pytest -q`.

## Docs

`src/news/platforms/coindesk/DOCS.md` gained a new Gotcha bullet documenting the removal, the
propagation path, and the reworded stop message; `timeline.py`'s LOC was updated (80→77);
`discover.py`'s LOC was re-verified unchanged (282, the stop-message edit replaced text on the same
line). `dev/tests/DOCS.md` gained a `test_coindesk_timeline.py` entry and added
`src/news/platforms/coindesk/` (timeline.py only, as of 2026-09-09) to its Role paragraph's
coverage list.
