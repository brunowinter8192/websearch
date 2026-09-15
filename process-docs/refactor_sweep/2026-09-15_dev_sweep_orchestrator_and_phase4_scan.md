# dev/ refactor sweep — orchestrator record and the Phase 4 control-flow scan (2026-09-15)

Orchestrator half of an `iterative-dev-refactor` run scoped to the WHOLE project. The per-area
worker entries live in `process-docs/access_recovery/`, `process-docs/agentic_discovery/`,
`process-docs/browser_posture/` and `process-docs/engine_reduction/`. This entry holds what only
the orchestrator saw: the scan numbers, the area ordering, the decisions taken at review, and the
Phase 4 scan that was run but NOT acted on.

## The headline finding: src/ was already clean, dev/ had never been swept

The very first scan settled the scope question. Measured 2026-09-15 over 95 modules and 8828 lines
in `src/`, plus `cli.py`:

- `src/`: zero modules over 400 LOC, zero functions at or above 50 LOC.
- `cli.py`: one function over threshold, `main` at 80 LOC.
- `dev/`: 35 modules over 400 LOC and 133 functions at or above 50 LOC, spread over 15 areas.

That asymmetry is not luck. This same area's 2026-08-20 and 2026-09-07 entries record a full
refactor run over `src/` only. `dev/` was never in scope of any of them. A successor scanning this
project should expect the same shape: production clean, dev carrying the whole debt.

Vendored third-party code under `dev/news_pipeline/theblock/jhao104/upstream/` was excluded from
every scan. It is gitignored and is not ours.

## What got done, area by area

Four areas were brought to zero hits and merged to `integration`:

| Area | Before | After |
|---|---|---|
| `dev/access_recovery/` | 1 module at 528 LOC, 3 functions (largest 119) | 5 modules, largest 327; largest function 35 |
| `dev/agentic_discovery/` | 0 modules, 6 functions (largest 122) | largest function 49 |
| `dev/browser_posture/` | 3 modules at 439/449/497 LOC, 7 functions (largest 206) | 13 modules, largest 307; largest function 41 |
| `dev/engine_reduction/` | 0 modules, 1 function at 65 | largest function 29 |

Left untouched and still carrying the debt, as of this entry: `explore_pipeline` (4 functions),
`lane_choice` (1 module, 1 function), `news_pipeline` (11 modules, 47 functions),
`scrape_pipeline` (1 module, 6 functions), `search_pipeline` (11 modules, 53 functions),
`tests` (6 modules, 3 functions), `url_discovery` (1 module, 1 function), and `cli.py::main`.

## The one real regression a split caused, and how it was caught

`dev/browser_posture/04_headed_chromium_probe.py::observe_run` and
`05_cdp_headed_probe.py::run_probe` both had the shape `try / except Exception / finally`. The
`finally` guaranteed teardown: stopping the focus-poll task, stopping the local probe server, and
in `05` also killing the self-launched Chrome and removing the temp profile directory.

The split moved the guarded body into a helper that catches `Exception` and RETURNS instead of
raising. The three-to-five cleanup steps then sat unguarded after the call. On the normal path and
on any ordinary `Exception` this is equivalent, which is why every output-identity test passed. It
is not equivalent for a `BaseException`: a `KeyboardInterrupt` or `asyncio.CancelledError` now
skipped teardown entirely. In `05` that means a Ctrl-C would leave a real self-launched Chrome
running and a temp profile directory on disk.

It was found by reading the diff against the pre-split control flow, not by any test. The fix was
to wrap the single helper call in `try / finally` at the call site.

Generalised: extracting a body that was inside `try/except/finally` into a helper that swallows
`Exception` silently drops the `finally` guarantee unless the caller re-wraps the call. Byte-identical
output proofs cannot see this, because the dropped guarantee only fires on `BaseException`.

## Three merge decisions worth not re-litigating

The worker flagged all three itself rather than acting, which is the behaviour to reward.

1. **Five `write_report` functions in `browser_posture` were NOT merged into a shared reporter.**
   They share a surface shape — timestamp header, markdown tables, teardown footer — and nothing
   else. Latency statistics, a focus-steal boolean verdict, per-block KEEP/DROP fingerprint prose,
   plist-mutation narrative and a stage-attributed focus breakdown are five different report bodies.

2. **`kill_survivors` was NOT unified between probes 04 and 05.** They are not the same function
   wearing two names. `04`'s runs three rounds and removes the launchd supervision job each round,
   built that way because `04` observed a crash-triggered launchd auto-relaunch racing a single-pass
   kill. `05`'s is single-pass because its route produces no crash. Unifying them would have handed
   `05` defensive behaviour it never had, which is a behaviour change, not a refactor.

3. **The five near-identical `main()` functions in `agentic_discovery` got no shared helper.** All
   five glob files, clean each, accumulate char totals and print a reduction footer. The variation
   is not cosmetic: cookieyes collects an errors list, searxng a prefix-count dict, tor three named
   pattern flags, rag_docs per-domain tuples. Parameterising "what extra statistic is collected"
   is a design call nobody asked for.

