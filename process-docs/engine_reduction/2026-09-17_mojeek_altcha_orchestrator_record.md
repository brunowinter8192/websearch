# Mojeek ALTCHA — orchestrator record of how the answer was reached (2026-09-17)

Orchestrator half of the milestone whose worker entry sits in this same folder under
`2026-09-17_mojeek_altcha_trigger_probe.md`. That entry documents the probe and its result. This
one holds what only the orchestrator saw: how the investigation started by accident, three wrong
inferences it produced along the way, and what still stands between the result and production.

Read the worker entry for the mechanism. Read this one before trusting any reasoning about the
result.

## How this started, and why that matters

Nobody planned to revisit Mojeek. The session was resuming an `iterative-dev-refactor` run. The
user asked which issues were open, saw `Mojeek-API` among them, and asked how Mojeek is currently
operated. The answer, from this folder's 2026-09-05 entry, was that it is not operated at all: it
was removed because four independent access methods all landed on the same captcha page.

The user then asked to see the scrape path run headful, purely to look at it. That single request
produced the whole finding. There was no hypothesis behind it.

## The eight runs, and the one column that explains all of them

Every run below went through the production `scrape_url_chromium` path against
`https://www.mojeek.com/search?q=python+asyncio+tutorial` unless noted.

| Run | Window | delay_before_return_html | Human clicked | Outcome |
|---|---|---|---|---|
| 1 | backgrounded | 5s | no | captcha |
| 2 | foreground | 30s | **yes** | 10 real results |
| 3 | backgrounded | 30s | no | captcha |
| 4 | foreground | 5s | no | captcha |
| 5 | foreground | 30s, different query | no | captcha |
| 6 | foreground | 30s, same query as run 2 | no | captcha |
| 7 | foreground | 30s, after a 7 minute pause | **yes** | 10 real results |
| 8 | foreground | 30s, immediately after 7 | no | captcha |

The click column is the only thing that separates success from failure. Window position, wait
budget, query text and idle time were all varied and none of them moved the outcome.

The orchestrator did not know about the clicks. The user was watching the foreground window and
clicked the widget, twice, without saying so at the time. That is not a criticism of the user; it
is the reason the orchestrator's own reading of its own data was wrong twice in a row.

**The lesson for a successor: a headful run is not an unattended run.** The moment a window is
visible to a human, the human is part of the apparatus. Either keep the window backgrounded so no
interaction is possible, or record explicitly whether anyone touched it. Runs 2 and 7 are the only
two successes in the entire session's scrape-path history and both are human-assisted.

## Three inferences the orchestrator presented as observations

All three were caught by the user, not by the orchestrator. They are recorded because the pattern
repeated three times inside one session and cost real work.

**One: "the wait returned immediately."** A `worker-cli wait` call was described as returning at
once. The trace log shows it ran 68 seconds and exited correctly. The orchestrator experienced the
gap as instantaneous because it does nothing in between, and wrote that experience down as a
measurement.

**Two: the throttling hypothesis.** After run 2 succeeded and runs 3 to 6 failed, the orchestrator
noticed that run 2 had followed several minutes of quiet and built an explanation on it: Mojeek
lets a fresh attempt through and then hardens. It then designed a control experiment around that
explanation. The hypothesis was dead on arrival, because the success was a click. Two data points
were enough to grow a theory that explained nothing.

**Three: "it runs 55 minutes and reports a timeout."** Said about `worker-cli wait`, read off the
code's timeout constant, never observed. The same trace log the orchestrator had already parsed
contains zero timeout exits of that shape. Two occurrences existed, at 277 and 436 seconds, and a
human killed both before any ceiling was reached.

The common shape: a conclusion drawn from code or from a handful of observations, written in the
same register as a measurement. A successor writing in this area should assume its own confident
sentences are the ones worth checking.

## What the 2026-09-05 removal got right, and the one thing it did not have

The removal entry's cause analysis holds up completely under today's evidence. The widget does not
self-start, and a click is required. That was correct twelve days before it was confirmed.

What it did not have was ALTCHA's own documentation. The entry establishes that the widget has no
`auto` attribute and that ALTCHA only self-starts when `auto="onload"`, and stops there. The
documentation, retrieved today from `https://altcha.org/docs/integration/widget/`, additionally
gives:

- A public `verify()` method on the widget element, described as initiating the verification
  process. No click needed at all.
- Events including `statechange` over a state enum and `verified`, which replace guessing a wait
  duration with an actual completion signal.
