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

## Decision of 2026-09-19

No further probing for now. The production query log already records Brave's verdict on every
run, including the marker and the status chain, so the behaviour is observable without spending
dedicated live requests. Watch the log instead.

Open question, not answered here: whether the search terms that trigger the challenge are ones
production would ever issue on its own. The seven observed cases were all typed by hand during
investigation work on other engines' captchas. If ordinary user queries never trigger it, the
engine defect in `src/search/engines/brave.py` costs far less than the 61 EMPTY runs in the log
suggest.

## Known gap left open

`dev/_lib/browser_launch.py` hardcodes the literal Google Chrome app rather than patchright's
resolved bundle. The probe inlined its own launch wrapper instead of reusing it. The helper
was left unfixed.
