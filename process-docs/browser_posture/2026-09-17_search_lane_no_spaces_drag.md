# Search lane must not drag the owner across macOS Spaces (M2) — 2026-09-17

Worker session (worktree `wsfocus`). Milestone: `websearch search_web` must not pull the owner
across macOS Spaces (virtual desktops) mid-search. Scoped entirely to `src/search/browser.py`; no
change to Google result extraction, engine yield, or anything else.

## The problem, as reported by the owner, and how it differs from the prior M1 milestone

M1 (`2026-09-15_search_lane_focus_steal_watchdog.md`, this same area) fixed in-Space OS focus
steal: a watchdog reclaims focus within one poll interval whenever the search lane's own Chrome
becomes frontmost. That fix does nothing for a DIFFERENT symptom the owner separately reported:
if he is working on a macOS Space other than the one the CLI call was started on, `search_web`
pulls him to another Space entirely. A reactive watchdog cannot prevent this — by the time it
would reclaim focus, the OS has already switched the owner's visible desktop out from under him.
The scrape lane (`chromium_scrape.py`/`chromium_process.py`) does not do this; its window lands on
whatever Space the owner is already on.

## Root cause (owner's working hypothesis, going in; not independently re-measured after the fix)

Both lanes launch a headed Chrome via macOS `open -g -n -a`, both pass `--no-startup-window`, both
run an identically-shaped focus-steal watchdog. None of those three things differ between the
lanes, so none of them explain the Spaces-only difference. The one structural difference: the
scrape lane launches patchright's own downloaded Chromium bundle, resolved to a full `.app` path;
the search lane launched the owner's actual, personal "Google Chrome" by bare name.

Reasoning that survived a full read of both lanes' code (no better explanation found): a CDP
`Target.createTarget` call implicitly activates the app that owns the new window (this is exactly
what upstream playwright#41282's `background:true` option was built to suppress — see the M1/M0
groundwork already documented in this same area). macOS keeps each app's windows "at home" on
whatever Space they last existed on; activating an app that already owns a window elsewhere brings
the OS to that Space. The owner's personal Google Chrome almost certainly already has a window
living on some other Space (he uses it as his daily browser); a dedicated bundle he has never
otherwise opened owns no window anywhere, so its new window has nothing to be dragged toward and
just appears on whatever Space is already active. This explains why `-g`/`--no-startup-window`/the
watchdog are all irrelevant here — none of them touch app *identity*, only launch-moment
activation or post-hoc reclaim.

Not independently verified live in this session (the standing rule: no live browser launch by an
agent, only the owner runs those) — this is the reasoning that justified the fix, not a measured
confirmation that the fix works. That confirmation is the owner's own verification step, see below.

## The fix

