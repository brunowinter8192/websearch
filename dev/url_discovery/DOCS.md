# dev/url_discovery/

## Role
Two independent tools built for the capture pipeline's URL-discovery step
(`src/crawler/discovery.py` + its three seed feeders): (1) execution-verified probes of
`crawl4ai`'s deep-crawling internals against a REAL site (`01_resume_state_probe.py`) — this
predates, and is independent of, `discovery.py`'s current shape (`discovery.py` no longer runs any
`crawl4ai` traversal — see its own DOCS.md Gotchas for the removal); it remains as a dormant probe
for whoever next needs to re-verify `BFSDeepCrawlStrategy`'s `resume_state` mechanics (e.g. if
link-following is rebuilt on top of it elsewhere, such as the scrape step); (2) a deterministic
LOCAL fixture site (`_fixture_site.py`/`02_fixture_site_server.py`) whose page inventory is a fact
stated in code, replacing a live host as the thing `discover_urls_workflow`'s three feeders (and
their own merge into one seed set) get checked against — see
`process-docs/url_discovery/2026-08-28_validation_against_live_sites_was_the_wrong_unit.md` for why
live-site verification stopped being trustworthy. Not the place for the seed-feeder implementations
themselves or a discovery CLI — those belong under `src/` once a design is confirmed.

## Public Interface
No `__init__.py`. Two standalone entry points, run directly:
`./venv/bin/python dev/url_discovery/01_resume_state_probe.py` (live-site probe) and
`./venv/bin/python3 dev/url_discovery/02_fixture_site_server.py [--port N]` (fixture server,
Ctrl+C to stop). `_fixture_site.py` is also imported directly by any future dev script/test that
needs a deterministic discovery target: `start_fixture_server()`/`stop_fixture_server()`/
`ground_truth()`/`seed_url()`.

## Flow
`01_resume_state_probe.py`: fixed set of real `books.toscrape.com` URLs → four small
`BFSDeepCrawlStrategy` runs against one shared `AsyncWebCrawler` → one timestamped report under
`md/`. `_fixture_site.py`/`02_fixture_site_server.py`: source lists of page paths (navtree
versions, sitemap entries, robots paths) → generated HTML/XML routes served by a
`ThreadingHTTPServer` → a caller (a real `discover_urls_workflow` run, or a feeder called directly)
gets checked against `ground_truth()`, computed from those same source lists.

## Modules

### 01_resume_state_probe.py (258 LOC)

**Purpose:** Verifies, by running it, whether `BFSDeepCrawlStrategy(resume_state=...)` can
pre-populate the BFS frontier with an arbitrary URL set instead of a single `start_url` — and, if
so, the exact `resume_state` dict shape, `start_url`'s fate, depth bookkeeping against `max_depth`,
and whether injected URLs bypass the `FilterChain` the way a depth-0 seed does.
**Reads:** nothing on disk; fetches live pages from `books.toscrape.com` via `crawl4ai`.
**Writes:** `md/01_resume_state_probe_report_<ts>.md` (one per run, never overwritten).
**Called by:** run directly, ad hoc, when the pre-seeding assumption needs re-verifying (e.g.
after a `crawl4ai` version bump).
**Calls out:** `crawl4ai` (`AsyncWebCrawler`, `BrowserConfig`, `CrawlerRunConfig`, `CacheMode`,
`crawl4ai.deep_crawling.BFSDeepCrawlStrategy`/`FilterChain`/`URLPatternFilter`).

---

### _fixture_site.py (117 LOC)

