# M3 — pipe_scraper's -g/--headed flag, and the focus question, 2026-09-15

Worker session (worktree `mechanics`). Milestone: `pipe_scraper` (`src/crawler/pipe_scraper.py`,
the batch capture-pipeline scrape step) gets a `-g`/`--headed` flag so its chromium-engine browser
runs visible instead of headless. This entry records what shipped, the reasoning behind shipping it
WITHOUT a focus-defense mechanism on the first pass, and — same day, same session — the project
owner's own live measurement that answers what the reasoning alone could not: see "The open
question, answered by live measurement" below for the numbers. Read the reasoning section as the
state of knowledge BEFORE that measurement, not as this entry's own final word.

## New standing rule this milestone operated under

Effective 2026-09-15, workers do not launch a real browser for verification — not `cli.py
scrape_url_chromium`, not `websearch search_web`, not a direct `..._workflow` call, not a camoufox
launch. Every browser entry point in `dev/tests/` is mocked; that suite is the verification surface
now. When a milestone genuinely needs a live run, the worker names the exact command and the
project owner runs it once, out of band, and reports back. This milestone is the FIRST real use of
that division — everything below about the flag's actual on-screen behavior is unverified by
construction, on purpose, per that rule.

## What shipped

- `src/crawler/pipe_scraper_config.py::_build_configs(headed: bool = False)` — `headless = not
  headed`, nothing else in the fixed anti-bot posture (`enable_stealth`, `simulate_user`,
  `override_navigator`, `magic=False`, `remove_consent_popups`) changes either way.
  `_extract_pipe_config_stamp` already read `browser_cfg.headless` live off the real object, so the
  log/config-stamp reflects `headed` with zero additional code.
- `src/crawler/pipe_scraper.py` — `scrape_urls_workflow`/`_scrape_all` both gained a trailing
  `headed: bool = False` parameter (default preserves every existing caller's behavior unchanged —
  `dev/news_pipeline/prod_scrape_smoke.py` calls with 2 positional args only, unaffected). Argparse
  gained `-g`/`--headed` (`action='store_true'`, help text kept to what the flag literally does —
  "run the browser visible instead of headless" — per instruction, no limitation language in the
  argparse string itself; the limitation lives here and in `src/crawler/DOCS.md`, not at the
  terminal).
- `-g` reaches only the chromium engine. The camoufox engine (`_scrape_one_camoufox` →
  `src/scraper/camoufox_scrape.py::try_scrape_camoufox`) already launches headed unconditionally,
  with its own no-focus-steal mechanism (`_ensure_no_focus_steal`/`LSUIElement`) already in place —
  `_build_configs` (the only function `-g` touches) is never called on that code path. `-g` combined
  with `--engine camoufox` is a silent no-op. Documented in `src/crawler/DOCS.md`'s Gotchas so an
  operator who tries that combination and sees nothing change has somewhere to look.

## Why no focus-defense mechanism shipped — the reasoning, not a verdict on the real behavior

Read `src/scraper/chromium_process.py` (ad-hoc lane) and `src/search/browser.py` (search lane, M1)
in full before reading this section — both already ship a working defense, and neither transfers
here cleanly. Confirmed by reading `crawl4ai`'s own `browser_manager.py` directly (not assumed):
`pipe_scraper`'s chromium engine, with no custom `cdp_url`, launches through crawl4ai's own
`ManagedBrowser` — a plain-`playwright`-resolved Chromium, not the `patchright`-resolved bundle the
ad-hoc lane's own `_resolve_chromium_bundle_path` depends on — with no `open -g` subprocess
wrapping anywhere on that path. Two concrete consequences:

1. **No launch-moment backgrounding is available to reuse.** `open -g` is what suppresses
   activation at the launch instant in both existing lanes; there is no equivalent knob on
   crawl4ai's own `ManagedBrowser` launch, and nothing in `BrowserConfig`'s full field list (printed
   directly, not guessed) exposes one.
2. **A watchdog cannot be safely keyed without a live check this milestone was not permitted to
   run.** The ad-hoc lane's watchdog is name-keyed, safe specifically because it watches a
   dedicated, dynamically-resolved bundle distinct from anything else on the machine. Reusing
   `_resolve_chromium_bundle_path()` here would very likely resolve the WRONG bundle — a different
   Chromium install than the one plain-`playwright`/crawl4ai actually launches — and there was no
   way to confirm or rule that out without exactly the live run this milestone's standing rule
   forbids.

