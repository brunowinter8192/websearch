# Degraded-run notice for search_web (2026-09-21)

## What this closes

On 2026-09-21 a real `cli.py search_web` run printed a clean-looking, exit-0 engine breakdown
table with every one of the 7 browser-backed engines at `0`, caused by patchright's pinned
chromium revision (1228) having been deleted from `~/Library/Caches/ms-playwright/` by an
unrelated `npx playwright install chromium` run in a different project the day before. `open -g`
launched against a bundle path that no longer existed, failed silently (stderr to `DEVNULL`),
`DevToolsActivePort` never appeared, and every browser engine returned `ERROR_BROWSER` or
`TIMEOUT_WATCHDOG`. Nothing in the printed output distinguished this from "the query legitimately
has no results." This is the second occurrence of this exact defect class in this project — the
first hit the scrape side in 2026-07 (chromium revision 1208) and got a guard
(`is_browser_launch_error` in `src/scraper/chromium_scrape.py`); the search side never did, until
now.

## The mechanism added

`src/search/search_web.py` gained three pure functions plus one wiring line in the orchestrator:

- `_failing_engines(engine_stats)` — filters `engine_stats` (already captured per engine, nothing
  new to compute) down to engines whose `status` is in `_FAILURE_STATUSES` (the 4 `ERROR_*` and 3
  `TIMEOUT_*` constants from `status_error.py`/`status_timeout.py`). `OK`, `EMPTY`, and `RATE_SKIP`
  are never in this set — a fully successful run, a legitimately-empty engine (OpenAlex on a
  postal-address query, a solved-but-still-empty captcha page), and a rate-limiter skip are none of
  them "our own code failed."
- `_format_degraded_notice(engine_stats)` — `None` if `len(failing) / len(engine_stats)` is below
  `DEGRADED_ENGINE_FAILURE_RATIO` (0.30, a module constant in `search_web.py`). Otherwise a plain
  fact block: `"Engine failures: N/M selected engines returned an error or timeout status."`, one
  indented `name  STATUS` line per failing engine (same `{:<20}` alignment the breakdown table
  already uses), and — conditionally — a `Repair: ./venv/bin/python -m patchright install
  chromium` line.
- `_prepend_degraded_notice(breakdown_text, engine_stats)` — returns `breakdown_text` unchanged
  when the notice is `None`; otherwise `f"{notice}\n\n{breakdown_text}"`.
- Orchestrator: `formatted_text = _format_breakdown(...)` then
  `formatted_text = _prepend_degraded_notice(formatted_text, engine_stats)` — a straight
  pass-through, no branching logic added to the orchestrator itself.

No new capture mechanism — `engine_stats[name]["status"]` already existed before this milestone,
per engine, for every `search_web` call.

## Why 30%, not 50%

The user's own operational-log analysis (164 `engine_run` records) found `>=30%` of engines with
an error/timeout status fires 7 times, all 7 real defects, 0 false alarms; `>=50%` fires 6 times,
6 real, 0 false — i.e. the 50% cut misses exactly one real defect that the 30% cut catches. That
one record is `2026-09-15T18:43:05`, query `"gegarte Speisen abkuehlen Kuehlschrank Zeitvorgabe
Bacillus cereus"`:

```
google:     ERROR_BROWSER
duckduckgo: TIMEOUT_WATCHDOG
openalex:   EMPTY
startpage:  TIMEOUT_WATCHDOG
brave:      EMPTY
bing:       OK  (10 results)
yandex:     EMPTY
```

3 of 7 = 42.9%. It fires at 30%, would stay silent at 50%. The run still returned bing's 10 URLs —
this is the case that proves the notice must not be gated on "total results is zero"; a run can
look superficially fine (some URLs came back) while 3 engines' worth of coverage silently vanished
underneath it. This exact record is now a test fixture
(`dev/tests/test_search_web_degraded_notice.py::test_gegarte_speisen_boundary_case_...`).

