#!/usr/bin/env python3
"""
Value Eval Probe — Stage 1+2: pool fetch + C-method scoring (bead searxng-g82).

Fetches results for each (mode, query) pair; saves pool.json (oracle input: url/title/snippet only,
no scores) and methods.json (C1/C2/C2'/C3 Top-10 URLs) per pair.

Methods:
  C1  — Overlap-Count: sort (-n_engines, min_position)
  C2  — BM25 vanilla (k1=1.2, b=0.75, sw=on, title+snippet) on full filtered pool
  C2' — BM25-Capped: BM25 on capped pool (position ≤ google_count, then filtered)
  C3  — Cross-Encoder rerank (Qwen3-Reranker-0.6B, port 8082) on full filtered pool

Smoke mode (--smoke): one pair only (general × transformer attention mechanism),
  then auto-runs Stage 4 aggregator with --no-oracle to verify the chain.

Usage:
  ./venv/bin/python dev/search_pipeline/value_eval_probe.py [--smoke] [--ts-dir PATH]
"""

# INFRASTRUCTURE
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse as _urlparse

import httpx

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

# Dev-module imports (src/ access via rerank_probe_smoke / bm25_sweep_smoke intermediaries)
from bm25_sweep_smoke import _build_pool, _doc_repr
from rerank_probe_smoke import (
    RERANKER_URL,
    cross_encoder_rerank,
    _bm25_score,
    close_browser,
    _query_engines_concurrent,
    _select_engines,
)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "runs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N     = 10
BM25_REPR = "title+snippet"

MODES = ["general", "pdf", "books", "docs"]

QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]

SMOKE_MODE  = "general"
SMOKE_QUERY = "transformer attention mechanism"

# --- URL filter data (mirrors src/search/{pdf_filter,book_whitelist,docs_filter}.py) ---

_PDF_HOSTS = frozenset({
    "arxiv.org", "aclanthology.org", "openreview.net",
    "biorxiv.org", "medrxiv.org", "chemrxiv.org", "osf.io",
    "mdpi.com", "pmc.ncbi.nlm.nih.gov",
    "inspirehep.net", "zenodo.org", "hal.science", "hal.archives-ouvertes.fr", "europepmc.org",
})
_PDF_BAD = frozenset({
    "github.com", "gitlab.com", "books.google.com",
    "scribd.com", "semanticscholar.org", "openalex.org", "researchgate.net",
})
_PDF_PATHS = (".pdf", "/pdf/", "/pdfs/", "/content/pdf/", "/_downloads/")

_BOOK_WHITELIST = frozenset({
    "amazon.com", "amazon.de", "amazon.in", "amazon.co.uk", "abebooks.de", "thalia.de",
    "barnesandnoble.com", "kulturkaufhaus.de", "buecher.de", "hugendubel.info", "beck-shop.de",
    "exsila.ch", "booklooker.de", "buchshop.bod.de", "books.apple.com", "ebooks.com",
    "audible.com", "blinkist.com", "perlego.com", "ebookaktiv.de", "legimi.de",
    "e-booksdirectory.com", "hqaudiobooks.net", "book-sharing.de", "downmagaz.net", "ebooksyard.com",
    "oreilly.com", "manning.com", "simonandschuster.com", "penguinrandomhouse.com",
    "hachettebookgroup.com", "fischerverlage.de", "chbeck.de", "bloomsbury.com", "penguin.de",
    "tharpa.com", "bibleandbookcenter.com",
    "goodreads.com", "gutenberg.org", "openlibrary.org", "archive.org", "books.google.com",
    "deutsche-digitale-bibliothek.de", "en.wikisource.org", "yumpu.com", "worldmags.net",
    "drive.google.com",
    "fivebooks.com", "bookauthority.org", "ordertoread.com", "reedsy.com",
    "bookseriesinorder.com", "booksinorder.org", "infobooks.org", "booksaremythirdplace.com",
    "eatyourbooks.com", "fictionhorizon.com", "shortform.com", "dedp.online", "harrypotter.com",
    "refactoring.guru", "formdesignpatterns.com", "cleancodecookbook.com",
    "superfastpython.com", "pythonbooks.org", "buddho.org", "berniegourley.com", "eternalisedofficial.com",
})
_BOOK_BAD  = frozenset({"github.com", "gitlab.com", "bitbucket.org", "gist.github.com"})
_BOOK_PATHS = (
    "/books/", "/buecher/", "/buch/", "/book/show/", "/dp/", "/ebooks/",
    "/detail/isbn-", "/library/view/", "/title/", "/ebook/",
)

