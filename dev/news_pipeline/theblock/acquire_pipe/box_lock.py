# INFRASTRUCTURE
import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOCK_DIR    = Path.home() / ".websearch-locks"
_FLOCK_FILE = LOCK_DIR / "acquire_pipe.flock"
_SIDECAR    = LOCK_DIR / "acquire_pipe.lock"
_TS_FMT     = "%Y-%m-%dT%H:%M:%SZ"


# FUNCTIONS

@contextmanager
def acquire(job: str, target: str):
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_stale()

    fd = _FLOCK_FILE.open("a")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise LockBusyError(_busy_message())

    _write_sidecar({
        "pid":        os.getpid(),
        "job":        job,
        "target":     target,
        "started_at": datetime.now(timezone.utc).strftime(_TS_FMT),
        "status":     "running",
    })
    try:
        yield
    finally:
        _SIDECAR.unlink(missing_ok=True)
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def cleanup_stale() -> None:
    if not _SIDECAR.exists():
        return
    data = json.loads(_SIDECAR.read_text(encoding="utf-8"))
    pid  = data.get("pid")
    if pid is None:
        _SIDECAR.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _SIDECAR.unlink(missing_ok=True)
    except PermissionError:
        logger.warning("acquire_pipe lock holder pid=%s is owned by another user, sidecar kept", pid)


class LockBusyError(RuntimeError):
    pass


def _busy_message() -> str:
    data       = json.loads(_SIDECAR.read_text(encoding="utf-8"))
    pid        = data.get("pid", "?")
    job        = data.get("job", "?")
    target     = data.get("target", "?")
    started_at = data.get("started_at", "")
    elapsed    = ""
    if started_at:
        t0      = datetime.strptime(started_at, _TS_FMT).replace(tzinfo=timezone.utc)
        elapsed = f", running {int((datetime.now(timezone.utc) - t0).total_seconds())}s"
    return (
        f"acquire_pipe already running: pid={pid}, job={job!r}, "
        f"target={target!r}{elapsed}"
    )


def _write_sidecar(data: dict) -> None:
    tmp_fd, tmp_path = tempfile.mkstemp(dir=LOCK_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, str(_SIDECAR))
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