Caution for whoever reads this next: an earlier draft of the milestone brief cited a "3 of 7 (43%)"
record for a *different* query, `"Hackfleisch Lagertemperatur Vorschrift"` — that citation was
wrong, caused by merging two adjacent `2026-09-15T18:43` log lines when the brief was written. The
real `"Hackfleisch Lagertemperatur Vorschrift"` record (18:43:16) is 5 of 7 = 71%, not 43%. Both
records are real, both fire, but they are not the same boundary case — the `"gegarte Speisen ..."`
record (18:43:05) is the one that actually sits near the 30/50 boundary. Re-verify against the raw
`src/logs/query_log.jsonl` directly if this number is ever needed again; do not trust a summary
table without re-pulling the line.

## Why the repair hint is "any ERROR_BROWSER present," not a substring match

`src/scraper/chromium_scrape.py`'s `is_browser_launch_error(exc)` has to string-match a raw
exception message (`"executable doesn't exist"`, `"playwright install"`, etc.) because all it has
is the exception. `search_web.py` is one layer further downstream: `_classify_engine_exception`
already turned that same class of exception (pydoll/websocket/`ConnectionError`) into the
`ERROR_BROWSER` status constant, per engine, before the notice code ever runs. Re-matching a
substring on top of that would be a second guess stacked on a fact that already exists — the
notice just reads the fact.

Checked before committing to this: scanned all 164 `engine_run` records for a case where the
30% gate fires but no engine in the failing set is `ERROR_BROWSER`. There is none — every real
degraded run in this project's recorded history that crosses 30% has at least one `ERROR_BROWSER`
in it, including both the 2026-09-21 incident and the 2026-09-15 records above. The one test that
exercises "fires without `ERROR_BROWSER`, no repair line" is explicitly a hypothesis in the test
file (`test_hypothesis_fires_without_error_browser_omits_repair_hint`) — it cannot be built from an
observed record, so it is not presented as one.

## Placement: before the breakdown table, not after

First draft put the notice after the existing "Use ... drilldown ..." line. Corrected during
review: `cli.py`'s own `discover_urls` already solved this exact question and the reasoning is
recorded in the root `DOCS.md` — `ok`/`failed_feeders` print first, unconditionally, specifically
so a thin result cannot be mistaken for a complete one "just because that fact would otherwise sit
below the fold." The 2026-09-21 incident happened because the one fact that mattered was easy to
miss; putting the new fact below an existing table would repeat that exact mistake in miniature.
The notice is now prepended, not appended.

## Exit code: left at 0, deliberately

No `sys.exit()` added anywhere in `cli.py`'s `search_web` branch. Reasoning:

- The scraper precedent this milestone is modeled on does not escalate `acquisition_error:
  "browser_missing"` to a non-zero exit either — it logs at ERROR and returns normally. Introducing
  divergent exit-code conventions for the same defect class on the two sides of this codebase would
  be worse than picking either one consistently.
- `discover_urls` is the one place in this CLI that does use exit code as a signal, but its reason
  is a downstream FILE contract (`pipe_scraper --url-file` must never be silently handed an
  empty-looking file). `search_web` has no equivalent file consumer — its output is text an agent
  reads directly, which the notice itself already makes loud.
- No current caller inspects `search_web`'s exit code (`cli.py`'s `search_web` branch never calls
  `sys.exit`). Introducing a new non-zero contract now, with no existing consumer and an unresolved
  boundary question (the 43%-real, still-returned-results case would look identical, via exit code
  alone, to a total-zero-results crash), was decided against. Revisit if a real caller ever needs
  to branch on this programmatically — this decision was explicit, not an oversight.

## Real per-record fixtures used in tests

`dev/tests/test_search_web_degraded_notice.py` uses `status`-only dicts built from these real
`engine_run` records (re-pulled from `src/logs/query_log.jsonl`, not from the milestone brief's
own summary table):

