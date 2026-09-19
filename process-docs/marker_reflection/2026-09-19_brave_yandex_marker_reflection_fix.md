# Brave and Yandex discarding results because of their own block-marker text (2026-09-19)

## The bug

`src/search/engines/brave.py` and `src/search/engines/yandex.py` both decided "this page is a
CAPTCHA block" by scanning text the page itself controls very loosely — Brave scanned
`document.body.innerText` + `document.title` for substrings like `captcha`; Yandex scanned the
full navigated URL string (path AND query string) for substrings like `showcaptcha`. Both checks
ran BEFORE the engine ever looked at whether real result containers existed on the page. A
completely ordinary, fully-populated results page that happened to contain one of these substrings
anywhere in its text (in the query the user typed, echoed into the page title or into a search
result's own content; or in a URL's `?text=` parameter, which also echoes the raw query) was
discarded outright, ten real results and all.

`src/search/engines/startpage.py` and `src/search/engines/bing.py` never had this defect, despite
having near-identical marker word lists. The reason is ordering, not marker quality: both of them
only call `_diagnose(tab)` AFTER `_wait_for_results()` has already established, via a real
`querySelectorAll` container count, that the page is empty. A successful page with 10 real
containers never reaches the marker scan at all. `brave.py` (and, for a related but distinct
reason, `yandex.py`) called their block check first.

## The production evidence (read from `src/logs/query_log.jsonl`, 131 `workflow_summary` records,
## 2026-09-05 through 2026-09-19, main-repo checkout — the worktree's own copy starts empty)

Brave: 62 of 131 runs carried `marker` or `pow_link` in the diagnosis.
- 53 (all on 2026-09-15, one burst) had `document_status_chain: [429]`, `pow_link: true`, and the
  generic `title: "Brave Search"` — a real rate-limit/challenge page. Not this bug. Left untouched.
- 9 had `document_status_chain: [200]`, `pow_link: false`, and the ordinary personalized
  `title: "<query> - Brave Search"` — the bug. 6 of the 9 had the marker word literally inside the
  query text (`cloudflare turnstile captcha widget verify programmatically`,
  `yandex showcaptcha spravka cookie after`, `mojeek captcha verification blocked automation`,
  `mojeek community altcha captcha challenge`, `altcha proof of work widget`,
  `yandex captcha why am i seeing this support`).

Yandex: 101 of 131 runs took the `_is_block_url` branch (`containers_found: null` in the
diagnosis). 100 were real redirects to `https://yandex.com/showcaptcha?...` (title `"Are you not
a robot?"`). 1 — query `yandex showcaptcha spravka cookie after solving captcha` — had
`url: "https://yandex.com/search/?text=yandex+showcaptcha+spravka+cookie+after+solving+captcha&lr=100"`,
the ordinary, un-redirected search URL. `_is_block_url` matched the substring `showcaptcha`
sitting inside the `?text=` parameter — the query itself — not inside the path.

## The DS18B20 anomaly, and why the 9 stayed one population

3 of Brave's 9 false positives carried NO marker word in the query text at all:
`DS18B20 1-wire dropout compressor fridge electrical noise relay switching`,
`altcha widget auto onload verify programmatically`, `altcha widget server verification cookie`.
For all 3 the `title` field also had no marker word (title = the personalized results title), so
whatever matched had to be in `document.body.innerText` from a source other than the query.

