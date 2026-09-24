# INFRASTRUCTURE
import json
import re
import sys
import time

import httpx

from _stage3_method_run_v3_config import TOP_N

# From bm25_sweep_smoke.py: BM25 helpers
from bm25_sweep_smoke import _doc_repr

BM25_REPR    = "title+snippet"
HYBRID_ALPHA = 0.5   # weight for C3 component in hybrids (M8, M10)

# Instruction prefix for M7
M7_PREFIX = "Find authoritative primary or official sources for: "

# LLM prompt for M11 / M12 (see _build_llm_prompt)
LLM_SYSTEM = (
    'You are evaluating search results for the query: "{query}"\n'
    "Select exactly 10 URLs from the candidate list below that are MOST LIKELY to be "
    "authoritative primary or official sources. Avoid SEO listicles, content farms, "
    "and tutorial blogs unless they are the canonical reference. "
    "Reply with a JSON array of exactly 10 URLs, no other text."
)


# FUNCTIONS

# Cross-encoder rerank call; returns [(index, relevance_score), ...]
def _cross_encoder_rerank(query: str, documents: list[str], reranker_url: str) -> list[tuple[int, float]]:
    r = httpx.post(reranker_url, json={"query": query, "documents": documents}, timeout=120.0)
    r.raise_for_status()
    return [(item["index"], item["relevance_score"]) for item in r.json().get("results", [])]


# M6 — C3 Cross-Encoder vanilla; returns (urls, ms, score_dict)
def _apply_m6(pool: list[dict], query: str, reranker_url: str) -> tuple[list[str], int, dict[str, float]]:
    return _rerank_pool(pool, query, reranker_url, query_text=query)


# M7 — C3 + Instruction-Prefix; returns (urls, ms, score_dict)
def _apply_m7(pool: list[dict], query: str, reranker_url: str) -> tuple[list[str], int, dict[str, float]]:
    return _rerank_pool(pool, query, reranker_url, query_text=M7_PREFIX + query)


# Shared reranker implementation for M6/M7
def _rerank_pool(pool: list[dict], query: str, reranker_url: str, query_text: str) -> tuple[list[str], int, dict[str, float]]:
    if not pool:
        return [], 0, {}
    valid = [(m, _doc_repr(m, BM25_REPR)) for m in pool if _doc_repr(m, BM25_REPR).strip()]
    if not valid:
        return [], 0, {}
    docs_v  = [m for m, _ in valid]
    texts_v = [t for _, t in valid]
    t0 = time.perf_counter()
    try:
        pairs      = _cross_encoder_rerank(query_text, texts_v, reranker_url)
        score_dict = {docs_v[idx]["url"]: score for idx, score in pairs}
        ranked     = sorted(pairs, key=lambda x: -x[1])[:TOP_N]
        ms         = round((time.perf_counter() - t0) * 1000)
        return [docs_v[idx]["url"] for idx, _ in ranked], ms, score_dict
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000)
        print(f"  reranker error: {exc}", file=sys.stderr)
        return [], ms, {}


# Min-max normalize a score dict to [0, 1]; returns new dict
def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 0.5 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


# M8 — RRF + C3 Hybrid (no GPU; reuses c3_scores from M6 and rrf_scores from M2)
def _apply_m8(
    pool: list[dict], c3_scores: dict[str, float], rrf_scores: dict[str, float]
) -> tuple[list[str], int]:
    t0       = time.perf_counter()
    c3_norm  = _normalize(c3_scores)
    rrf_norm = _normalize(rrf_scores)
    combined = {
        m["url"]: HYBRID_ALPHA * c3_norm.get(m["url"], 0.0) + (1 - HYBRID_ALPHA) * rrf_norm.get(m["url"], 0.0)
        for m in pool
    }
    ranked = sorted(pool, key=lambda m: -combined[m["url"]])
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:TOP_N]], ms


