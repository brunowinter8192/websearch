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

---

# M2 — Mojeek back in the engine pool (same session, 2026-09-17)

`src/search/engines/mojeek.py` exists again, solves the ALTCHA challenge itself, and is wired into
the production pool. Verified live through `cli.py search_web`.

## The decision, so it is not reopened

**Decided 2026-09-17 by the user: Mojeek returns to the engine pool, with automated solving of its
ALTCHA challenge.** The open question — whether this project wants to solve a captcha on a service
that sells API access to the same data — was put to the user explicitly before any code was
written, and answered explicitly. It is the user's decision, not the agent's. A successor should
treat it as settled and not relitigate it; if circumstances change, that is a new decision for the
user, not an inference from this record.

## The correction that changed the design: never key on a string you have not seen match

The plan going in was to key the diagnosis `marker` on the literal `Verification required`. The
user rejected the assumption and was right to: M1's own classifier ordered `widget_present` ahead
of `block_marker_present`, so on every challenged query it returned CHALLENGE_PENDING and the block
branch was never reached. **That literal had never once been observed matching a live Mojeek page
in this project.** Building an engine's block signal on it would have been a guess wearing the
clothes of a measurement.

One live request settled it (`dev/mojeek_return/mojeek_challenge_capture.py`, report in that area's
`md/`). What the challenge page actually serves:

| fact | value |
|---|---|
| `title` | `Captcha` |
| `html_lang` | `de` |
| body copy | English: `Verification required` / `Please complete the challenge to continue.` |
| footer | German: `Über`, `Unterstützung`, `Datenschutz` |
| `#captcha-note` | `Waiting for verification.` -> `Checking verification with server...` -> `Verified successfully. Reloading...` |
| solved URL | gains a `chv=<hex>` parameter on the reload |
| `result_link_count` at first match | **1** |

So the literal *does* match — but the page mixes an English challenge with German chrome, which
means the copy is not reliably locale-stable, and the results page body would contain those same
words for anyone who searched them. That is the `roboter`/`robot` false positive this project
already has on record, one step removed.