The DS18B20 case was checked directly against session context: the two Brave calls immediately
bracketing it in the same run (`DS18B20 disappears from /sys/bus/w1/devices reboot fixes` ~40s
before, `linux w1 slave_ttl module parameter timeout search removes slave` ~17s after) both
returned `OK` with 10 results — ruling out a session-level block (the real 429 cluster blocks
consecutive queries; this one didn't). No literal HTML capture exists for this historical run —
nothing in this codebase captures raw Brave HTML on a marker hit — so the exact string that
matched cannot be confirmed. Working hypothesis, stated as a hypothesis: one of the ten organic
result snippets on that page contained the word "captcha" as part of "re**CAPTCHA**" — Google's
form-protection disclaimer boilerplate ("This site is protected by reCAPTCHA and the Google
Privacy Policy...") that appears in the crawled text of a large fraction of the web, including
exactly the kind of tech-support forum pages DS18B20 troubleshooting turns up. This is NOT
confirmed against raw HTML; it is the only mechanism consistent with every other fact in hand
(no query overlap, no session-level pattern, ordinary title, immediate-neighbor success).

This does not split the population. All 9 are the same defect (a substring-of-page-text decision
made before checking for real containers) with three different sources of the matched text: the
query reflected into the title, the query reflected into an organic result's own content (as in
the Yandex URL case), or unrelated organic content that happens to contain the substring. The fix
does not care which source produced the match — it never runs the scan at all when containers are
already known to exist.

An earlier investigation (`process-docs/brave_return/2026-09-19_brave_pow_probe_blind_run.md`,
written before this fix) reached "Brave challenges on the content of the search term" from the
same 2026-09-15-onward data, but its own query list has only 7 entries and silently omits the
DS18B20 case — it was never explained there either.

## The fix

`brave.py`: removed the unconditional `asyncio.sleep(1.5)` + `_diagnose(tab)` that ran
immediately after navigation, before `_wait_for_results()`. `search_with_reason` now calls
`_wait_for_results()` first; `_diagnose(tab)` only runs if that returns `False`. This is the exact
shape `bing.py`/`startpage.py` already used. Side effect: the success path got FASTER, not slower
— it no longer pays for the fixed 1.5s sleep or the now-skipped `_diagnose` JS round trip.
`containers_found` can no longer be `None` for this engine (there is no branch left that
short-circuits before `_wait_for_results` runs) — it is `False` or `True`, same as
bing/startpage/duckduckgo.

`yandex.py`: `_is_block_url` now reads `urlparse(url).path` only, never the full URL string. The
early short-circuit (checking `current_url` right after navigation, before `_wait_for_results`)
was deliberately KEPT in place — unlike Brave, Yandex has no equivalent of a JS round trip to pay
for here (`tab.current_url` is a cheap property read, not a DOM script eval), and the engine's own
DOCS.md already documented this as an intentional "fast short-circuit" so a confirmed redirect
doesn't burn the full container-wait budget. The defect was never really about ordering for this
engine — it was that the check read a URL component (the query string) that is always,
unavoidably, the user's own text. Scoping to `path` fixes that directly: Yandex's own redirect
target (`/showcaptcha`) lives in the path, confirmed live in 100/100 genuine cases in the log; the
query string never does.

Neither change touches `pow_link` (Brave) or the HTTP 429 path, or the marker word lists
themselves — per the task constraints, no blacklist, no query-string stripping, no new signal
invented. Both fixes make an existing, already-reliable signal (a real container count; a real
redirect path) win over an unreliable one (arbitrary page text) by construction, not by pattern
special-casing.

## Other engines checked, not touched

`google.py`, `duckduckgo.py`, `mojeek.py`, `startpage.py`, `bing.py`, `openalex.py`, `scholar.py`
were read in full and checked against the production log. None showed the defect:
- `startpage.py`/`bing.py`: already diagnose only after establishing emptiness (the pattern this
  fix brings brave.py in line with). 0 production evidence of any false block.
- `duckduckgo.py`: diagnoses before waiting (same ordering as old brave.py), but its signal is a
  CSS selector count (`form#challenge-form`), not scanned text — a query cannot inject a DOM
  element. 0 occurrences of `challenge_form: true` in 131 runs.
- `google.py`: gates on a URL PATH segment (`/sorry/`, requires literal slashes) — already scoped
  the way this fix scopes yandex.py. No false positives found.
- `mojeek.py`: its `marker` diagnosis field is always `None` (never populated by its own
  `_JS_DIAGNOSE`, which returns `challenge_widget`/`challenge_state`/`captcha_note` instead); the
  actual gate is a link count plus a real custom-element method (`altcha-widget.verify`), not text.
- `openalex.py`/`scholar.py`: no DOM/text scan at all (HTTP status codes, one XPath structural
  check for scholar).

## Tests

`dev/tests/test_brave_engine.py` and `dev/tests/test_yandex_engine.py` (both pre-existing files,
extended — new files under `dev/` cannot import from `src.`, so this is not optional) gained
fixture-driven, real-pydoll-Chrome, real-JS tests. A pure-Python fixture cannot exercise this bug:
the thing under test IS the JS (`_JS_DIAGNOSE`/`_JS_PARSE`/`_JS_WAIT`) reading real DOM state, so a
real browser executing real JS against real local HTML is required — matching why
`dev/brave_return/test_brave_pydoll_core.py` and `dev/mojeek_return/test_mojeek_pydoll_core.py`
both do the same thing for their own (different) purposes.

Mechanism: `dev/tests/conftest.py`'s `_no_real_browser_launch` autouse fixture only traps
`src.search.browser.Chrome`. The new tests never touch that module — they monkeypatch `brave.py`'s
/`yandex.py`'s own already-imported `new_tab`/`kill_tab` names directly to a small pydoll `Chrome`
instance started via pydoll's native `options.headless = True; await browser.start()` (confirmed
directly: this is a complete, simple, working launch path — no need for the elaborate app-bundle/
`open -g`/focus-watchdog machinery `dev/brave_return/_brave_probe_launch.py` builds, none of which
exists for platform-UX reasons irrelevant to an automated headless test). A
`http.server.ThreadingHTTPServer` on `127.0.0.1:0` serves canned HTML by exact path, ignoring the
query string — same shape as the two probe scripts' fixture servers, inlined rather than shared
since a new file with no `from src.` import would have been fine to add but wasn't needed for just
this.

