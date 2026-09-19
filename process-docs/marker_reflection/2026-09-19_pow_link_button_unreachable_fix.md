# Brave's challenge button was unreachable whenever pow_link was also true (2026-09-19)

## The bug

The challenge-solving milestone earlier the same day (`2026-09-19_brave_challenge_solving.md`,
this area) added a button click to `_wait_for_results`, but its own "What stayed exactly as the
prior milestone left it" section explicitly kept `pow_link`'s fast-exit ordered BEFORE the button
check, reasoning that "a genuine hard block never waits for a button that was never there." That
assumption was built on the review-round evidence available that day: an 8-query live measurement
that came back contaminated (every one of those 8 was itself rate-limited by the session's own
prior traffic), and a separate 3-query clean sample that never showed `pow_link` true at all. No
sample that day showed `pow_link` and a real, clickable button on the same page — so the milestone
shipped `_wait_for_results` in this order: containers, then `pow_link` (`return False`
immediately), then the button-matched click. Whenever `pow_link` was true, the click branch could
never execute, no matter what else was on the page.

## The evidence that proved the assumption wrong

A production run at 19:43 the same day, against a page the project owner had open on screen at the
same moment, logged this diagnosis for brave:

```json
{
  "marker": "captcha",
  "pow_link": true,
  "url": "https://search.brave.com/search?q=waermepumpe+jahresarbeitszahl+berechnen+zwei",
  "ready_state": "complete",
  "title": "Brave Search",
  "containers_found": false,
  "challenge_triggered": false,
  "button_present": true,
  "document_status_chain": [429],
  "http_status": 429
}
```

The visible browser on the same machine at the same time showed the Brave logo, a heading ("Es
wird überprüft, dass du kein Bot bist"), a subtitle, a primary "Verifizieren" button, and a
secondary "Zum klassischen CAPTCHA wechseln" link — the exact page shape the earlier probe
(`dev/brave_return/md/brave_pydoll_probe_20260919_133706.md`) had already solved once that day with
a plain deep-queried `.click()` (navigation 329ms, button in DOM 535ms, click fired 538ms, results
present at 3012ms, all times cumulative from navigation start, not additive on top of one another).
`button_present: true` and `challenge_triggered: false` in the same record, on a page a human was
looking at with a working button on it, is the bug: the 429/pow-link shape and the button-challenge
shape are the SAME page, not two different ones.

## The fix

`_wait_for_results` now checks `button_matched` before it ever acts on `pow_link`:

```python
if state["button_matched"] and not challenge_triggered:
    challenge_triggered = await _click_challenge_button(tab)
elif state["pow_link"] and not challenge_triggered and not button_present:
    pow_link_idle_cycles += 1
    if pow_link_idle_cycles >= POW_LINK_GRACE_CYCLES:
        return False, challenge_triggered, button_present
```

Once a click has been attempted (`challenge_triggered` true), the `elif` branch is structurally
unreachable on later cycles even if `pow_link` is still observed true (the page has not reloaded
yet) — the loop just keeps polling for real results in the same, unchanged budget, exactly as it
already did for a button challenge with no `pow_link` at all.

## What `pow_link` means now

Before this fix, `pow_link: true` was read as "give up, this cannot be solved." That was never
actually true — it only ever meant "this page carries Brave's proof-of-work challenge script,"
which says nothing about whether a solvable button is also present. `pow_link` is now purely
descriptive DOM telemetry, same status as `marker`/`title`/`url` — it does not drive an immediate
verdict by itself. The thing that still ends the wait early is the ABSENCE of anything clickable
for a bounded number of cycles while `pow_link` is true, not `pow_link` by itself.

## The pow_link-with-no-button case: a decision, not a measurement

No sample gathered today or in the prior milestone shows a page with `pow_link: true` that NEVER
carries a button of any kind. Every genuine-block sample on file (the 53-record 2026-09-15 cluster,
the `pow_link_block.html`/`genuine_block.html` fixture built from it) is a plain static 429 body
with no button and no client-side rendering at all — the button, if the page has one, has always
been observed present from the very first paint in every sample gathered so far.

Given that, spinning the full `MAX_WAIT_CYCLES`/`WAIT_INTERVAL` budget (20 × 0.3s = 6.0s, matching
`ENGINE_WATCHDOG_TIMEOUT` exactly) on a page shape that has never actually been observed felt like
the wrong default: it would cost the owner up to 6 real seconds on every occurrence of a shape that
may not exist, for a benefit that has never been needed. But bailing on the very first cycle (the
pre-fix behavior for `pow_link`) removes the chance for a button that renders asynchronously (the
button-challenge fixture and the earlier probe both needed ~200ms of client-side JS to mount their
button) to ever be seen at all.

`POW_LINK_GRACE_CYCLES = 2` is the middle ground chosen: if `pow_link` is true and no button
(matched or merely present) has ever been seen after 2 consecutive polls (one `WAIT_INTERVAL`,
0.3s, of patience beyond the first sighting), the wait ends early instead of running the remaining
~5.4s of budget. This number is an engineering choice, not a measured fact — it is sized to clear
the one observed button-render delay (~206ms, from the earlier probe: 535ms button-in-DOM minus
329ms navigation-complete) with roughly 94ms of margin, and to cost the far more common plain-429
case (53/131 historical Brave records) a small, bounded ~0.3-0.4s instead of nothing. Flagging this
explicitly per instruction: no live page has ever been observed proving a button needs more than
one `WAIT_INTERVAL` to render, and none has been observed proving `pow_link` can persist forever
with genuinely nothing ever clickable — this constant is a bet that the one rendering delay we did
observe is representative, sized with margin, not a verified worst case.

Once ANY button has ever been seen (`button_present` sticky true, matched or not), the grace-exit
branch never fires again for the rest of that query's wait — an unmatched-vocabulary button (the
"button present but not matched by trigger" state) is left to run its full, unchanged remaining
budget, same as before this fix. That case was not touched: it was not reported as a problem, and
`pow_link` being true alongside an unmatched button gives no reason to believe waiting longer would
help, but also no reason found today to believe it would definitely not — left alone rather than
guessed at further.

