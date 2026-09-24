# INFRASTRUCTURE

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from proxy_status_log import proxy_key


# ORCHESTRATOR

class AcquireLogger:

    def __init__(self, total_urls: int, log_dir: Path):
        self._total      = total_urls
        log_dir.mkdir(parents=True, exist_ok=True)
        ts               = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._jsonl_path = log_dir / f"acquire_events_{ts}.jsonl"
        self._jsonl_fh   = self._jsonl_path.open("a", encoding="utf-8", buffering=1)

    def record_attempt(self, proto: str, host_port: str, url: str, ok: bool) -> None:
        event = {
            "proxy_key": proxy_key(proto, host_port),
            "ts":        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url":       url,
            "result":    "ok" if ok else "fail",
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def record_pool_refresh(self, size: int) -> None:
        event = {
            "event": "pool_refresh",
            "size":  size,
            "ts":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._jsonl_fh.write(json.dumps(event) + "\n")

    def close(self) -> None:
        self._jsonl_fh.close()
