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

**Implementation trap in `merge.py`, worth keeping in mind for the next field added to
`SearchResult`:** the fresh `SearchResult` built per pool entry names every field explicitly
(`url, title, snippet, engine, position, engine_positions, date, pdf_url`) rather than copying the
source object. A new `SearchResult` field added later (the way `date` and `pdf_url` were before
this milestone) must be added to that explicit constructor call in `merge.py` too, or it silently
drops on every entry that passes through `build_engine_pools` — this was already true before M2 and
remains true after, unchanged by the dedup-inversion itself. This is DOCS.md's `merge.py` Purpose
line detail that got cut down to one sentence per the 25-word rule; recorded here so it isn't lost.

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

---

# Google goto-redirect fix + snippet-selector fix (2026-09-19, same session)

Same area, same session, unrelated milestone from the two above — Google was returning zero
results in 127 of 132 logged searches, and the M1/M2 pool-cap and dedup-inversion work above did
not touch it (explicitly out of scope for that milestone). This entry covers why, and the fix.
Google engine internals were the ONLY thing in scope here; the pool cap and `merge.py` were
explicitly not touched, per instruction, and were not touched.

## Why Google returns zero — measured, not guessed

A live probe (`dev/access_recovery/01_google_dom_probe.py`, 20 real navigations, 15s-paced to
match the production rate limiter) found 2 OK, 18 EMPTY_PARSED, 0 blocked, 0 errors. The page
loads fine, `div.MjjYud` containers are found, but the JS parse's anchor selector
(`a[href^="http"]`) matches nothing — Google no longer puts the destination in the href. A real
organic result anchor, verbatim from saved HTML:

```html
<a jsname="UWckNb" class="zReHs" href="/goto?url=CAES3QEB6zswFaZLUN_Z...">
  <h3 class="LC20lb MBeuO DKV0Md">The Best ANC Headphones to Buy in 2025</h3>
```

The href is now a same-origin `/goto?url=<opaque blob>` redirector. The blob decodes as base64url
to 226 bytes of protobuf-shaped data; the bytes `http` do not occur in it — the destination is not
recoverable from the page at all, by design or accident, doesn't matter, it just isn't there.

## What makes the fix possible — also measured, not guessed

Three real `/goto?url=` links, fetched with `curl_cffi impersonate="chrome"`,
`allow_redirects=False`, roughly an hour after the page that contained them was saved, from a
session that no longer existed: all three came back `302`, `Location` header carrying the real
destination, no body. Two of the three were different blobs resolving to the identical page —
confirming duplicates are possible and must collapse, which is why `_resolve_urls` dedups by
resolved URL, not by blob.

**A second, follow-up measurement, done live during this milestone (not by me — supplied
directly), replaces what would otherwise have been a guessed timeout value:** all 8 organic
`/goto` links from the SAME saved page, resolved concurrently, exactly the shape `_resolve_urls`
now uses: 8 of 8 returned 302 with an absolute `https` `Location`. Individually 110–125 ms,
median 116 ms. All eight together, wall clock: **128 ms**. `GOTO_RESOLVE_TIMEOUT_S = 1.5` in
`google.py` is therefore roughly **10x** the measured concurrent-resolution wall time, not a
guess — this is the number the design conversation's earlier arithmetic (below) was missing before
this measurement existed.

## Watchdog budget — the arithmetic, now grounded

`search_web.py`'s `ENGINE_WATCHDOG_TIMEOUT = 6.0`, uniform across all 8 engines, no per-engine
override (the `ENGINE_WATCHDOG_OVERRIDE` table an older snapshot of `search_pipeline.md` describes
is gone from the actual code — confirmed by grep before relying on it). Google's redirect
resolution shares this same 6.0s with navigation, consent-handling, wait-for-results and parsing;
it does not get its own separate budget.

From the DOM probe's real per-navigation elapsed times: most runs 552 ms–1362 ms, two outliers at
4423 ms and 6147 ms (the latter already exceeds the 6.0s watchdog on navigation alone, before any
resolution work is added — that case was already going to time out before this milestone, and
still will; this fix does not make it worse). Typical-case slack after nav+parse: roughly
4.5–5.4s. Against that, and against the 128ms-wall/1.5s-cutoff ratio above, `GOTO_RESOLVE_TIMEOUT_S
= 1.5` has comfortable headroom in the common case and still fits (barely) in the 4423ms-outlier
case (4423 + 1500 = 5923ms, under 6000ms).

**Hard requirement carried into the tests: no test may depend on this value in any way.** All
`_resolve_urls` tests run against the real loopback fixture and must pass identically whether the
cutoff is 1.5s or 15s — none of them simulate a hanging endpoint or assert on timing. The number
lives in exactly one place (`GOTO_RESOLVE_TIMEOUT_S`, `google.py` INFRASTRUCTURE) and nothing in
`dev/tests/test_google_engine.py` reads or reproduces it.

## The "no timeouts" rule — what it means here, confirmed before implementing

