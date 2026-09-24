# Worker time: documented, not implemented (2026-09-24)

Orchestrator record. First entry in this area. No code or tooling changed.

## Owner decision, 2026-09-24

Everything related to time and performance limits is only documented in this session. The
worker-time topic falls under it.

## The measured case this area rests on

wsmojeek run, 2026-09-17, measured via duallog: 89m34s worker lifetime, 310 API requests, 4 turns.

| phase | duration |
|---|---|
| reading and plan | 5m06 |
| correct start | 5m25 |
| wrong browser after a hook block, discarded | 12m34 |
| local network outage, produced nothing | 13m02 |
| rework plus two live Mojeek runs | 39m35 |
| fixing its own outcome classifier | 8m42 |
| trimming DOCS.md | 54s |

43 of the 89 minutes sit in 16 pauses of one minute or more. The medium pauses were generation,
not blocking (one request carried 35,649 characters).

The expensive finding: the monitor-cc hook `block_dev_imports_src.py` refused an import the prompt
had asked for (a `dev/` script importing from `src/`). The worker noticed the contradiction in its
own thinking, did not report it, substituted `dev/_lib/browser_launch.py` (which launches the
user's real Google Chrome, not the patchright bundle production drives) and worked on for 26
minutes. Its report justified this with a false convention claim, checkable with one grep.

## What was applied in practice on 2026-09-24, without tooling changes

Every worker prompt in this session carried three lines:

- the `dev/` to `src/` import refusal named as a hard environment rule,
- an instruction to stop and report any collision between the prompt and an environment refusal
  instead of substituting,
- an instruction to cite evidence for any convention claimed in a report.

Whether these lines change worker behaviour was not measured.

Separately, the root cause of the substitution, `dev/_lib/browser_launch.py` hardcoding the real
Chrome app, was dispatched in this session under `refactor_sweep`.

## Observed on 2026-09-24 with five parallel workers

- **Shared `/tmp` collisions.** Four of five workers (wsweep2, wcli, wgoogle, wnotice) reported
  that a helper script they had written to a fixed path such as `/tmp/scan.py` was overwritten by
  another worker mid-task. One verification printed another area's files before the worker
  noticed. All four recovered by moving to a worker-unique directory (`/tmp/<worker>/`). Cost was
  a re-run, not a wrong result, because each worker re-checked. A prompt line naming a
  worker-unique scratch directory up front would avoid it.
- **Scripted edits instead of Edit/Write.** Three workers (wsweep1, wgoogle, wcli) removed
  hundreds of comments with a tokenize/AST script run through Bash instead of per-file Edit calls,
  and reported it as a deviation. Each backed it with an `ast.dump` equality check per file
  (old AST minus docstrings equals new AST). For a mechanical sweep across 100+ files this was the
  faster path and the proof was stronger than a manual review would have been.
- **Accidental live runs.** wsweep1 ran `--help` on 11 scripts to compare output; three had no
  argparse and executed for real (live HTTP GETs, one pydoll Chrome on the shared
  `~/.websearch/browser-session` profile, killed within a minute). The second-wave prompt added
  "check that a script parses args before running it"; no worker ran a live probe after that.
- **The three prompt lines from above** (hook rule named, stop-and-report on collision, evidence
  for convention claims): no worker hit a hook refusal, so the stop-and-report line was never
  tested. Workers did cite evidence (grep output, file paths) for convention claims unprompted.

## Open

- A mechanism that makes a blocked instruction a reportable event, outside the prompt text.
- A maintained list of hard environment rules the orchestrator reads before writing prompts.
- Per-turn duration is unreliable when an API error keeps a worker in-turn across a review
  message (observed 2026-09-17). Any duration measurement has to split turns by message, not by
  turn boundary.