| ts | query | n | failing | ratio | must |
|---|---|---|---|---|---|
| 2026-09-06T16:02:08 | Shear Revival Grey Ghost ingredients | 7 | 0 | 0% | silent |
| 2026-09-19T14:51:53 | hauswasserwerk druckschalter vwin1 | 8 | 1 | 12.5% | silent |
| 2026-09-17T21:41:13 | altcha proof of work widget | 8 | 1 (incl. 1 ERROR_BROWSER) | 12.5% | silent |
| 2026-09-21T08:40:45 | Techniker Krankenkasse Hauptverwaltung Anschrift Hamburg | 8 | 7 | 87.5% | fires |
| 2026-09-21T08:41:49 | Techniker Krankenkasse Bramfelder Straße 140 Hamburg | 8 | 7 | 87.5% | fires |
| 2026-09-15T18:42:57 | Hackfleisch Lagertemperatur 2 Grad Verordnung 853/2004 | 7 | 7 | 100% | fires |
| 2026-09-15T18:43:16 | Hackfleisch Lagertemperatur Vorschrift | 7 | 5 | 71% | fires |
| 2026-09-15T18:43:05 | gegarte Speisen abkuehlen Kuehlschrank Zeitvorgabe Bacillus cereus | 7 | 3 | 42.9% | fires (boundary) |

## Live verification performed

1. **Healthy run, unmodified vs. modified code, same live query** (`"python asyncio tutorial"`,
   repaired environment, `git stash`/`stash pop` around the code change): output differed only in
   `google` (9 vs 8 results) and `yandex` (10 vs 0 results, `EMPTY` — a real captcha hit, not an
   error/timeout status) — both are live search variance between two separate runs, not caused by
   the code change. Confirmed against `query_log.jsonl` for the second run: `yandex` status is
   `EMPTY`, ratio 0/8, notice correctly did not fire. Both outputs have the same 12-line shape.
2. **Failure path, real reproduction, not a mock**: temporarily `mv`'d
   `~/Library/Caches/ms-playwright/chromium-1228` to `chromium-1228.bak` (the exact revision named
   in the 2026-09-21 incident), inside a script that sets a bash `trap ... EXIT` to restore it
   BEFORE running anything against the broken state — the restore is unconditional on the script's
   own exit path, not a final cleanup line that a crash could skip. Ran
   `cli.py search_web "Techniker Krankenkasse Bramfelder Strasse 140 Hamburg repro test"` against
   the broken state. Real output:

   ```
   Engine failures: 7/8 selected engines returned an error or timeout status.
     google               TIMEOUT_WATCHDOG
     duckduckgo           TIMEOUT_WATCHDOG
     mojeek               TIMEOUT_WATCHDOG
     startpage            ERROR_BROWSER
     brave                ERROR_BROWSER
     bing                 ERROR_BROWSER
     yandex               ERROR_BROWSER
   Repair: ./venv/bin/python -m patchright install chromium

   Engine breakdown for "Techniker Krankenkasse Bramfelder Strasse 140 Hamburg repro test":
     google               0
     duckduckgo           0
     mojeek               0
     openalex             0
     startpage            0
     brave                0
     bing                 0
     yandex               0

   Use `websearch search_engine_drilldown "..." --engine <name>` to see URLs per engine.
   ```

   This is a near-exact live re-creation of the original incident's own shape (openalex 0
   legitimately, all 7 browser engines failed) — confirmed the `chromium-1228` directory was back
   in place immediately after (verified via a separate `ls`, and via a following healthy
   `cli.py search_web` call that returned normal per-engine counts).

## What was NOT touched

- `cache_write` still receives `capped_pools`, never `formatted_text` — the disk cache contract
  (`~/.cache/websearch/<key>.json`, consumed by `search_engine_drilldown`) is byte-for-byte
  unaffected by this milestone.
- No exit code change (see above).
- No new status constants — `_FAILURE_STATUSES` is a fixed set built entirely from constants that
  already existed in `status_error.py`/`status_timeout.py`.