The owner's rule ("no timeouts, no waiting, no backoff, no retry loops") was confirmed to target
the wait-and-retry-until-the-block-clears machinery a prior Google backoff implementation used
(466 seconds of wall time burned for zero benefit, deliberately removed) — NOT a single bounded
network-call attempt with a hard cutoff and no retry. `GOTO_RESOLVE_TIMEOUT_S` on each of the 8
concurrent `_resolve_one` calls is exactly that shape, the same one `tab.go_to(timeout=3.0)`
already uses everywhere in this codebase, including elsewhere in this same file. No second rate
limiter was added for the 8 concurrent sub-requests either — confirmed out of scope; the existing
per-engine `4/60s` limiter already governs how often `search_with_reason` itself runs, not what it
does internally once running.

## curl_cffi over httpx

`httpx` has no TLS/JA3 impersonation. The only thing actually proven against this real,
bot-defended `/goto` endpoint was `curl_cffi impersonate="chrome"` — `httpx` was never tested
against it at all. `curl_cffi` is an existing project dependency with one production precedent
(`src/news/engine/proxy_pool/fetch.py`, sync `Session(impersonate="chrome")`, `timeout=` kwarg —
confirms a single bounded attempt is already this project's house style for this exact client) and
several dev precedents (`AsyncSession`, used concurrently in
`dev/news_pipeline/theblock/probe_liveness.py`). Match what was proven against a bot-defended
surface, don't gamble on an untested client — the same reasoning the owner confirmed.

## Two bugs, not one — kept separate deliberately

**Bug 1 (the one the brief described): the href selector.** `a[href^="http"]` matches nothing
against `/goto?url=...` (relative, not absolute-looking as a literal attribute string, regardless
of what the resolved `.href` DOM property would later show). Fixed: `a[href^="/goto?url="]`,
still matched by href SHAPE rather than by Google's own volatile per-request class/jsname hashes,
same philosophy the original selector already used. Cross-validated independently: on the saved
page, `a[jsname="UWckNb"][class="zReHs"]` matches exactly the same 8 anchors, no ads or widgets
among them — supplied as a second, independent confirmation, not used as the actual selector
(jsname/class values are Google's own internal identifiers, more likely to churn across
deployments than the `/goto?url=` href shape).

**Bug 2 (found independently, during this milestone, by reading the real saved HTML rather than
trusting the existing selector list): the snippet selector.** The pre-existing fallback chain
tried `.wHYlTd` FIRST. Measured against all 8 organic containers on the real saved page,
`.wHYlTd` is present in every one of them — and it is not a snippet element at all, it is the
outer wrapper for the ENTIRE result block (title + cite + snippet, and on the page's first result
also a "Web results" section heading), an ANCESTOR of the real snippet element `.VwiC3b`. This
means the CURRENT (pre-fix) code has been returning a garbled composite as "snippet" for every
single Google result, independent of and unrelated to the href bug — the href bug meant no results
came back at all, so this second bug's damage has been fully masked until the href bug is fixed.
Fixed by dropping `.wHYlTd` from the selector priority list entirely and promoting `.VwiC3b`
(confirmed present and correct in all 8 organic containers); `[data-sncf]`/`.lEBKkf` kept as
defensive fallbacks, no counter-evidence found against either. Regression-guarded by
`test_js_parse_no_longer_prioritizes_wHYlTd_as_snippet_selector` in
`dev/tests/test_google_engine.py` — a source-string check, not a runtime check, since the JS
itself cannot run in this suite (see below); asserts `.wHYlTd` is absent and `.VwiC3b` is present
in the `_JS_PARSE` constant.

Recorded as two separate bugs, not folded into one narrative, so a future reader can tell which
measurement supports which fix.

## Date extraction — new, evidence-derived

The brief asked for title/snippet/date/href. The date lives in `span.YrbPuc` inside the snippet
block (`<span class="YrbPuc"><span>21 Nov 2025</span> — </span>`), present in 6 of 8 organic
containers on the saved page, absent in 2 (no fallback needed, `null` is a legitimate value,
`SearchResult.date` already treats it that way for API engines). The new JS extracts it
separately AND excludes its text from the computed `snippet` string (string-replace of the
date element's own textContent out of the snippet container's full textContent) — this was a
deliberate design choice, not required by the brief in so many words, but a direct and cheap
consequence of adding a structured date field: it also happens to fix a pre-existing gap where
`snippet.py`'s `_strip_bloat` only ever stripped ABSOLUTE-format date prefixes
(`r'\d{1,2} \w{3,9} \d{4} — '`) and never touched relative ones ("7 days ago — ", present in 2 of
the 8 containers) — those would have kept leaking into the rendered snippet forever if the date
had stayed embedded in the snippet string instead of being extracted and removed at the source.

## Position renumbering after drop/dedup — 1..N, sequential, no gaps

`merge.py`'s cross-engine dedup deliberately leaves position gaps (a URL another engine owns is
just absent, not renumbered around) — documented, deliberate, and left untouched by this
milestone. `_resolve_urls`'s within-engine drop-and-dedup is different in kind: it is entirely
internal to one engine's own pool, there is no "another engine owns position 3" concept here, a
gap would just look like an unexplained skip in that one engine's own drilldown numbering. Survivors
are renumbered 1..N in resolution order after dropping failures and collapsing duplicates.
Confirmed with the owner as the right call before implementing, given the actual reason (engine-
internal sequence vs. merge.py's deliberate cross-engine gaps are different problems with different
right answers) rather than either copying or contradicting `merge.py`'s own choice by reflex.

