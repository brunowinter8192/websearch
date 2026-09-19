# A cancelled engine's diagnosis no longer has to be None (2026-09-19)

## Why now

`_engine_with_timing` (`src/search/search_web.py`) wraps every engine call in
`asyncio.wait_for(engine.search_with_reason(...), timeout=ENGINE_WATCHDOG_TIMEOUT)`. On timeout the
`except` branch returned `diagnosis=None`, unconditionally, for all 9 engines, always. This had
already cost real information once: a genuine Brave `pow_link`/429 block that ran into the 6.0s
watchdog lost its `pow_link` and `http_status` facts entirely — the log kept nothing but
`TIMEOUT_WATCHDOG` and a duration. It was about to cost more, for a reason new as of the immediately
preceding `marker_reflection` milestone: Brave's own block page describes a temporary cookie access
token granted after a solved challenge, that token lives in the browser profile, and the profile is
now a fresh `tempfile.mkdtemp()` deleted at the end of every run (`process-docs/browser_posture/`).
If Brave hands out that token at all, no run can inherit a solved state from an earlier one, so a
button-challenge click becomes the ordinary path rather than the rare one — and a click that
occasionally overruns 6.0s is exactly the event this whole mechanism needed to be able to see.

## Read first, per instruction: `process-docs/search_pipeline/2026-09-05_guessed_verdict_removal.md`

That milestone drew one line and kept redrawing it: *"A status describing what OUR OWN code did...
is a fact and stays... A status guessing what the REMOTE side meant... is a verdict and goes."* A
concrete case it fixed: `roboter-bausatz.de` logged `EMPTY_BLOCK` for mojeek because the query
substring `roboter` contains `robot`, one of mojeek's own block keywords — a guessed verdict,
indistinguishable from a real block, permanently.

This milestone is a direct continuation of that same rule, not a new one: `diagnosis_partial` and
`elapsed_ms` (below) describe exactly what OUR OWN code observed and when, never a guess about what
the remote side was doing when the cancellation happened. The negative case matters exactly as much
as the positive one and is tested for directly (see Tests, below): if an engine's poll loop never
reached even one checkpoint before cancellation, the diagnosis stays `None` — inventing a fact that
was never observed would be worse than the `None` it replaced, not an improvement on it.

## The mechanism

`asyncio.wait_for(coro, timeout)` cancels `coro`'s own `Task` — not the caller. A `ContextVar` set
inside that Task does not propagate back to the caller either: each `asyncio.Task` gets its own
copied context at creation, a plain fact of asyncio's own design, not something this project's code
controls. The only channel that survives a cancelled Task and is visible to whoever cancelled it is
a mutable object the cancelled code was handed by reference and wrote into before the cancellation —
the same principle `document_status.py`'s `status_chain` list already used for network facts, just
never previously exposed past `search_with_reason`'s own return statement.

`search_with_reason` gained a 4th, keyword-defaulted parameter: `partial: dict | None = None`, on
`BaseEngine` and all 9 concrete engines. `_engine_with_timing` creates `partial = {}` before
`asyncio.wait_for`, passes it in. Each of the 7 browser engines' own poll loop writes into it on
EVERY iteration, using facts it had already computed that same iteration for its own control-flow
decision — no new DOM round trip, the success path is unaffected either way (the loop already runs
there too; it just returns before the `except` branch is ever reached). `document_status.py`'s new
`update_partial(partial, status_chain, t0, facts)` does the actual merge, reusing the pre-existing
`attach_document_status` internally rather than duplicating its logic. On any exception —
deliberately not gated to `asyncio.TimeoutError` specifically, since the same channel and the same
"was anything actually observed" question apply just as well to a genuine mid-poll crash —
`_engine_with_timing`'s `except` branch uses `{**partial, "diagnosis_partial": True}` if `partial`
has anything in it, `None` otherwise.

