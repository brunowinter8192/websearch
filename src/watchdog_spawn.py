# INFRASTRUCTURE
import os
import subprocess
import sys
from pathlib import Path


# FUNCTIONS

def spawn_watchdog(pids: list[int], cleanup_dir: str | None = None) -> int | None:
    if not pids and not cleanup_dir:
        return None
    read_fd, write_fd = os.pipe()
    cmd = [sys.executable, str(Path(__file__).resolve().parent / "death_pipe.py"), ",".join(str(p) for p in pids)]
    if cleanup_dir:
        cmd.append(cleanup_dir)
    subprocess.Popen(
        cmd, stdin=read_fd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    os.close(read_fd)
    return write_fd
