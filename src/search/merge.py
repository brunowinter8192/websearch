# INFRASTRUCTURE
import random
from collections import defaultdict

from src.search.result import SearchResult


# FUNCTIONS

def build_engine_pools(results: list[SearchResult]) -> dict[str, list[SearchResult]]:
    url_buckets: dict[str, list[SearchResult]] = defaultdict(list)
    for r in results:
        url_buckets[r.url].append(r)

    pools: dict[str, list[SearchResult]] = defaultdict(list)
    for url, bucket in url_buckets.items():
        min_pos = min(r.position for r in bucket)
        tied = [r for r in bucket if r.position == min_pos]
        winner = random.choice(tied)
        engine_positions = {r.engine: r.position for r in bucket}
        pools[winner.engine].append(SearchResult(
            url=winner.url,
            title=winner.title,
            snippet=winner.snippet,
            engine=winner.engine,
            position=winner.position,
            engine_positions=engine_positions,
            date=winner.date,
            pdf_url=winner.pdf_url,
        ))

    return {eng: sorted(pool, key=lambda r: r.position) for eng, pool in pools.items()}
