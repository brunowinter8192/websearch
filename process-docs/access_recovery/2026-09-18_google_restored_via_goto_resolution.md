# Google delivers again: the redirect is resolvable, and the whole access framing was wrong (2026-09-18)

Orchestrator record, written after the live verification. Continues the `access_recovery` area and
closes the question the entry `2026-09-18_google_dom_probe_completed.md` in this same folder left
open. The implementation and its own reasoning live in `process-docs/search_pipeline/`; this entry
records the decision path, the measurements that drove it, and the verification.

## Where this area stood before today

`2026-09-15_sprint_opening_state.md` framed Google as an access problem: IP reputation, browser
fingerprints, proxies, a two-layer model. It named
`dev/access_recovery/01_google_dom_probe.py` as "the single most valuable outstanding measurement
in this area" and recorded that it had never run to completion.

It ran today. Twenty real navigations, zero blocked, zero errors, eighteen with containers found and
nothing extracted. There was never an access problem. There was an extraction problem, and the
entire area had been named after the wrong layer.

## The four candidate paths, and why three were dropped

Once the cause was known — Google replaced result hrefs with a relative `/goto?url=<opaque blob>`
and the destination is not in the page in plaintext — four options were on the table.

1. **Resolve each result's redirect.** Initially judged expensive and risky. SearXNG's own
   maintainer had advised against exactly this shape for the ChinaSo engine (searxng#4694): too
   slow, and firing one request per result looks like a bot to the origin. Our own Google rate
   limiter allows 4 requests per 60 seconds, so eight resolutions looked impossible.
2. **Pass the opaque link downstream unresolved**, letting the scrape step follow the redirect it
   was going to follow anyway. Free, but the cross-engine annotation would never match for Google.
3. **The Google Docs Explore endpoint.** Published in searxng#6359 on 2026-07-21 by a contributor
   who had kept it private for two weeks. A POST to
   `https://docs.google.com/document/d/<any public doc id>/explore/search` with a single
   URL-encoded `request` parameter returns stable JSON with real URLs, no browser, no captcha,
   pagination via a two-byte base64 token, `hl` and `lr` both working. Real, and the community's
   own answer after they abandoned HTML parsing entirely.
4. **Drop Google.** Startpage serves Google's index and delivered in 93 percent of logged runs;
   Google itself delivered in 2.8 percent.

Option 1 won on two measurements, both taken before anything was built.

## Measurement one: the redirect does not need the session

Three `/goto?url=` links were lifted out of HTML the probe had saved at 18:18, and fetched from a
separate Python process roughly an hour later with `curl_cffi` `impersonate="chrome"` and
`allow_redirects=False`. All three answered 302 with the real destination in the `Location` header,
and the destinations then fetched normally.

This is the finding the whole milestone turns on. The browser session that produced the link is
irrelevant, the link does not expire within an hour, and the destination comes back in a header
with no body attached. Everything the earlier reasoning feared about option 1 rested on the
unexamined assumption that resolution needed a full page fetch inside the session.

## Measurement two: eight concurrent resolutions cost 128 milliseconds

The worker's implementation plan proposed a 1.5 second per-request cutoff, which was a guess. All
eight organic `/goto` links from one saved page were then resolved concurrently, exactly the way
the production code would:

- 8 of 8 returned 302 with an absolute https `Location`.
- Individually 110 to 125 ms, median 116.
- All eight together, wall clock, **128 ms**.

The engine watchdog budget is 6.0 seconds, uniform across engines, covering navigation, consent,
result wait and parsing. 128 ms of added concurrent work against that budget ended the discussion.
The 1.5 second cutoff stayed, now grounded rather than guessed: roughly ten times the measured
wall time, a single attempt, no retry.

A useful side finding from that same run: the eight organic anchors are matched exactly by
`a[jsname="UWckNb"][class="zReHs"]`, eight matches on the page, with no ads or widgets among them.
The page carries 54 `/goto` hrefs in total, so the anchor identity matters.

## The owner's rule that shaped the work

Stated before the milestone was written, and it belongs on record because it changed the brief:

> we test. and if we cannot test because we need the Google environment, then we run a verify, and
> if the verify passes we ship to production.

Concretely, and stated in the brief as the first rule: no timeouts, no waiting, no backoff, no
retry loops — above all not in the test. This project has paid for that once already, with 466
seconds of backoff burned for zero benefit. A single bounded network attempt with no retry was
explicitly ruled to be a different thing from wait-and-retry machinery, and approved on that basis.
No test is permitted to depend on the cutoff value; the tests run on loopback and pass identically
whether the cutoff is 1.5 or 15 seconds.

## Verification, run once, against the real thing

`websearch search_web "faltenbalg antriebswelle wechseln kosten werkstatt"` on the merged branch:

```
google 9, duckduckgo 10, mojeek 10, openalex 0, startpage 10, brave 10, bing 10, yandex 0
```

`google` logged `status OK`, `result_count 9`, `search_ms 2298`. The run's bottleneck was brave at
3305 ms, not google. The drilldown returned nine real absolute URLs — fairgarage.com,
kfzteile24.de, autoteileprofi.de, autoreparaturen.de, motor-talk.de and others — each with a clean
snippet, six of them carrying a date. Not one unresolved `/goto` link reached the output.

This is the first Google delivery on record in this log since the window opened on 2026-09-04.

## What has not been measured, and should not be assumed

- **Rate behaviour over time.** One verification run is one run. Whether Google tolerates eight
  redirect resolutions per search across a day of real use is unknown. The failure mode to watch
  for is not a crash: it is `status OK` with a shrinking `result_count`, or resolutions starting to
  answer something other than 302. Both are visible in `query_log.jsonl` without any new
  instrumentation.
- **Result count.** The probe measured 8 organic results on one page, the verification returned 9.
  Expect single digits, not ten. The pool cap of 10 never binds for Google.
- **Link lifetime beyond an hour.** Tested at roughly one hour. Irrelevant in production, where
  resolution happens seconds after the page loads, but stated so nobody later reads "verified" as
  "verified indefinitely".

## The Docs Explore endpoint is parked, not rejected

It remains the strongest fallback if the redirect route ever closes, and the details in
searxng#6359 are enough to build from without further research. Its own risk is that it belongs to
a feature Google killed over two years ago and could remove at any time. It was not built because
the redirect route reuses the browser run we already pay for and depends on nothing that is already
scheduled to die.

## A correction to this area's own framing

The area name `access_recovery` now describes a diagnosis that did not hold. Google was never
blocked in any of the twenty probe navigations, nor in the verification run. Work continuing here
should not inherit the IP-and-fingerprint framing from the 2026-09-15 entry without re-checking
whether it applies to the specific failure at hand. The two-layer model remains correct for brave,
yandex and mojeek, which genuinely do fail as challenges.
