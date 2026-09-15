# M3 — pipe_scraper's -g/--headed flag, and the focus question left open, 2026-09-15

Worker session (worktree `mechanics`). Milestone: `pipe_scraper` (`src/crawler/pipe_scraper.py`,
the batch capture-pipeline scrape step) gets a `-g`/`--headed` flag so its chromium-engine browser
runs visible instead of headless. This entry records what shipped, the reasoning behind shipping it
WITHOUT a focus-defense mechanism, and — this is the part to read carefully — leaves the actual
focus-stealing behavior of the shipped flag as an OPEN QUESTION, not a closed one. Do not read this
entry as settling that question. It settles nothing about what the flag actually does on a real
desktop; it only settles what was decided and why, on paper, without a live run.

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

## The open question, and what would close it

**Open, as of 2026-09-15: does `pipe_scraper -g` actually steal focus in practice, and if so, how
often and how disruptively over a real multi-URL run?** Nothing in this entry, in the code, or in
the reasoning above answers that — it is a claim about real macOS window-activation behavior for a
launch path (crawl4ai's `ManagedBrowser`, plain `playwright`, no `open -g`) that has never been
observed running headed by anyone on this project before this milestone.

**What closes it:** the project owner runs `pipe_scraper -g` live, once, against a small URL file,
and reports what happens to focus during the run — whether the window steals focus at launch, at
each new URL/tab, both, or neither, and how disruptive that was in practice. That report is the
next entry in this area, not a revision of this one (this file is not maintained after today, per
the project's own process-docs convention). If the answer is "disruptive," the follow-up is a
watchdog analogous to M1's — PID-keyed (name-keying is unsafe here for a different reason than the
search lane's: not user-Chrome collision, but the unconfirmed-bundle-identity risk above), built and
verified the same way M1's was: implemented, then caught and fixed against real live-probe evidence,
not shipped on reasoning alone. If the answer is "tolerable," the flag ships as-is and this question
closes without further code.

## Verification actually performed this session

`dev/tests/` — 374 passed (368 baseline + 6 new: 4 on `_build_configs(headed=...)`'s config-level
effect including the config-stamp reflection, 2 on `_scrape_all`'s own `headed` parameter reaching
`_build_configs` unchanged, mirroring the existing `block_images`/camoufox wiring-test pattern
already in the file). No argparse-level test was added, matching this file's own established
boundary — `--engine`/`--block-images` have none either, only the functions they feed do.
Every caller of `_build_configs`, `scrape_urls_workflow`, and `_scrape_all` was found by
whole-repo grep (`_build_configs`: only `pipe_scraper.py` and its own tests;
`scrape_urls_workflow`: `pipe_scraper.py` and `dev/news_pipeline/prod_scrape_smoke.py`, both
unaffected by the new trailing-default parameter). No live browser was launched, per the standing
rule — everything above the "Verification actually performed" heading is reasoning from source
reading, not observation.
