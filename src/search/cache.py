# INFRASTRUCTURE
import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path

from src.search.result import SearchResult
from src.search.snippet import _strip_bloat, _truncate, MAX_SNIPPET_LEN

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "websearch"
DEFAULT_TTL = 3600


# FUNCTIONS

def cache_key(
    query: str,
    language: str,
    engines: str | None,
    time_range: str | None,
) -> str:
    canonical = f"{query.lower().strip()}|{language}|{engines or ''}|{time_range or ''}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def cache_write(
    key: str,
    pools: dict[str, list[SearchResult]],
    query: str,
    language: str,
    engines: str | None,
    time_range: str | None,
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    serialized_pools: dict[str, list[dict]] = {}
    for engine_name, pool in pools.items():
        serialized_pools[engine_name] = [
            {
                "url":      r.url,
                "title":    r.title,
                "snippet":  r.snippet,
                "position": r.position,
                "date":     r.date,
                "pdf_url":  r.pdf_url,
            }
            for r in pool
        ]
    payload = {
        "query":      query,
        "language":   language,
        "engines":    engines,
        "time_range": time_range,
        "timestamp":  int(time.time()),
        "pools":      serialized_pools,
    }
    target = cache_path(key)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)
        total = sum(len(p) for p in serialized_pools.values())
        logger.debug("Cache written: %s (%d urls across %d engines)", target, total, len(serialized_pools))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            logger.warning("Failed to remove temp file %s", tmp)
        raise


def cache_read(key: str, ttl_seconds: int = DEFAULT_TTL) -> dict | None:
    path = cache_path(key)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Cache read error %s: %s", path, e)
        return None


def format_engine_pool(pool: list[dict], engine_name: str, query: str) -> str:
    if not pool:
        return f'No results from {engine_name} for "{query}"'
    lines = [f'Results from {engine_name} for "{query}"\n']
    for entry in pool:
        lines.append(f"{entry['position']}. {entry['title']}")
        lines.append(f"   URL: {entry['url']}")
        pdf_url = entry.get("pdf_url")
        if pdf_url:
            lines.append(f"   PDF: {pdf_url}")
        date = entry.get("date")
        if date:
            lines.append(f"   Date: {date}")
        raw = entry.get("snippet") or ""
        if raw:
            snippet = _truncate(_strip_bloat(raw), MAX_SNIPPET_LEN)
            if snippet:
                lines.append(f"   Snippet: {snippet}")
        lines.append("")
    return "\n".join(lines)