**Purpose:** The HTTP serving mechanics for the fixture site — request handling, the two switchable
failure modes (thin-body-200, sliding-window 429), and server lifecycle. Re-exports the constants
and `ground_truth()`/`seed_url()` from `_fixture_site_content.py` so `dev.url_discovery._fixture_site`
stays the one import surface `dev/tests/` and `02_fixture_site_server.py` already depend on.
**Reads:** nothing on disk — ground truth is stated as source lists in `_fixture_site_content.py`.
**Writes:** nothing (in-memory HTTP responses only).
**Called by:** `02_fixture_site_server.py` (standalone use); `dev/tests/test_discovery.py` and
`dev/tests/test_seed_feeders.py` (`start_fixture_server`/`stop_fixture_server`/`ground_truth`/
`seed_url` plus re-exported constants); any future dev script/test needing a deterministic
discovery target.
**Calls out:** `_fixture_site_content.py` (same directory, `sys.path`-inserted import, matching
`02_fixture_site_server.py`'s own convention); stdlib only otherwise (`http.server`, `threading`,
`json`, `urllib.parse`) — no `crawl4ai`/`httpx` dependency, since this module is a target, never a
client.

### _fixture_site_content.py (226 LOC)

**Purpose:** Defines the fixture site's shape — every constant (navtree/sitemap/robots page lists),
every page/route content generator (`__NEXT_DATA__` pages, leaf pages, the RSC demo page, robots.txt,
sitemap XML), `_build_routes()`, and `ground_truth()`/`_expected_seeds()`/`seed_url()` computed off
those same source lists.
**Reads:** nothing on disk — ground truth is stated as source lists in this file itself.
**Writes:** nothing.
**Called by:** `_fixture_site.py` (imports constants + `_build_routes`/`ground_truth`/`seed_url` for
re-export and for `start_fixture_server`).
**Calls out:** stdlib only (`json`, `urllib.parse`).

### 02_fixture_site_server.py (35 LOC)

