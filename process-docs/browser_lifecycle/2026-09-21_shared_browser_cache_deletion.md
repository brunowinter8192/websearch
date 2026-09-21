# A foreign project deleted our pinned Chromium revision (2026-09-21)

## What was observed

`cli.py search_web` returned all eight engines at `0`, exit code 0, across four consecutive runs
between 10:40 and 10:47 local time. The printed output carried no hint of a defect. The first
suspicion was the query itself, which was a German postal address.

The query was not the cause. No search had succeeded since 2026-09-19 20:09, where the same
pipeline returned 79 URLs across 8 engines.

## Diagnosis path that worked, in order

1. `src/logs/cli.log` showed `Browser prewarm failed: DevToolsActivePort did not appear` followed
   by `Cannot connect to host localhost:<port>` for every browser engine. Chrome was never up.
2. Launching Chrome by hand with the exact flags from the log SUCCEEDED. Same flags, same TMPDIR
   profile directory. This ruled out the flags, the profile path and macOS permissions, and is the
   step that redirected the investigation away from the launch arguments.
3. The difference between the manual run and production is the binary. `src/search/browser.py`
   does NOT launch the Chrome in `/Applications`. It calls `_resolve_chromium_bundle_path()`, which
   asks **patchright** for `pw.chromium.executable_path` and launches that bundle via
   `open -g -n -a`. The path in the log line `Using Chrome binary: /Applications/Google Chrome.app`
   is pydoll's own default resolution being logged, NOT what actually gets launched. Do not trust
   that log line.
4. Resolving patchright's path directly showed the answer:

   ```
   executable_path: .../ms-playwright/chromium-1228/chrome-mac-arm64/Google Chrome for Testing.app/...
   exists: False
   ```

The single most useful probe in this whole investigation was step 4, and it is three lines of
Python. Run it FIRST next time, before reading any logs:

```python
from patchright.async_api import async_playwright
pw = await async_playwright().start()
print(pw.chromium.executable_path, Path(pw.chromium.executable_path).exists())
```

## Root cause

All projects on this machine share ONE browser cache at `~/Library/Caches/ms-playwright/`. It is
not per-project and not inside any venv.

On 2026-09-20 at 14:52 a Claude Code session working on the **canvas** project (Excalidraw
harness testing, worktree `builder`, registered under the `rag-cli` project directory) ran:

```
cd /tmp/m3-verify && npx playwright install chromium
```

That installer's own output, recovered verbatim from the session transcript:

```
Removing unused browser at .../ms-playwright/chromium-1228
Removing unused browser at .../ms-playwright/chromium_headless_shell-1228
Downloading Chrome for Testing 153.0.8010.12 (playwright chromium v1243)
```

Revision 1228 is exactly what patchright pins. The Node installer considered it unused and
removed it. Nothing in websearch was touched; the project broke without a single line of its own
code changing.

## Why it was considered "unused"

Playwright decides what is in use by reading `~/Library/Caches/ms-playwright/.links/`. Each file
there points at an installation directory, and each installation's `browsers.json` claims its own
revision. A revision no link claims is garbage-collected on the next `install`.

At the time of deletion there was no link claiming 1228. After running
`./venv/bin/patchright install chromium` on 2026-09-21 a link now exists pointing at
`.../site-packages/patchright/driver/package`. This makes a repeat less likely, but it has NOT
been proven against a real subsequent `npx playwright install` — treat it as untested.

## Which revisions this project actually needs

- **1228 — patchright — genuinely required.** BOTH browser lanes resolve through it:
  `src/search/browser.py` (search) and `src/scraper/chromium_process.py` (scrape). Confirmed by
  access time: it was touched by the verification run minutes after reinstalling.
- **1223 — playwright — never launched by this project's own code.** No module imports
  `playwright` directly; `grep` for it across `src/` and `cli.py` returns nothing. It arrives only
  as a transitive dependency of `crawl4ai`, `camoufox` and `playwright-stealth`. crawl4ai can use
  either library and picks patchright under its `use_undetected` path; websearch additionally
  attaches crawl4ai to an ALREADY RUNNING Chrome over CDP, so crawl4ai never launches a browser of
  its own here. 1223's access time was five days stale while searches and scrapes were running.

Do not "clean up" 1223. It is not in `requirements.txt` and cannot be removed there — it is pulled
in transitively, so any reinstall brings it straight back. The maintenance cost of fighting it is
real and its presence costs nothing.

## This was the second occurrence, not the first

The same defect class hit the SCRAPE side in 2026-07 with revision 1208, recorded in
`process-docs/scrape_pipeline/`. That side got a guard (`is_browser_launch_error`, an
`acquisition_error: "browser_missing"` outcome, an ERROR-level log naming the repair command).
The search side never received an equivalent, which is why the 2026-09-21 incident was silent for
two days. A degraded-run notice for `search_web` was added the same day this file was written —
see `process-docs/search_pipeline/`.

## The repair

```
./venv/bin/patchright install chromium
```

This re-downloads 1228 and, as a side effect, removed 1243. That removal was verified harmless:
`/tmp/m3-verify` no longer exists and the canvas project has no `playwright` in its
`node_modules`. Verification after repair: seven engines returned 10 results each for the query
that had returned all zeros.

## Reproducing the broken state safely

To test any guard against this failure, move the revision aside rather than deleting it, and set
the restore trap BEFORE breaking anything:

```bash
trap 'rm -rf "$SRC"; mv "$BAK" "$SRC"' EXIT INT TERM HUP
mv "$SRC" "$BAK"
```

This was executed twice on 2026-09-21 (once by the implementing worker, once independently) and
the cache was intact afterwards both times. Known limit, stated because it is easy to assume
otherwise: a shell trap does not survive `SIGKILL` of the process tree.

## What was ruled out, so nobody re-tests it

- The query. A German postal address searches fine; the same query returned 51 URLs after repair.
- The launch flags, the TMPDIR profile directory, macOS permissions. All verified working by hand
  while production was still failing.
- System resource exhaustion. File-descriptor and process limits, memory and load average were all
  measured healthy during a failing run.
- OpenAlex returning 0. It is an academic API and a postal address legitimately has no papers.
  It returns 0 on healthy runs too and must not be read as part of this defect.
