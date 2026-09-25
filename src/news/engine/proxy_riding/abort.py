# INFRASTRUCTURE

import os
import signal
import sys

from src.news.engine.proxy_riding.state import RiderState


# FUNCTIONS

def abort_done(state: RiderState) -> None:
    print(
        f"[watchdog] all-done but in_flight={state.in_flight} — "
        f"wedged slot(s) on already-done URLs; writing report → os._exit(0)",
        file=sys.stderr,
    )
    state.termination = "all-done"
    _abort_write_report_and_exit(state, log_prefix="[watchdog]", exit_code=0)


def _abort_write_report_and_exit(state: RiderState, log_prefix: str, exit_code: int) -> None:
    state.job_dir.mkdir(parents=True, exist_ok=True)

    try:
        from src.news.engine.proxy_riding.reporter import write_riding_report
        write_riding_report(state, state.job_dir, state.t_job_start)
        print(f"{log_prefix} job.md → {state.job_dir / 'job.md'}", file=sys.stderr)
    except Exception as exc:
        print(f"{log_prefix} write_riding_report WARN: {exc}", file=sys.stderr)

    sys.stderr.flush()
    os._exit(exit_code)


def abort_interrupted(state: RiderState, signum: int) -> None:
    name      = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    exit_code = 130      if signum == signal.SIGINT else 143
    print(
        f"[rider] {name} received — writing report → os._exit({exit_code})",
        file=sys.stderr,
    )
    state.termination = "interrupted"
    _abort_write_report_and_exit(state, log_prefix="[rider]", exit_code=exit_code)


def abort_stall(state: RiderState, idle_s: float) -> None:
    print(
        f"[watchdog] STALL {idle_s:.0f}s ≥ {state.stall_timeout_s:.0f}s — "
        f"writing report → os._exit(1)",
        file=sys.stderr,
    )
    state.termination = "stall"
    _abort_write_report_and_exit(state, log_prefix="[watchdog]", exit_code=1)