Given that, building a watchdog anyway would have meant shipping unverified guesswork dressed as a
fix — the same failure class the M1 anchor-capture race proved live probing catches and mock-based
unit tests do not. That is the reason this milestone's own decision rests on: shipping a known,
named gap beats shipping an unverified defense that might silently not defend anything at all,
or worse, might misfire against the wrong process.

A second, narrower point was raised in review and is recorded here so it is not mistaken for
settled: "visible" and "takes focus" are not the same claim, and a batch run over N URLs is a
stream of window-creation events, not one. An operator who wants to glance at a running scrape may
still not want the window grabbing the keyboard every few seconds. That distinction does NOT
license a conclusion either way here — it is the exact shape of the question that stays open below,
not an argument that settles it.

## The open question, answered by live measurement (2026-09-15, same day)

The project owner ran the exact command named above, once, live: 3 URLs (`example.com`,
`rfc-editor.org/rfc/rfc7231.html`, `iana.org/domains/reserved`), this worktree, `-g` on, with an
external `osascript` poller sampling the frontmost app every 0.2s for the whole run — 56 samples
total. The scrape completed in 4s, 3/3 at HTTP 200, all three `.md` files written. Frontmost app
went `ghostty` → `"Google Chrome for Testing"` → `ghostty`; 6 of the 56 samples were non-`ghostty`.
The steal lasted roughly 2 seconds and released on its own — nothing reclaimed it, because nothing
was watching.

Sample size, stated honestly: three URLs, one run. This does not generalize to a hundred-URL batch
on its own; it establishes the SHAPE of one real run, not a distribution.

Three findings, in the order the owner gave them:

1. **The name-keying blocker from the reasoning section above is resolved by observation, not by
   further argument.** The app that took focus reports as `"Google Chrome for Testing"` — a
   different name from the user's own `"Google Chrome"` AND from the ad-hoc lane's own bundle name.
   The concern that a name-keyed watchdog might key against the wrong process, or collide with the
   user's own separate Chrome the way the search lane's did, does not apply here: this app name is
   unambiguous on this machine, confirmed live, not assumed from reading `browser_manager.py` alone.
2. **The predicted "stream of window-creation events over N URLs" did not materialize.** One steal,
   at launch, for the whole 3-URL run — not one per URL. The chromium engine shares a single
   crawler across the whole URL list (`async with AsyncWebCrawler(...) as crawler:` wraps the
   entire `asyncio.gather` in `_scrape_all`), so per-URL page fetches are not separate window
   creations from the OS's point of view, at least at this sample size.
3. **The steal is both RARER and LONGER than the other two lanes'.** One occurrence per run here,
   versus a genuine stream of potential steals in the ad-hoc/search lanes' own architectures. But
   its duration (~2s, self-released) is well over an order of magnitude past the sub-second flicker
   both of those lanes bound their own watchdog-defended steals to (`FOCUS_STEAL_POLL_INTERVAL_S
   =0.25s` plus subprocess overhead, consistently under ~1s in every live measurement recorded for
   those two lanes).

**Whether to build a watchdog for this lane is a follow-up nobody has decided yet.** The blocker
that stopped this milestone from attempting one is gone (finding 1), but building one is explicitly
OUT OF SCOPE for this milestone by the project owner's own instruction, separate from and after
this measurement. If a future milestone picks this up: the simple, name-keyed
`_focus_steal_watchdog` already in `src/scraper/chromium_process.py` — not M1's PID-keyed
machinery, which existed specifically to solve the search lane's user's-own-Chrome collision, a
problem this lane does not have — is the mechanism finding 1 says would be unambiguous here. That
is a statement about which existing mechanism would fit, not an instruction to build it now.

## Verification actually performed this session (worker side)

`dev/tests/` — 374 passed (368 baseline + 6 new: 4 on `_build_configs(headed=...)`'s config-level
effect including the config-stamp reflection, 2 on `_scrape_all`'s own `headed` parameter reaching
`_build_configs` unchanged, mirroring the existing `block_images`/camoufox wiring-test pattern
already in the file). No argparse-level test was added, matching this file's own established
boundary — `--engine`/`--block-images` have none either, only the functions they feed do.
Every caller of `_build_configs`, `scrape_urls_workflow`, and `_scrape_all` was found by
whole-repo grep (`_build_configs`: only `pipe_scraper.py` and its own tests;
`scrape_urls_workflow`: `pipe_scraper.py` and `dev/news_pipeline/prod_scrape_smoke.py`, both
unaffected by the new trailing-default parameter). No live browser was launched by the worker, per
the standing rule — the worker's own contribution is the mocked-suite result and the source-reading
above; the live measurement in "The open question, answered by live measurement" section above is
the project owner's own run, reported back the same day, not a worker observation.
