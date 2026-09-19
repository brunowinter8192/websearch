# Brave PoW challenge under the search lane's pydoll browser

Run: 2026-09-18T20:10:33Z
Browser: the SAME resolved Chromium bundle `src/search/browser.py` launches in production (`patchright.async_api`'s own `chromium.executable_path`, walked up to its enclosing `.app`), NOT the literal `Google Chrome` app — inlined into this probe's own launch wrapper rather than reused from `dev/_lib/browser_launch.py`, which still hardcodes the literal app and was deliberately left unfixed this milestone. Same profile-directory, backgrounding-flag and `browser_preferences` shape as `src/search/browser.py` otherwise.
Live requests against search.brave.com this run: 14. Minimum gap between consecutive Brave navigations: 20s (production's limiter is 4 requests per minute). Control navigations go to a neutral URL, not to Brave, and are not counted here.

Live budget for this milestone: a hard ceiling of 20 real requests against search.brave.com. Base plan: 4 (phase A) + 4 (phase C) + 2 (phase D) = 10 requests. One bounded extension is allowed by the brief: if phases A and C together produce zero button challenges, up to 4 additional navigations on a third fresh profile may run before phase D, still inside the 20-request ceiling. Phase D always runs last. This run used the extension.

## Phases

**A cold** — a brand new empty profile, one browser process, four queries in sequence.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-cold-bd_x2ezs`
Queries challenged: 0 of 4

**C warm after relaunch** — the same profile directory as phase A, after a full teardown and a relaunch of Chrome. Production's shape: the profile persists on disk, the process does not.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-cold-bd_x2ezs`
Queries challenged: 0 of 4

**B extension (zero button challenges in A+C)** — a third, brand new profile, run only because phases A and C together produced zero button challenges. Bounded to at most 4 queries by the brief.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-extension-zlz4mci9`
Queries challenged: 0 of 4

**D fresh control** — a second (or third, if the extension ran) brand new profile, run last. The discriminator between 'the profile carried something' and 'Brave stopped challenging this address during the run'.
Profile: `/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-fresh-q7xwho1a`
Queries challenged: 0 of 2

## Per-query result

All times in milliseconds from navigation start.

| Phase | Query | Challenge served | Final state | Verdict | Links | Trigger | nav | button | fired | results | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A cold | DS18B20 1-wire dropout compressor fridge | False | RESULTS | SUCCESS_UNCHALLENGED | 19 | - | 982 | - | - | 991 | 991 |
| A cold | postgres index bloat diagnosis | False | RESULTS | SUCCESS_UNCHALLENGED | 19 | - | 712 | - | - | 716 | 716 |
| A cold | rust borrow checker explained | False | RESULTS | SUCCESS_UNCHALLENGED | 19 | - | 689 | - | - | 693 | 693 |
| A cold | sqlite wal mode checkpoint | False | RESULTS | SUCCESS_UNCHALLENGED | 18 | - | 762 | - | - | 767 | 767 |
| C warm after relaunch | nginx reverse proxy config | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 788 | - | - | 798 | 798 |
| C warm after relaunch | kubernetes ingress tls | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 743 | - | - | 749 | 749 |
| C warm after relaunch | ffmpeg concat filter | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 925 | - | - | 949 | 949 |
| C warm after relaunch | pandas groupby apply | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 739 | - | - | 750 | 750 |
| B extension (zero button challenges in A+C) | python asyncio tutorial | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 748 | - | - | 788 | 789 |
| B extension (zero button challenges in A+C) | how does dns work | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 252 | - | - | 10816 | 10816 |
| B extension (zero button challenges in A+C) | fastapi websocket reconnect | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 1336 | - | - | 1352 | 1352 |
| B extension (zero button challenges in A+C) | argon2 memory hard hashing | False | RESULTS | SUCCESS_UNCHALLENGED | 16 | - | 1106 | - | - | 1139 | 1139 |
| D fresh control | python asyncio tutorial | False | RESULTS | SUCCESS_UNCHALLENGED | 20 | - | 958 | - | - | 983 | 983 |
| D fresh control | rust borrow checker explained | False | UNKNOWN | INCONCLUSIVE_UNKNOWN | 0 | - | 98 | - | - | - | 30118 |

## Q1 — does the flow complete under the search lane's own pydoll browser, driven from code?

Queries that presented the button-challenge shape and offered a clickable candidate: 0. Trigger attempted on 0, actually fired (`js_click` or `cdp_dispatch`) on 0. Reached real result links: 0.
Queries that landed on the 429/pow-link shape instead (no known clickable element, not attempted): 0.

Trigger mechanism used per query is in the summary table above (`js_click` = a deep-queried `.click()` call, matching a light-DOM or shadow-hosted button uniformly but producing an `isTrusted: false` event; `cdp_dispatch` = a real `Input.dispatchMouseEvent` at the same element's bounding-rect center, tried only when `js_click` produced no observable progress).

## Q2 — what does a challenged query cost, end to end, against the 6.0 second watchdog?

Clock starts at the instruction before `tab.go_to(...)` and stops when the state machine reaches a terminal state (`RESULTS`, `POW_LINK_BLOCK` or `BLOCKED`) or the per-query budget (30s) runs out. Poll interval is 200ms.

| Population | n | min | median | max | over 6.0s |
|---|---|---|---|---|---|
| challenged | 0 | - | - | - | 0 |
| unchallenged | 14 | 693 | 874 | 30118 | 2 |

### Splits inside the challenged span

- navigation: n=0, min=-ms, median=-ms, max=-ms
- button in DOM: n=0, min=-ms, median=-ms, max=-ms
- trigger fired: n=0, min=-ms, median=-ms, max=-ms
- results present: n=0, min=-ms, median=-ms, max=-ms

- `new_tab()` around the span: n=14, median=51ms, max=1074ms
- `kill_tab()` after the span: n=14, median=1ms, max=36ms

`ENGINE_WATCHDOG_TIMEOUT` in `src/search/search_web.py` is 6.0s and this milestone does not change it. The 'over 6.0s' column counts individual queries, not an average.

## Q3 — does a solved challenge carry over, within a run and across runs?

Machine-classified verdict: **UNMEASURABLE_COLD_PROFILE_WAS_NOT_CHALLENGED**

- Phase A (cold profile, one browser process): challenged per query [False, False, False, False]
- Phase C (same profile directory, browser killed and relaunched in between): [False, False, False, False]
- Phase D (fresh profile, run last on the same machine and network): [False, False]

Phase D is the discriminator. Without it, a quiet Phase C is equally well explained by Brave having stopped challenging this address during the run. The verdict above only reports a carry-over when a fresh profile at the end of the run was challenged again.

### What survived the browser process being killed

```json
{
  "cookie_store_file_after_phase_a": {
    "path": "/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-cold-bd_x2ezs/Default/Cookies",
    "exists": true,
    "size_bytes": 20480,
    "mtime": 1789760664.5201733
  },
  "cookie_store_file_before_phase_c": {
    "path": "/var/folders/t2/_8msw65s0glfkr10g1mp_4g40000gn/T/brave-probe-cold-bd_x2ezs/Default/Cookies",
    "exists": true,
    "size_bytes": 20480,
    "mtime": 1789760664.5201733
  },
  "brave_cookies_at_end_of_phase_a": [],
  "brave_cookies_at_start_of_phase_c": [],
  "names_present_on_both_sides_of_the_process_kill": [],
  "names_whose_value_was_byte_identical_across_the_kill": [],
  "session_scoped_at_end_of_phase_a": [],
  "persistent_at_end_of_phase_a": []
}
```

### Cookies Brave set, and what survived

**A cold / DS18B20 1-wire dropout compressor fridge**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**A cold / postgres index bloat diagnosis**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**A cold / rust borrow checker explained**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**A cold / sqlite wal mode checkpoint**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**C warm after relaunch / nginx reverse proxy config**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**C warm after relaunch / kubernetes ingress tls**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**C warm after relaunch / ffmpeg concat filter**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**C warm after relaunch / pandas groupby apply**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**B extension (zero button challenges in A+C) / python asyncio tutorial**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**B extension (zero button challenges in A+C) / how does dns work**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**B extension (zero button challenges in A+C) / fastapi websocket reconnect**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**B extension (zero button challenges in A+C) / argon2 memory hard hashing**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**D fresh control / python asyncio tutorial**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

**D fresh control / rust borrow checker explained**

- present before navigation: []
- added by the navigation: []
- added or changed during verification: []
- present at the end: []

```json
[]
```

## Q4 — does passing the button challenge have any effect on the 429/pow-link shape?

Observational only, n=14 across the whole run. NOT provoked — deliberately triggering a 429 would require bursting past the 20s pacing this milestone's budget requires, so this section reports what was seen at ordinary pacing, not what a burst would show.

429/pow-link rate before any button-challenge in this run was solved: 0.0
429/pow-link rate after a button-challenge was solved: None
All final states this run, in order: ['RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'RESULTS', 'UNKNOWN']

A direction, not a cause, at this sample size. Do not read a single run's before/after split as proof either way.

## What this run does not measure

- **The concurrent case.** Production fans out eight engines at once inside one browser. Every query here is sequential with a gap. Nothing in this report extends to a Brave query sharing a browser with seven concurrent engine tabs.
- **Production's own profile.** This probe uses dedicated temporary profile directories, never `~/.websearch/browser-session`, so it cannot contaminate production state or be contaminated by it.
- **Whether the trigger mechanisms used here generalize.** Both `js_click` and `cdp_dispatch` were tried against whatever this run's own live pages actually presented; this report does not claim either mechanism is reliable beyond what it observed.
- **Q4 is a single run's observation, n small by construction, not a controlled experiment.**
- **The bounded extension was used** (phases A and C together produced zero button challenges, so a third fresh profile ran before phase D). See the phase list above for what it added.

## Methodology

Every phase launches Chrome through an inline copy of `src/search/browser.py`'s launch shape (no `from src.` import, which this repo's tooling blocks for new dev files), resolving the SAME dedicated Chromium bundle production launches via `patchright.async_api`'s `chromium.executable_path`, and, before the first Brave navigation of that phase, navigates a neutral control URL. If that control navigation fails the whole probe aborts with the raw error.

Per query the page is polled every 200ms and classified into one of six states: RESULTS (`div[data-type="web"]` present), BUTTON_VERIFYING (an in-flight marker such as 'Letting you in...' is present), BUTTON_PENDING (a deep-queried button/role=button element whose text matches a trigger-word list is present, searched through shadow roots too), POW_LINK_BLOCK (a `pow-captcha` link is present with no clickable candidate found), BLOCKED (a block marker with neither a button nor a pow-link), UNKNOWN. Only RESULTS, POW_LINK_BLOCK and BLOCKED are terminal. There is deliberately no branch that treats a marker or pow-link's mere presence as terminal on the first poll - that is brave.py's own current defect, and repeating it in this probe's polling would make Q1 unanswerable by construction.

The trigger, once a BUTTON_PENDING state is seen, is a deep-queried `.click()` call (searches through shadow roots for a `button`/`[role=button]` element whose text matches a trigger-word list, then clicks it directly - this finds the element correctly regardless of shadow DOM, but produces an `isTrusted: false` event). If that produces no observable state change, `Input.dispatchMouseEvent` is tried at the same element's bounding-rect center on the next poll - a real, trusted input event, though the same limitation the `engine_reduction` area recorded against shadow-DOM-scoped elements may apply.

Cookies are read via CDP `Storage.getCookies` (browser-wide, not `Tab.get_cookies()`, which the `mojeek_return` area's own investigation found is scoped to whatever page the tab currently shows and reads empty on a blank tab by construction) at three points per query - before the navigation, right after it, and after the page settles.

Queries per phase: {"A cold": ["DS18B20 1-wire dropout compressor fridge", "postgres index bloat diagnosis", "rust borrow checker explained", "sqlite wal mode checkpoint"], "C warm after relaunch": ["nginx reverse proxy config", "kubernetes ingress tls", "ffmpeg concat filter", "pandas groupby apply"], "B extension (zero button challenges in A+C)": ["python asyncio tutorial", "how does dns work", "fastapi websocket reconnect", "argon2 memory hard hashing"], "D fresh control": ["python asyncio tutorial", "rust borrow checker explained"]}. Per-query budget 30s, gap between consecutive Brave navigations 20s.