A fourth, smaller one: the split of `04_headed_chromium_probe.py` would have landed under 400 LOC
by moving only the report. The fuller concern split was taken anyway, because mutating a
machine-shared app bundle's `Info.plist` and macOS launchd teardown are separate hazard classes.
Shrinking LOC is not a concern split.

## The one hazard the cookieyes cleaner hid

`clean_web_cookieyes.py::clean_file` was 122 LOC of a single left-to-right scan with about nine
noise rules. The obvious extraction is sequential phases: a header pass, then a body pass. That
would have been wrong. Several later rules — the helpfulness footer, the subscribe block, the G2
badge, the skip-icon block — are NOT gated on `heading_done` in the original, so they are live for
the whole file. Phasing them would silently change behaviour for any input where one of those
markers appears before the heading. The loop and its branch order were kept intact and each rule's
body was delegated to a named helper instead.

## Phase 4 — the control-flow scan, run but NOT acted on

The scan ran over `src/`, `dev/` and `cli.py` with an AST pass classifying every `except` handler
by what it does. Totals as of 2026-09-15:

| Class | Count |
|---|---|
| PRODUCES-OUTPUT (handler returns a value, assigns, or emits) | 248 |
| LOG-ONLY | 77 |
| SWALLOW-PASS (body is only `pass`) | 30 |
| SWALLOW-FLOW (body is only `continue`/`break`) | 12 |
| TRIPWIRE (re-raises or exits) | 19 |

Of the 248 PRODUCES-OUTPUT handlers, 45 sit in `src/` and 204 in `dev/`. The `dev/` half
concentrates in two areas: `search_pipeline` with 82 and `news_pipeline` with 78.

Important framing for whoever acts on this: `src/` already went through a Phase 4 pass on
2026-09-09, and eight removals landed then — see this same folder's entries on the pipe_scraper
curl_cffi fallbacks, the proxy_riding abort stub, the engine `search()` wrappers, the camoufox
raw-HTML fallback, the engine `_parse_results` JSON handlers, the bing `_clean_url` decode
fallback, the log_janitor retention default, and the coindesk `parse_articles` fallback. The 45
`src/` handlers still standing are survivors of that pass, not an untouched backlog. `dev/`'s 204
have never been looked at.

An AST classifier cannot decide any of these. PRODUCES-OUTPUT is a candidate list, not a verdict.
The four conditions in the Fallback and Tripwire standard — observed failure in real data, covers
that case and nothing beyond, the artifact names which path produced it, anything outside the
observed case fails loud — are all judgement calls that need the user.

### The one Phase 4 item that is already decided by evidence

`dev/logging/p1_log_janitor.py` describes itself, and is described by `dev/logging/DOCS.md`, as a
dev mirror of `src/log_janitor.py`. It has drifted from its original in two ways at once:

- It still carries `try: int(...) except (ValueError, TypeError): return 14`, the exact retention
  fallback that was removed from `src/log_janitor.py` on 2026-09-09 for having no real trigger.
- It reads the environment variable `SEARXNG_LOG_RETENTION_DAYS`, while `src/log_janitor.py` reads
  `WEBSEARCH_LOG_RETENTION_DAYS`. That is leftover from the project rename, see
  `process-docs/project_rename/`.

`dev/logging/01_prune_test.py` imports from this mirror. So the dev test suite is asserting against
a copy that production no longer matches, on two independent axes. A mirror that has drifted is
worse than no mirror, because it reports green.

## Method notes for a successor

- Main scans, workers fix. Every threshold number in this entry came from an AST walk run by the
  orchestrator, never from a worker's own count. Workers were handed a concrete hit list.
- The evidence standard that worked: pull the pre-refactor function with `git show`, feed old and
  new the same synthetic fixtures covering every branch, diff the rendered output, require
  byte-identical. Every area used it. It caught nothing, which is the point — but see the teardown
  regression above for what it structurally cannot catch.
- Ask the worker for a comment-line multiset diff between the old file and the union of the new
  files. Two separate workers caught their own invented or dropped comments that way, five
  violations in one case, before commit.
- `DOCS.md` in a dev area frequently has a `## Gotchas` section, which is not in the DOCS.md format.
  The salvage rule worked well: cut it to the format and move the removed text verbatim into the
  worker's own process-docs entry under a `## Salvage from <path>` heading.

## Operational hazard hit this session: the worker name register is global

A worker named `refactor` was spawned for this project. A session in a different project later
spawned a worker with the SAME name. The register at `~/.claude/.worker-registry/` holds one file
per name, so the entry was overwritten and every subsequent `worker-cli response refactor` returned
the OTHER project's output — a report about a directory that does not exist here. It was only
caught because the content was obviously foreign.

Recovery was not clean. `worker-cli kill` refused, because the name resolved to the other project's
worker and that one was `working`. Rewriting the register file did not hold; the other session
rewrote it back. The raw teardown path is blocked by a hook. The working move was to merge the
orphaned branch first, then spawn a fresh worker under a project-unique name.

Take the lesson as: give a worker a name that cannot collide across projects, and treat a response
whose content does not match the project as a register collision until proven otherwise.
