# All eight engines failed within 300 ms, and the code was not the cause (2026-09-24)

Orchestrator record. Continues from two areas: `browser_lifecycle` (the 2026-09-21 total outage
with a different root cause) and `search_pipeline` (the degraded-run notice added 2026-09-21).

## What was observed

Two consecutive `search_web` calls from another Claude Code session, 2026-09-24 19:13:08 and
19:13:10 local time (17:13Z in `query_log.jsonl`):

- `excalidraw text shifts when editing safari`
- `webkit line-height fractional rounded textarea`

Both runs, every engine:

| engine | status | drop_reason (shortened) | search_ms |
|---|---|---|---|
| google, duckduckgo, mojeek, startpage, brave, bing, yandex | ERROR_BROWSER | `Navigation to <url> failed: net::ERR_CONNECTION_REFUSED` | 221-359 |
| openalex | ERROR_HTTP | `502 Bad Gateway` | 45-69 |

The previous calls, 16:00 local, were healthy apart from one google `Page load timed out`.

## What the logs rule out

- **Not the 2026-09-21 defect (deleted Chromium bundle).** `cli.log` shows `Starting Chrome
  session` followed by `Own Chrome pids: [...]` for both runs. Chrome was up. The 2026-09-21
  signature is different and is the one to compare against:
  `Failed to get browser ws address: Cannot connect to host localhost:<port>`.
- **Not an engine-side block.** All seven browser engines fail in the same ~300 ms window with
  the same network error, across unrelated hosts.
- **Not persistent.** The first query re-run at ~19:30 local returned google 9, duckduckgo 10,
  mojeek 10, openalex 0, startpage 10, brave 10, bing 10, yandex 10.

## How the two failure paths reach the network

This is the non-obvious part, and it explains why the two error strings differ:

- **openalex (httpx)** honours `HTTPS_PROXY` from the environment. Claude Code sessions on this
  machine run with `HTTPS_PROXY=http://localhost:8081` (a `mitmdump`, monitor-cc). `cli.log` at
  19:13:08 shows `connect_tcp` to `localhost:8081` succeeding, then `CONNECT` answered with
  `502 Bad Gateway`. The proxy was alive; it could not reach upstream.
  Other sessions use other ports (8083 seen the same day), so the port identifies the calling
  session.
- **The seven browser engines** run in Chrome launched via `open -g -n -a <bundle>`
  (`src/search/browser.py`). Chrome does not read `HTTPS_PROXY`; `scutil --proxy` is empty, so it
  goes direct. It got `ERR_CONNECTION_REFUSED`.

Both paths failing in the same second, one direct and one through the proxy, points at the
machine's outbound network, not at either path.

## Conclusion, as a hypothesis

A short local network outage. Same shape as the one recorded 2026-09-17 in
`process-docs/engine_reduction/` (curl to example.org also failed, recovered on its own after
10-15 minutes). The logs hold nothing further; no network-side log from 19:13 was found
(checked: files written 19:12-19:15 under the ClaudeCode tree and `~/.mitmproxy`, only rag-cli
server start lines, unrelated).

Fastest check next time, run while the outage is live:
`curl -sS -o /dev/null -w '%{http_code}\n' https://example.org` with and without
`--noproxy '*'`. Both failing = network. Only the proxied one failing = mitmdump.

## The defect this exposed

The degraded-run notice added 2026-09-21 prints
`Repair: ./venv/bin/python -m patchright install chromium` whenever any failing engine is
`ERROR_BROWSER`. On 2026-09-24 that is the wrong advice: Chrome was installed and running. An
agent following it would reinstall Chromium and change nothing. The notice was built from the
2026-09-21 incident only, when `ERROR_BROWSER` and "browser missing" happened to coincide.

Fix dispatched as a milestone in this session: show each failing engine's drop_reason in the
notice, and emit the repair line only for the observed launch-failure signature above.