Six new tests total (3 brave, 2 yandex end-to-end + 2 pure-`_is_block_url` — one of the two
`_is_block_url` tests already existed): each fixture-driven test was run BOTH against the fixed
code and, via `git stash push -- src/search/engines/<brave|yandex>.py`, against the original code,
confirming every new test fails on the original and passes on the fix. The one exception worth
noting: the genuine-block fixture test for Brave also fails on old code, but not because it
detects a behavior regression in whether it blocks — both old and new code correctly return zero
results for a genuine block. It fails because old code's immediate-bail branch hard-codes
`containers_found = None`, while the fixed code (no immediate-bail branch left) reports `False`
via the same path every other engine already uses. That is an intentional, expected contract
change, not evidence the test is checking the wrong thing.

Full suite after the change: `438 passed` (`dev/tests/`, ~19s).

## Live verification (2026-09-19, against real Brave/Yandex, this worktree's own
## `src/logs/query_log.jsonl` — starts empty, separate from the main checkout's historical log)

`./venv/bin/python cli.py search_web "cloudflare turnstile captcha widget verify programmatically"`
— the exact query from the original bug report. Before this fix: Brave 0/10. After: Brave 10/10,
Yandex 10/10, all 8 engines OK. Diagnosis for both: `{"document_status_chain": [200],
"http_status": 200}` — the minimal network-only shape, confirming `_diagnose(tab)` was never
called on this success (the "facts, not verdicts" / DOM-facts-are-empty-only-on-success contract
in `src/search/DOCS.md` held).

A second, ordinary query with no marker words
(`"sourdough starter feeding schedule ratio"`) was run as a regression check: Brave 10/10, Yandex
10/10, same minimal diagnosis shape. No latency or behavior change on an unrelated query.

## For whoever picks this up next

