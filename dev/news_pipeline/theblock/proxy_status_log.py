#!/usr/bin/env python3

# INFRASTRUCTURE

import json
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LOG_PATH   = SCRIPT_DIR / "logs" / "proxy_status_log.json"

# ORCHESTRATOR

def record_run(results: list[dict], source_label: str) -> None:
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _load_log()

    for r in results:
        key = proxy_key(r["proto"], r["host_port"])
        host, port = _parse_host_port(r["host_port"])

        if key not in data:
            data[key] = {
                "protocol":   r["proto"],
                "host":       host,
                "port":       port,
                "checks":     0,
                "alive":      0,
                "dead":       0,
                "last_status": "",
                "first_seen": ts,
                "last_seen":  ts,
            }

        entry = data[key]
        entry["checks"]     += 1
        entry["last_seen"]   = ts
        entry["last_status"] = "alive" if r["alive"] else "dead"
        if r["alive"]:
            entry["alive"] += 1
        else:
            entry["dead"] += 1

    _save_log(data)
    alive = sum(1 for r in results if r["alive"])
    print(f"proxy_status_log: {len(results)} results ({alive} alive) folded → {len(data)} unique proxies on record  [{LOG_PATH}]")

# FUNCTIONS

def _load_log() -> dict:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        return {}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def _save_log(data: dict) -> None:
    LOG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def partition_fresh(
    entries: list[tuple[str, str]],
    window_s: int,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    data = _load_log()
    now  = datetime.now(timezone.utc)
    to_check: list[tuple[str, str]]      = []
    skipped_fresh: list[tuple[str, str]] = []
    for proto, host_port in entries:
        key   = proxy_key(proto, host_port)
        entry = data.get(key)
        if entry is None:
            to_check.append((proto, host_port))
            continue
        last_seen_dt = datetime.strptime(entry["last_seen"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_s        = (now - last_seen_dt).total_seconds()
        if age_s >= window_s:
            to_check.append((proto, host_port))
        else:
            skipped_fresh.append((proto, host_port))
    return to_check, skipped_fresh


def proxy_key(proto: str, host_port: str) -> str:
    host, port = _parse_host_port(host_port)
    return f"{proto}://{host}:{port}"


def _parse_host_port(host_port: str) -> tuple[str, int]:
    clean        = host_port.split("@")[-1]
    host, port_s = clean.rsplit(":", 1)
    return host, int(port_s)
