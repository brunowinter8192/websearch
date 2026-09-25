#!/usr/bin/env python3
# INFRASTRUCTURE
import os
import shutil
import sys
import time
from pathlib import Path

import psutil

_LOG_PATH = Path(
    os.environ.get("WEBSEARCH_DEATH_PIPE_LOG_PATH")
    or (Path(__file__).parent / "logs" / "cli.log")
)


# ORCHESTRATOR

def _watchdog_main() -> None:
    pids, cleanup_dir = _parse_watchdog_args(sys.argv)
    _wait_for_parent_death()
    killed = terminate_then_kill(pids)
    dir_removed = _remove_cleanup_dir(cleanup_dir)
    _report_intervention(killed, dir_removed, cleanup_dir)


# FUNCTIONS

def _parse_watchdog_args(argv: list[str]) -> tuple[list[int], str | None]:
    pids = [int(p) for p in argv[1].split(",") if p.strip()] if len(argv) > 1 else []
    cleanup_dir = argv[2] if len(argv) > 2 else None
    return pids, cleanup_dir


def _wait_for_parent_death() -> None:
    os.read(0, 1)


def terminate_then_kill(pids: list[int], timeout_s: float = 5.0) -> list[int]:
    procs = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            procs.append(proc)
        except psutil.NoSuchProcess:
            continue
    gone, alive = psutil.wait_procs(procs, timeout=timeout_s)
    killed = [p.pid for p in gone]
    for proc in alive:
        try:
            proc.kill()
            killed.append(proc.pid)
        except psutil.NoSuchProcess:
            continue
    return killed


def _remove_cleanup_dir(cleanup_dir: str | None) -> bool:
    dir_removed = False
    if cleanup_dir and Path(cleanup_dir).exists():
        shutil.rmtree(cleanup_dir, ignore_errors=True)
        dir_removed = not Path(cleanup_dir).exists()
    return dir_removed


def _report_intervention(killed: list[int], dir_removed: bool, cleanup_dir: str | None) -> None:
    if killed or dir_removed:
        _log_intervention(
            f"parent died without tearing down its own browser — killed pids={killed}, "
            f"removed_dir={cleanup_dir if dir_removed else None}"
        )


def _log_intervention(message: str) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{ts} [WARNING] src.death_pipe:watchdog - {message}\n")


if __name__ == "__main__":
    _watchdog_main()