_DOCS_BAD_HOSTS = frozenset({
    "reddit.com", "stackoverflow.com", "bugs.python.org",
    "medium.com", "youtube.com", "dev.to",
    "github.com", "gitlab.com", "bitbucket.org",
    "w3schools.com", "geeksforgeeks.org", "freecodecamp.org", "codezup.com", "riptutorial.com",
    "slideshare.net", "scribd.com", "deepwiki.com",
})
_DOCS_BAD_PATHS = ("/blog/", "/community/")

# --- Mode modifier engines ---
_MODE_ENGINES = frozenset({"google", "duckduckgo"})


# ORCHESTRATOR

async def run_probe(smoke: bool, ts_dir_arg: Path | None) -> Path:
    _verify_reranker()

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = ts_dir_arg or (REPORT_DIR / f"value_eval_{ts}")
    ts_dir.mkdir(parents=True, exist_ok=True)

    pairs   = [(SMOKE_MODE, SMOKE_QUERY)] if smoke else [(m, q) for m in MODES for q in QUERIES]
    n_pairs = len(pairs)

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Pairs: {n_pairs} | Output: {ts_dir}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        for i, (mode, query) in enumerate(pairs, 1):
            print(f"[{i}/{n_pairs}] mode={mode} | {query}", file=sys.stderr)
            meta = await _run_one_pair(ts_dir, mode, query, selected)
            print(
                f"  google={meta['google_count']}  pool={meta['pool_size']}"
                f"  capped={meta['capped_pool_size']}  filtered={meta['filtered_pool_size']}"
                f"  fetch={meta['fetch_ms']}ms  c3={meta['c3_ms']}ms",
                file=sys.stderr,
            )
    finally:
        await close_browser()

    print(f"\nOutput dir: {ts_dir}", file=sys.stderr)

    if smoke:
        from value_eval_aggregate import run_aggregate
        print("\n--- Running Stage 4 (no-oracle smoke) ---", file=sys.stderr)
        run_aggregate(ts_dir=ts_dir, ts_out=ts, no_oracle=True)

    return ts_dir


# FUNCTIONS

# Abort if reranker unreachable
def _verify_reranker() -> None:
    print("Verifying reranker …", file=sys.stderr)
    try:
        r = httpx.post(RERANKER_URL, json={"query": "warmup", "documents": ["test"]}, timeout=10.0)
        r.raise_for_status()
        print(f"  Reranker OK ({r.elapsed.microseconds // 1000}ms)", file=sys.stderr)
    except (httpx.HTTPError, httpx.ConnectError) as e:
        sys.exit(f"ERROR: Reranker unreachable at {RERANKER_URL}: {e}")
    print(file=sys.stderr)


# Slug for file naming — must match value_eval_aggregate._query_slug
def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


# Build query_modifier_map for the given mode (None for general)
def _modifier_map(mode: str) -> dict | None:
    if mode == "books": return {e: (lambda q: f"{q} book")          for e in _MODE_ENGINES}
    if mode == "pdf":   return {e: (lambda q: f"{q} pdf")           for e in _MODE_ENGINES}
    if mode == "docs":  return {e: (lambda q: f"{q} documentation") for e in _MODE_ENGINES}
    return None