**Resolution: the engine matches no page literal anywhere.** It keys on structure
(`document.querySelector('altcha-widget')`, `typeof el.verify === 'function'`) and records
`#captcha-note`'s text verbatim in whatever language it arrives. `marker` stays `None`, which the
field contract explicitly allows for engines whose signal is not text-based (google's is a URL
path, duckduckgo's an element count). The generalisable rule, which cost nothing here only because
it was caught in review: **before keying on a string, check whether any code path has ever seen it
match.** A literal in a fixture you wrote yourself is not an observation.

## The four design decisions

**1. Parse on sufficiency-or-stability, not on first sight.** `_is_ready_to_parse(count, previous,
target)`: zero links is never ready; `count >= target` (target = `min(max_results, 10)`, Mojeek
serves 10 per page) parses at once; otherwise it parses only once the count stops growing. The
partial render is real and reproduced three times — 1 link at the instant the poll first matched,
in both M1 phase-A runs and again in the challenge capture. The cost lands where the problem is:
unchallenged pages present 10 links on the first poll and parse immediately, exactly like the
removed engine, so the common path pays nothing. Only a mid-render list pays one extra 200ms poll,
on a query that already has ~2.6s of unused budget. A flat settle-sleep after the first match was
rejected: it would tax every query forever for a case that occurs about once per profile lifetime.

**2. `MOJEEK_BUDGET_S` stays 4.5.** Measured challenged span was 1784-1813ms plus ~50ms of
`new_tab()`, so ~1.9s against a 4.5s deadline — 2.6s of headroom inside the budget, and the 1.5s
the constant leaves under the 6.0s watchdog still covers `_diagnose` plus `kill_tab`. Nothing
measured justifies moving it in either direction. Raising it would eat watchdog margin for a case
never observed; lowering it to "fit" 1.9s would remove the slack that absorbs a slow verification
round trip. Note that ALTCHA's own `timeout` is 90000ms, so a stalled verification will never
self-resolve inside any budget we could set — the budget's job is to cut it off and report facts,
not to wait it out. The single-deadline-anchored-at-the-first-line shape is kept verbatim from the
removed engine, including `tab.go_to(..., timeout=3.0)`.

**3. The empty record separates four cases.** `_diagnose` carries the common fields plus
`challenge_widget` (element present now), `challenge_triggered` (Python-side run fact, so it
survives the page moving on), `challenge_state` (the widget's own `getState()`), and `captcha_note`
(verbatim). Readings:

- `challenge_triggered: true, challenge_state: "verifying"` -> challenge appeared, PoW unfinished
- `challenge_triggered: true, captcha_note: "Checking verification with server..."` -> PoW done, server round trip still open at the deadline
- `challenge_widget: true, challenge_triggered: false` -> widget appeared but never became triggerable, the drift case (e.g. Mojeek moves `verify` behind a shadow root)
- all false/null with `containers_found: false` -> no challenge at all, Mojeek simply returned nothing

On success the network half alone already tells the story: `document_status_chain` of length 2 is
the solved-challenge trace (challenge page, then the post-verification reload), length 1 means no
challenge was served.

**4. No block early-exit branch at all.** The engine's only decision is "are there result links
yet" — false at the start, true later. There is deliberately no `if block_marker: return []`
branch, because that condition is true from the first poll and stays true through the whole
verification sequence: such a branch would return empty on iteration zero on every challenged query
and the challenge would never be solved. That is the 2026-09-17 defect from the `engine_reduction`
area, and in an engine it would not be a wrong report, it would be a permanently broken engine.
`test_block_boilerplate_from_first_poll_does_not_short_circuit` guards it. **Do not add a
"fast block detection" optimisation here.**

## Live verification, in production's own profile

Three `cli.py search_web` runs through the real production path, distinct queries. Precondition
checked first, not assumed: the production profile's cookie DB held **zero** mojeek cookies, so
run 1 had to pay the challenge.

| run | query | status | results | search_ms | `document_status_chain` |
|---|---|---|---|---|---|
| 1 | python asyncio tutorial | OK | 10 | 2461 | `[200, 200]` |
| 2 | rust borrow checker explained | OK | 10 | 880 | `[200]` |
| 3 | postgres index bloat | OK | 10 | 985 | `[200]` |

Run 1's two-document chain is the challenge being solved and the page reloading; runs 2 and 3 are
single-document, i.e. never challenged. After run 1 the production profile held
`chllg` (`has_expires=1`, expiry ~30 days out). So **M1's carry-over finding holds in production's
own profile, across the `kill_own_chrome()` teardown that ends every run** — not just in a
temporary probe profile. Worst observed cost, 2461ms, is 41% of the 6.0s watchdog.

One reading trap worth recording: run 3's breakdown table showed `1` for every engine including
mojeek. That is the pool cap (`K = google_count`, and google returned 1 that run), not an engine
result. The per-engine truth is in `query_log.jsonl`'s `engine_run` record, which showed
`result_count: 10`. **Read the log record, not the breakdown table, when verifying an engine.**

## Live budget for M2

4 live requests against mojeek.com: 1 for the challenge capture, 3 for the verification runs. Each
verification run also queried the other seven engines, which is ordinary production traffic and not
Mojeek spend. Milestone total across M1 and M2: 24 requests.

## What is still unmeasured after M2

- **Concurrency.** The verification runs exercised mojeek inside the real seven-engine fanout, so
  the concurrent case is no longer entirely untested — but only at n=3, all of them healthy. The
  interaction between a challenged mojeek query and six sibling tabs under load is still not
  characterised.
- **A challenge that does not resolve.** Every live challenge so far has been solved. The
  `INCONCLUSIVE`-shaped branches (`challenge_triggered` true, no results by the deadline) are
  covered by offline tests against scripted tabs, never by a live occurrence.
- **Cookie expiry in practice.** ~30 days by the cookie's own `expires`. Whether Mojeek invalidates
  it server-side sooner, or re-challenges at some volume threshold, is untested. At a 4/minute
  limiter this project will not approach the ~8M/day automated traffic the vendor cited as its
  motivation, but "will not approach" is a reasoning step, not a measurement.
- **Drift.** The engine works because Mojeek leaves `auto` unset, keeps the widget in the light
  DOM, and exposes `verify()`. Any of those can change. The drift shows up as
  `challenge_widget: true, challenge_triggered: false` in the diagnosis, which is why that pair of
  fields is separate rather than collapsed into one boolean.

---

# Recap of this session (2026-09-17)

Two milestones, one branch (`wsmojeek2`), one area (`mojeek_return`). M1 measured whether Mojeek's
ALTCHA wall is passable under the search lane's browser; M2 put the engine back in the pool on the
strength of that measurement. Everything above is the record; this section is only what the recap
itself turned up.

## Where mojeek's name has to appear, learned the hard way

Adding an engine is not four registry edits. The full set this session touched, after a review pass
found several still describing a seven-engine world:

- `src/search/search_web.py` — import, `_DEFAULT_ENGINES`, `_BROWSER_ENGINES`, `ENGINE_MAX_RESULTS`, `ENGINES`
- `src/search/engines/mojeek.py` — the `_limiters["mojeek"]` registration at import time, without which `get_limiter` raises
- `cli.py` — the `--engine` help string for `search_engine_drilldown`
- `src/search/engines/DOCS.md` — module entry, the `kill_tab` Gotcha's engine list, the diagnosis-field contract's per-engine extras, and four separate engine counts (production 7->8, browser 6->7, total 8->9, "the 2 challenged engines" -> 3)
- `src/search/DOCS.md` — the Role paragraph's fan-out count, `search_web.py`'s Purpose and its `_BROWSER_ENGINES` Reads note, `browser.py`'s Called-by engine list, `document_status.py`'s Called-by list and its "all 7 browser engines" parenthetical, the active-engines Gotcha, and the diagnosis Gotcha's "brave/yandex (the challenged engines)"
- `dev/tests/DOCS.md` — the test module entry

**A count in prose is the thing that rots.** Every one of these was a number or a list written out
by hand, and a grep for `yandex` found them all in seconds — that is the cheap way to audit this,
because any engine-shaped claim that names one sibling names them all. A successor adding or
removing an engine should run `grep -rn <sibling-engine-name> --include=DOCS.md .` before calling
the job done, not just grep for the engine being changed (which by definition appears nowhere yet).

Also corrected in passing: `DOCS.md` (repo root) claimed `cli.py (193 LOC)` against an actual 200.
That drift predates this session — the one-line help-string edit here did not change the count —
but `cli.py` was in this session's inventory, so it was brought in line rather than left.

## Shape of the session, for anyone repeating it

The order that worked, and would be worth repeating: measure first in `dev/` with no `src/` changes
at all (M1), get the measurement reviewed, and only then write the engine (M2) with the numbers
already in hand. Every M2 design decision — the parse rule, the budget, the diagnosis fields —
resolved to "what did M1 actually observe", and the two that were not backed by an observation
(the `Verification required` literal, and an early assumption that the cookie question could be
answered without a fresh-profile control arm) were both caught by review before they shipped.

Two facts in this file were produced by being wrong first: the browser-wide cookie read (M1) and
the unobserved literal (M2). Both cost a live run or a rewrite, both were cheap to fix at the time
they were caught, and both would have been expensive as a silent property of a production engine.
