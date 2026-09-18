# Yandex is cookie-gated, not rate-gated, and one human click fixed it (2026-09-18)

Orchestrator record. Continues the `engine_expansion` area, where yandex was wired in
(`yandex_wiring_2026-07-21.md`) and re-evaluated (`yandex_reeval_2026-07-21.md`). No code was
changed. This entry records a diagnosis, a vendor statement, an observation, and a decision to
leave the engine alone for now.

## The state that triggered the investigation

Measured from `src/logs/query_log.jsonl`, 133 `engine_run` records between 2026-09-04 and
2026-09-18: yandex delivered at least one result in 24 runs and nothing in the rest. Every single
failure had the same shape.

Of all 100 empty runs carrying a diagnosis dict, **100 were redirects to a captcha URL**. Not one
was an extraction failure. This is the opposite of the Google case investigated the same day, where
zero of twenty probe navigations were blocked and every failure was extraction.

`src/search/engines/yandex.py` already detects this correctly and cheaply: `_is_block_url` checks
`window.location` for `showcaptcha`/`checkcaptcha`/`/captcha` immediately after `go_to` and returns
empty without burning the result-wait budget. That early exit was added deliberately on 2026-07-21
and it does exactly what it was built to do.

## The volume correlation, which was real but not the cause

Hit rate against the gap since the previous run:

| gap to previous run | runs | delivered |
|---|---|---|
| under 1 minute | 71 | 14% |
| 1 to 10 minutes | 29 | 17% |
| 10 to 60 minutes | 13 | 8% |
| 1 to 24 hours | 14 | 43% |
| over 24 hours | 5 | 40% |

By position within a day: runs 1 and 2 delivered 36% and 45%, runs 4 to 10 delivered 0% to 5%.

This looks like a volume ceiling, and the 2026-07-21 entry's own note ("SmartCaptcha after ~7")
reads the same way. It is the wrong conclusion, for the same reason the mojeek cycle's volume
framing was wrong before someone read the vendor's own words.

## The vendor's own words, which settled it

`https://yandex.com/support2/smart-captcha/en/often-captcha.md`, titled "I'm getting too many
captchas", lists as its first reason:

> The browser is not allowed to save cookies, **which tell the server you've already solved a
> captcha**.

That is a statement about a gate, not about a rate. It is the same sentence the Mojeek forum staff
gave on 2026-06-24 ("10 a day isn't theoretically possible so can we check whether you delete
cookies?"), which reframed that entire cycle. The generalisable rule recorded in
`process-docs/mojeek_return/` held again here, on the very next engine: **read what the vendor says
publicly about its own blocking before designing an experiment to measure it.**

## The observation that confirmed it, on the production profile

The owner was shown a live yandex search in the production bundle and the production profile
(`~/.websearch/browser-session-selflaunch`), foreground, same launch flags as production. He saw a
plain "I'm not a robot" checkbox, clicked it once, and was through.

The profile's cookie store afterwards, read directly from the Chromium cookie DB:

```
.yandex.com   spravka   persistent=True   expires 2026-10-18
```

Persistent, roughly 30 days out. Structurally identical to Mojeek's `chllg` (persistent, ~30.4
days), which was itself proven to survive the `kill_own_chrome()` teardown that ends every
production run.

Three consecutive production `search_web` runs immediately afterwards, unrelated German consumer
queries: **yandex 10, 10, 10**.

For the record, the same three runs were the first time the whole pool stood at once: google 9,
duckduckgo 10, mojeek 10, startpage 10, brave 10, bing 10, yandex 10, openalex 0 to 2.

## Why this was not turned into code, and what the two options actually cost

The obvious next step is Mojeek's: delete the early block-exit and have the engine solve the
challenge itself. `process-docs/mojeek_return/` states the structural point in capital letters —
mojeek's engine deliberately has no fast block detection, because the block boilerplate is present
from the first poll and an early exit would return empty before the challenge could ever be solved.
`yandex.py` has exactly that early exit today. So the code change is understood.

It was still not done, and the reason is a difference in what the two challenges actually test.

**ALTCHA is proof of work.** The browser computes a hash puzzle; Mojeek's own widget reported 123
to 127 ms of real work. The server can only check whether the work was done. There is no judgement
about who did it, so dispatching `verify()` from code succeeds exactly as often as a human click.

**Yandex SmartCaptcha does not work that way.** Its own product page states that the user first
sees a simple task, a checkbox or a slider, and that the service then analyses the request and
shows something harder if it looks suspicious. The checkbox is the trigger, not the test. What is
evaluated is how the click arrived: pointer movement, timing, browser fingerprint, address
reputation. A CDP-dispatched click moves no mouse.

So the owner's human click passing tells us nothing about whether an automated click would pass.
That is a live question with an open outcome, unlike Mojeek's, which was a safe win once the
mechanism was understood.

**Decision, the owner's, 2026-09-18: leave `yandex.py` untouched.** The cookie buys roughly thirty
days. If yandex starts returning empty again, one human click in a browser on the production
profile restores it. That is thirty seconds of manual work per month against an implementation
whose success probability is unknown and which would have to be verified live against an adversarial
service.

## What to watch, and what would change the decision

Self-recording, no new instrumentation needed. A yandex `engine_run` record whose diagnosis carries
a captcha URL is the gate closing again.

- **If yandex holds until roughly 2026-10-18 and then fails**, the cookie simply expired and the
  manual click is the whole maintenance story. Nothing to build.
- **If yandex fails well before that**, the cookie is being invalidated server-side, or there is a
  volume threshold on top of the gate. Then the monthly click is not enough, and automating it
  becomes worth its risk.
- **If a future cookie capture shows `spravka` as session-scoped**, the across-runs half of this
  finding dies immediately, exactly as the mojeek entry warns for `chllg`.

## One caveat on the 10-10-10

Three runs. The cookie was minutes old and the address had just been exercised by a human. Nobody
should read three runs as a stable rate. The honest claim is that the gate opened and stayed open
across three consecutive production runs including the `kill_own_chrome()` teardown between them.
