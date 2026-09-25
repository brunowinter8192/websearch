# INFRASTRUCTURE

import json
import logging
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from src.config import LOG_DIR
from src.news.platform import Platform

PRECONDITION_TIMEOUT = 10


# FUNCTIONS

def _setup_logging(name: str) -> logging.Logger:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = LOG_DIR / f"news_{name}_{today}.log"
    fmt = "[%(asctime)s] %(levelname)s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger(f"news.{name}")
    log.info(f"Log file: {log_file}")
    return log


def _check_internet(platform: Platform, log: logging.Logger) -> bool:
    try:
        with urllib.request.urlopen(platform.precondition_url, timeout=PRECONDITION_TIMEOUT):
            log.info(f"  [OK] Internet reachable ({platform.precondition_url})")
            return True
    except Exception as e:
        log.error(f"  [FAIL] Internet unreachable: {e}")
        return False


def _persist_master_list(entries: list[dict], master_path: Path, log: logging.Logger) -> None:
    master_path.parent.mkdir(parents=True, exist_ok=True)
    new_lines: set[str] = set()
    for e in entries:
        lastmod = e.get("lastmod", "")
        if not lastmod or len(lastmod) < 10:
            continue
        url = e.get("url", "")
        if not url:
            continue
        new_lines.add(f"{lastmod[:10]}\t{url}")
    existing: set[str] = set()
    if master_path.exists():
        for line in master_path.read_text(encoding="utf-8").splitlines():
            if line:
                existing.add(line)
    merged = existing | new_lines
    master_path.write_text("\n".join(sorted(merged)) + "\n", encoding="utf-8")
    log.info(
        f"master_urls.txt → {len(merged)} lines ({len(new_lines - existing)} new) → {master_path}"
    )


def _write_discover_snapshot(entries: list[dict], discover_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = discover_dir / f"discover_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_marker(name: str, log: logging.Logger) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker = LOG_DIR / f"news_{name}_last_run.txt"
    marker.write_text(ts + "\n", encoding="utf-8")
    log.info(f"Last run marker: {ts}")