If a new false-block report shows up for Brave or Yandex with `containers_found: False/True` (not
`None`) in the diagnosis, it is NOT this bug — the container check already ran and found nothing,
which is a real "Brave/Yandex returned zero results" case, not a block being misread. Only a
`containers_found: None` on Yandex, or ANY reproduction where a personalized results page with a
non-empty title is discarded before `_wait_for_results` gets a chance, would indicate this class
of defect is back.

No raw-HTML capture mechanism exists anywhere in this codebase for a marker hit — if the DS18B20-
style "unrelated organic content" false-positive source needs to be pinned down precisely rather
than hypothesized, that capture would need to be built first (a `_diagnose(tab)` call is cheap
enough to add a `document.body.innerHTML` dump behind, guarded to only fire when `marker` is
truthy — but that is a new capability, not touched here).

## Review round: the block path regressed to timing out (2026-09-19)

Code review caught a real bug in the first pass at the Brave fix above. Before that fix, a genuine
Brave block (the 429/pow-link cluster) took the immediate-bail branch: `sleep(1.5)` + one
`_diagnose` call, roughly 1.6s, landing in the log as `EMPTY` with the full diagnosis (`marker`,
`pow_link`, `title`) intact. After removing that immediate-bail branch, a genuine block had no
early exit left at all — it fell all the way through `_wait_for_results`'s loop, `MAX_WAIT_CYCLES
× WAIT_INTERVAL = 20 × 0.3 = 6.0s`, exactly equal to `ENGINE_WATCHDOG_TIMEOUT` in
`search_web.py`. `_engine_with_timing` wraps the whole `search_with_reason` call in
`asyncio.wait_for(..., timeout=6.0)`, so the wait loop alone was enough to trip the watchdog before
`search_with_reason` ever returned — `asyncio.TimeoutError`, caught by `_classify_engine_exception`,
status becomes `TIMEOUT_WATCHDOG`, and the whole diagnosis dict (`marker`, `pow_link`, `title`,
everything) is lost, not just delayed. This would have silently turned all 53 of the 2026-09-15
genuine-block records into unexplained timeouts.

Measured directly before touching anything (`dev/tests/test_brave_engine.py`'s own genuine-block
fixture, run through `asyncio.wait_for(..., timeout=6.0)` at the real `MAX_WAIT_CYCLES=20`,
`WAIT_INTERVAL=0.3`, no monkeypatching): `TimeoutError after 6.00s`. Confirmed exactly as
predicted before writing a line of fix code.

The test committed in the first pass had quietly conceded this by monkeypatching
`MAX_WAIT_CYCLES=3, WAIT_INTERVAL=0.05` for the genuine-block case only — a tell that the code
under test could not survive the real production constants, which is exactly what happened when
the same fixture was re-run without that monkeypatch.

Fix: `pow_link` was already established (Part 1 of this investigation, and again in this review)
as a signal that never produced a false positive across all 62 marker/pow_link hits in the
production log — unlike free-text `marker`, it is a real DOM element
(`a[href*="pow-captcha"]`), not scanned text. `_JS_WAIT` (container count only) became `_JS_POLL`,
one script returning both `count` and `pow_link` in a single round trip. `_wait_for_results`'s loop
now returns `True` on `count > 0` (found, unchanged) but ALSO returns `False` immediately — without
exhausting the remaining poll budget — the moment `pow_link` is seen, instead of only after
`MAX_WAIT_CYCLES` iterations. This is not a reintroduction of "decide before results are
established": the check runs INSIDE the same polling loop that is still actively waiting for
containers, on a signal that has never once been wrong, and only short-circuits a wait that would
otherwise run to completion anyway with the identical outcome (no results). The orchestrator itself
did not change from the first pass — `_diagnose(tab)` still only runs once `_wait_for_results`
returns `False`, so `containers_found` is still always `False`/`True` for this engine, never the
old `None` sentinel.

Re-measured after the fix, same fixture, same production constants, wrapped in the same 6.0s
`asyncio.wait_for`: `COMPLETED in 0.06s`, `diag = {'marker': 'proof of work', 'pow_link': True,
'title': 'Brave Search', 'containers_found': False, ...}` — full diagnosis intact, two orders of
magnitude under the watchdog. `dev/tests/test_brave_engine.py`'s genuine-block test was rewritten
to assert against the real `MAX_WAIT_CYCLES`/`WAIT_INTERVAL` module constants directly (not
monkeypatched) and to assert `elapsed < 1.0` end to end through `search_with_reason`, wrapped in
the same `asyncio.wait_for(6.0)` `_engine_with_timing` uses — so a future regression back to the
"no early exit" shape fails this test the same way it fails production, not a smaller synthetic
version of the problem.

Re-verified against `git stash` of the previous commit's `brave.py`: the rewritten test now fails
exactly there too (the timing case this time, not just the containers_found-shape case caught by
the two other fixture tests) — confirmed the test would have caught this had it existed before
the first pass shipped.

The equivalent question for `yandex.py` does not arise: its early `_is_block_url` check was never
moved behind `_wait_for_results` in the first pass (kept as the documented "fast short-circuit"),
so it never had this failure mode — `tab.current_url` is a cheap property read, not a JS round
trip inside a polling loop, and it still runs exactly once, immediately after navigation.

## Review round: comments and docstrings pruned, stepdown order fixed

The first pass added a module-docstring expansion and a new banner-comment block to both
`dev/tests/test_brave_engine.py` and `dev/tests/test_yandex_engine.py`, restating context that
already lives in this file. Reverted both files' docstrings back to their original text and
removed the added banners — the two files' PRE-EXISTING docstrings and `_build_results`/
`_is_block_url` banners (from before this session) were left alone, not this session's business.

`brave.py`'s `_build_results`/`_parse_results` order was also fixed while already touching that
section: `_parse_results` is the caller, `_build_results` the callee — stepdown puts the caller
first. `_build_results` now follows `_parse_results`, matching the read-order the rest of the file
already follows (`_wait_for_results` → `_poll_state` → `_diagnose` → `_log_empty_result` →
`_parse_results` → `_build_results`).

## Final numbers after the review round

Full suite: `438 passed` (`dev/tests/`, ~19s), unchanged count from before the review round — the
fixes changed what the existing tests exercise, not how many pass.

Live re-verification, same two queries as before, same worktree-local `src/logs/query_log.jsonl`:
`cloudflare turnstile captcha widget verify programmatically` → Brave 10/10 (search_ms 2326 and
1200 across two runs), Yandex 10/10; `sourdough starter feeding schedule ratio` → Brave 10/10
(search_ms 1214 and 897), Yandex 10/10. Diagnosis on every success record:
`{"document_status_chain": [200], "http_status": 200}` — unchanged shape, confirming the
DOM-facts-empty-on-success contract still holds after the timing fix.

## Recap pass

Two `DOCS.md` files describe the six files this task touched: `src/search/engines/DOCS.md`
(`brave.py`/`yandex.py`, kept current throughout the session, not just at the end — LOC and
behaviour description both re-checked against the final code in this pass) and `dev/tests/DOCS.md`
(`test_brave_engine.py`/`test_yandex_engine.py`, whose entries had gone stale — they still
described the pre-session pure-function-only shape). Both `dev/tests/DOCS.md` entries were
rewritten to cover the new fixture-driven sections, and a new Gotchas bullet was added there
documenting the two files as a second deliberate exception to `conftest.py`'s real-browser trap
(same shape as the existing `test_discovery.py`/`test_seed_feeders.py` exception already described
in that file's Role section) — the trap patches `src.search.browser.Chrome` specifically, and
these two files never import that module, so it structurally cannot fire; explained rather than
left for a future reader to rediscover by tracing imports.