`get_tab()` (`src/search/browser.py`) now resolves patchright's own Chromium `.app` bundle path
(`_resolve_chromium_bundle_path`/`_find_app_bundle`, same shape as `chromium_process.py`'s pair) as
its very FIRST action — before the cross-process lock is even acquired, since resolving the bundle
touches nothing under `SESSION_DIR` and there is no reason to hold the lock any longer than the
existing code already does. `_open_background_process_creator` now takes that resolved path as a
parameter and launches `open -g -n -a <bundle_path> --args ...` instead of the previous
`open -g -n -a "Google Chrome" --args ...`; the resolved path is threaded into
`BrowserProcessManager`'s `process_creator` via `functools.partial`, since
`_open_background_process_creator` is referenced by the manager as a bare callable and has no other
way to carry the extra argument through pydoll's own call shape.

Everything else in `browser.py` is unchanged: the cross-process lock, `death_pipe`'s crash
watchdog, `_reap_session_profile`/`_record_own_pids` (both `pgrep -f user-data-dir=<SESSION_DIR>`,
identity-agnostic — they match on the launch argument, not on which binary produced the process),
and the PID-keyed focus-steal watchdog from M1 all keep working exactly as before, because none of
them care which binary is running under that user-data-dir.

## Decision 1 — duplicate the resolver, do not import `src.scraper` into `src.search`

Main's instruction going in: duplicate `_find_app_bundle`/`_resolve_chromium_bundle_path` locally
in `src/search/browser.py` rather than `from src.scraper.chromium_process import (...)`. Two
reasons, both already load-bearing in this codebase before this session started:

1. This project already established, in the M1 milestone in this same area, that lane-specific
   OS-interaction primitives get duplicated between `src/search/` and `src/scraper/` rather than
   forced into a shared abstraction — that precedent was set for the focus-steal watchdog itself
   (`_focus_steal_watchdog` vs. `_focus_steal_watchdog_by_pid`, structurally different identity
   mechanisms). The bundle resolver is smaller and, unlike the watchdog, IS structurally identical
   between the two call sites today — but the precedent is about which package boundary decisions
   get made across, not about whether the duplicated code happens to be byte-identical this time.
2. Neither package currently depends on the other in either direction. A new `src.search ->
   src.scraper` import would be the first such edge in the codebase and the wrong layering
   direction for a project where `src/scraper/` is the batch/single-URL scrape package and
   `src/search/` is the engine-fanout package — nothing about search's own responsibilities needs
   scrape's package to exist.

**Do not re-open this by proposing a shared `browser_launch_shared.py` or similar later** unless
the two resolvers actually diverge in behavior first (e.g. one lane needs a version pin the other
doesn't) — until then, this is a settled duplication, not an open question.

## Decision 2 — a separate persistent profile directory, not the owner's real-Chrome profile

The Keychain/os_crypt risk flagged going into this session (cookie/credential encryption on macOS
is keyed to the launching bundle's own identity; pointing a DIFFERENT bundle at a profile directory
built up under real Google Chrome risks that bundle being unable to decrypt what is already there)
was judged real enough to design around rather than just watch for in verification.

`SESSION_DIR` moved from `~/.websearch/browser-session` to `~/.websearch/browser-session-selflaunch`
— a NEW, separate, still-persistent directory under the owner's home. The old directory is left
completely untouched on disk: not migrated, not deleted, not read from. If this milestone is ever
reverted, the old profile (and whatever session state it held) is still intact.

`LOCK_PATH` was changed from a hardcoded `Path(SESSION_DIR).parent / "browser-session.lock"` to a
derived `Path(SESSION_DIR).parent / f"{Path(SESSION_DIR).name}.lock"` — this was not strictly
required (a single hardcoded lock filename would have kept working, since this module only ever
manages one shared browser at a time), but it means `LOCK_PATH` can never silently point at a name
that no longer matches `SESSION_DIR` if the directory is renamed again later. `_reap_session_profile`,
`_record_own_pids`, and `_wait_for_devtools_port(SESSION_DIR, ...)` all already read the `SESSION_DIR`
module constant directly rather than a hardcoded path literal, so they follow the rename with zero
code change — confirmed by re-reading each of the three, not assumed.

**Accepted, expected cost:** every DOM-scraped engine (startpage, brave, bing, yandex, mojeek,
duckduckgo, google) starts from a cold, empty profile once — first run after this change may need
to re-clear a consent page or re-solve a challenge it had already cleared before. This is
self-healing (the new profile accumulates its own session state exactly as the old one did) and
was accepted explicitly by Main rather than treated as a defect to engineer around.

**Nothing in `dev/search_pipeline/*.py`'s ~40 direct callers of `close_browser`/`new_tab` was
touched.** Several of those scripts hardcode their own standalone `SESSION_DIR` literals (some
under an even older `.searxng-mcp` naming, pre-dating this project's own rename) rather than
importing `browser.SESSION_DIR` — confirmed by reading, not assumed a risk worth fixing here: they
are historical, standalone dev probes, out of this milestone's scope, and changing them was not
asked for.

## Decision 3 — the browser-identity risk is named, not solved in code

patchright's Chromium presents a different identity to every search engine than the owner's real
Google Chrome did — different user agent, different build, different branding. This can move
engine block/challenge rates in either direction, and there is no way to fix this in code without
undermining the whole point of the fix (a dedicated bundle IS the fix). Per instruction, this is
handled two ways only: named as an open risk here, and folded into the verification instruction
handed to the owner below — not guessed at or engineered around speculatively.

**Pre-change baseline**, from `src/logs/query_log.jsonl`, 141 `engine_run` records, 2026-09-04
through 2026-09-17 — share of runs returning at least one result:

| Engine | Share of runs with >=1 result |
|---|---|
| bing | 99.3% |
| duckduckgo | 95.0% |
| startpage | 92.9% |
| brave | 53.2% |
| openalex | 33.3% |
| yandex | 19.1% |
| mojeek | 4.0% (only 25 runs — small sample, wide error bars) |
| google | 2.8% |

Google's own near-zero share going in is a pre-existing, unrelated fact (CAPTCHA pressure, not
something this milestone changes or explains) — included here only so a post-change re-read isn't
mistaken for a NEW regression this fix caused.

## Verification — the owner's step, not this session's

Two things to check in the same real runs, not two separate sessions:

1. **The actual fix.** Run `websearch search_web "<any query>"` from a macOS Space that is not the
   one any of your personal Chrome windows live on. Watch whether you get pulled to another Space.
   The in-Space focus flicker (M1's fix, bounded to well under 1s by the existing watchdog) is
   still expected and unchanged — that is not what this milestone targets, do not read it as a
   regression.
2. **The named engine-identity risk.** On the very first run or two, watch whether
   startpage/brave/bing/yandex/mojeek/duckduckgo ask you to re-consent or re-solve a challenge you
   had already cleared before — expected once, self-healing, not a bug (Decision 2's cost). After a
   handful of real `search_web` runs have accumulated, recompute the same per-engine
   "share of runs with >=1 result" straight from `src/logs/query_log.jsonl`'s `engine_run` records
   (same query used to build the baseline table above — filter to `record_type == "engine_run"`,
   group by `engine`, divide successes by total) and compare against the table above. A material
   drop on any one engine (not the sample-size noise mojeek's 25-run baseline already carries) is
   the signal that the identity swap cost something concrete on that engine — worth a follow-up
   investigation at that point, not something to pre-empt in code now.

## Test results

Baseline before any change, this worktree: `./venv/bin/python3 -m pytest dev/tests/` — **402
passed, 0 failed.**

After the fix: **405 passed, 0 failed** — 3 new tests added directly on the changed behavior
(`test_find_app_bundle_walks_up_to_app_suffix`, `test_find_app_bundle_returns_none_when_no_app_ancestor`
— both duplicated from `chromium_process.py`'s own equivalents onto `browser.py`'s new copy — and
`test_open_background_process_creator_targets_resolved_bundle_path_not_bare_name`, asserting the
built `open` command targets the resolved bundle path, not the literal string `"Google Chrome"`).
`test_browser_get_tab.py`'s three `get_tab()`-launch-path tests were updated to mock
`_resolve_chromium_bundle_path` (never called for real in this suite, same standing precedent as
`chromium_scrape.py`'s own tests never calling its identically-shaped function for real either) and
the ordering test now asserts `resolve_bundle` runs before `lock` — the one new step in the launch
sequence, and specifically BEFORE the cross-process lock is acquired.

No new entry was needed in `dev/tests/conftest.py`'s launch-primitive tripwire:
`_resolve_chromium_bundle_path` does not launch a browser (it starts and immediately stops
patchright's own driver process purely to read `executable_path`), and this project's own existing
precedent (`chromium_scrape.py`'s identically-shaped function is likewise absent from that tripwire
list, relying instead on every call site mocking it directly) was followed rather than expanding
the tripwire's scope beyond what was asked in this milestone.

## What was deliberately left alone

`background=True` on `Target.createTarget` (upstream playwright#41282's own mechanism, and pydoll's
`TargetCommands.create_target` already accepts the parameter) was considered and explicitly
deferred to a follow-up milestone, approved by Main as written in the pre-implementation proposal
for this session. Reasoning recap: it is a per-`new_tab()`-call, CDP-protocol-level change touching
all seven browser engines uniformly (versus this fix's single-function, launch-time change);
pydoll has no client-side focus-emulation shim the way Playwright does alongside its own
`background:true` support, so a tab created this way may genuinely report
`document.visibilityState === "hidden"` to page JS with nothing compensating for it — a distinct
risk axis (possible challenge-rate regression on the already-challenged engines) that deserves its
own live verification rather than being folded into this milestone's blast radius. This project
already logs exactly the telemetry (`document_status_chain`, `containers_found`,
per-engine `diagnosis` in `query_log.jsonl`) a before/after comparison for that follow-up would
need, with no new instrumentation required.