Per engine, what gets written on each poll checkpoint: brave writes the richest set
(`containers_found`/`pow_link`/`button_present`/`challenge_triggered` — everything it already
computes for its own control flow that cycle); mojeek reuses its own pre-existing `trace` dict,
narrowed to the two fields (`containers_found`, `challenge_triggered`) that are actually part of
its documented diagnosis contract — `link_count`/`poll_count` stay internal, not smuggled into the
snapshot just because they were free; google/duckduckgo/startpage/bing/yandex write the one fact a
raw-count-only loop genuinely has: `containers_found: False`. `openalex`/`scholar` accept the
parameter (required — `_engine_with_timing` calls every selected engine positionally with 4 args
now, uniformly) but never write to it: a single `httpx` call has no intermediate checkpoint, and
openalex's own internal timeout (3.6s) already sits under the 6.0s watchdog, so the cancellation
this exists for is not expected to fire there in practice.

## Point 1 — staleness, closed with a cheap observed number

A partial dict written at 200ms and one written at 5900ms mean very different things but would have
looked identical without a timestamp. Closed with `elapsed_ms` — `update_partial` computes
`round((time.perf_counter() - t0) * 1000)` internally, where `t0` is captured as the literal first
line of every engine's own `search_with_reason`, matching the same reference frame
`_engine_with_timing`'s own `search_ms` uses (measured from just before the coroutine starts). This
is a genuinely free number — `time.perf_counter()` is a wall-clock read, not I/O — folded into the
SAME `update_partial` call every engine already needed for the network facts, not a separate
mechanism. The field contract note in `engines/DOCS.md` states the consequence explicitly:
`diagnosis_partial: True` means every OTHER field in that dict describes the state as of the last
completed checkpoint, not a concluded outcome — `containers_found: False` normally means "the loop
exhausted its own budget and never found anything"; under `diagnosis_partial: True` it means only
"not yet, as of `elapsed_ms` — the loop never got to finish, the next cycle is unknown."

## Point 2 — what the verification below does and does not prove

Live verification (below) forces real `TIMEOUT_WATCHDOG` records via a deliberately low
`engine_timeout` passed to `search_web_workflow` directly. This is the right way to test the
mechanism and was asked for explicitly. **It is not the same event as a genuine Brave
button-challenge click overrunning the real 6.0s budget — nobody has observed that live, not this
session, not before it.** The forced-timeout runs prove: the channel works, facts written before a
real `asyncio.wait_for` cancellation of REAL running engine code survive it, `elapsed_ms` is
populated correctly, the negative case (nothing captured) still yields `None`, and the success path
is provably unaffected (byte-identical diagnosis shapes on a normal run, checked directly against
the pre-existing documented shapes). None of that is the same claim as "this is what a genuine
Brave overrun looks like in production" — that specific event, if and when it happens, is now
observable for the first time; whether it happens at all, and what it looks like when it does, is
future evidence, not something this milestone manufactures or should be read as having already
shown.

## Point 3 — backward compatibility, confirmed by running, not by reading

`search_with_reason`'s abstract signature gained a parameter that 9 engines implement and dev
scripts call. Confirmed live, in this order: `grep -rln "search_with_reason" dev/ --include="*.py"`
outside `dev/tests/` found exactly 2 files — `scholar_http_probe.py` (defines its OWN independent
`search_with_reason` on a standalone probe class that does not inherit `BaseEngine`, structurally
unaffected by anything on the abstract class) and `no_google_burst_smoke.py` (calls
`engine.search_with_reason(query, "en", 10)`, 3 positional args, no `partial` — exactly the shape a
keyword-defaulted 4th parameter is backward compatible with). Both imported cleanly via
`python -c "import ..."` after `sys.path.insert(0, "dev/search_pipeline")` — a real import, not a
read of the source. All 9 engine modules (`base` + 7 browser + `openalex` + `scholar`) imported
cleanly the same way. Then a REAL live call, not mocked: `OpenAlexEngine().search_with_reason(
'asyncio python', 'en', 3)` — 3 positional args, the exact old-style shape every dev script and
`BaseEngine.search()`'s own delegation still uses — returned 3 real results from the live OpenAlex
API with no `TypeError`, `partial` correctly defaulting to `None`; `BaseEngine.search()` itself
(the delegation `no_google_burst_smoke.py` and ~40 other dev scripts reach indirectly) was called
the same way immediately after, same result.