- A `humanInteractionSignature` option, on by default, which is the one real risk this whole
  question hinged on.

That last one is why the investigation was worth running rather than assuming. An automated trigger
that starts the computation still tells you nothing if the server validates a human-interaction
signature. The probe measured it: Mojeek leaves the collector enabled, and it did not prevent any
of the three triggers from succeeding.

**The generalisable point: the 2026-09-05 investigation ended one external document short of the
answer.** It reasoned correctly from the page's own markup and stopped. Fetching the vendor's
documentation would have surfaced `verify()` and the event model the same day.

## The review finding that decided the result

The probe's first two live runs reported `auto_onload` as a success and the other two triggers as
rejected by the server, and the worker attributed that to the human-interaction signature. Both
runs agreed, including one with the settle budget raised from 15 to 35 seconds, which the worker
read as confirmation.

It was a code defect. `_wait_for_page_settle` looped only while the outcome classified as
`UNKNOWN`, and `_classify_page_outcome` returned `BLOCKED` as soon as Mojeek's block-page
boilerplate was present in the body. That text is present from the first poll of every run,
including throughout the verification sequence, because Mojeek keeps the challenge page on screen
until results replace it. The loop therefore exited on iteration zero every time, and the settle
timeout never had any effect. Raising it from 15 to 35 and getting the same verdict was not
confirmation; it was the same instant measured twice.

The evidence was in the worker's own captured body text, which read
`Verified ... Checking verification with server...` at the moment of classification. An in-flight
state, reported as a refusal.

Found by reading the code against the report during review, not by the probe, and not by the
worker. After the fix all three triggers resolve to real results.

**Two things a successor should take from this.** A terminal verdict must never be keyed on a
condition that is also true at the start, and an in-flight state needs its own class rather than
being folded into failure. And when a parameter is raised and the outcome does not change, the
first thing to check is whether the parameter was ever read.

## Why the paid API is not the answer the user wants

The issue `Mojeek-API` frames the goal as reaching Mojeek's index through the official Web Search
API. Mojeek's own pricing page, scraped 2026-09-05, advertises a free trial with limited queries,
but only via a contact form, not as a self-service tier. The user checked and reported that it comes
down to a paid plan. So the API removes the technical problem and introduces a cost one, which is
why the scraped path was the original choice and remains the preferred one.

## What stands between today's result and production

Nothing in `src/` was touched. Mojeek is still absent from the engine pool. The probe lives in
`dev/search_pipeline/`. Four things are open, and the first is the largest.

**The wrong browser stack was used.** The probe drives patchright over `connect_over_cdp`, which is
the scrape lane. Search engines run on pydoll through `src/search/browser.py`. The probe's own first
version was pydoll-based and never reached Mojeek at all, because a local network outage hit exactly
during that run. So the pydoll path is entirely unproven against Mojeek. For a question about bot
detection the browser build is the subject, not an implementation detail.

**The per-engine time budget is unmeasured.** `ENGINE_WATCHDOG_TIMEOUT` in `src/search/search_web.py`
is 6.0 seconds. A challenged query costs a page load, the proof-of-work computation, a server
verification round trip, and then the results page. The computation alone measured between 115ms and
524ms across the successful runs. The total was never measured, because the probe was not built to
measure it.

**One query, four successful runs.** The challenge appeared on effectively every request today, so
in production every Mojeek query would solve a captcha. Whether that holds up at real session volume
is unknown, and finding out means real requests against a third party.

**It is fragile by construction.** It works because Mojeek leaves `auto` unset and keeps the widget
in the light DOM. Either could change. The probe is repeatable, so drift is detectable rather than
mysterious, which is the mitigation.

## A distinction the user corrected, and it applies to the next step

The orchestrator proposed a follow-up described as a test with several real queries. That is wrong
by this project's own vocabulary. A test runs in an environment the author fully controls and
returns the same result on the hundredth repetition. Several live queries against a third party is
neither controlled nor repeatable, so it is a verification, not a test.

The correction matters for how the next milestone is framed. The controllable part, the classifier
and the trigger plumbing, can be tested against local fixtures, and the worker already did exactly
that when it fixed the settle loop. Everything that touches mojeek.com is verification and must be
reported with its live request count, as the probe's report already does.

## The unresolved non-technical question

Automatically solving a captcha on a service that sells API access for the same data is a decision
about how this project wants to behave, not a technical one. It was put to the user once and left
open. A successor should not treat the technical result as settling it.
