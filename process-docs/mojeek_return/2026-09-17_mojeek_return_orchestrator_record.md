# Mojeek return — orchestrator record (2026-09-17)

Orchestrator half of the cycle whose worker entry sits in this same folder under
`2026-09-17_mojeek_pydoll_probe.md`. That entry documents the probe, the engine, and their
measurements. This one holds what only the orchestrator saw: where the decisive fact came from,
the two corrections that changed the worker's design, and one claim this orchestrator got wrong
and had to withdraw.

Read the worker entry for the mechanism. Read this one before trusting any reasoning about how
the cycle was steered.

## Why this area exists rather than continuing engine_reduction

Issue `Mojeek-API` named `engine_reduction` as its area, and the whole ALTCHA history sits there.
A new area was opened because the work builds on a second area as well: the engine lane in
`src/search/`, its pydoll browser and its per-engine watchdog, all of which belong to
`search_pipeline`. Two parent areas is the condition for branching, so `mojeek_return` starts here
with `engine_reduction` and `search_pipeline` behind it.

## The decisive fact came from the vendor's own forum, not from an experiment

The cycle opened with four items listed as open in the issue. Three of them were measurement
questions. The fourth, the cost per query at real session volume, looked like the expensive one:
it reads as a question that can only be answered by making a lot of live requests over a long
window against a third party.

It was answered by reading, in about ten minutes, with zero live requests.

Mojeek runs a Discourse forum at `community.mojeek.com`. A thread opened 2026-06-24, titled
"ALTCHA appears before I can get search results and I can't pass it", carries this exchange. A
user reports hitting the challenge roughly ten times a day. A Mojeek staff member replies:

> "10 a day isn't theoretically possible so can we check whether you delete cookies?"

The same staff member gives the motivation for the wall, which went live 2026-06-23: "on average
~100 automated searches per second and ~8M a day".

That single reply reframed the entire cycle. It says the challenge is gated by a cookie the
server sets, not charged per request. Everything after it — the four-phase probe design, the
cold-versus-warm split, the phase D discriminator — exists to turn that sentence into a
measurement. Without it, the probe this cycle would have built is a volume study.

**The generalisable point: before designing an experiment to measure a vendor's rate-limiting
behaviour, read what the vendor's own staff say about it in public.** The 2026-09-05 removal and
the 2026-09-17 probe in `engine_reduction` both reasoned from the page's markup and from ALTCHA's
documentation, and both were correct as far as they went. Neither looked at the operator's own
support channel, which is where the operating rule was written down in plain language.

Supporting material, retrieved the same way and supplied to the worker in the prompt because the
worker has no web access:

- ALTCHA's widget documentation (`altcha.org/docs/integration/widget/`) for the method list,
  the event list and the state enum.
- ALTCHA's form-integration description for `setCookie`, `verifyUrl` and the hidden-input default.
  Mojeek's captured configuration has `setCookie: null` and `verifyUrl: ""`, so the solution
  travels as a form field to Mojeek's own `POST /captcha/verify`, and whatever cookie follows is
  Mojeek's, not the widget's. That is why the cookie question was Mojeek's to answer and not
  ALTCHA's.
- A public "how to bypass ALTCHA" gist, checked and discarded: it targets ALTCHA v1
  (`SHA-256`, `maxnumber`, `number`). Mojeek serves v2 (`PBKDF2/SHA-256`, `cost: 8000`,
  `keyPrefix`, `derivedKey`, `counter`). It does not transfer, and nothing in this cycle needed
  it, because the browser solves the challenge the way a browser is supposed to.

## Two corrections that changed the worker's design

Both were raised before the worker wrote code, and both changed what got built. Recorded because
the pattern is reusable, not because the worker was wrong to propose what it proposed.

**One: do not key a verdict on a string you have never seen match.** The worker planned to key
the engine's `marker` field on the literal `Verification required`. Checking where that string
came from showed it had never matched anything: the M1 classifier ordered `widget_present` ahead
of `block_marker_present`, so on every challenged page it returned CHALLENGE_PENDING and the block
branch never ran. Meanwhile the probe's own captured body samples come back in German
("Ergebnisse 1 bis 10 von 24,511"), so the page is localised and an English literal is a poor
anchor. The worker spent one live request capturing the challenge page properly, found the copy
is English on a page whose `html lang` is `de` with a German footer, and concluded the literal
matches but is not locale-stable. The shipped engine therefore matches no page literal anywhere:
it keys on structure (`altcha-widget` present, `typeof verify === 'function'`) and records
`#captcha-note` verbatim in whatever language it arrives.

That capture also returned two facts nobody had: the note narrates the whole sequence
(`Waiting for verification.` -> `Checking verification with server...` ->
`Verified successfully. Reloading...`), and a solved challenge appends `chv=<hex>` to the URL on
the reload.

**Two: a milestone's framing can contain a factual error, and the worker should be free to say
so.** The M1 prompt described production as reusing "one persistent profile". The worker corrected
it: the profile *directory* persists, the Chrome *process* does not, because
`search_web_workflow` calls `kill_own_chrome()` in a `finally` on every run. A session cookie
would not survive that. The real question was therefore whether the gate cookie survives a process
kill onto disk, which is a different and sharper question, and the worker built phase C around it.
The answer is that `chllg` is persistent with a ~30-day expiry, so it does survive. Had it been
session-scoped, the production verdict would have been one challenge per run rather than one per
profile lifetime, and the same probe would have found that too.

## One claim this orchestrator made and had to withdraw

At the session recap this orchestrator proposed opening an issue for "the concurrent case is
unmeasured", carried over from the worker's own scope note.

It was wrong. The worker's scope note was about the *probe*, which measures sequential queries
with 20-second gaps. Its *verification* was three `cli.py search_web` runs, and that command fans
out all eight engines concurrently in one browser. So the challenged case under full concurrency
was already observed, in the very run that paid the challenge. Re-checked afterwards on the merged
branch: one more production run, `mojeek` OK with 10 results in 1594 ms alongside seven other
engines, `document_status_chain: [200]`, i.e. unchallenged, the cookie holding.

**The shape of the error: a caveat attached to one artifact was carried over to a different
artifact that did not share it.** A scope limit is scoped to the thing that stated it. Check which
artifact it belongs to before promoting it to an open question.

## What is genuinely left open, and why it is not a blocker

The cookie's durability beyond one sitting. Observed: it survives `browser.stop()` plus a
SIGTERM/SIGKILL of every Chrome process on the profile, with a byte-identical value, and its
declared expiry is ~30.4 days. Not observed: whether Mojeek invalidates it server-side earlier, or
re-challenges above some volume threshold. The forum's "~8M automated searches a day" makes a
threshold plausible; plausible is not observed.

This needs elapsed time, not work, and it is self-recording: a `mojeek` record in
`query_log.jsonl` whose `document_status_chain` has length 2 is a challenge being paid. No issue
was opened for it, by the user's decision.

## The non-technical question, settled

`engine_reduction`'s orchestrator record left open whether this project wants to solve a captcha
automatically on a service that sells API access for the same data, and warned that the technical
result does not settle it. It was put to the user at the start of this cycle, as one of three
options for what the cycle should be. The user chose to bring Mojeek into the engine pool. The
decision is the user's, made 2026-09-17, and it is not reopened by the next agent.
