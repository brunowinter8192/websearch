# Mojeek ALTCHA under the search lane's pydoll browser

Run: 2026-09-17T21:06:56Z
Browser: the same build, flags and launch shape `src/search/browser.py` produces (pydoll `Chrome` + `BrowserProcessManager(process_creator=...)` re-launching the user's real Google Chrome via `open -g -n -a`, `--user-data-dir` profile, `--disable-blink-features=AutomationControlled`, backgrounding flags, same `browser_preferences`), inlined rather than imported.
Live requests against mojeek.com this run: 10. Minimum gap between consecutive Mojeek navigations: 20s (production's limiter is 4 requests per minute). Control navigations go to a neutral URL, not to Mojeek, and are not counted here.

Second live run of this milestone. An earlier run of this same probe, same day, same shape (10 Mojeek navigations), produced the identical per-phase challenge pattern but its cookie capture was void: it read cookies through `Tab.get_cookies()`, which resolves to CDP `Network.getCookies` scoped to the page the tab currently shows, so every before-navigation snapshot was taken on `about:blank` and came back empty. That was diagnosed against a local fixture (a cookie set on one origin is invisible to `Network.getCookies` from a blank tab and visible to `Storage.getCookies`), the reader was switched to browser-wide `Storage.getCookies`, and the run was repeated. Total live requests against mojeek.com for this milestone: 20 across the two runs, against a budget of 40.

## Phases

**A cold** — a brand new empty profile, one browser process, four queries in sequence. Query 1 is the cold data point; queries 2 to 4 are warm within a single browser process.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/mojeek-probe-carryover-mnw05wpq`
Queries challenged: 1 of 4

**C warm after relaunch** — the same profile directory as phase A, after a full teardown and a relaunch of Chrome. This is production's shape: the profile persists on disk, the process does not.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/mojeek-probe-carryover-mnw05wpq`
Queries challenged: 0 of 4

**D fresh control** — a second, brand new profile, run last. The discriminator between 'the profile carried something' and 'Mojeek stopped challenging this address during the run'.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/mojeek-probe-fresh-y7gywody`
Queries challenged: 1 of 2

## Per-query result

All times in milliseconds from navigation start. `pow_ms` is ALTCHA's own self-reported client-side proof-of-work time out of the solution payload, not a probe measurement.

| Phase | Query | Challenge served | Verdict | Links | nav | widget | verify() | verified | results | total | pow_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A cold | python asyncio tutorial | True | SUCCESS_CHALLENGED | 1 | 362 | 365 | 369 | 870 | 1784 | 1784 | 127 |
| A cold | rust borrow checker explained | False | SUCCESS_UNCHALLENGED | 10 | 348 | - | - | - | 350 | 350 | - |
| A cold | postgres index bloat | False | SUCCESS_UNCHALLENGED | 10 | 198 | - | - | - | 201 | 201 | - |
| A cold | sqlite wal mode | False | SUCCESS_UNCHALLENGED | 10 | 411 | - | - | - | 414 | 414 | - |
| C warm after relaunch | nginx reverse proxy config | False | SUCCESS_UNCHALLENGED | 10 | 329 | - | - | - | 331 | 331 | - |
| C warm after relaunch | kubernetes ingress tls | False | SUCCESS_UNCHALLENGED | 10 | 278 | - | - | - | 281 | 281 | - |
| C warm after relaunch | ffmpeg concat filter | False | SUCCESS_UNCHALLENGED | 10 | 382 | - | - | - | 385 | 385 | - |
| C warm after relaunch | pandas groupby apply | False | SUCCESS_UNCHALLENGED | 10 | 226 | - | - | - | 229 | 229 | - |
| D fresh control | python asyncio tutorial | True | SUCCESS_CHALLENGED | 10 | 369 | 372 | 383 | 889 | 1813 | 1813 | 123 |
| D fresh control | rust borrow checker explained | False | SUCCESS_UNCHALLENGED | 10 | 385 | - | - | - | 387 | 387 | - |

## Q1 — does the ALTCHA flow complete under this project's pydoll build?

Challenged queries: 2. `verify()` dispatched successfully on 2 of them. Reached real result links: 2.

The trigger is a single main-world `el.verify()` call through pydoll's `Tab.execute_script`, which is `Runtime.evaluate` with no isolated world. The patchright-specific failure mode recorded in the `engine_reduction` area (page-defined custom element methods being invisible in an isolated context) does not exist on this path; it was verified against a local fixture widget before any live request.

## Q2 — what does a challenged query cost in wall-clock time?

Clock starts at the instruction before `tab.go_to(...)` and stops at the first poll at which the production selector `ul.results-standard > li > a.ob` matches. Poll interval is 200ms, which is this measurement's granularity. `new_tab()` and `kill_tab()` are measured separately below because production's per-engine watchdog covers them too.

| Population | n | min | median | max | over 6.0s |
|---|---|---|---|---|---|
| challenged | 2 | 1784 | 1799 | 1813 | 0 |
| unchallenged | 8 | 201 | 341 | 414 | 0 |

### Splits inside the challenged span

- navigation: n=2, min=362ms, median=366ms, max=369ms
- widget in DOM: n=2, min=365ms, median=368ms, max=372ms
- verify() dispatched: n=2, min=369ms, median=376ms, max=383ms
- client-side verified: n=2, min=870ms, median=879ms, max=889ms
- results present: n=2, min=1784ms, median=1799ms, max=1813ms
- ALTCHA self-reported PoW: n=2, min=123ms, median=125ms, max=127ms

- `new_tab()` around the span: n=10, median=50ms, max=62ms
- `kill_tab()` after the span: n=10, median=1ms, max=2ms

`ENGINE_WATCHDOG_TIMEOUT` in `src/search/search_web.py` is 6.0s and this milestone does not change it. The 'over 6.0s' column counts individual queries, not an average.

## Q3 — does a solved challenge carry over to later queries?

Machine-classified verdict: **CARRIES_OVER_WITHIN_RUN_AND_ACROSS_RUNS**

- Phase A (cold profile, one browser process): challenged per query [True, False, False, False]
- Phase C (same profile directory, browser killed and relaunched in between): [False, False, False, False]
- Phase D (second, fresh profile, run last on the same machine and network): [True, False]

Phase D is the discriminator. Without it, a quiet Phase C is equally well explained by Mojeek having stopped challenging this address during the run. The verdict above only reports a carry-over when a fresh profile at the end of the run was challenged again.

Within-run and across-run carry-over are reported separately on purpose. They are two different production verdicts: `search_web_workflow` calls `kill_own_chrome()` in a `finally` on every run, so production never keeps a browser process between runs, only the profile directory on disk.

### What survived the browser process being killed

```json
{
  "cookie_store_file_after_phase_a": {
    "path": "/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/mojeek-probe-carryover-mnw05wpq/Default/Cookies",
    "exists": true,
    "size_bytes": 20480,
    "mtime": 1789679090.5027826
  },
  "cookie_store_file_before_phase_c": {
    "path": "/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/mojeek-probe-carryover-mnw05wpq/Default/Cookies",
    "exists": true,
    "size_bytes": 20480,
    "mtime": 1789679090.5027826
  },
  "mojeek_cookies_at_end_of_phase_a": [
    {
      "name": "chllg",
      "domain": "www.mojeek.com",
      "path": "/",
      "expires": 1792308774.634886,
      "session_scoped": false,
      "http_only": false,
      "secure": false,
      "same_site": null,
      "value_length": 141,
      "value_sha256_12": "a2d9cfa814c3"
    }
  ],
  "mojeek_cookies_at_start_of_phase_c": [
    {
      "name": "chllg",
      "domain": "www.mojeek.com",
      "path": "/",
      "expires": 1792308774.634886,
      "session_scoped": false,
      "http_only": false,
      "secure": false,
      "same_site": null,
      "value_length": 141,
      "value_sha256_12": "a2d9cfa814c3"
    }
  ],
  "names_present_on_both_sides_of_the_process_kill": [
    "chllg"
  ],
  "names_whose_value_was_byte_identical_across_the_kill": [
    "chllg"
  ],
  "session_scoped_at_end_of_phase_a": [],
  "persistent_at_end_of_phase_a": [
    "chllg"
  ]
}
```

`session_scoped` is read straight off the CDP cookie record: an `expires` of -1 (or absent) is a session cookie, which Chrome does not normally persist across a restart. This single attribute is what a successor needs in order to reason about production without re-running this probe.

### Cookies Mojeek set, and what survived

**A cold / python asyncio tutorial**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: ['chllg']
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**A cold / rust borrow checker explained**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**A cold / postgres index bloat**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**A cold / sqlite wal mode**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**C warm after relaunch / nginx reverse proxy config**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**C warm after relaunch / kubernetes ingress tls**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**C warm after relaunch / ffmpeg concat filter**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**C warm after relaunch / pandas groupby apply**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308774.634886,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "a2d9cfa814c3"
  }
]
```

**D fresh control / python asyncio tutorial**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: ['chllg']
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308941.060001,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "83c2f608a112"
  }
]
```

**D fresh control / rust borrow checker explained**

- present before navigation: ['chllg']
- added by the navigation: []
- added or changed during verification: []
- present at the end: ['chllg']

```json
[
  {
    "name": "chllg",
    "domain": "www.mojeek.com",
    "path": "/",
    "expires": 1792308941.060001,
    "session_scoped": false,
    "http_only": false,
    "secure": false,
    "same_site": null,
    "value_length": 141,
    "value_sha256_12": "83c2f608a112"
  }
]
```

## Widget as served this run

First captured on A cold / python asyncio tutorial.

```json
{
  "attributes": {
    "id": "altcha-widget",
    "challenge": "/captcha/challenge",
    "name": "altcha",
    "theme": "default"
  },
  "configuration": {
    "audioChallengeLanguage": "",
    "auto": "off",
    "barPlacement": "bottom",
    "challenge": "/captcha/challenge",
    "codeChallenge": null,
    "codeChallengeDisplay": "standard",
    "credentials": null,
    "debug": false,
    "disableAutoFocus": false,
    "display": "standard",
    "floatingAnchor": "",
    "floatingOffset": 8,
    "floatingPersist": false,
    "floatingPlacement": "auto",
    "hideFooter": false,
    "hideLogo": false,
    "humanInteractionSignature": true,
    "language": "",
    "mockError": false,
    "minDuration": 500,
    "overlayContent": "",
    "name": "altcha",
    "popoverPlacement": "auto",
    "retryOnOutOfMemoryError": true,
    "setCookie": null,
    "serverVerificationFields": false,
    "serverVerificationTimeZone": false,
    "test": false,
    "timeout": 90000,
    "type": "checkbox",
    "validationMessage": "",
    "verifyFunction": null,
    "verifyUrl": "",
    "workers": 14
  }
}
```

## What this run does not measure

- **The concurrent case.** Production fans out seven engines at once inside one browser. Every query here is sequential with a gap. Nothing in this report extends to a Mojeek query sharing a browser with six concurrent engine tabs.
- **Production's own profile.** This probe uses dedicated temporary profile directories with identical flags, never `~/.websearch/browser-session`, so it cannot contaminate production state or be contaminated by it.
- **Anything beyond this machine and network.** The 2026-09-05 removal recorded the block as tied to this project's network. A single run cannot separate a Mojeek policy from a local reputation effect beyond what Phase D tests.

## Methodology

Every phase launches Chrome through an inline copy of `src/search/browser.py`'s launch shape (no `from src.` import, which this repo's tooling blocks for new dev files) and, before the first Mojeek navigation of that phase, navigates a neutral control URL. If that control navigation fails the whole probe aborts with the raw error. One tripwire, no branch per failure mode: a session that cannot reach the open internet cannot tell 'Mojeek refused' from 'this machine is blind right now'. A local network outage hit this probe's predecessor mid-run on 2026-09-17, which is why the tripwire exists.

Per query the page is polled every 200ms and classified into one of five states: RESULTS (production result links present), IN_FLIGHT (the literal string 'Checking verification with server...'), CHALLENGE_PENDING (an `altcha-widget` is in the DOM), BLOCKED (the string 'Verification required' with no widget and no in-flight marker), UNKNOWN. Only RESULTS and BLOCKED are terminal. Mojeek's block-page boilerplate is present from the first poll and stays on screen through the whole verification sequence, so a verdict keyed on it would fire on iteration zero every time - the defect that produced two wrong live runs on 2026-09-17. A fixture that keeps that boilerplate visible along the entire success path is part of the offline test module and asserts that the first poll is never terminal.

The trigger is `document.querySelector('altcha-widget').verify()`, dispatched once, as soon as the widget is in the DOM and reports `typeof verify === 'function'`. Widget events are buffered in the page (`window.__mojeekEvents`) and drained on each poll; event timestamps are mapped onto the probe's own clock through an offset captured at attach time.

Cookies are read via CDP at three points per query - before the navigation, right after it, and after the page settles. Values are never written to this report: each cookie is recorded as name, domain, path, expiry, flags, value length and a 12-character SHA-256 prefix of the value, which is enough to prove that the same value carried across queries and across a process restart without putting a live session token into version control.

Queries per phase: {"A cold": ["python asyncio tutorial", "rust borrow checker explained", "postgres index bloat", "sqlite wal mode"], "C warm after relaunch": ["nginx reverse proxy config", "kubernetes ingress tls", "ffmpeg concat filter", "pandas groupby apply"], "D fresh control": ["python asyncio tutorial", "rust borrow checker explained"]}. Per-query budget 60s, gap between consecutive Mojeek navigations 20s.
