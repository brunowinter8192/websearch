#!/usr/bin/env python3
# INFRASTRUCTURE
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

_LOG_PATH = Path(
    os.environ.get("WEBSEARCH_DEATH_PIPE_LOG_PATH")
    or (Path(__file__).parent / "logs" / "cli.log")
)


# FUNCTIONS

def spawn_watchdog(pids: list[int], cleanup_dir: str | None = None) -> int | None:
    if not pids and not cleanup_dir:
        return None
    read_fd, write_fd = os.pipe()
    cmd = [sys.executable, str(Path(__file__).resolve()), ",".join(str(p) for p in pids)]
    if cleanup_dir:
        cmd.append(cleanup_dir)
    subprocess.Popen(
        cmd, stdin=read_fd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    os.close(read_fd)
    return write_fd


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


def _log_intervention(message: str) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{ts} [WARNING] src.death_pipe:watchdog - {message}\n")


def _watchdog_main() -> None:
    pids = [int(p) for p in sys.argv[1].split(",") if p.strip()] if len(sys.argv) > 1 else []
    cleanup_dir = sys.argv[2] if len(sys.argv) > 2 else None

    os.read(0, 1)

    killed = terminate_then_kill(pids)
    dir_removed = False
    if cleanup_dir and Path(cleanup_dir).exists():
        shutil.rmtree(cleanup_dir, ignore_errors=True)
        dir_removed = not Path(cleanup_dir).exists()

    if killed or dir_removed:
        _log_intervention(
            f"parent died without tearing down its own browser — killed pids={killed}, "
            f"removed_dir={cleanup_dir if dir_removed else None}"
        )


if __name__ == "__main__":
    _watchdog_main()
