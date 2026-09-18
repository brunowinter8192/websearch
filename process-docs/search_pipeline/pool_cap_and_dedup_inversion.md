# Pool cap fix + dedup-to-annotation inversion (2026-09-19)

Two milestones, same two files (`src/search/search_web.py`, `src/search/merge.py`, plus
`src/search/cache.py` for M2), driven by a 132-search sample from `src/logs/query_log.jsonl`.
Google engine internals were explicitly out of scope and were not touched. Shipped as two separate
commits, M1 first.

## M1 — pool cap stopped being anchored to google

`_cap_pools` used to set `K = len(pools["google"])`, falling back to 10 only when google returned
zero. Google now returns zero in 127 of 132 logged searches; on the other 5 it returned 1 or 2,
which cut EVERY engine's pool to 1 or 2 regardless of how much that engine actually returned (one
logged case: 7 engines returned 10/10/10/10/6/1/0, breakdown printed 1/1/1/1/1/1/0).

Fix: `POOL_CAP = 10`, fixed, no per-engine table, no google lookup, no fallback branch. Lives in
`search_web.py` INFRASTRUCTURE.

**Why this barely touches 6 of the 8 engines:** `duckduckgo`, `mojeek`, `startpage`, `brave`,
`bing`, `yandex` already fetch at most 10 via `ENGINE_MAX_RESULTS` (a different, pre-existing
constant — how many results an engine is *asked* for, not how many survive into the pool). The
fixed pool cap of 10 is a structural no-op for those six; it only ever does real work on `google`
(fetch cap 100) and `openalex` (fetch cap 100). Useful to keep in mind for anyone tuning `POOL_CAP`
later: raising it above 10 only changes behavior for those two engines, nothing else.

Tests: `dev/tests/test_pool_cap.py`, new file, 6 tests — fixed-value assertion, three "google
returns few/zero results, other engines stay unaffected" cases (reproducing the espressomaschine
case verbatim from the brief), one below-cap-is-unaffected case.

Suite: 405 before, 411 after (`+6`). Committed alone, before touching `merge.py`.

## M2 — cross-engine dedup inverted from reassignment to annotation

### What changed

`build_engine_pools` (`merge.py`) used to group results by URL, then hand the URL to exactly ONE
engine — whichever had the lowest position number for it, random tie-break. Every other engine
that had also returned that URL lost it entirely. `engine_positions` (all engines' positions for
that URL) was computed and carried, but only on the single winning entry.

Measured against the query log (cap effect subtracted, this is dedup loss alone):

| engine | returned | lost to other engines' pools |
|---|---|---|
| duckduckgo | 299 | 19% |
| brave | 310 | 16% |
| bing | 169 | 15% |
| startpage | 403 | 7% |
| yandex | 10 | 20% |

Overall 11%. This loss only pays for itself if several engines get drilled per query — measured
reality is 1.17 engines per drilled search (92/109 drilled searches drilled exactly one engine), so
in practice the agent almost never sees the benefit and eats the loss on whichever one engine it
picks.

