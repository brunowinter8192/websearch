# Mojeek under the search lane's pydoll browser — 2026-09-17

Milestone M1 of the Mojeek return question. Three open questions from the `engine_reduction` area's
2026-09-17 work were answered with measurements. Nothing under `src/` was touched; `mojeek` is
still absent from the engine pool.

## The three answers, up front

**Q1 — the ALTCHA flow completes under the pydoll build.** Two challenged queries across the two
live runs, `verify()` dispatched on both, real result links on both.

**Q2 — a challenged query cost 1784ms and 1813ms** on the final run (1790ms and 2040ms on the
earlier one). The per-engine watchdog is 6.0s. Zero queries of any kind went over it.

**Q3 — a solved challenge carries over both within a run and across runs**, and the mechanism is a
persistent cookie named `chllg` with a roughly 30-day expiry, not a session cookie.

## Q3 in the detail that matters

The pattern reproduced identically on two independent live runs, four hours apart in wall time but
minutes apart in practice:

| Phase | Shape | Challenged per query |
|---|---|---|
| A cold | brand new profile, one browser process, 4 queries | `[True, False, False, False]` |
| C warm | same profile directory, Chrome killed and relaunched in between, 4 queries | `[False, False, False, False]` |
| D fresh | second brand new profile, run last, 2 queries | `[True, False]` |

Phase D is what makes this a measurement rather than a story. A quiet Phase C on its own is equally
well explained by Mojeek having stopped challenging this address during the run. A fresh profile
challenged again at the end, on the same machine and network, rules that out. Whoever repeats this
must keep Phase D; without it the result is confounded, and the probe's own verdict function
returns `CONFOUNDED_FRESH_PROFILE_ALSO_UNCHALLENGED` in exactly that case rather than claiming a
carry-over.

The cookie, as captured on 2026-09-17:

```
name: chllg, domain: www.mojeek.com, path: /, httpOnly: false, secure: false,
value length 141, expires ~30.4 days after it was set, session_scoped: false
```

Byte-identical value (SHA-256 prefix `a2d9cfa814c3`) at the end of Phase A and at the start of
Phase C, i.e. it survived `browser.stop()` plus a SIGTERM/SIGKILL of every Chrome process on that
profile. That is the production shape: `search_web_workflow` calls `kill_own_chrome()` in a
`finally` on every run, so production never keeps a browser process between runs, only the profile
directory on disk. Because `chllg` is persistent rather than session-scoped, the kill does not cost
it. **If a future capture shows `expires: -1` on this cookie, the across-runs half of the answer
dies immediately** and Mojeek becomes one challenge per production run rather than one per profile
lifetime.