**Purpose:** Standalone entry point — starts `_fixture_site.py` on a fixed/given port, prints its
seed URL + `ground_truth()`, blocks until Ctrl+C, then shuts it down cleanly.
**Reads:** nothing on disk.
**Writes:** stdout/stderr only (the startup banner).
**Called by:** run directly, ad hoc: `./venv/bin/python3 dev/url_discovery/02_fixture_site_server.py [--port N]`.
**Calls out:** `_fixture_site.py` (same directory, `sys.path`-inserted import, matching
`dev/browser_posture/_lib.py`'s own convention).

---

## State
`01_resume_state_probe.py`: no persistent state of its own — each run's `md/` report is a dated,
standalone snapshot, nothing resumed or accumulated across runs. `_fixture_site.py`: `_ROUTES`
(built fresh per `start_fixture_server()` call) and `_STATE` (request counter + the two
failure-mode flags, mutated only via `/_control/*` and read under `_STATE_LOCK`) are both
module-level — see the Gotcha below on the one-instance-per-process consequence of that.

## Gotchas
- **The 429 failure mode is a sliding window (`rate_limit_limit`/`rate_limit_window_s` +
  `_REQUEST_TIMESTAMPS`), not an absolute counter — this replaced an earlier `rate_limit_after=N`
  shape that could NOT distinguish a well-paced caller from a badly-paced one.** Both eventually
  send N total requests and both tripped the old counter identically, with no way back — the exact
  property this fixture exists to let a caller measure (process-docs/url_discovery/
  2026-09-05_pacing_measurement.md). The window is pruned lazily on every request check
  (`_REQUEST_TIMESTAMPS[0] < now - window` popped before counting), guarded by the same
  `_STATE_LOCK` every other piece of shared state uses — no separate lock, no separate race.
- **`_fixture_site.py`'s `_ROUTES`/`_STATE` are module-level globals, not per-instance — only ONE
  fixture server is meant to run per process at a time.** A second `start_fixture_server()` call in
  the same process overwrites the first's routes/state (the first server keeps serving on its own
  port, but against the second's route table). Tests/scripts that need genuine isolation should run
  in separate processes, not just separate threads.
- **`ROBOTS_EMPTY_404_PATHS` (`/internal/staging-notes`) is a genuine EMPTY-body 404, distinct from
  an ordinary 404 with a small error page — a distinction that mattered when `discover_urls_workflow`
  itself still re-fetched every seed (a plain HTTP 404 with a real body does NOT read as a failed
  fetch to `crawl4ai`; `crawl_result.success = bool(html)` is set before any anti-bot check runs —
  confirmed by reading `async_webcrawler.py`/`antibot_detector.py` directly). `discover_urls_workflow`
  no longer fetches any discovered URL itself, so this distinction is currently inert there — the
  robots feeder only ever parses `robots.txt` text, never fetches the paths it lists. Kept for
  whichever future caller (the scrape step) fetches these paths for real.
- **`THIN_BODY_HTML`'s exact shape (`<div id="app"></div>`, no `p`/`h1`/etc.) is deliberate, not
  arbitrary minification.** `antibot_detector._structural_integrity_check` needs 2+ signals to
  block a page this small (`<5000` bytes): 0 visible chars after stripping tags (`minimal_text`)
  AND 0 of `p/h1-6/article/section/li/td/a/pre` anywhere in the html (`no_content_elements`). Every
  other page this fixture serves deliberately carries a real `<h1>`+`<p>` sentence for the opposite
  reason — to never accidentally trip this same check on the "normal" ground-truth run.
- **`/rsc-demo` and its two children are deliberately never linked from the main site graph, and
  are NOT counted in `ground_truth()`'s `total_urls`.** They exist solely so
  `navtree_feeder_workflow` can be called directly against the RSC (`self.__next_f.push`) shape,
  since a real `discover_urls_workflow` run only ever calls the navtree feeder once, against the
  main site's `__NEXT_DATA__` shape. Wiring `/rsc-demo` into the main graph would change
  `total_urls` and conflate two independent purposes (shape-detection demo vs. the site's own
  ground truth) — do not link it in.
- **`ORPHAN_CHAIN`/`REVISIT_TEST_PAGE`/`VERSION_DUP_TEST_PAGE` (link-only pages, a rediscovered
  already-known sitemap URL, and an explicit-version duplicate link) were REMOVED from this
  fixture, not left inert.** All three existed solely to exercise `discovery.py`'s former
  browser-driven link-graph traversal (BFS reach beyond depth 1, the `"visited"` pre-population
  fix, and version-duplicate alias recognition respectively) — with that traversal removed (see
  `src/crawler/DOCS.md`'s Gotchas), none of the three has a consumer left, so they were deleted
  along with the tests that exercised them rather than kept "just in case". `NAVTREE_V1_ONLY_PAGES`
  is a different, still-live case: it tests the navtree feeder's OWN version union, not the
  traversal, and stays.
- Each of the four `01_resume_state_probe.py` experiments cancels its `BFSDeepCrawlStrategy` from inside its own
  `on_state_change` callback right after the single seed URL's first BFS level is processed —
  the discovered next-level URLs are inspected via the captured state dict, never actually
  fetched. This keeps every run to a handful of real requests; it also means `results` lists in
  the report only ever contain the directly-injected seed(s), not their children.
- `resume_state={}` (empty dict) is FALSY in Python, so `BFSDeepCrawlStrategy` silently takes the
  non-resume branch and crawls `start_url` normally instead of entering "zero pending URLs" resume
  mode — confirmed in Experiment 2c. A caller that constructs an empty dict on an empty-seed-list
  path will get a silent single-URL fallback, not an empty crawl and not an error.
- A wrong key in a non-empty `resume_state` (e.g. `"seed_urls"` instead of `"pending"`) fails
  silently too: the dict is truthy so resume mode IS entered, but `.get("pending", [])` finds
  nothing, `current_level` is empty, and `start_url` is never used either — the crawl produces
  zero results with no exception raised (Experiment 2b).
- Experiment 3's `children_discovered_count` reads `holder.get("state", {}).get("pending", [])`
  — a plain `.get()` chain with a `0`-shaped default at every level. `on_state_change` does fire
  whenever `result.success` is `True` regardless of what `link_discovery` found (confirmed by
  reading `_arun_batch`), and both variants' seed fetches did succeed, so the `0` reported for
  Variant A is a genuine "zero children" measurement here, not an artifact of a callback that
  never ran. But the code has no assertion that `"state" in holder` before reading the count, so
  the same pattern reused against a failing seed fetch would silently report `0` for the wrong
  reason. A stricter version would assert `"state" in holder` before trusting the count.
