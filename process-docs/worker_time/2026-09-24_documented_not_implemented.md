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

## Open

- A mechanism that makes a blocked instruction a reportable event, outside the prompt text.
- A maintained list of hard environment rules the orchestrator reads before writing prompts.
- Per-turn duration is unreliable when an API error keeps a worker in-turn across a review
  message (observed 2026-09-17). Any duration measurement has to split turns by message, not by
  turn boundary.