# M9 — SPLADE standalone; returns (urls, ms, splade_scores)
def _apply_m9(pool: list[dict], query: str, splade_url: str) -> tuple[list[str], int, dict[str, float]]:
    if not pool:
        return [], 0, {}
    docs    = [_doc_repr(m, BM25_REPR) for m in pool]
    all_texts = [query] + docs
    t0 = time.perf_counter()
    try:
        r = httpx.post(splade_url, json={"input": all_texts, "model": "splade"}, timeout=120.0)
        r.raise_for_status()
        vectors   = [item["sparse_vector"] for item in r.json()["data"]]
        q_vec     = vectors[0]
        q_map     = dict(zip(q_vec["indices"], q_vec["values"]))
        scores: dict[str, float] = {}
        for m, d_vec in zip(pool, vectors[1:]):
            dot = sum(q_map.get(i, 0.0) * v for i, v in zip(d_vec["indices"], d_vec["values"]))
            scores[m["url"]] = dot
        ranked = sorted(pool, key=lambda m: -scores[m["url"]])
        ms     = round((time.perf_counter() - t0) * 1000)
        return [m["url"] for m in ranked[:TOP_N]], ms, scores
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000)
        print(f"  SPLADE error: {exc}", file=sys.stderr)
        return [], ms, {}


# M10 — SPLADE + C3 Hybrid (no GPU; reuses c3_scores from M6 + splade_scores from M9)
def _apply_m10(
    pool: list[dict], c3_scores: dict[str, float], splade_scores: dict[str, float]
) -> tuple[list[str], int]:
    t0          = time.perf_counter()
    c3_norm     = _normalize(c3_scores)
    splade_norm = _normalize(splade_scores)
    combined    = {
        m["url"]: HYBRID_ALPHA * c3_norm.get(m["url"], 0.0) + (1 - HYBRID_ALPHA) * splade_norm.get(m["url"], 0.0)
        for m in pool
    }
    ranked = sorted(pool, key=lambda m: -combined[m["url"]])
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:TOP_N]], ms


# Build LLM prompt for M11/M12; pool_entries is the candidate list
def _build_llm_prompt(query: str, pool_entries: list[dict]) -> tuple[str, str]:
    system = LLM_SYSTEM.format(query=query)
    lines  = ["Candidates:"]
    for i, m in enumerate(pool_entries, 1):
        title   = (m.get("title")   or "").strip().replace("\n", " ")[:120]
        snippet = (m.get("snippet") or "").strip().replace("\n", " ")[:200]
        lines.append(f"{i}. {m['url']} — {title}")
        if snippet:
            lines.append(f"   {snippet}")
    user = "\n".join(lines)
    return system, user


# Call generator-4b; return (urls, ms, (tokens_in, tokens_out))
def _call_generator(system: str, user: str, known_urls: set[str], generator_url: str) -> tuple[list[str], int, tuple[int, int]]:
    payload = {
        "model":       "qwen",
        "messages":    [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens":  512,
        "temperature": 0.0,
    }
    t0 = time.perf_counter()
    try:
        r = httpx.post(generator_url, json=payload, timeout=120.0)
        r.raise_for_status()
        body       = r.json()
        content    = body["choices"][0]["message"]["content"].strip()
        tokens_in  = body.get("usage", {}).get("prompt_tokens", 0)
        tokens_out = body.get("usage", {}).get("completion_tokens", 0)
        # Strip markdown fences if present
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content).rstrip("`").strip()
        urls  = json.loads(content) if content.startswith("[") else []
        urls  = [u for u in urls if isinstance(u, str) and u in known_urls][:TOP_N]
        ms    = round((time.perf_counter() - t0) * 1000)
        return urls, ms, (tokens_in, tokens_out)
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000)
        print(f"  generator error: {exc}", file=sys.stderr)
        return [], ms, (0, 0)


# M11 — Two-Stage C3 + LLM-Filter (C3 top-20 → generator filter → top-10)
def _apply_m11(
    pool: list[dict], query: str, c3_scores: dict[str, float], generator_url: str
) -> tuple[list[str], int, tuple[int, int]]:
    if not pool:
        return [], 0, (0, 0)
    # Stage a: take C3 top-20
    ranked_by_c3  = sorted(pool, key=lambda m: -c3_scores.get(m["url"], 0.0))
    top20_entries = ranked_by_c3[:20]
    known_urls    = {m["url"] for m in top20_entries}
    # Stage b: generator filter
    system, user  = _build_llm_prompt(query, top20_entries)
    urls, ms, toks = _call_generator(system, user, known_urls, generator_url)
    return urls, ms, toks


# M12 — LLM-as-Selector direct (full filtered pool → generator → top-10)
def _apply_m12(pool: list[dict], query: str, generator_url: str) -> tuple[list[str], int, tuple[int, int]]:
    if not pool:
        return [], 0, (0, 0)
    known_urls    = {m["url"] for m in pool}
    system, user  = _build_llm_prompt(query, pool)
    urls, ms, toks = _call_generator(system, user, known_urls, generator_url)
    return urls, ms, toks