Fix: same URL-bucketing (still needed — it's what produces `engine_positions`), but instead of
picking one cross-engine winner, keep one entry PER ENGINE that returned the URL, each carrying the
full `engine_positions` dict (all engines, not just itself). Same-engine duplicates still collapse
to one entry (min position wins) — "dedup within a single engine" was never in question, only
cross-engine reassignment was. `random.choice`/`import random` are gone; there is no more
cross-engine tie to break, only a same-engine `min()`, which is deterministic.

### The gap found while implementing: `cache_write` was silently dropping `engine_positions`

Before this milestone, `cache_write` (`cache.py`) serialized only
`url/title/snippet/position/date/pdf_url` per entry — `engine_positions` was never in that dict.
Since `search_engine_drilldown` reads exclusively from the on-disk cache (never from the in-memory
pools `build_engine_pools` returns), "the cross-engine knowledge is not thrown away, it stays as an
annotation" would have been false in practice: `merge.py` would compute it, and `cache.py` would
throw it away one function call later, and no caller would ever be able to observe it. Added
`engine_positions` to `cache_write`'s serialized fields. It is NOT rendered in
`format_engine_pool`'s text output — confirmed with the owner before implementing: he does not act
on this signal today, the drilldown text stays exactly as it reads now, this is purely "computed,
persisted, available to a future reader of the cache JSON." Guarded by
`test_format_engine_pool_does_not_render_engine_positions` so it doesn't silently regrow into
visible output later without a deliberate decision.

### Downstream check (as required by the brief)

- `cli.py`'s drilldown path (`pools[args.engine]`, `[entry["url"] for entry in pools[...]]`) makes
  no exclusivity assumption anywhere — reads one engine's list, doesn't care if the same URL is
  also sitting in another engine's list. Unchanged.
- `cache.py`'s schema was already a flat `dict[engine → list]` with no cross-engine uniqueness
  constraint baked in — the only real gap was the missing `engine_positions` field above, now
  fixed.
- `query_logger.py`'s `drilldown` record (written by `cli.py`) logs `urls`/`result_count` for one
  engine at a time, no exclusivity assumption — `result_count` simply grows, which is the intended,
  expected effect of the fix, not a bug.
- `src/search/DOCS.md` already carried a Gotchas line, written against the OLD winner-take-all
  code, stating "a URL can NEVER be attributed to exactly one engine... any log record or downstream
  tooling claiming 'this URL came from engine X' is wrong by construction." That line remains true
  after M2 — if anything it goes from "true but hidden by the pool structure" to "true and visible
  in the pool structure" — left as-is; only the pool-cap and dedup-policy DOCS.md sentences actually
  changed.

### Cap ordering after M2 — deliberately left where it is

`_cap_pools` still runs after `build_engine_pools`, unchanged position, still slicing each engine's
own list independently to its own top 10 by its own native position order. Since M2 makes every
engine's pool independent of what any other engine returned, a URL several engines share now
legitimately consumes a cap slot in EACH of those engines' own top-10 — not a shared global slot.
This is the correct behavior for "at most 10 results per engine, then peace": each engine's cap is
purely a function of that engine's own list now, with no cross-engine coupling left anywhere in the
pipeline. Owner confirmed this reasoning explicitly before implementation. Recording it here so it
isn't re-litigated later: it was a deliberate call, not an oversight of not moving the cap.

### Cache growth (1h TTL) — bounded, not a concern

With `POOL_CAP=10` fixed by M1, worst case is `10 entries × 8 engines = 80` small dicts per cache
file regardless of how much cross-engine overlap M2 now lets through. This is strictly more
predictable than the pre-M1 cache, where a google-anchored K could make every pool balloon
(K=100 when google happened to return 100) or collapse (K=1) unpredictably.

### Tests

New: `dev/tests/test_merge.py` (7 tests) — same URL from two engines lands in both pools, each
entry's `engine_positions` lists both engines with their own native positions; a shared URL across
three engines; same-engine duplicate URL collapses to one entry at the better position; a URL
unique to one engine is unaffected; pools stay sorted by each engine's own native position.
`dev/tests/test_cache.py` (3 tests, new file — `cache_write` had never been exercised for real
anywhere in the suite before this, only ever `patch.object`-mocked out in `test_query_logger.py`):
`cache_write`→`cache_read` round trip preserving `engine_positions` (the gap found above, both a
multi-engine and a single-engine case); `format_engine_pool` does NOT render an
`engine_positions`/"also seen in" line.

Existing `test_openalex_engine.py` tests referencing `build_engine_pools`
(`..._preserves_pdf_url_on_winner`, `..._pdf_url_none_when_absent`) needed no changes — both feed a
single result for a single URL, so old winner-take-all and new per-engine-entry collapse to
identical output.

Suite count: 411 before M2, **421 after** (`+10`: 7 in `test_merge.py`, 3 in `test_cache.py`). Full
suite (`dev/tests/`) green at 421 with both milestones applied.

## Pre-existing drift noted, not touched

`process-docs/search_pipeline/search_pipeline.md` (a different agent's file, not edited here — the
process-docs rule forbids editing another session's file) is a self-declared 2026-06 historical
snapshot. As of this milestone it describes REMOVED behavior for both the pool cap (documents the
google-anchored K as current design, including the now-dead "K provides a natural, query-adaptive
bound (typical 8-11 URLs)" rationale) and the dedup policy (documents winner-take-all as current
design, "URL assigned to exactly one engine... position gaps in drilldown output are normal").
Anyone reading it for pool/dedup behavior after 2026-09-19 needs the code, not that file, for either
of these two areas. Separately, unrelated to this milestone, that same file's cache-schema example
path (`~/.cache/searxng/<key>.json`) doesn't match the real `CACHE_DIR` in `cache.py`
(`~/.cache/websearch`) — pre-existing drift from before this session, not introduced here.

## Open question for whoever looks at drilldown engine selection next — NOT this milestone's job

The skill instructs the agent to pick which engine to drill "guided by the hit counts." After M2,
six of the eight engines (`duckduckgo`, `mojeek`, `startpage`, `brave`, `bing`, `yandex`) fetch at
most 10 results AND the pool cap is now also fixed at 10, with no dedup loss left to pull any of
them below that ceiling in the common case.

Quantified from this same milestone's own measured dedup-loss table: `duckduckgo` lost 19% out of
299 returned across the 132-search sample (roughly 1-2 URLs per 10-result search), `brave` lost 16%
of 310 (also roughly 1-2 per search), `bing` 15% of 169, `startpage` 7% of 403 (startpage was
already close to full before the fix — it fetches/returns generously and lost the least
proportionally of the five). `yandex` lost 20% of only 10 total returned across the WHOLE
132-search sample — yandex returns close to nothing per search regardless of dedup, so its loss
rate is close to irrelevant in absolute terms even though the percentage looks similar to the
others. Put together: on a search where the five higher-volume engines (`duckduckgo`, `brave`,
`bing`, `startpage`, and by extension `mojeek`, unmeasured here but fetch-capped the same way) each
return their fetch-ceiling of 10 raw results with the kind of overlap the 15-19% loss rates imply is
common, the breakdown will now read ten-ten-ten-ten for most of them almost every time post-fix,
where before it read varied numbers (8, 9, 7, 10, 6 or similar) purely as a side effect of how much
dedup luck each engine happened to have that query. A breakdown of ten-ten-ten-ten carries no signal
for "guided by the hit counts" — the exact instruction the skill currently gives the agent for
choosing which engine to drill. This is a direct, foreseeable consequence of M1+M2 as specified, not
a bug in either; flagging by name so the next person who notices "drilldown selection feels
arbitrary now" doesn't have to re-derive why.
