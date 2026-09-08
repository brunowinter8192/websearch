# Chromium ad-hoc lane's focus-steal countermeasures (as of 2026-08-25)

This entry transfers the substance of several code comments in `src/scraper/chromium_scrape.py`
and `src/scraper/chromium_process.py` into a process-doc, ahead of a comment-rule conformance pass
that removes those comments from the source (only the three section markers stay in code). As of
2026-08-25 (the commit that introduced the mechanism, `cd65f8f`), the chromium ad-hoc lane's
focus-steal countermeasures were: `_focus_steal_watchdog`, `_reject_popup_pages` +
`_close_popup_page`, the `.app`-path launch detail in `_self_launch_chrome`, and the read-fresh
detail in `_live_scrape_profile_dirs`. No new measurement is claimed here beyond what the comments
already recorded.

## Why open -g alone isn't enough: the focus-steal watchdog

The self-launched scrape Chrome is a regular, non-accessory app — `LSUIElement` crashes this
bundle (see `dev/browser_posture/DOCS.md`) — so any window it creates can auto-activate it
(playwright#42343), regardless of `open -g`, which only covers the initial launch moment.
`_focus_steal_watchdog` (`chromium_process.py`) is a background task running for the whole
acquisition span: whenever THIS app_name specifically (never the user's own separate "Google
Chrome", never any other app) is frontmost, it immediately re-activates whichever app was
frontmost the moment before — tracked dynamically as the loop runs, never hardcoded — bounding any
steal to one `FOCUS_STEAL_POLL_INTERVAL_S` flicker. It is cancelled in `_acquire_cdp_headed`'s
`finally` (net 1); an in-process asyncio task dies with its own process, so unlike a separate
watchdog subprocess it cannot outlive a crashed CLI and leave a poll loop behind.

## Popup pages are a second window-creation-event risk

`_reject_popup_pages` (`chromium_scrape.py`) is crawl4ai's `on_page_context_created` hook target:
it closes any page the context creates BEYOND the one `main_page` crawl4ai itself asked for
(ad/consent-flow popups, `window.open`) — each such extra page is an independent window-creation
event that can trigger the same playwright#42343 activation the focus-steal watchdog guards
against; closing it fast shrinks that window further.

`_close_popup_page` (`chromium_scrape.py`) is the actual close call behind that hook: best-effort —
the page may already be gone/closing — logged, not raised, since a stray popup failing to close
must degrade gracefully and never fail the main scrape it has nothing to do with.

## Self-launch targets the resolved .app path directly

`_self_launch_chrome` (`chromium_process.py`) launches the resolved chromium bundle
headed-but-backgrounded via macOS `open -g -n -a` — the same no-focus-steal mechanism as
`src/search/browser.py` and `dev/browser_posture/05_cdp_headed_probe.py` — targeting the `.app`
PATH directly, never a bare name, so the launch is deterministic with no Launch Services ambiguity
about which installed copy gets opened.

## Live-profile-dir sweep reads fresh state each pass

`_live_scrape_profile_dirs` (`chromium_process.py`) computes the set of `scrape-url-cdp-*` profile
dir paths that currently have at least one live process. It is read fresh — after any kill that
already ran earlier in the same `_reap_orphaned_scrapes` pass — so a dir whose process was just
killed in that same pass is correctly seen as sweepable immediately, rather than waiting for the
next `try_scrape` call to notice it.

See `process-docs/camoufox_lane/` for the sibling lane's own no-focus-steal mechanism
(`LSUIElement` + `ignore_default_args=["-foreground"]`, no watchdog) — a structurally different
fix for the same class of problem, not interchangeable with this one.