## Tests

`dev/tests/test_query_logger.py`: `_make_mock_engine_with_reason` gained a `partial_facts`
parameter (writes into the caller-supplied `partial` before its own `asyncio.sleep(delay)`, if
given). `test_engine_with_timing_timeout_preserves_facts_written_before_cancellation` proves the
positive case end to end against the mock; the pre-existing `test_engine_with_timing_timeout`
(unchanged mock, no `partial_facts`) proves the negative case — `diagnosis` stays `None` when
nothing was captured, unchanged behavior, still tested.

`dev/tests/test_brave_engine.py`:
`test_stuck_challenge_cancelled_mid_loop_leaves_partial_facts_behind` is the one test in this
milestone that cancels REAL running engine code, not a mock — the real `button_challenge_stuck.html`
fixture (button present from byte one, never resolves), `asyncio.wait_for(BraveEngine().
search_with_reason("fixture query", partial=partial), timeout=0.3)` from outside, mirroring
`_engine_with_timing` exactly. Confirmed non-flaky on the first real run: `partial` held
`containers_found=False`, `pow_link=False`, `button_present=True`, `challenge_triggered=True` (the
click reliably lands within the first one or two 0.05s-interval iterations, well inside the 0.3s
budget), plus `document_status_chain`/`http_status`/`elapsed_ms`.

`dev/tests/test_mojeek_engine.py`: `_await_results` gained 3 new positional parameters
(`status_chain`, `t0`, `partial`) — all 6 existing call sites already used `deadline=`/`target=`
keywords, so a local `_run_await_results(tab, deadline, target, partial=None)` wrapper supplies the
3 new ones without rewriting each site by hand.

Full suite: 452 → 453 passed (mostly rewritten/extended in place rather than net-new — the
signature change touched call sites in `test_mojeek_engine.py` and the mock helper in
`test_query_logger.py` before any new test could even run).

## Live verification

Baseline (unforced, default 6.0s watchdog), `kubernetes readiness liveness probe difference`: every
engine's diagnosis shape byte-identical to what `engines/DOCS.md` already documented before this
milestone — `brave: {"challenge_triggered": false, "document_status_chain": [200], "http_status":
200}`, `bing`/`startpage`/`duckduckgo`/`mojeek`: `{"document_status_chain": [...], "http_status":
200}`, `yandex`'s genuine block record unchanged shape. No `diagnosis_partial`/`elapsed_ms`
anywhere. The success/no-forced-timeout path is provably untouched, not just argued to be.

Forced (`engine_timeout=1.0`, then again at `1.8`, both via `search_web_workflow(...)` called
directly — not through `cli.py`, which does not expose `engine_timeout`, the same direct-call shape
`fetch_search_results` already uses, still the real production code path, real engines, real query
log write): every browser engine plus openalex hit real `TIMEOUT_WATCHDOG`. Six of eight showed
`diagnosis: null` both times — genuinely nothing was captured in that window, the honest answer, not
a bug. `mojeek` carried facts both times:

```json
{"containers_found": false, "challenge_triggered": true, "document_status_chain": [200],
 "http_status": 200, "elapsed_ms": 869, "diagnosis_partial": true}
```

and, on the second (1.8s) run:

```json
{"containers_found": false, "challenge_triggered": true, "document_status_chain": [200],
 "http_status": 200, "elapsed_ms": 1769, "diagnosis_partial": true}
```

`challenge_triggered: true` in both means mojeek's own ALTCHA `verify()` was genuinely dispatched
before the cutoff — the exact kind of fact that used to vanish, now on record, `elapsed_ms` showing
how close to the cutoff each checkpoint actually was. Two real records, not cherry-picked from a
larger batch — the first two forced-timeout runs attempted, both kept. No further forced-timeout
runs were made once the mechanism was demonstrated cleanly, matching this project's standing
"verify, don't over-verify" practice from adjacent milestones.
