# INFRASTRUCTURE
import re
import time
from urllib.parse import urlparse

from _stage3_method_run_v3_config import TOP_N

from rerank_probe_smoke import _bm25_score

RRF_K        = 60


# FUNCTIONS

def _apply_m1(pool: list[dict]) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    ranked = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:TOP_N]], ms


def _apply_m2(pool: list[dict]) -> tuple[list[str], int, dict[str, float]]:
    t0  = time.perf_counter()
    scores: dict[str, float] = {}
    for m in pool:
        url   = m["url"]
        pos   = m.get("positions", {})
        score = sum(1.0 / (RRF_K + p) for p in pos.values()) if pos else 1.0 / (RRF_K + m.get("min_position", 999))
        scores[url] = score
    ranked = sorted(pool, key=lambda m: -scores[m["url"]])
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:TOP_N]], ms, scores


def _apply_m3(pool: list[dict]) -> tuple[list[str], int]:
    t0 = time.perf_counter()

    def _penalty(url: str) -> float:
        p   = 0.0
        low = url.lower()
        if re.search(r"[?&](q|query|search|keyword|term|p)=", low):
            p -= 0.5
        parsed = urlparse(url)
        path   = parsed.path.lower()
        if re.search(r"/(search|results|sresults)/", path):
            p -= 0.3
        depth = len([s for s in path.split("/") if s])
        if depth > 4:
            p -= 0.1 * (depth - 4)
        return p

    scored = [(m, _penalty(m["url"])) for m in pool]
    ranked = sorted(scored, key=lambda x: (-x[1], x[0].get("min_position", 999)))
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in ranked[:TOP_N]], ms


def _apply_m4(pool_full: list[dict], query: str) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(pool_full, query, TOP_N)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms


def _apply_m5(pool: list[dict], query: str) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(pool, query, TOP_N)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms
