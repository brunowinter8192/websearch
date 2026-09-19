# Bringing Brave's button-challenge solve into production (2026-09-19)

## Starting point

`dev/brave_return/`'s probe (`brave_pydoll_probe.py`) reached a real, live Brave button challenge
for the first time on 2026-09-19T13:37:06Z (`dev/brave_return/md/brave_pydoll_probe_20260919_133706.md`,
never committed by the session that produced it — read directly from the main checkout, since git
worktrees do not share uncommitted files). One challenged query out of ten: navigation 329ms,
button in the DOM 535ms, trigger fired 538ms, real results 3012ms, verdict `SUCCESS_CHALLENGED`,
trigger mechanism `js_click` (a deep-queried `.click()` reaching through shadow roots, `isTrusted:
false`). `cdp_dispatch` (a real `Input.dispatchMouseEvent`) was available as a fallback and never
needed. Q3 (does a solved challenge carry over) came back `CONFOUNDED_FRESH_PROFILE_ALSO_UNCHALLENGED`
— nothing built here assumes carry-over.

`src/search/engines/brave.py` before this milestone treated any challenge as a dead end:
`_wait_for_results` polled for containers, `pow_link` short-circuited it (the prior milestone's
fix), and an empty result came back without ever attempting the button.

## The localization hole, found in review before any code shipped

The first draft's click trigger matched button text against `['verifizieren', 'verify', "i'm not
a robot", 'i am not a robot']` — the probe's own vocabulary, proven live. Review caught the defect
before it shipped: Brave localizes the challenge page, the probe's one live sample was one
language (German, because the machine that ran it asked for German), and a challenge served in a
third language would leave the button unclicked with NO visible trace — indistinguishable from an
ordinary empty page. This is the same shape of defect as the marker-reflection bug this same area
already fixed once, now one level removed (matching TEXT to find a button, instead of matching
TEXT to detect a block) — flagged explicitly: do not fix it by guessing more languages into the
list.

## Two directions, both tested live before choosing

**Direction 1 — force a single deterministic language.** Tried `NetworkCommands.set_extra_http_headers`
on the tab with `Accept-Language: en-US,en;q=0.9` (tab-scoped via pydoll's CDP session routing —
confirmed by reading `Tab._execute_command`, which resolves a `session_id` and attaches it to every
command, so this does NOT touch other engines' tabs the way changing `src/search/browser.py`'s
shared `build_options()` would have). Live result: navigated to an ordinary Brave query with the
header forced, `document.documentElement.lang` still read `de-de`. **Confirmed dead, not assumed
dead** — Brave's language decision is not driven by the `Accept-Language` header from this
vantage point (almost certainly IP/GeoIP-based, which nothing in this codebase can change).
`pydoll`'s `EmulationCommands` has no `set_locale_override` in the installed version either. This
direction is closed; do not re-attempt it without a different mechanism in hand.

**Direction 2 — key the click on structure instead of words.** The reviewer's own supporting
evidence ("9 of 9 unchallenged queries had no button candidate") was re-checked against what it
actually measures: the probe's `button_candidates` field is ALREADY text-filtered, so that evidence
supports "no TEXT-MATCHING candidate", not "no button element of any kind". Checked directly, live,
against three ordinary un-challenged queries, polling with an UNFILTERED deep query for
`button, [role="button"]` (through shadow roots) at the same cadence production would: real
Brave results pages carry DOZENS of buttons — search-form buttons, a "header-button" cluster, an
"ask-button", carousel prev/next, per-result "kebab" menus, "Mehr"/"Mehr anzeigen" (German "show
more") footer buttons — all Svelte-framework chrome (`class="... svelte-xxxxx"`), and in all three
samples these render in the SAME initial paint as the result containers (`count > 0` already true
on the very first poll). An unfiltered "click whatever button is there" rule would have clicked
real page chrome on an ordinary page — this was a real, evidenced risk, not a hypothetical one,
and ruled out a pure-structural click trigger.

## The design that survived both checks

Split "what triggers a click" from "what gets recorded":

- **The click stays text-gated** — same narrow, evidence-backed EN+DE vocabulary as the first
  draft (`verify`/`i'm not a robot`/`i am not a robot`/`verifizieren`). This is the only mechanism
  with live confirmation of being SAFE (never matched Brave's own page-shell buttons in the
  samples checked) as well as WORKING (matched and clicked the real live challenge button). Not
  expanded with guessed languages, per the explicit instruction.
- **A separate, UNFILTERED structural fact (`button_present: bool`) is computed in the SAME
  `_JS_POLL` round trip, at zero extra network/CDP cost**, and attached to the diagnosis on every
  branch, success included. This is the answer to "the diagnosis must make an unmatched button
  visible rather than silent": `button_present=True` with `challenge_triggered=False` means a
  button-shaped element existed on an otherwise-empty page and nothing matched it — worth a human
  looking at, whatever language it turns out to be — without ever risking an unsafe click itself.
  Both `_JS_POLL` and the separate `_JS_CLICK_CHALLENGE` (fired once, only when a text match is
  found) share one JS fragment (`_JS_DEEP_BUTTONS`, a shadow-root-crossing button finder) composed
  via plain Python string concatenation — this is NOT the probe's own composition code, just the
  same general (and now necessary) technique, independently written, much smaller than the probe's
  version (no candidate rects, no verifying-marker text, no `cdp_dispatch` — see below).
- `cdp_dispatch` was deliberately NOT ported. The probe's own live sample showed `js_click` alone
  sufficient — Brave does not appear to gate on `isTrusted` — and porting an untested fallback
  mechanism (real synthetic mouse events via CDP) for zero observed benefit is exactly the kind of
  complexity this milestone's constraints warn against adding. If a future live run shows
  `js_click` failing where `cdp_dispatch` would have succeeded, that is the evidence needed to add
  it; none exists yet.

`challenge_triggered: bool` (did this run actually click something) is attached the same way as
`button_present` — every branch, success included, at zero extra cost (both are already known in
Python memory from the poll loop; attaching them is not a DOM read). This is a deliberate departure
from the codebase's general "DOM facts stay empty-only on success" convention (documented in
`src/search/DOCS.md`'s Gotchas): that convention exists to avoid paying for an unneeded
`_diagnose(tab)` call, which these two fields never require. Omitting them on success (mojeek's own
existing, narrower pattern) would make a solved-challenge success indistinguishable from an
ordinary one — directly the opposite of what was asked for. `challenge_triggered` reuses mojeek's
exact field name for the same concept (the one deliberately-shared name across two engines'
diagnosis shapes, noted in `src/search/engines/DOCS.md`).

`_log_empty_result` now has four distinguishable outcomes instead of two: a button seen but never
clicked (warning, the "not silent" case), a button clicked but no results within budget (warning,
distinct wording), a genuine `pow_link`/marker block (warning, unchanged), plain empty (debug,
unchanged).

## What stayed exactly as the prior milestone left it

`MAX_WAIT_CYCLES`/`WAIT_INTERVAL` (20 × 0.3s = 6.0s) untouched — the measured real solve (~2.7s of
loop time, excluding the ~329ms navigation `go_to()` already accounts for before the loop starts)
fits with real margin against the existing budget, so there was no reason to touch the existing
loop's shape, matching the instruction to reuse it rather than build a new one. `pow_link`'s
existing fast-exit (checked every cycle, before the button check) is untouched and still wins
immediately — a genuine hard block never waits for a button that was never there.

## Verification before writing any test

Before touching `dev/tests/`, the new JS was run directly against all six fixtures in
`dev/brave_return/fixtures/` via a throwaway script (not committed, `/tmp`): `results_no_challenge.html`
→ found, 3 results, no click attempted. `button_challenge_success.html` (light DOM) → found, 1
result, `challenge_triggered=True`. `button_challenge_success_shadow.html` (shadow-hosted button) →
same, confirming the deep query crosses shadow roots correctly. `pow_link_block.html` → not found,
`challenge_triggered=False`, `button_present=False` — the prior milestone's fast-exit untouched.
`button_challenge_stuck.html`/`button_challenge_refused.html` (budget scaled down for the check
only) → not found, `challenge_triggered=True`, `button_present=True` — attempted, unresolved,
correctly distinguishable from a never-challenged empty page. End-to-end success-path latency
against the local fixture, 5 runs: 25–49ms — the added deep-button query (now part of the same
single `_JS_POLL` round trip that already existed) costs nothing measurable.

## Tests

`dev/tests/test_brave_engine.py` (pre-existing, already imports from `src.` — extended, not
replaced). The three marker-reflection-milestone tests' diagnosis assertions were updated for the
new always-present `challenge_triggered`/`button_present` keys (they would otherwise fail on an
exact-dict-equality check against the new shape). Four new tests use a SECOND fixture server
(`_start_real_fixture_server`, `SimpleHTTPRequestHandler(directory=...)` pointed directly at
`dev/brave_return/fixtures/`) to run against the real, previously-built fixtures rather than
reimplemented copies: light-DOM solve, shadow-DOM solve, a stuck challenge (budget monkeypatched
down — unlike the `pow_link` timing fix in the prior milestone, there is no "should exit fast"
correctness contract here to protect; a genuinely stuck challenge has no reliable early-exit
signal, so there is nothing a faster test constant could hide), and the real `results_no_challenge.html`
fixture as a control proving an ordinary page never attempts a click. All 7 fixture-driven tests
(3 existing + 4 new) were confirmed, via `git stash` of `brave.py` back to the prior milestone's
code, to fail on that code and pass on this one. Full suite: 442 passed (up from 438 — 4 net new
tests, `dev/tests/`, ~26s).

## Live verification

Ordinary query (`kubernetes ingress tls configuration`) through the real CLI: Brave 10/10,
1742ms, `diagnosis = {"challenge_triggered": false, "button_present": false, "document_status_chain":
[200], "http_status": 200}` — the unaffected success path, confirmed live.

The curl method (25 plain requests, ordinary browser UA, against `search.brave.com`) was used
exactly once, as instructed ("use it sparingly"): the first 10 returned 200, the remaining 15
returned 429. A real CLI search fired immediately afterward landed the browser navigation itself
in a 429 (`document_status_chain: [429]`, `marker: "captcha"`, `pow_link: true`) — the pre-existing
hard-block path, still correct and still fast: `927ms`, `challenge_triggered: false`,
`button_present: false` (no button ever shown on this shape, matching every prior observation).
This is the SAME shape the prior milestone already fixed the timing for; unaffected by this one.

A second attempt, ~55s later (letting the acute 429 window decay, no additional curl requests
fired), landed on an ORDINARY, never-challenged success — `document_status_chain: [200]`,
`challenge_triggered: false`. The soft button-challenge state the probe's report captured live
was NOT reproduced in this session: whatever transitional window exists between "actively
429-ing" and "back to normal" either closed faster than ~55s for this burst, or this specific
address/timing didn't pass through it at all this time. Per the explicit "use sparingly"
instruction, no further curl bursts were fired to keep hunting for that window — the fixture-driven
tests (built from the report's own captured shape, plus the pre-existing `button_challenge_success*`/
`button_challenge_stuck` fixtures) remain the primary verification for the challenge-solving path
itself; live verification here confirms the two paths around it (ordinary success, hard block) are
unaffected, which is what a live run can actually add on top of the fixtures without spending the
scarce resource further. Whoever next gets a live soft-challenge (via this method or otherwise)
should capture the raw page (title, `documentElement.outerHTML` or similar) before solving it —
nothing in this codebase does that today, and it would settle, with real evidence instead of a
single one-word screenshot description, exactly what language(s) and DOM shape production actually
meets in the wild.

## Review round: button_present was leaking into success, fixed architecturally (2026-09-19)

Code review caught a real defect in `button_present` as first shipped. The field was tracked
STICKY across `_wait_for_results`'s whole poll loop — set `True` the moment ANY cycle saw a
button-shaped element while `count` was still 0 — and attached on every diagnosis branch including
success, on the reasoning that both new fields were already known for free from the loop (no
extra DOM read). That reasoning covered the COST correctly but missed the CORRECTNESS problem:
this session's own earlier live check already knew real Brave results pages carry dozens of
ordinary chrome buttons (header, search-form, "Ask", carousel, footer). If any of that chrome
renders even one poll cycle before the result containers do — plausible on a slower load, this
session's evidence for it was thin — an entirely ordinary, never-challenged query would latch
`button_present=True` and carry it straight into a genuine success record. The field exists
specifically so a reader can tell a challenge we could not act on apart from an ordinary page;
a field that is ALSO sometimes true on ordinary successes cannot be read for that purpose, which
is the same silent-failure shape this whole area exists to close, one level further down.

### What was actually measured, honestly

Told to check first rather than guess: an 8-query live multi-cycle measurement was attempted
(polling each query at the real `MAX_WAIT_CYCLES`/`WAIT_INTERVAL` cadence, watching for a
`count==0 and button_present==True` moment before results). It came back 8/8 "positive" — but
every single one showed `count` staying at 0 for the FULL 20-cycle budget, never resolving to
real results at all. A follow-up single-query check with a full `_diagnose(tab)` read at the end
explained why: `pow_link: true`, title `"Captcha - Brave Search"` — this session's own testing
address was, by that point, under an actual Brave rate-limit from the day's cumulative live
requests (the curl burst earlier, plus this session's several `cli.py search_web` live-verification
runs, plus the measurement attempts themselves). The 8-query result measures a genuinely
rate-limited state, not ordinary traffic, and is not usable as the answer to the question asked.

One useful thing did come out of the contaminated run: in that trace, `pow_link` was true on the
SAME poll cycle `button_present` was. `_wait_for_results` checks `pow_link` strictly before
updating the sticky `button_present` on each cycle (`if state["pow_link"]: return ...` comes
before `if state["button_present"]: button_present = True`), so in production this exact trace
would have returned at cycle 1 via the `pow_link` fast-exit with `button_present` still `False` —
confirming the EXISTING check ordering already protects the hard-block case. It says nothing
about the soft, no-`pow_link` staggered-render case the review was actually asking about.

The only CLEAN (pre-contamination) live data available was the earlier 3-query single-poll check
from earlier in this same milestone (`postgres index bloat diagnosis` and 2 others): all 3 showed
containers and the full button chrome present TOGETHER on the very first poll, no staggering
observed. That is 3 single-poll data points, not a multi-cycle measurement, and not enough to
assert a low false-positive rate with any confidence — particularly since the one thing this
session now knows for certain is that its own address is presently in a degraded state from
today's volume of live requests, which is exactly the kind of condition (server load, throttled
responses) most likely to produce the staggered rendering this whole question is about, and
exactly the condition this session can no longer cleanly test now that it has induced one.
No further live queries were fired to chase a clean number — the user has since said they will
run live verification themselves; hammering the same already-strained address further to settle
a number that has a zero-live-request-cost alternative fix available was not a reasonable trade.

### The fix, and why it does not need that number

Rather than pick a persistence threshold (require the sticky fact to hold for N consecutive
cycles before latching) — which WOULD need a real measurement of the staggering distribution to
size correctly, exactly the number not cleanly available — the fix is architectural: `button_present`
is now attached ONLY on the two branches that return empty results (`if not found:` and the
zero-parsed-after-`found`-branch), never on the one true success branch (`if results:`). This
closes the leak unconditionally, independent of how long any staggering window actually is,
because a genuine success means the query already got what it needed — whatever else was or
wasn't on the page during the load race stops being interesting the moment real results exist.
`challenge_triggered` is untouched, still attached on every branch including success, per explicit
instruction — it answers a different question ("did we act on something") that stays meaningful
on a success (a solved challenge IS a success, and that is exactly the case worth being able to
see).

### Fixture coverage, and what it does and does not prove

`test_unrelated_button_before_containers_never_leaks_into_success_diagnosis`
(`dev/tests/test_brave_engine.py`) is a new, offline, fully deterministic fixture: a page with an
unrelated `<button>Menu</button>` present from the first byte, result containers appended via
`setTimeout(..., 500)`. Confirmed to fail against the pre-fix code (via `git stash`) and pass
against the fix. This proves the SPECIFIC mechanism (a button rendering strictly before containers,
by a comfortable 500ms margin) cannot leak into a success diagnosis, regardless of how long the
real-world staggering window turns out to be — since the fix does not depend on the window's
length at all. **It does NOT prove, and is not offered as proof of, how often real Brave traffic
actually experiences this staggering, nor how long that window typically is** — that number was
sought honestly (see above) and not obtained cleanly this session. The fixture is a correctness
proof for the chosen fix's mechanism, not a frequency measurement; the two should not be
conflated by a future reader.

Full suite after this round: `443 passed` (`dev/tests/`, ~28s; +1 net new test).