## Fresh SearchResult, no mutation

`_resolve_one` builds a new `SearchResult` with the resolved URL rather than mutating the parsed
one in place — matches `merge.py`'s own explicit-field-construction style (see the dedup-inversion
section above), confirmed as the preferred style before implementing.

## `_clean_url` — now a dead no-op, left in place

`_clean_url`'s `"/url?" in href` branch targeted the OLD Google redirect format (`/url?q=...`).
Zero occurrences of that format found anywhere in the real saved HTML — today's markup is
entirely `/goto?url=...`, and that string does not contain the substring `/url?` (the `?` in
`goto?url=` is not preceded by a `/`), so the branch never fires against current real results; it
silently passes the goto URL through unchanged, which is exactly the input `_resolve_urls` needs.
Left in place, unmodified — removing it isn't required for the fix and wasn't asked for. Noted
here explicitly so a future reader doesn't mistake it for live, exercised behavior; it is not.

## Fixture design — deviation from `_fixture_site.py`, and why

`dev/search_pipeline/_google_fixture.py` follows `_fixture_site.py`'s primitives
(`http.server.ThreadingHTTPServer`, OS-assigned port via `port=0`, daemon thread, `start_/stop_
fixture_server` naming) but NOT its one-module-scoped-server-plus-`/_control/*`-mutation shape.
`_fixture_site.py`'s tests all probe different FEEDERS against the SAME fixed site; this
milestone's four required test scenarios (8 happy results, 3 unhappy `/goto` cases mixed with
happy ones, a duplicate-destination pair, zero results) each need genuinely different served
content, so `start_fixture_server(specs, ...)` takes the result specs as a parameter and each test
starts and stops its own short-lived server — confirmed as the right adaptation before
implementing (test-local content, not shared fixed content, is the actual shape of this
milestone's tests).

The results page is GENERATED, not a trimmed copy of the real 816 KB saved page (same choice
`_fixture_site.py` itself makes, same reason: the statement drives the page). Kept, verbatim from
the real page's structure: the full element chain and class names from `div.MjjYud` down to
`a.zReHs[jsname=UWckNb][href^="/goto?url="] > h3.LC20lb`, and the sibling snippet block
`div.VwiC3b` with its `span.YrbPuc` date span and trailing `a.vzmbzf` "Read more" link. Dropped:
base64 inline `<img>` data URIs, the multi-KB inline `<script>`/`<style>` blocks, and Google's own
chrome (login/policy/footer links, People Also Ask, ads, related searches, sitelinks) — none of it
is read by `google.py`'s parse JS before or after this fix.

`/goto?url=<token>` values are short semantic tokens (`"ok1"`, `"dup_a"`/`"dup_b"`,
`"bad_status"`, `"no_location"`, `"bad_location"`), not realistic-looking base64 blobs — the real
blob's bytes carry no recoverable meaning (see above), so an opaque readable token is equally
faithful to what actually matters (a per-result opaque identifier) while being far easier to read
in a test failure. Confirmed as the right call before implementing.

## No browser in tests — confirmed reading, matches project precedent

`conftest.py`'s autouse `_no_real_browser_launch` fixture traps any real `browser.Chrome` launch
project-wide, not scoped to real Google specifically — its own docstring states this is
deliberate. No engine in this codebase tests its own DOM-parsing JS (`test_yandex_engine.py`,
`test_startpage_engine.py`, etc. all test only the Python-side `_build_results`, fed literal item
dicts). This milestone follows the same split: `_build_results` tested with item dicts derived
directly from the real saved HTML (no browser, no network), `_resolve_urls` tested against the
real, running local fixture server (real local HTTP, real network I/O, but loopback-only and
instant). The `.wHYlTd` fix, living entirely inside the JS string, gets a source-level regression
guard instead of a runtime test, for the same reason. Confirmed correct before implementing — do
not try to work around conftest's trap.

## Suite count

405 before the two search-pipeline milestones above touched anything, 421 after M1+M2 in this
same file's first section, then unchanged going into this milestone. This milestone: 421 before,
**431 after** (+10: 4 on `_build_results`, 1 source-level `.wHYlTd` regression guard, 5 on
`_resolve_urls` against the real fixture server — 8-happy, 3-unhappy-mixed, duplicate-collapse,
all-fail-clean-empty, empty-input-clean-noop).

## Verification — the orchestrator's own step, not run here

Not run as part of this milestone, deliberately — no live browser, no request to real Google, per
instruction. The orchestrator's own verification: run a real `search_web` for a query, then
`search_engine_drilldown --engine google`, and confirm URLs come back where the breakdown
previously showed 0 for `google` in 127 of 132 logged searches out of the `src/logs/query_log.jsonl`
sample this whole investigation was measured against.
