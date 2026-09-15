# access_recovery — opening state of the sprint, 2026-09-15

Main-session entry. This area was opened on 2026-09-15 to answer one question: why do searches and
scrapes fail to get through, and what can be done about it. The project owner's framing, stated
during the session: error pages reaching the agent are WANTED behaviour — showing the agent what
is actually there is the premise. The lever is reducing how many blocked responses happen at all.

`src/` work during this session was mechanical only. The research itself got as far as the
measurements below before the session ended.

## Where the numbers come from

`src/logs/query_log.jsonl` and `src/logs/scrape_log.jsonl`, both gitignored, both pruned to a
14-day window by `src/log_janitor.py`. Two audits written the same day carry the full detail:

- `process-docs/search_pipeline/engine_yield_audit_2026-09-15.md` — the query log.
- `process-docs/scrape_pipeline/adhoc_output_audit_2026-09-15.md` — the scrape log.

## Engine yield, the current 7-engine pool

Six engines plus mojeek were removed from the pool in early September (`acf4750`, `5f32ee7`), so
figures spanning the whole 14-day window mix two different pools. Restricted to the 91 searches
from 2026-09-06 onward, which is the current pool only:

| engine | runs | OK | OK% | mean results |
|---|---|---|---|---|
| bing | 91 | 91 | 100% | 8.1 |
| duckduckgo | 91 | 88 | 97% | 9.6 |
| startpage | 91 | 87 | 96% | 8.4 |
| brave | 91 | 46 | 51% | 5.1 |
| openalex | 91 | 28 | 31% | 12.5 |
| yandex | 91 | 15 | 16% | 1.6 |
| google | 91 | 2 | 2% | 0.0 |

A single confirming run on 2026-09-15 after the launch rework: duckduckgo 10, startpage 10,
openalex 100, bing 3, google 1, brave 0, yandex 0.

## Google: the failure is extraction, not blocking

Across the full 137-summary window google's non-OK breakdown was 84 plain `EMPTY`, 41
`EMPTY_NO_RESULTS`, 5 `EMPTY_BLOCK`, 2 `ERROR_BROWSER`. In 79 of the 84 `EMPTY` cases the
diagnosis carried `http_status: 200`, `ready_state: "complete"`, `marker: null` and
`containers_found: true`.

`src/search/engines/google.py` sets `containers_found` true when `div.MjjYud` is present, then
runs a separate JS pass looking for `h3` or `.LC20lb` inside those containers and walking up to an
enclosing `a[href^="http"]`. Container matches, contents do not. The break is inside the container.

Three external findings, gathered 2026-09-15:

1. **`num=100` was removed by Google in September 2025**, roughly the 8th to the 14th, without
   announcement. Results are capped at 10 per page since. Consistent across searchengineland,
   botify, brodieclark and searchenginejournal. This project still sends it —
   `ENGINE_MAX_RESULTS["google"] = 100` reaches the URL as `&num=100`.
2. **Google forced JavaScript on the no-JS paths on 2026-07-01.** Ancient-User-Agent tricks stopped
   working that day; searxng/searxng issue #6359 is a 30-comment thread on it. This does not
   explain our failure — we drive a real browser that executes JS.
3. **SearXNG no longer scrapes Google's normal web page at all.** Their source says the normal
   version needs JavaScript and is therefore unused. They fetch `https://www.google.com/wml/search`
   with a Nokia Symbian User-Agent and `impersonate="chrome99_android"`, no browser, lxml over the
   response. Their selectors: container `div.zMzFAb`, title `a.fuLhoc span.CVA68e`, url
   `a.fuLhoc/@href` unwrapped from `/url?q=` and cut at `&sa=U`, snippet `div.taTFJ span.FrIlee`.

## The WML route is closed from this IP

`dev/access_recovery/02_google_wml_probe.py` ran SearXNG's exact combination against 10 queries on
2026-09-15, paced at 5s. All 10 returned HTTP 429. Zero parsed, zero containers, no partial
success. Report: `dev/access_recovery/md/google_wml_probe_20260915_201200.md`.