# Bare domain (strip www.) from URL
def _url_domain(url: str) -> str:
    try:
        host = _urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


# True if URL is a known-PDF host or path pattern; blacklisted hosts return False
def _is_pdf_url(url: str) -> bool:
    d = _url_domain(url)
    if d in _PDF_BAD or any(d.endswith("." + h) for h in _PDF_BAD): return False
    if d in _PDF_HOSTS or any(d.endswith("." + h) for h in _PDF_HOSTS): return True
    return any(p in _urlparse(url).path.lower() for p in _PDF_PATHS)


# True if URL is in book whitelist or book path pattern; code-hosting blacklist returns False
def _is_book_url(url: str) -> bool:
    d = _url_domain(url)
    if d in _BOOK_BAD or any(d.endswith("." + h) for h in _BOOK_BAD): return False
    if d in _BOOK_WHITELIST or any(d.endswith("." + h) for h in _BOOK_WHITELIST): return True
    return any(p in _urlparse(url).path.lower() for p in _BOOK_PATHS)


# True if URL is NOT in noise blacklist (inverted: passes docs, blocks noise)
def _is_docs_url(url: str) -> bool:
    d = _url_domain(url)
    if d in _DOCS_BAD_HOSTS or any(d.endswith("." + h) for h in _DOCS_BAD_HOSTS): return False
    return not any(p in _urlparse(url).path.lower() for p in _DOCS_BAD_PATHS)


# Apply mode URL filter to pool of dicts
def _filter_pool(pool: list[dict], mode: str) -> list[dict]:
    if mode == "pdf":   return [m for m in pool if _is_pdf_url(m["url"])]
    if mode == "books": return [m for m in pool if _is_book_url(m["url"])]
    if mode == "docs":  return [m for m in pool if _is_docs_url(m["url"])]
    return pool


# Cap raw results to position <= K and dedup
def _build_capped_pool(raw_results: list, K: int) -> list[dict]:
    return _build_pool([r for r in raw_results if r.position <= K])


# C1 Overlap-Count: sort (-n_engines, min_position), return Top-N URLs + latency ms
def _apply_c1(pool: list[dict], top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    ranked = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m in ranked[:top_n]], ms