This is also the first measurement in this project that agrees with the Mojeek forum staff claim
from 2026-06-24 ("10 a day isn't theoretically possible so can we check whether you delete
cookies?"). It was a vendor statement in a forum; it is now an observation on this machine.

## Q2, and what the number does and does not cover

Splits inside the challenged span, n=2, from the final run:

- navigation 362-369ms
- widget in DOM 365-372ms (the challenge page is served fast)
- `verify()` dispatched 369-383ms
- client-side `verified` 870-889ms
- result links present 1784-1813ms
- ALTCHA's own self-reported PoW time 123-127ms

So the shape is: roughly 370ms to get the challenge page, roughly 500ms of widget work of which
about 125ms is actual proof-of-work, and then roughly 900ms of server round trip before results
replace the page. Unchallenged queries ran 201-414ms on the same run.

Two caveats a successor needs:

- The clock stops at the **first** matching result link, because that is what the removed
  production engine's `_wait_for_results` did. On the challenged Phase A query the link count at
  that instant was 1, not 10 — the list was still rendering. An engine that parses immediately on
  that signal can therefore parse a partial list. This is a property of the production polling
  idiom, not of this probe, and it is visible in the report's own table.
- `new_tab()` cost a median of 50ms and `kill_tab()` 1ms, measured separately, because
  production's watchdog covers them too. They do not change the verdict against 6.0s.

## The mistake that cost a live run, and how it was found

The first live run produced the correct behavioural pattern but an empty
`mojeek_cookies_at_start_of_phase_c`, which would have meant "nothing survived the process kill"
while Phase C was simultaneously unchallenged — two facts that cannot both be true under the
cookie explanation.

Cause: `Tab.get_cookies()` in pydoll resolves to CDP `Network.getCookies` with no `urls`
parameter, which returns cookies **for the page the tab currently shows**. Every before-navigation
snapshot was taken on a fresh `about:blank` tab, so it came back empty by construction. The
after-navigation snapshots looked fine, which is exactly why this was easy to miss.

It was diagnosed against a local fixture before spending anything further, and the diagnosis is a
measurement, not a deduction:

```
on the page,  tab.get_cookies():        ['scope_probe']
blank tab,    tab.get_cookies():        []
blank tab,    Storage.getCookies:       ['scope_probe']
```

The reader was switched to browser-wide `Storage.getCookies`, the offline suite gained a check that
reads a known cookie from a blank tab, and the live run was repeated in full. The first run's
report was deleted rather than committed with a void section, matching how the `engine_reduction`
area handled its own void run. Its behavioural numbers are preserved above and in the Q3 table.

**The generalisable point:** a snapshot that is empty for structural reasons looks exactly like a
snapshot that is empty because nothing was there. Any before/after comparison needs a check that
the "before" reader can see anything at all.

## What was tested offline before any live request

47 checks in `dev/mojeek_return/test_mojeek_pydoll_core.py`, run three times with identical output
before the first live request. The ones that earned their keep:

- **The boilerplate-at-t0 guard.** `fixtures/challenge_success.html` keeps "Verification required"
  on screen along the entire success path, and the test asserts the first poll is never a terminal
  state. This is the 2026-09-17 defect from the `engine_reduction` area turned into an executable
  assertion instead of a code-review habit. That defect survived two live runs and a raised timeout
  because nothing tested it.
- **A stuck fixture** that reaches `verified` and then holds "Checking verification with
  server..." forever, asserting `INCONCLUSIVE_STILL_PENDING` and never `BLOCKED`, plus an
  assertion that the run actually spent its budget rather than exiting on iteration zero.
- **The trigger itself** against a fixture-defined `altcha-widget` custom element, which proves
  the one mechanism Q1 rests on without touching the network.
- **The report builder**, run on real measurement objects, so a crash could not waste live budget.

## pydoll versus patchright, on the one point that matters

The `engine_reduction` area recorded that patchright's `Page.evaluate` defaults to
`isolated_context=True`, which silently breaks calls to page-JS-defined custom element methods like
`verify()`. **That failure mode does not exist on pydoll.** `Tab.execute_script` builds
`RuntimeCommands.evaluate` with no isolated world at all, so `el.verify()` works in the main world
by default. This is why `verify_call` was the right trigger to pick for the search lane: it is one
main-world call, it maps directly onto the `new_tab -> go_to -> execute_script` idiom every engine
in `src/search/engines/` already uses, and it needs neither an init script racing Mojeek's own
scripts (`auto_onload`) nor the CDP click path whose shadow-DOM limitation that same area recorded
as unresolved (`real_click`).

## Live budget, precisely

20 real requests against mojeek.com across two runs of 10 (4 + 4 + 2 navigations per run), against
a milestone budget of 40 and a self-imposed ceiling of 20. 20 seconds between every consecutive
Mojeek navigation; production's limiter is 4 per minute. Control navigations went to `example.org`
and are not Mojeek requests. No run hit the tripwire; the network was healthy throughout, unlike
the predecessor probe's 2026-09-17 outage.

## What is still unmeasured

- **The concurrent case.** Production fans out seven engines at once in one browser. Every query
  here was sequential with a 20s gap. Nothing in this milestone extends to a Mojeek query sharing a
  browser with six concurrent engine tabs, and the report says so rather than implying coverage.
- **Durability of the cookie beyond one sitting.** The expiry says 30 days; this run observed it
  surviving one process kill and about a minute. Whether Mojeek invalidates it server-side earlier,
  or re-challenges at some volume threshold, is untested. The forum thread's "~8M automated
  searches a day" motivation makes a volume threshold plausible, but plausible is not observed.
- **Production's own profile.** The probe deliberately used dedicated temporary profiles with
  identical flags, never `~/.websearch/browser-session`, so it could neither contaminate production
  state nor be contaminated by it. The mechanism is profile-directory-agnostic, so this does not
  weaken the answer.
- **The non-technical question** of whether this project wants to solve a captcha on a service that
  sells API access for the same data. The `engine_reduction` area flagged it as open and put to the
  user once. The technical result does not settle it, and a successor should not treat it as
  settled.

## A conflict in the existing record, noted and not edited

The `engine_reduction` area's committed report gives client-side PoW times of 128/424/460ms; its
orchestrator record in the same folder says "between 115ms and 524ms", a range that matches no
committed payload. This run measured 122-153ms across four challenged queries, which sits with the
report's low end. Recorded here rather than corrected there, per the rule that each agent writes
only its own process-docs file.
