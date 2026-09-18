# INFRASTRUCTURE
from collections import defaultdict

from src.search.result import SearchResult


# FUNCTIONS

def build_engine_pools(results: list[SearchResult]) -> dict[str, list[SearchResult]]:
    url_buckets: dict[str, list[SearchResult]] = defaultdict(list)
    for r in results:
        url_buckets[r.url].append(r)

    pools: dict[str, list[SearchResult]] = defaultdict(list)
    for url, bucket in url_buckets.items():
        engine_positions = {r.engine: r.position for r in bucket}
        best_per_engine: dict[str, SearchResult] = {}
        for r in bucket:
            current = best_per_engine.get(r.engine)
            if current is None or r.position < current.position:
                best_per_engine[r.engine] = r
        for engine, r in best_per_engine.items():
            pools[engine].append(SearchResult(
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                engine=r.engine,
                position=r.position,
                engine_positions=engine_positions,
                date=r.date,
                pdf_url=r.pdf_url,
            ))

    return {eng: sorted(pool, key=lambda r: r.position) for eng, pool in pools.items()}