## The four distinguishable outcomes, and why no new field was needed

The existing fields (`pow_link`, `button_present`, `challenge_triggered`, `containers_found`,
non-empty `results`) already say everything the four required states need, once the reorder itself
is fixed:

1. **Challenge solved** — `results` non-empty, `diagnosis == {"challenge_triggered": true, ...}`
   (the success-branch shape, no `button_present`/`pow_link`/`containers_found` — those stay
   empty-only on success, per `src/search/DOCS.md`'s existing DOM-facts convention).
2. **Challenge attempted, not resolved in budget** — `results == []`, `challenge_triggered: true`,
   `button_present: true`, `containers_found: false`. Already covered by the pre-existing
   `test_stuck_challenge_gives_up_within_budget_and_records_it_was_attempted` fixture test.
3. **Button present but not matched by the trigger** — `results == []`, `challenge_triggered:
   false`, `button_present: true`. Unchanged by this fix.
4. **No challenge at all** — `results == []` (or non-empty on success), `challenge_triggered:
   false`, `button_present: false`, `pow_link: false`, `marker: None`.

A fifth shape now exists that is neither of the four asked for, and is deliberately NOT confused
with state 4: `pow_link: true`, `button_present: false`, `challenge_triggered: false` — the grace
period ran out with nothing ever clickable. `_log_empty_result`'s existing third branch
(`elif diag["marker"] or diag["pow_link"]:`) already logs this correctly as a block, distinctly
from the plain-debug state-4 case, with zero code changes needed there.

## Tests

New fixture: `dev/brave_return/fixtures/pow_link_with_button.html` — models the exact production
page shape (title `"Brave Search"`, German heading, a `pow-captcha` link, and a `Verifizieren`
button that swaps in real results 500ms after being clicked). This is the shape called out
explicitly as missing: "a fixture carrying both a pow-link and a working button."

`dev/tests/test_brave_engine.py::test_pow_link_with_clickable_button_solves_challenge_instead_of_giving_up`
drives the real engine against it via the existing real-fixture loopback server, at the real
`MAX_WAIT_CYCLES`/`WAIT_INTERVAL` constants (no monkeypatching), and asserts a real, non-empty
result plus `challenge_triggered: true`. Confirmed via `git stash push -- src/search/engines/brave.py`
to fail on the pre-fix code (`Brave challenge candidate seen but not clicked` logged, `results ==
[]`) and pass on the fix.

`test_genuine_pow_link_block_still_yields_no_results` (pre-existing, `genuine_block.html`, no
button on that fixture at all) gained one new assertion, `elapsed < 2.0`, using the `elapsed`
variable the test already computed but never checked — this proves the grace-period bail actually
fires well short of the 6.0s budget on the plain-block shape, rather than only asserting on the
resulting diagnosis shape.

Full suite after this fix: `454 passed` (`dev/tests/`, ~32s).

## Live verification

The curl-burst method (25 plain requests, ordinary browser UA, against `search.brave.com`) was
fired once: 10 returned 200, the remaining 15 returned 429, confirming the rate-limit window was
active. Immediately afterward, two live `./venv/bin/python cli.py search_web "<query>"` calls (no
further curl bursts):

`waermepumpe jahresarbeitszahl berechnen zwei` (the exact query from the production evidence
above) — Brave 10/10, `search_ms: 4718`, `diagnosis: {"challenge_triggered": true,
"document_status_chain": [429, 200], "http_status": 200}`. This is the closing record: a real
429/challenge page, solved, with real results, comfortably inside the 6.0s watchdog (~1.3s of
margin left).

`sourdough starter feeding schedule ratio` (an unrelated query, run right after) — Brave 10/10,
`search_ms: 4662`, same shape: `{"challenge_triggered": true, "document_status_chain": [429, 200],
"http_status": 200}`. The rate-limit window from the single burst was still active for this second
query too (no second burst was fired), so this is not a clean "never challenged" control — it is,
instead, a second independent confirmation that the click-and-recover path works reliably across
different query text while the window is open, not a one-off.

No second curl burst was fired to also capture a clean "ordinary, never-challenged" live record —
the offline fixture (`test_real_no_challenge_fixture_never_attempts_a_click`) and the untouched
code path (an ordinary success never sees `pow_link` true, so this fix's new branch is structurally
never reached on it) already establish that the success path pays nothing new, and the resource is
explicitly scarce ("use it sparingly" — the owner loses Brave access for a few minutes per burst).

## For whoever picks this up next

If a future live or fixture case shows `pow_link: true`, `button_present: true`,
`challenge_triggered: false` in a final (non-partial) diagnosis, this exact bug is back — it means
a button was seen at least once but never clicked despite `pow_link` also being true, which should
now be structurally impossible (the `button_matched` check runs unconditionally before the
`pow_link` branch every cycle). Check first whether `button_present` was true but `button_matched`
was false the whole time (state 3, not this bug — an unmatched-vocabulary button, expected and
already covered) before assuming the ordering regressed.

If `POW_LINK_GRACE_CYCLES` ever needs to change, do it with a real measurement of how long a
genuinely-clickable button can take to render on the block-page shape, not by feel — the current
value of 2 is sized against exactly one observed data point (206ms) and says so above.
