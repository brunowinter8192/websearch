# INFRASTRUCTURE
import fcntl
import json
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
POLL_INTERVAL_S = 0.25


class LockHandle:
    def __init__(self, fd, sidecar_path: Path):
        self._fd = fd
        self._sidecar_path = sidecar_path

    def release(self) -> None:
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()
        self._sidecar_path.unlink(missing_ok=True)


# FUNCTIONS

def acquire(lock_path: Path, hard_budget_s: float, on_stale: Callable[[], None] | None = None) -> LockHandle:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path = lock_path.with_suffix(".json")
    while True:
        fd = open(lock_path, "a")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _write_sidecar(sidecar_path)
            return LockHandle(fd, sidecar_path)
        except BlockingIOError:
            fd.close()
        age = _sidecar_age_s(sidecar_path)
        if age is not None and age > hard_budget_s:
            logger.warning(
                "breaking stale browser-session lock: holder pid=%s age=%.1fs budget=%.1fs",
                (_read_sidecar(sidecar_path) or {}).get("pid"), age, hard_budget_s,
            )
            if on_stale is not None:
                on_stale()
            _break_lock(lock_path, sidecar_path)
            continue
        time.sleep(POLL_INTERVAL_S)


def _write_sidecar(sidecar_path: Path) -> None:
    tmp_path = sidecar_path.with_suffix(f".json.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps({
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).strftime(_TS_FMT),
    }))
    os.replace(tmp_path, sidecar_path)


def _read_sidecar(sidecar_path: Path) -> dict | None:
    try:
        return json.loads(sidecar_path.read_text())
    except FileNotFoundError:
        return None


def _sidecar_age_s(sidecar_path: Path) -> float | None:
    data = _read_sidecar(sidecar_path)
    if data is None:
        return None
    started = datetime.strptime(data["started_at"], _TS_FMT).replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - started).total_seconds()


def _break_lock(lock_path: Path, sidecar_path: Path) -> None:
    lock_path.unlink(missing_ok=True)
    sidecar_path.unlink(missing_ok=True)
