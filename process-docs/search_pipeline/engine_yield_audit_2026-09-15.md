# Engine yield audit from query_log, 2026-09-15

## Question that triggered this

Asked during the 2026-09-15 session: do we actually log how many results each engine returned
for recent queries? Answer: yes, in detail. This entry records what the log contains and what
the 14-day window showed.

## Where the data lives and what shape it has

`src/logs/query_log.jsonl` (gitignored, pruned by `src/log_janitor.py` on the same 14-day
default retention as the scrape log). 419 lines in the window 2026-09-01 to 2026-09-15.

Three record types share the file, distinguished by the `record_type` field:

| record_type | count in window | fields |
|---|---|---|
| `workflow_summary` | 137 | ts, query, language, search_key, engines_requested, engines_excluded, engines (per-engine dict), total_wall_ms, bottleneck_engine |
| `engine_run` | 137 | ts, query, language, engines, engines_requested |
| `drilldown` | 145 | ts, query, language, engine, search_key, cache_status, engine_in_pools, result_count, urls |

`workflow_summary.engines` is the per-engine payload and carries, per engine:
`rate_wait_ms`, `search_ms`, `status`, `result_count`, `drop_reason`, and a `diagnosis` sub-dict.
The `diagnosis` sub-dict carries `http_status`, `document_status_chain`, and for browser-driven
engines also `title`, `url`, `ready_state`, `marker`, `containers_found`, `pow_link`.

So per-engine result counts are logged per query, and the failure reason is logged alongside.
Nothing needed to be added to answer the original question.

## Status vocabulary observed

Across 137 workflow_summaries, 1160 engine slots:

`OK` 619, `EMPTY` 350, `EMPTY_BLOCK` 90, `EMPTY_NO_CONTAINER` 43, `EMPTY_NO_RESULTS` 41,
`ERROR_BROWSER` 7, `TIMEOUT_WATCHDOG` 6, `TIMEOUT_HTTPX` 4.

## Per-engine yield in the window

`runs` counts how often the engine appeared in a workflow_summary. `avgRes` is mean
`result_count` over all its runs including failures. `medMs` is median `search_ms`.

| engine | runs | OK | EMPTY | other | OK% | avgRes | medMs |
|---|---|---|---|---|---|---|---|
| crossref | 25 | 25 | 0 | 0 | 100% | 200.0 | 1026 |
| bing | 137 | 137 | 0 | 0 | 100% | 8.4 | 845 |
| duckduckgo | 137 | 132 | 0 | 5 | 96% | 9.6 | 1175 |
| startpage | 137 | 131 | 0 | 6 | 96% | 8.4 | 2970 |
| brave | 137 | 89 | 41 | 7 | 65% | 6.4 | 2490 |
| openalex | 137 | 48 | 83 | 6 | 35% | 14.9 | 782 |
| yandex | 137 | 42 | 71 | 24 | 31% | 3.1 | 895 |
| semantic_scholar | 25 | 5 | 0 | 20 | 20% | 1.6 | 3455 |
| open_library | 25 | 2 | 23 | 0 | 8% | 0.1 | 936 |
| lobsters | 25 | 1 | 0 | 24 | 4% | 0.1 | 1087 |
| stack_exchange | 25 | 1 | 24 | 0 | 4% | 0.0 | 345 |
| marginalia | 25 | 1 | 24 | 0 | 4% | 0.3 | 260 |
| google | 137 | 5 | 84 | 48 | 4% | 0.0 | 1239 |
| mojeek | 51 | 0 | 0 | 51 | 0% | 0.0 | 944 |

The crossref avgRes of 200.0 is an API page size, not a quality measure — it returns a fixed
large page. It is not comparable to the ~8-10 of the general web engines.

Zero of the 137 queries ended with zero total results. The healthy engines covered every query.

## google was effectively dead for the whole window

5 OK out of 137, mean result count 0.0. Per day (OK/runs): 09-01 0/8, 09-02 1/10, 09-03 2/9,
09-04 0/22, 09-05 0/2, 09-06 1/6, 09-08 0/5, 09-09 0/14, 09-12 0/4, 09-13 0/5, 09-15 1/52.

The failure shape is the interesting part. Of the 132 non-OK google slots:

- 84 were plain `EMPTY` with `http_status: 200`, `ready_state: complete`, `marker: null`, and —
  in 79 of those 84 — `containers_found: true`.
- 41 were `EMPTY_NO_RESULTS` (these records carry no diagnosis dict at all).
- 5 were `EMPTY_BLOCK`, 2 were `ERROR_BROWSER`.

A verbatim google EMPTY diagnosis:

```json
{"title": "strong hold pomade sensitive scalp dandruff - Google Search",
 "url": "https://www.google.com/search?q=strong+hold+pomade+sensitive+scalp+dandruff&hl=en&num=100",
 "ready_state": "complete", "marker": null, "containers_found": true,
 "document_status_chain": [200], "http_status": 200}
```

Page loaded, no block marker fired, result containers were found, and still zero results came
out. That pattern is consistent with a selector/extraction mismatch rather than with a block.
Stated as a hypothesis — it was not confirmed against live google HTML in this session. The
competing hypothesis is that google served a genuinely result-free page under `num=100`.

Note the `&num=100` in the request URL, since google deprecated `num=100` behaviour in 2025.
That is a lead, not a finding.

## mojeek returned EMPTY_BLOCK in all 51 runs

Uniform: `status: EMPTY_BLOCK`, `result_count: 0`, `diagnosis` carrying only
`http_status: null`, median `search_ms` 944. No captcha marker, no HTTP status at all. The
scraped mojeek path produced nothing in the entire window.

## yandex and brave fail as challenges, not as extraction

- yandex, 95 non-OK: 59 carried `marker: "captcha"`. The 71 `EMPTY` cases came back with
  `http_status: 200`.
- brave, 48 non-OK: 41 carried `marker: "captcha"` together with `http_status: 429` and
  `pow_link: true`. That is Brave's proof-of-work challenge plus rate limiting.

These two are rate-limit and challenge problems, distinct in kind from the google case.

## startpage is the wall-clock bottleneck

`bottleneck_engine` over 137 summaries: startpage 109, semantic_scholar 16, brave 4, openalex 3,
duckduckgo 2, google 2, open_library 1. startpage's median `search_ms` of 2970 is the highest
among the engines that actually deliver, and it sets total wall time in 80 percent of queries.

## Engines that only ran 25 times

crossref, semantic_scholar, open_library, lobsters, stack_exchange and marginalia each appear in
exactly 25 of the 137 summaries. mojeek appears in 51. They are pool-conditional rather than
always requested, so their percentages describe their own subset and not the full window.
