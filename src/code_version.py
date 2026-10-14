# INFRASTRUCTURE
import subprocess
from functools import cache
from pathlib import Path

from src.config import PROJECT_ROOT

SHA_LENGTH = 10
GIT_TIMEOUT_S = 5
DIRTY_SUFFIX = "+dirty"
UNKNOWN_VERSION = "unknown"


# FUNCTIONS

@cache
def code_version() -> str:
    return read_code_version(PROJECT_ROOT)


def read_code_version(root: Path) -> str:
    sha = _git_output(root, ["rev-parse", f"--short={SHA_LENGTH}", "HEAD"])
    if not sha:
        return UNKNOWN_VERSION
    tracked_changes = _git_output(root, ["status", "--porcelain", "--untracked-files=no"])
    if tracked_changes is None:
        return UNKNOWN_VERSION
    return sha + DIRTY_SUFFIX if tracked_changes else sha


def _git_output(root: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
