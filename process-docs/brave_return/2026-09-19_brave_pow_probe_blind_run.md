# Brave PoW challenge: the probe exists, the 2026-09-18 run was blind (2026-09-19)

## Why this area exists

Brave is an active engine in the default pool. `src/search/engines/brave.py` treats the mere
presence of a challenge marker as a terminal state, so a challenged query is recorded as a
failure without the challenge ever being attempted.

Separately, the user reported that clicking Brave's challenge button by hand, once, in an
ordinary browser, made Brave stop challenging for roughly two days. That is not an operating
model. The goal of this area is the same shape the `mojeek_return` area already reached for
Mojeek: solve the challenge from code, unattended, inside the search lane's own browser.

## What was built

`dev/brave_return/` holds a complete four-phase live probe plus an offline test module driven
by local HTML fixtures. The module layout mirrors `dev/mojeek_return/` almost one to one,
deliberately, so the two are comparable.

The probe answers four questions: does the button flow complete from code, what does a
challenged query cost against the 6.0 second engine watchdog, does a solved challenge carry
over across a browser process kill, and does solving it change the 429 pow-link rate.

## The run of 2026-09-18 answered none of them

Fourteen live navigations against search.brave.com, spread over four phases and four separate
Chrome profiles, three of them brand new and empty. Zero challenges. Every query landed
directly on results.

The probe classified its own carry-over result as `UNMEASURABLE_COLD_PROFILE_WAS_NOT_CHALLENGED`,
which is correct and is the single most useful line in that report.

Read `dev/brave_return/md/brave_pydoll_probe_20260918_201033.md` as a record of the method.
It is not a record of Brave's behaviour under challenge.

## Why the run was blind

The run happened inside the window the user's manual click had opened. Brave had no reason to
challenge anything.

This was not known while the probe was being designed, which is why the probe spends its whole
budget on phases that only produce signal when a challenge actually appears.

## Correction, same day: the trigger is the search term

Everything in the two sections below about an IP-bound unlock was written before the production
query log was read. The log contradicts it. Keep reading; the sections are left in place because
the cookie evidence in them still stands on its own.

`src/logs/query_log.jsonl` holds 130 runs that included Brave, from 2026-09-05 to 2026-09-19.
Brave came back EMPTY with `marker: "captcha"` in 61 of them. Two distinct shapes:

- 53 on 2026-09-15 with `document_status_chain: [429]`. Rate limiting, a burst.
- 8 from 2026-09-16 onward with `document_status_chain: [200]`. This is the button challenge.

Every single one of the eight `[200]` cases was a query about captchas:

```
altcha widget auto onload verify programmatically
altcha widget server verification cookie
mojeek captcha verification blocked automation
mojeek community altcha captcha challenge
altcha proof of work widget
yandex captcha why am i seeing this support
yandex showcaptcha spravka cookie after
```

Every ordinary query in the same window went through unchallenged:

```
espressomaschine siebtraeger test 2025
dachrinne reinigen intervall
laminat verlegen dehnungsfuge
wasserhahn tropft reparieren
sqlite wal mode checkpoint
```

Seven challenged queries, seven about captchas, no counterexample either way.

The sharpest pair is on 2026-09-18. At 19:08:08 `yandex showcaptcha spravka cookie after` was
challenged. At 19:09:20, seventy-two seconds later, on the same profile, same process, same
address, `dachrinne reinigen intervall` returned ten results. Nothing happened in between.

So Brave challenges on the content of the search term. It is not a rate limiter, not a profile
state, not an address reputation.

This also explains the blind run directly. The probe's queries were `sqlite wal mode checkpoint`,
`rust borrow checker explained`, `nginx reverse proxy config` and the like — all harmless. It
could not have been challenged no matter how many profiles it burned.

It also dissolves the manual-click story. The user clicked once by hand and observed two quiet
days. In those two days the user simply stopped searching for captcha terms. The click is not
known to have done anything.

## Where the unlock lives: not in the profile

This is the one real finding the blind run produced, and it was free.

Phases A, B and D each ran on a brand new, empty profile directory that the user had never
touched. None of them was challenged. Across all fourteen navigations Brave set not a single
cookie — the cookie store file on disk existed at 20480 bytes but held zero entries for the
Brave domain, before and after the process kill.

A profile-carried unlock would have produced a challenge on the fresh profiles. It did not.
The only variable held constant across all four profiles was the network address.

Hypothesis, consistent with all fourteen observations: the unlock is bound to the IP address,
not to the browser profile. Not yet confirmed against a second address.

## Confirmation on 2026-09-19

Two independent checks that morning, both unchallenged:

A production `search_web` run at 10:53 returned ten Brave results in 2803ms with a
`document_status_chain` of exactly `[200]`. A single 200 means one navigation and no
interstitial — Brave answered directly.

A headful Chrome on a brand new empty profile, launched straight at a Brave search URL and
watched by the user, also showed results immediately.

