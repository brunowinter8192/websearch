# INFRASTRUCTURE

import httpx

from src.config import MONOSANS_URL, PROXY_LIST_FETCH_TIMEOUT
from src.news.engine.proxy_pool.pool_retry import fetch_with_retry


# ORCHESTRATOR

def load_monosans_proxies() -> list[tuple[str, str]]:
    raw = _fetch_json(MONOSANS_URL)
    return _build_entries(raw)


# FUNCTIONS

def _fetch_json(url: str) -> list[dict]:
    def _do():
        resp = httpx.get(url, timeout=PROXY_LIST_FETCH_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    return fetch_with_retry(_do)


def _build_entries(raw: list[dict]) -> list[tuple[str, str]]:
    return [_build_entry(e) for e in raw]


def _build_entry(entry: dict) -> tuple[str, str]:
    proto    = entry["protocol"]
    host     = entry["host"]
    port     = entry["port"]
    username = entry.get("username")
    password = entry.get("password")
    if username and password:
        host_port = f"{username}:{password}@{host}:{port}"
    else:
        host_port = f"{host}:{port}"
    return (proto, host_port)
