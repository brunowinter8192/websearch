# Live verification of the dedicated-bundle launch, and why the background-target milestone was dropped (2026-09-18)

Orchestrator record. Continues the `browser_posture` area, directly on top of the worker entry
`2026-09-17_search_lane_no_spaces_drag.md` in this same folder, which shipped the change but could
not verify it (agents did not run live browsers in that session). This entry records the live runs
that verified it, the numbers they produced, and one milestone that was cancelled as a result.

## What the owner reported before the change

Two symptoms, reported as one complaint about `websearch search_web` on macOS:

1. A browser window flickered into the foreground during a run.
2. Worse: if the owner was working on a macOS Space other than the one the CLI call ran on, the
   search pulled him to a different Space, out of whatever he was doing.

The scrape lane never did either. His own framing, which turned out to be correct: the scrape lane
also spawns a browser, also with `open -g`, and its window lands on the Space he is already on.

## The live runs

Run against the merged `integration` branch, on the owner's own machine, driving the real
`websearch search_web` CLI. Focus was measured by an external `osascript` poller reading the
frontmost application process, running as a separate background shell loop around the CLI call —
the same instrument shape the 2026-09-15 entries in this area used.

**Run 1** — one search, poller sleeping 0.25s between samples: 21 samples, all `ghostty`. Zero
samples showed any browser.

**Run 2** — two searches back to back, poller with no sleep at all (maximum resolution the
`osascript` round trip allows, roughly 5 samples per second): 95 samples, all `ghostty`. Zero
samples showed any browser.

The owner separately confirmed by eye, unprompted, that there was no focus steal, no flicker and
no Space switch.

## Why 95 samples is enough to call the flicker gone

The pre-change measurement recorded in `2026-09-15_search_lane_focus_steal_watchdog.md` measured
two focus steals per `search_web` run, lasting 0.5s and 1.03s. Steals of that length cannot hide
between samples taken roughly every 0.2s across two full runs — they would have produced many
hits, not zero. This is a real absence, not a sampling gap.

## The consequence: the background-target milestone was cancelled

A second milestone was planned and scoped before these runs: pass `background=True` to
`Target.createTarget`, the parameter pydoll's `TargetCommands.create_target` accepts and pydoll's
own `Browser.new_tab()` never passes. Upstream (microsoft/playwright #41306 and PR #41282) that
parameter is exactly what stops headed Chromium from activating the app on page creation, verified
by that PR's author on macOS.

It was cancelled, and the reason matters more than the decision:

- Its entire purpose was to remove the per-`new_tab()` activation, which is what the flicker was.
  After the bundle change there is no measurable activation left to remove.
- It carries a real cost that the flicker no longer justifies. Playwright ships `background:true`
  together with a focus-emulation shim so page JS still sees the tab as focused and visible.
  pydoll has no such shim — checked in the installed package, `pydoll.commands.EmulationCommands`
  has no focus-emulation member at all. A tab created with `background=True` through pydoll may
  genuinely report itself hidden to page JS. On a lane whose engines already fight challenges
  (brave, yandex, mojeek), handing them a new "this tab is hidden" signal for no measurable gain
  is the wrong trade.

**If the flicker ever returns**, this is the first thing to reach for, and the shim is the thing to
solve alongside it: pydoll can send a raw CDP command through its generic `Command` object, so
`Emulation.setFocusEmulationEnabled` is reachable even without a helper.

## Both symptoms had one root, which is why one change closed both

The working hypothesis going into the milestone was only about Spaces: the owner's personal Google
Chrome owns windows on other Spaces, activating it makes macOS switch there, and a dedicated
bundle that owns no window anywhere has nothing to switch to. That hypothesis survives.

What it did not predict is that the flicker would disappear too. Both symptoms are downstream of
the same event — the app being activated on target creation — and the observed result is that the
activation itself stopped, not merely that it stopped costing a Space switch. This is recorded as
an observation, not an explanation; no mechanism was measured for why a dedicated, never-otherwise-
opened bundle is not activated where the owner's daily-driver Chrome was.

## Engine yield after the change, measured on the same three runs

The worker entry flagged an open risk: patchright's Chromium presents a different browser identity
to the engines than the owner's real Chrome did, so block and challenge rates could move either
way. A pre-change baseline was taken from `src/logs/query_log.jsonl`, 141 `engine_run` records
between 2026-09-04 and 2026-09-17, as the share of runs returning at least one result: bing 99.3%,
duckduckgo 95.0%, startpage 92.9%, brave 53.2%, openalex 33.3%, yandex 19.1%, mojeek 4.0% (25 runs
only), google 2.8%.

Three post-change runs is far too small a sample to restate those percentages, so this entry does
not. What it records is that nothing looked degraded and several things looked better than the
baseline would predict:

- The first run returned, per engine result count: duckduckgo 10, mojeek 10, startpage 10,
  brave 10, yandex 10, bing 6, google 1, openalex 0. Every engine reported HTTP 200, none reported
  a block.
- mojeek delivered in all three runs. Its baseline share was 4% over 25 runs.
- brave and yandex delivered in runs where their baselines (53% and 19%) would suggest otherwise.

Nobody should read three runs as a measured improvement. The honest statement is that the feared
regression did not appear, and that a recount from `query_log.jsonl` after a few weeks of real use
is the thing that would settle it.

## The consent risk that was designed around, and did not materialise

The worker moved `SESSION_DIR` to a new, separate persistent directory rather than reusing the
profile the owner's real Chrome had built, because macOS encrypts a profile's cookie store against
the launching bundle's own identity. The accepted, expected cost was that DOM engines would need
to clear consent once on a cold profile.

That cost was not observed. No consent wall appeared in any of the three runs, and every engine
returned results on the first run against the brand-new profile. Recorded because the next reader
would otherwise plan around a one-time cost that, at least on these engines on this day, did not
occur.

## A pointer, not a claim

The old profile directory the search lane used before this change is still on disk, untouched. If
this change ever has to be reverted, it is intact.
