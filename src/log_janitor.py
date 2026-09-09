# INFRASTRUCTURE
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_MARKER_MAX_AGE_SECS = 3600


# FUNCTIONS

def get_retention_days() -> int:
    try:
        return int(os.environ.get("WEBSEARCH_LOG_RETENTION_DAYS", 14))
    except (ValueError, TypeError):
        return 14


def maybe_prune_jsonl(log_path: Path) -> None:
    marker = Path(str(log_path) + ".lastprune")
    if _is_recent(marker):
        return
    try:
        _prune_jsonl(log_path, marker)
    except Exception as e:
        logger.warning("log_janitor: prune_jsonl failed for %s: %s", log_path, e)


def maybe_prune_sidecars(sidecar_dir: Path) -> None:
    marker = sidecar_dir / ".lastprune"
    if _is_recent(marker):
        return
    try:
        _prune_sidecars(sidecar_dir, marker)
    except Exception as e:
        logger.warning("log_janitor: prune_sidecars failed for %s: %s", sidecar_dir, e)


def _is_recent(marker: Path) -> bool:
    try:
        return time.time() - marker.stat().st_mtime < _MARKER_MAX_AGE_SECS
    except FileNotFoundError:
        return False


def _prune_jsonl(log_path: Path, marker: Path) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_retention_days())
    kept = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                parsed_ts = datetime.fromisoformat(record["ts"])
                if parsed_ts >= cutoff:
                    kept.append(stripped)
            except Exception:
                logger.warning("log_janitor: dropping unparseable line in %s", log_path)
    tmp = Path(str(log_path) + ".tmp")
    tmp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    os.replace(tmp, log_path)
    marker.touch()


def _prune_sidecars(sidecar_dir: Path, marker: Path) -> None:
    cutoff_mtime = time.time() - get_retention_days() * 86400
    deleted = 0
    for f in sidecar_dir.glob("*.md"):
        try:
            if f.stat().st_mtime < cutoff_mtime:
                f.unlink()
                deleted += 1
        except Exception:
            logger.warning("log_janitor: failed to unlink sidecar %s", f)
    logger.info("log_janitor: pruned %d sidecar(s) from %s", deleted, sidecar_dir)
    marker.touch()