This is a finding about this machine's IP on this day, not a general verdict on the method — the
same caveat the 2026-07-21 Startpage probe carries.

## The DOM path was never measured

`dev/access_recovery/01_google_dom_probe.py` exists and is unfinished. It is built to run each of
the same 10 queries twice, at `num=100` and `num=10`, capture raw HTML, and run a diagnostic JS
pass reporting what actually sits inside a `div.MjjYud` today. It paces navigations at 15s and
treats Google's `/sorry/` path as a third outcome distinct from both success and empty-containers,
so a block cannot be misread as a DOM break.

It was never run to completion. The session ended first. This is the single most valuable
outstanding measurement in this area.

## Scrape side: what the audit showed

91 scrapes over 14 days, 69 distinct hosts, all of them `filtered`/`chromium`/
`cdp_headed_backgrounded` — one configuration, no camoufox, no raw mode.

13 of 91 were non-200: five 404, three 403, two 301, one 307, one 410, one with no status at all.
The 403s were edge blocks (stern.de via Akamai, cosdna.com). One paywall was found, iz.de on
2026-09-08, HTTP 200, the article body cut mid-word at "die vorläufige Ve" and then continuing
normally into the footer — nothing in the record distinguishes it from a complete article.

Filter ratio is not a quality signal. moquer.com kept 5281 of 37353 bytes, ratio 0.14, and the
surviving text carries the full product description, the complete INCI table and the review. The
ratio tracks page chrome, not content loss.

Consent residue survives the filter: 26 of 90 sidecar files contain the word "cookie", one of them
40 times; 18 carry navigation skip-links; 20 end on debris rather than a sentence.

## Prior art that this area inherits

- **The two-layer model.** Fingerprint layer versus IP-reputation layer. Headed browsing removes a
  class of fingerprint signals at the root and does nothing for IP reputation. All three surfaces
  in this project now run headed, and google/yandex/brave still fail — so what remains sits on the
  IP layer. See `process-docs/browser_posture/`.
- **The engine pool's own keep-criterion rests on an assumption that no longer holds.** The
  2026-07-21 general-axis entry states real usage as "2-4 near-simultaneous queries per session,
  then days idle", and explicitly rejects proxies and isolated profiles at that volume. Measured
  usage in this window: 137 searches over 14 days, 52 on 2026-09-15 alone. The entry names exactly
  this as the trigger to revisit.
- **The IP layer is already solved elsewhere in this project, for a non-browser fetcher.** The news
  pipeline runs a rotating free-proxy pool of roughly 32k addresses, fetches through
  `curl_cffi impersonate="chrome"`, gives burned proxies a 60-minute cooldown matching the observed
  CF block duration, and measured a per-proxy budget of 4 to 20 fetches. It also falsified the
  common "datacenter IPs are always blocked" prior against its own target: 18.8% of DC proxies
  passed, because that target's Cloudflare was signature-gated rather than reputation-gated. See
  `process-docs/news_pipeline/`.
  Whether any of that transfers to a browser-driven search lane is unmeasured.

## An unrelated finding, recorded because it distorts every reading of the breakdown

The printed engine breakdown caps every engine's pool to Google's pool size. On the 2026-09-15
confirming run google returned 1, so the breakdown printed `1` for duckduckgo, startpage, openalex
and bing as well, while their raw counts were 10, 10, 100 and 3. When google is broken, the cap
silently truncates the entire pool to google's count. Not touched this session.

## What was mechanical, and is done

Four milestones shipped to `src/` before the research began, plus two more during it. They are
written up in their own areas: `process-docs/browser_posture/` for the focus and launch work,
`process-docs/scrape_pipeline/` for the acquisition-facts removal and the dead-field audit,
`process-docs/pipe_scraper_hardening/` for the `-g` flag.
