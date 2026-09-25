# INFRASTRUCTURE

import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.config import PROXY_TS_FMT

logger = logging.getLogger(__name__)

LOCK_DIR = Path.home() / ".websearch-locks"


# ORCHESTRATOR

def acquire(job: str, target: str, lock_name: str = "proxy_pool"):
    return _held_lock(job, target, lock_name)


# FUNCTIONS

@contextmanager
def _held_lock(job: str, target: str, lock_name: str):
    flock_file, sidecar = _prepare_lock_paths(lock_name)
    fd = _take_flock(flock_file, sidecar)
    _write_sidecar(sidecar, _holder_record(job, target))
    try:
        yield
    finally:
        _release_flock(sidecar, fd)


def _prepare_lock_paths(lock_name: str) -> tuple[Path, Path]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    flock_file = LOCK_DIR / f"{lock_name}.flock"
    sidecar    = LOCK_DIR / f"{lock_name}.lock"
    cleanup_stale(sidecar)
    return flock_file, sidecar


def cleanup_stale(sidecar: Path) -> None:
    if not sidecar.exists():
        return
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    pid  = data.get("pid")
    if pid is None:
        sidecar.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sidecar.unlink(missing_ok=True)
    except PermissionError:
        logger.warning("proxy_pool lock holder pid=%s is owned by another user, sidecar kept", pid)


def _take_flock(flock_file: Path, sidecar: Path):
    fd = flock_file.open("a")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise LockBusyError(_busy_message(sidecar))
    return fd


class LockBusyError(RuntimeError):
    pass


def _busy_message(sidecar: Path) -> str:
    data       = json.loads(sidecar.read_text(encoding="utf-8"))
    pid        = data.get("pid", "?")
    job        = data.get("job", "?")
    target     = data.get("target", "?")
    started_at = data.get("started_at", "")
    elapsed    = ""
    if started_at:
        t0      = datetime.strptime(started_at, PROXY_TS_FMT).replace(tzinfo=timezone.utc)
        elapsed = f", running {int((datetime.now(timezone.utc) - t0).total_seconds())}s"
    return (
        f"proxy_pool already running: pid={pid}, job={job!r}, "
        f"target={target!r}{elapsed}"
    )


def _write_sidecar(sidecar: Path, data: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=LOCK_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, str(sidecar))
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _holder_record(job: str, target: str) -> dict:
    return {
        "pid":        os.getpid(),
        "job":        job,
        "target":     target,
        "started_at": datetime.now(timezone.utc).strftime(PROXY_TS_FMT),
        "status":     "running",
    }


def _release_flock(sidecar: Path, fd) -> None:
    sidecar.unlink(missing_ok=True)
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()
