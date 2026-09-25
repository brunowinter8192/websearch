# INFRASTRUCTURE
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass
class FeederResult:
    urls: list
    ok: bool
    error: str | None = None
    source: str | None = None
    version_keys: list | None = None
    dropped: int = 0


# FUNCTIONS

async def run_guarded(collect: Callable[[str], Awaitable[FeederResult]], seed_url: str) -> FeederResult:
    try:
        return await collect(seed_url)
    except Exception as exc:
        return FeederResult(urls=[], ok=False, error=str(exc))


def base_url(seed_url: str) -> str:
    parsed = urlsplit(seed_url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = host if port is None or port == _DEFAULT_PORTS.get(scheme) else f"{host}:{port}"
    path = parsed.path or "/"
    normalized = f"{scheme}://{netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def host_key(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _dedup_key(normalized_url: str) -> str:
    parsed = urlsplit(normalized_url)
    collapsed_host = host_key(parsed.hostname or "")
    netloc_key = f"{collapsed_host}:{parsed.port}" if parsed.port else collapsed_host
    return urlunsplit((parsed.scheme, netloc_key, parsed.path, parsed.query, ""))


def scope_and_dedup(urls: list, seed_host: str) -> tuple:
    seed_key = host_key(seed_host)
    seen_keys = set()
    result = []
    dropped = 0
    for raw in urls:
        try:
            normalized = normalize_url(raw)
            parsed = urlsplit(normalized)
        except ValueError:
            dropped += 1
            continue
        if host_key(parsed.hostname or "") != seed_key:
            continue
        key = _dedup_key(normalized)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        result.append(normalized)
    return result, dropped


def require_host(seed_url: str) -> str:
    host = urlsplit(seed_url).hostname
    if not host:
        raise ValueError(f"seed_url has no host: {seed_url!r}")
    return host
