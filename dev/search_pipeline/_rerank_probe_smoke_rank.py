# INFRASTRUCTURE
import re
import time
import warnings
from collections import Counter

import numpy as np

from _rerank_probe_smoke_config import BM25_B, BM25_K1, BM25_REPR, BM25_SW, RETRIEVE_N, TOP_N
from _rerank_probe_smoke_gpu import cosine_sim, cross_encoder_rerank, embed_batch
from bm25_sweep_smoke import BM25Uniform, _build_pool, _doc_repr, _tokenize

# Search-results-page URL patterns (generic, query-independent)
SEARCH_PAGE_RE = re.compile(
    r'[?&](q|query|search|keyword|term|p)='
    r'|/search/'
    r'|/sresults/'
    r'|/scholar\?q='
)


# FUNCTIONS

def _filter_search_pages(raw_results: list) -> tuple[list, int, Counter]:
    removed_urls    = [r.url for r in raw_results if is_search_results_url(r.url)]
    filtered_raw    = [r     for r in raw_results if not is_search_results_url(r.url)]
    filtered_count  = len(filtered_raw)
    # Pattern histogram
    pattern_hist = Counter()
    for url in removed_urls:
        if re.search(r'[?&](q|query|search|keyword|term|p)=', url):
            pattern_hist["query_param"] += 1
        if "/search/" in url:
            pattern_hist["/search/"] += 1
        if "/sresults/" in url:
            pattern_hist["/sresults/"] += 1
        if "/scholar?q=" in url:
            pattern_hist["/scholar?q="] += 1
    return filtered_raw, filtered_count, pattern_hist


def _run_bm25_only(pool: list[dict], query: str) -> tuple[list[dict], int]:
    t0 = time.perf_counter()
    bm25_pairs   = _bm25_score(pool, query, TOP_N)
    bm25_top     = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in bm25_pairs]
    bm25_ms      = round((time.perf_counter() - t0) * 1000)
    return bm25_top, bm25_ms


def _retrieve_candidates(pool: list[dict], query: str) -> tuple[list, int, list[dict], list[str]]:
    t0 = time.perf_counter()
    bm25_candidates = _bm25_score(pool, query, RETRIEVE_N)
    retrieve_ms = round((time.perf_counter() - t0) * 1000)

    cand_docs  = [d for d, _ in bm25_candidates]
    # Filter out empty/whitespace-only texts — reranker returns 400 on empty documents
    _raw_texts = [_doc_repr(d, BM25_REPR) for d in cand_docs]
    _valid     = [(d, t) for d, t in zip(cand_docs, _raw_texts) if t.strip()]
    cand_docs  = [d for d, _ in _valid]
    cand_texts = [t for _, t in _valid]
    return bm25_candidates, retrieve_ms, cand_docs, cand_texts


def _run_embed_rerank(query: str, cand_docs: list[dict], cand_texts: list[str]) -> tuple[list[dict], int]:
    t0 = time.perf_counter()
    if cand_texts:
        all_texts = [query] + cand_texts
        embeddings = embed_batch(all_texts)
        query_emb  = embeddings[0]
        doc_embs   = embeddings[1:]
        cosine_scores = [cosine_sim(query_emb, de) for de in doc_embs]
        cos_ranked = sorted(range(len(cand_docs)), key=lambda i: -cosine_scores[i])
        embed_top  = [
            {"url": cand_docs[i]["url"], "engines": cand_docs[i]["engines"], "score": cosine_scores[i]}
            for i in cos_ranked[:TOP_N]
        ]
    else:
        embed_top = []
    embed_ms = round((time.perf_counter() - t0) * 1000)
    return embed_top, embed_ms


def _run_ce_rerank(query: str, cand_docs: list[dict], cand_texts: list[str]) -> tuple[list[dict], int]:
    t0 = time.perf_counter()
    if cand_texts:
        ce_pairs  = cross_encoder_rerank(query, cand_texts)
        ce_sorted = sorted(ce_pairs, key=lambda x: -x[1])
        ce_top    = [
            {"url": cand_docs[idx]["url"], "engines": cand_docs[idx]["engines"], "score": score}
            for idx, score in ce_sorted[:TOP_N]
        ]
    else:
        ce_top = []
    rerank_ms = round((time.perf_counter() - t0) * 1000)
    return ce_top, rerank_ms


def _run_capped(raw_results: list, engine_stats: dict, query: str) -> tuple[int, list[dict], list[dict], int]:
    K           = _compute_K(engine_stats)
    capped_raw  = [r for r in raw_results if r.position <= K]
    capped_pool = _build_pool(capped_raw)
    t0 = time.perf_counter()
    capped_pairs = _bm25_score(capped_pool, query, TOP_N)
    capped_ms    = round((time.perf_counter() - t0) * 1000)
    capped_top   = [{"url": d["url"], "engines": d["engines"], "score": s} for d, s in capped_pairs]
    return K, capped_pool, capped_top, capped_ms


# Return True if URL looks like a search-results page (not a content page)
def is_search_results_url(url: str) -> bool:
    return bool(SEARCH_PAGE_RE.search(url))


# BM25 score pool; return top-N as [(doc, score), ...]
def _bm25_score(pool: list[dict], query: str, top_n: int) -> list[tuple[dict, float]]:
    if not pool:
        return []
    corpus = [_tokenize(_doc_repr(m, BM25_REPR), BM25_SW) for m in pool]
    qtoks  = _tokenize(query, BM25_SW)
    bm25   = BM25Uniform(corpus, k1=BM25_K1, b=BM25_B)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = bm25.get_scores(qtoks)
    scores = np.nan_to_num(scores, nan=0.0)
    ranked = sorted(range(len(pool)), key=lambda i: -float(scores[i]))
    return [(pool[i], float(scores[i])) for i in ranked[:top_n]]


# K = google result count; fallback 10
def _compute_K(engine_stats: dict) -> int:
    K = engine_stats.get("google", {}).get("result_count", 0)
    return K if K > 0 else 10
