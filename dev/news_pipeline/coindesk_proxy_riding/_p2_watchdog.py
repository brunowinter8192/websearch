# INFRASTRUCTURE

import asyncio
import os
import sys
import time
from pathlib import Path

from _p2_state import RiderState


# FUNCTIONS

async def _watchdog(
    state:         RiderState,
    output_dir:    Path,
    poll_interval: float | None = None,
) -> None:
    interval = poll_interval if poll_interval is not None else min(30.0, state.stall_timeout_s / 4)
    while True:
        await asyncio.sleep(interval)
        if state.all_resolved:
            return
        idle = time.monotonic() - state.last_progress_mono
        if idle > state.stall_timeout_s:
            _abort_stall(state, output_dir, idle)


def _abort_stall(state: RiderState, output_dir: Path, idle_s: float) -> None:
    print(
        f"[watchdog] STALL {idle_s:.0f}s ≥ {state.stall_timeout_s:.0f}s — "
        f"writing report + failure log → os._exit(1)",
        file=sys.stderr,
    )
    state.termination = "stall"

    queued = _drain_queue(state)

    inflight = sorted(state.in_flight_urls)

    fail_log = _write_remaining_urls_log(output_dir, idle_s, state.stall_timeout_s, queued, inflight)
    print(f"[watchdog] failure log → {fail_log}", file=sys.stderr)

    _write_stall_job_md(state, output_dir, idle_s)

    sys.stderr.flush()
    os._exit(1)


def _drain_queue(state: RiderState) -> list:
    queued: list[str] = []
    while True:
        try:
            queued.append(state.url_queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return queued


def _write_remaining_urls_log(output_dir: Path, idle_s: float, stall_timeout_s: float,
                               queued: list, inflight: list) -> Path:
    fail_log = output_dir / "remaining_urls.txt"
    lines = [
        f"# Remaining URLs at stall abort — idle {idle_s:.0f}s (threshold {stall_timeout_s:.0f}s)",
        f"# Total un-scraped: {len(queued) + len(inflight)}",
        "",
        f"# never attempted (queue) — {len(queued)} URLs",
    ] + queued + [
        "",
        f"# in-flight / wedged at abort — {len(inflight)} URLs",
    ] + inflight
    fail_log.write_text("\n".join(lines), encoding="utf-8")
    return fail_log


def _write_stall_job_md(state: RiderState, output_dir: Path, idle_s: float) -> None:
    try:
        from p4_reporter import write_riding_report
        write_riding_report(state, output_dir, state.t_job_start)
        print(f"[watchdog] job.md → {output_dir / 'job.md'}", file=sys.stderr)
    except Exception as exc:
        print(f"[watchdog] write_riding_report WARN: {exc}", file=sys.stderr)
        try:
            (output_dir / "job.md").write_text(
                "\n".join([
                    "# CoinDesk riding job — STALL ABORT",
                    "",
                    "termination: stall",
                    f"idle_s: {idle_s:.0f}",
                    f"n_ok: {state.n_ok}",
                    f"n_regwall: {state.n_regwall}",
                    f"n_failed: {state.n_failed}",
                    f"n_connect_fail: {state.n_connect_fail}",
                    "",
                    f"Reporter error: {exc}",
                ]),
                encoding="utf-8",
            )
        except Exception as write_exc:
            print(f"[watchdog] fallback job.md WARN: {write_exc}", file=sys.stderr)
