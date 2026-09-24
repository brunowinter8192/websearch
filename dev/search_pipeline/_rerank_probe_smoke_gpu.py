# INFRASTRUCTURE
import math
import sys

import httpx

from _rerank_probe_smoke_config import EMBEDDING_URL, RERANKER_URL


# FUNCTIONS

def _verify_services() -> None:
    print("Verifying services …", file=sys.stderr)
    try:
        r = httpx.post(EMBEDDING_URL, json={"input": ["warmup"], "model": "qwen-emb-0.6b"}, timeout=10.0)
        r.raise_for_status()
        print(f"  Embedding service OK ({r.elapsed.microseconds // 1000}ms)", file=sys.stderr)
    except (httpx.HTTPError, httpx.ConnectError) as e:
        sys.exit(f"ERROR: Embedding service unreachable at {EMBEDDING_URL}: {e}")

    try:
        r = httpx.post(RERANKER_URL, json={"query": "warmup", "documents": ["test"]}, timeout=10.0)
        r.raise_for_status()
        print(f"  Reranker  service OK ({r.elapsed.microseconds // 1000}ms)", file=sys.stderr)
    except (httpx.HTTPError, httpx.ConnectError) as e:
        sys.exit(f"ERROR: Reranker service unreachable at {RERANKER_URL}: {e}")
    print(file=sys.stderr)


def embed_batch(texts: list[str]) -> list[list[float]]:
    r = httpx.post(EMBEDDING_URL, json={"input": texts, "model": "qwen-emb-0.6b"}, timeout=60.0)
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]


def cross_encoder_rerank(query: str, documents: list[str]) -> list[tuple[int, float]]:
    r = httpx.post(RERANKER_URL, json={"query": query, "documents": documents}, timeout=60.0)
    r.raise_for_status()
    results = r.json().get("results", [])
    return [(item["index"], item["relevance_score"]) for item in results]


def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0