# C2 BM25 vanilla: score full filtered pool, return Top-N URLs + latency ms
def _apply_c2(pool: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(pool, query, top_n)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms


# C2' BM25-Capped: score capped+filtered pool, return Top-N URLs + latency ms
def _apply_c2p(capped_pool: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    t0     = time.perf_counter()
    scored = _bm25_score(capped_pool, query, top_n)
    ms     = round((time.perf_counter() - t0) * 1000)
    return [m["url"] for m, _ in scored], ms


# C3 Cross-Encoder: rerank pool, return Top-N URLs + latency ms (single attempt)
def _apply_c3(pool: list[dict], query: str, top_n: int) -> tuple[list[str], int]:
    if not pool:
        return [], 0
    valid = [(m, _doc_repr(m, BM25_REPR)) for m in pool if _doc_repr(m, BM25_REPR).strip()]
    if not valid:
        return [], 0
    docs_v  = [m for m, _ in valid]
    texts_v = [t for _, t in valid]
    t0 = time.perf_counter()
    try:
        pairs  = cross_encoder_rerank(query, texts_v)
        ranked = sorted(pairs, key=lambda x: -x[1])[:top_n]
        ms     = round((time.perf_counter() - t0) * 1000)
        return [docs_v[idx]["url"] for idx, _ in ranked], ms
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000)
        print(f"  C3 error: {exc}", file=sys.stderr)
        return [], ms


# Save pool.json — oracle-view only (url/title/snippet, no position or engine signals)
def _save_pool_json(ts_dir: Path, mode: str, slug: str, pool: list[dict], query: str) -> None:
    data = {
        "mode":      mode,
        "query":     query,
        "pool_size": len(pool),
        "pool": [
            {
                "url":     m["url"],
                "title":   (m.get("title") or "").strip(),
                "snippet": (m.get("snippet") or "").strip(),
            }
            for m in pool
        ],
    }
    (ts_dir / f"{mode}_{slug}_pool.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# Save methods.json — C1/C2/C2'/C3 Top-10 URL lists + metadata
def _save_methods_json(ts_dir: Path, mode: str, slug: str, data: dict) -> None:
    (ts_dir / f"{mode}_{slug}_methods.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# Fetch + score one (mode, query) pair; return progress metadata
async def _run_one_pair(ts_dir: Path, mode: str, query: str, selected: dict) -> dict:
    qmm = _modifier_map(mode)

    t0 = time.perf_counter()
    raw_results, engine_stats = await _query_engines_concurrent(
        query, "en", 10, selected, query_modifier_map=qmm
    )
    fetch_ms = round((time.perf_counter() - t0) * 1000)

    google_count = engine_stats.get("google", {}).get("result_count", 0)
    K            = google_count if google_count > 0 else 10

    full_pool   = _build_pool(raw_results)
    capped_pool = _build_capped_pool(raw_results, K)
    filt_pool   = _filter_pool(full_pool,   mode)
    filt_capped = _filter_pool(capped_pool, mode)

    slug = _query_slug(query)
    # Oracle sees capped+filtered pool sorted by URL (neutral ordering, ~40-80 URLs, practical to review)
    oracle_pool = sorted(filt_capped, key=lambda m: m["url"])
    _save_pool_json(ts_dir, mode, slug, oracle_pool, query)

    c_results = _apply_c_methods(filt_pool, filt_capped, query)

    _save_methods_json(ts_dir, mode, slug, {
        "mode":                      mode,
        "query":                     query,
        "google_count":              google_count,
        "pool_size":                 len(full_pool),
        "capped_pool_size":          len(capped_pool),
        "filtered_pool_size":        len(filt_pool),
        "filtered_capped_pool_size": len(filt_capped),
        "oracle_pool_size":          len(oracle_pool),
        **c_results,
        "method_pool_sizes":  {"c1": len(filt_capped), "c2": len(filt_pool), "c2p": len(filt_capped), "c3": len(filt_capped)},
        "fetch_ms": fetch_ms,
    })

    return {
        "google_count":       google_count,
        "pool_size":          len(full_pool),
        "capped_pool_size":   len(capped_pool),
        "filtered_pool_size": len(filt_pool),
        "fetch_ms":           fetch_ms,
        "c3_ms":              c_results["c3_ms"],
    }


def _apply_c_methods(filt_pool: list[dict], filt_capped: list[dict], query: str) -> dict:
    # C1/C2'/C3 operate on capped pool (same as oracle input); C2 on full pool (its defining property)
    c1_urls, c1_ms   = _apply_c1(filt_capped,  TOP_N)
    c2_urls, c2_ms   = _apply_c2(filt_pool,    query, TOP_N)
    c2p_urls, c2p_ms = _apply_c2p(filt_capped, query, TOP_N)
    c3_urls, c3_ms   = _apply_c3(filt_capped,  query, TOP_N)
    return {
        "c1":    c1_urls,   "c1_ms":  c1_ms,
        "c2":    c2_urls,   "c2_ms":  c2_ms,
        "c2p":   c2p_urls,  "c2p_ms": c2p_ms,
        "c3":    c3_urls,   "c3_ms":  c3_ms,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Value eval probe — Stage 1+2")
    parser.add_argument("--smoke",  action="store_true", help="Smoke: one pair only, auto-runs Stage 4")
    parser.add_argument("--ts-dir", default=None,        help="Output directory override")
    args       = parser.parse_args()
    ts_dir_arg = Path(args.ts_dir) if args.ts_dir else None
    ts_dir     = asyncio.run(run_probe(smoke=args.smoke, ts_dir_arg=ts_dir_arg))
    print(ts_dir)
