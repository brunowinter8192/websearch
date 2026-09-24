# Feeder pacing: documented, deliberately not implemented (2026-09-24)

Orchestrator record. No code changed.

## Owner decision, 2026-09-24

Everything that caps time or performance (pacing, timeouts, concurrency limits, rate limits) is
not touched in this session. It is only documented. Feeder pacing falls under this.

## State of the code on 2026-09-24

- `src/crawler/discovery.py::_run_feeders` starts the robots, sitemap and navtree feeders with one
  `asyncio.gather`, all at once.
- `src/crawler/seed_feeders_sitemap.py` and `seed_feeders_navtree.py` each bound their own fetches
  with `asyncio.Semaphore(8)` (`SITEMAP_FETCH_CONCURRENCY`, `NAVTREE_FETCH_CONCURRENCY` in
  `seed_feeders_constants.py`). This caps parallelism. It does not space requests in time; there
  is no sleep or delay anywhere in the feeder path.

## Why the original motivation may no longer hold

The burst was measured 2026-09-05 (this area): nine feeder requests within about 6 ms against the
local fixture. The harm recorded then was indirect. The burst consumed the fixture's sliding
rate-limit window, and the two residual failures at `semaphore_count=1` were sitemap seeds
fetched early in the browser traversal that followed.

That traversal was removed 2026-09-06 (this area). Discovery now makes only the feeder requests.
The mechanism by which the burst caused the recorded failures therefore no longer exists.

Hypothesis, not measured: the burst alone can still trip a strict per-IP limit on a real docs
host, because the sitemap feeder resolves nested sitemap indexes up to 8 at a time. No such
failure has been observed since 2026-09-06; `failed_feeders` would show it.

## If this is picked up again

Measure first: run `cli.py discover_urls` against a real sitemap-index-heavy docs host and check
`failed_feeders` and any 429 in `cli.log`. Only an observed feeder failure justifies pacing.