So the window was still open more than a day after the manual click, on a fresh profile. Both
checks strengthen the IP hypothesis and rule out the profile.

## What separates this from Mojeek, and why it matters

Mojeek was solvable because its challenge is an `altcha-widget` custom element exposing a
public `verify()` method. `src/search/engines/mojeek.py` calls that method directly. No click
happens, so the `isTrusted` question never arises.

Brave presents a button. The probe therefore carries two trigger mechanisms: a deep-queried
`.click()` that reaches through shadow roots but produces `isTrusted: false`, and a CDP
`Input.dispatchMouseEvent` at the element's bounding-rect centre as a second attempt. Neither
has ever fired against a live Brave challenge.

Whether Brave also exposes a callable element method, the way Mojeek does, is unknown. Nobody
has seen a live Brave challenge page from inside this tooling. That question should be asked
first the next time a challenge is reachable, because a positive answer makes the whole
click-mechanism problem disappear.

## For whoever picks this up

Do not re-run the probe with harmless queries. That is what produced the empty report.

If the challenge needs to be reached, the query list is the lever, not the pacing, not the
profile and not the address. The seven terms listed in the correction section above each
produced a challenge in production.

The first time a live challenge page is reached, capture it verbatim before trying to solve
it. The `mojeek_return` area has a dedicated single-navigation capture script for exactly this
purpose; `brave_return` does not, and that gap showed.

Two routes discussed on 2026-09-19 and deliberately not taken, recorded so they are not
re-proposed: routing through the `news_pipeline` proxy pool to get a different address, and
bursting past the pacing to provoke the 429. Both were argued from the IP hypothesis, which the
query log then contradicted. The 429 shape is in any case a `pow-captcha` link page with no
clickable candidate, a different page from the button challenge.

## Later the same day: the probe stopped being blind

Everything above was written before the reproduction method was known. It is now known, and the
probe has run against a real challenge.

A challenge can be produced on demand. Fire roughly 25 plain curl requests at
`https://search.brave.com/search?q=...` with an ordinary browser User-Agent. Every one of them
returns 429. Immediately afterwards, any navigation from a real browser on a brand new profile is
served the button challenge page. The window is short, single-digit minutes, so whatever is meant
to meet the challenge has to run right after the burst with no pause.

This worked on every attempt it was tried, four times across the afternoon. It is the single most
useful thing in this file.

With that, the probe ran again and its report is
`dev/brave_return/md/brave_pydoll_probe_20260919_133706.md`. One of ten queries was challenged and
the probe solved it: navigation 329ms, button in the DOM 535ms, click fired 538ms, real results at
3012ms, 19 links parsed. The trigger that worked was the plain deep-queried `.click()`. The CDP
mouse-event path was never needed, so Brave does not gate this on a trusted input event.

## The page: there is only one, not two

This file, and the engine, and a good deal of the reasoning on 2026-09-19 all assumed two distinct
pages — a soft, clickable button challenge, and a hard 429 block carrying a `pow-captcha` link that
could only be waited out.

That is wrong. It is one page. It carries HTTP 429, a `pow-captcha` link, and a working
"Verifizieren" button, all at once. The link is the route to the classic captcha offered underneath
the button, not evidence that nothing is clickable.

The cost of that assumption: `src/search/engines/brave.py` exited on `pow_link` before it ever
reached its own click branch, so the click was unreachable in production for the whole day it
existed. It was caught only when the owner looked at the page on screen while the log record for
that same minute sat next to it, reading `button_present: true` and `challenge_triggered: false`.

The fix and its evidence are in `process-docs/marker_reflection/`.

Lesson for whoever reads this next: the log fields were correct the whole time. What was wrong was
the meaning attached to them, and no amount of further log reading would have corrected it. Open
the page.

## Where this area stands at the end of 2026-09-19

Production solves the challenge on its own. Verified live at 20:04 with a burst-provoked
challenge and an ordinary query straight after: `challenge_triggered: true`,
`document_status_chain: [429, 200]`, ten results, 5631ms.

No further probing is needed to establish that it works. The production query log now carries
`challenge_triggered` on every branch including success, so every future solve is visible without
spending dedicated live requests.

One number is worth watching and was deliberately not acted on. Three measured solves came in at
3012ms, 4718ms and 5631ms against a 6.0s engine watchdog. Three points is not a distribution, and
the owner's decision was to gather ordinary production runs before touching the budget rather than
raise it on a hunch. If a solve ever overruns, the record will say `challenge_triggered: true` with
a `TIMEOUT_WATCHDOG` status, which is unambiguous.

An open question this area cannot answer: how often ordinary user queries meet a challenge at all.
Every challenge observed on 2026-09-19 was provoked, either by a curl burst or by the marked profile
that has since been retired. Nobody has yet seen one arrive unprovoked.

## Known gap left open

`dev/_lib/browser_launch.py` hardcodes the literal Google Chrome app rather than patchright's
resolved bundle. The probe inlined its own launch wrapper instead of reusing it. The helper
was left unfixed.
