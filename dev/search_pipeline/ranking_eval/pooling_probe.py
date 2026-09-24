#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent.parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from bm25_sweep_smoke import BM25Uniform, VANILLA_K1, _build_pool, _doc_repr, _tokenize

from rerank_probe_smoke import (
    QUERIES,
    QUERY_CATEGORIES,
    EMBEDDING_URL,
    RERANKER_URL,
    embed_batch,
    cross_encoder_rerank,
    cosine_sim,
    _bm25_score,
    _verify_services,
    close_browser,
    _query_engines_concurrent,
    _select_engines,
)

import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR    = SCRIPT_DIR / "md"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR      = SCRIPT_DIR / "jsonl"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BM25_REPR     = "title+snippet"
SNIPPET_CHARS = 200


# ORCHESTRATOR

async def run_probe() -> None:
    _verify_services()

    ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"pooling_probe_{ts}.md"
    jsonl_path  = DATA_DIR / f"pooling_probe_{ts}.queries.jsonl"

    selected, _ = _select_engines(None)
    print(f"Engines ({len(selected)}): {', '.join(sorted(selected.keys()))}", file=sys.stderr)
    print(f"Report:  {report_path}", file=sys.stderr)
    print(file=sys.stderr)

    query_sections: list[str] = []
    summaries:      list[dict] = []
    t_total = time.perf_counter()
    try:
        for qi, query in enumerate(QUERIES):
            print(f"[{qi + 1}/{len(QUERIES)}] {query}", file=sys.stderr)
            section, summary = await _run_one_query(query, selected)
            query_sections.append(section)
            summaries.append(summary)
            _print_query_summary(summary)
            if summary["rate_skip_count"] > 1:
                _print_cascade_stop(qi, query, summary["rate_skip_engines"])
                return
    finally:
        await close_browser()

    total_ms = round((time.perf_counter() - t_total) * 1000)

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for s in summaries:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    _write_report(query_sections, summaries, report_path, total_ms)
    print(f"\nReport:   {report_path}", file=sys.stderr)
    print(f"JSONL:    {jsonl_path}", file=sys.stderr)
    print(f"Total:    {total_ms}ms  ({total_ms / 1000:.1f}s)", file=sys.stderr)


# FUNCTIONS

def _print_query_summary(summary: dict) -> None:
    rsk = summary["rate_skip_engines"]
    print(
        f"  google_count={summary['google_count']}  pool={summary['pool_size']}"
        f"  skipped={summary['skipped']}"
        f"  RATE_SKIP={summary['rate_skip_count']} ({','.join(rsk) or 'none'})"
        f"  C1={summary['c1_ms']}ms  C2={summary['c2_ms']}ms"
        f"  C3={summary['c3_ms']}ms  C4={summary['c4_ms']}ms",
        file=sys.stderr,
    )


def _print_cascade_stop(qi: int, query: str, rsk: list) -> None:
    print(
        f"\nSTOP: RATE_SKIP cascade on query [{qi+1}] '{query}'\n"
        f"  RATE_SKIP engines: {rsk}\n"
        f"  Aborting. Check rate-limiter state (bee-fix regression?). Report not written.",
        file=sys.stderr,
    )


def _build_capped_pool(raw_results: list, google_count: int) -> list[dict]:
    return _build_pool([r for r in raw_results if r.position <= google_count])


def _rank_c1_overlap(pool: list[dict], top_n: int) -> list[dict]:
    return sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))[:top_n]


def _safe_rerank(query: str, texts_v: list[str], pool_v: list[dict], top_n: int) -> tuple[list[dict], bool]:
    if not texts_v:
        return [], False
    for attempt in range(2):
        try:
            ce_sorted = sorted(cross_encoder_rerank(query, texts_v), key=lambda x: -x[1])
            return [pool_v[idx] for idx, _ in ce_sorted[:top_n]], False
        except Exception as exc:
            print(f"  C3 API error attempt {attempt+1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return [], True


def _safe_embed(query: str, texts_v: list[str], pool_v: list[dict], top_n: int) -> tuple[list[dict], bool]:
    if not texts_v:
        return [], False
    for attempt in range(2):
        try:
            embs       = embed_batch([query] + texts_v)
            cos_scores = [cosine_sim(embs[0], e) for e in embs[1:]]
            return [pool_v[i] for i in sorted(range(len(pool_v)), key=lambda i: -cos_scores[i])[:top_n]], False
        except Exception as exc:
            print(f"  C4 API error attempt {attempt+1}: {exc}", file=sys.stderr)
            if attempt == 0:
                time.sleep(2)
    return [], True


async def _run_one_query(query: str, selected: dict) -> tuple[str, dict]:
    t0 = time.perf_counter()
    raw_results, engine_stats = await _query_engines_concurrent(query, "en", 10, selected)
    fetch_ms = round((time.perf_counter() - t0) * 1000)

    rate_skip_engines = [n for n, s in engine_stats.items() if s["status"] == "RATE_SKIP"]
    google_count      = engine_stats.get("google", {}).get("result_count", 0)

    if google_count == 0:
        return _build_skipped_section(query, engine_stats, fetch_ms), _skipped_summary(query, rate_skip_engines, fetch_ms)

    pool = _build_capped_pool(raw_results, google_count)

    pool_v, texts_v = _valid_docs(pool)

    t0 = time.perf_counter()
    c1_top = _rank_c1_overlap(pool, google_count)
    c1_ms  = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    c2_top = [d for d, _ in _bm25_score(pool, query, google_count)]
    c2_ms  = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    c3_top, c3_failed = _safe_rerank(query, texts_v, pool_v, google_count)
    c3_ms  = round((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    c4_top, c4_failed = _safe_embed(query, texts_v, pool_v, google_count)
    c4_ms  = round((time.perf_counter() - t0) * 1000)

    section = _build_query_section(
        query, engine_stats, google_count, len(pool), fetch_ms,
        c1_top, c2_top, c3_top, c4_top, c1_ms, c2_ms, c3_ms, c4_ms, c3_failed, c4_failed,
    )
    summary = {
        "query": query, "category": QUERY_CATEGORIES.get(query, "unknown"),
        "skipped": False, "c3_failed": c3_failed, "c4_failed": c4_failed,
        "google_count": google_count, "pool_size": len(pool),
        "rate_skip_count": len(rate_skip_engines), "rate_skip_engines": rate_skip_engines,
        "fetch_ms": fetch_ms, "c1_ms": c1_ms, "c2_ms": c2_ms, "c3_ms": c3_ms, "c4_ms": c4_ms,
        "c1_urls": [m["url"] for m in c1_top],
        "c2_urls": [m["url"] for m in c2_top],
        "c3_urls": [m["url"] for m in c3_top],
        "c4_urls": [m["url"] for m in c4_top],
    }
    return section, summary


def _skipped_summary(query: str, rate_skip_engines: list, fetch_ms: int) -> dict:
    return {
        "query": query, "category": QUERY_CATEGORIES.get(query, "unknown"),
        "skipped": True, "c3_failed": False, "c4_failed": False,
        "google_count": 0, "pool_size": 0,
        "rate_skip_count": len(rate_skip_engines), "rate_skip_engines": rate_skip_engines,
        "fetch_ms": fetch_ms, "c1_ms": 0, "c2_ms": 0, "c3_ms": 0, "c4_ms": 0,
        "c1_urls": [], "c2_urls": [], "c3_urls": [], "c4_urls": [],
    }


def _valid_docs(pool: list[dict]) -> tuple[list[dict], list[str]]:
    raw_texts   = [_doc_repr(m, BM25_REPR) for m in pool]
    valid_pairs = [(m, t) for m, t in zip(pool, raw_texts) if t.strip()]
    pool_v      = [m for m, _ in valid_pairs]
    texts_v     = [t for _, t in valid_pairs]
    return pool_v, texts_v


def _build_skipped_section(query: str, engine_stats: dict, fetch_ms: int) -> str:
    ok  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    rsk = [n for n, s in engine_stats.items() if s["status"] == "RATE_SKIP"]
    return "\n".join([
        f"## {query}",
        "",
        f"**SKIPPED — google_count=0**  fetch={fetch_ms}ms  ",
        f"**Engines with results ({len(ok)}):** {', '.join(f'{n}={c}' for n, c in ok)}  ",
        f"**RATE_SKIP:** {', '.join(rsk) or 'none'}",
        "",
    ])


def _url_entry(i: int, m: dict) -> str:
    url     = m["url"]
    engines = ", ".join(m.get("engines", []))
    title   = (m.get("title") or "").strip().replace("\n", " ")[:100]
    snippet = (m.get("snippet") or "").strip().replace("\n", " ")[:SNIPPET_CHARS]
    return (
        f"**{i}.** `{url}`  \n"
        f"engines: {engines}  \n"
        f"**Title:** {title}  \n"
        f"**Snippet:** {snippet}"
    )


def _build_query_section(
    query: str,
    engine_stats: dict,
    google_count: int,
    pool_size: int,
    fetch_ms: int,
    c1_top: list[dict],
    c2_top: list[dict],
    c3_top: list[dict],
    c4_top: list[dict],
    c1_ms: int,
    c2_ms: int,
    c3_ms: int,
    c4_ms: int,
    c3_failed: bool,
    c4_failed: bool,
) -> str:
    ok  = [(n, s["result_count"]) for n, s in sorted(engine_stats.items()) if s["result_count"] > 0]
    rsk = [n for n, s in engine_stats.items() if s["status"] == "RATE_SKIP"]

    lines = [
        f"## {query}",
        "",
        f"**google_count:** {google_count} | **capped_pool:** {pool_size} | "
        f"**fetch:** {fetch_ms}ms  ",
        f"**Engines ({len(ok)}):** {', '.join(f'{n}={c}' for n, c in ok)}  ",
        f"**RATE_SKIP:** {', '.join(rsk) or 'none'}",
        "",
    ]

    configs = [
        ("C1 — Overlap-Count (−n_engines, min_position)", c1_top, c1_ms, False),
        ("C2 — BM25 (k1=1.2, b=0.75, sw=on, title+snippet)", c2_top, c2_ms, False),
        ("C3 — Cross-Encoder direct (Qwen3-Reranker-0.6B, port 8082)", c3_top, c3_ms, c3_failed),
        ("C4 — Embedding-Cosine direct (Qwen3-Embedding-0.6B, port 8084)", c4_top, c4_ms, c4_failed),
    ]
    for label, top, ms, failed in configs:
        lines += [f"### {label} — {ms}ms{' — API FAILED after retry' if failed else ''}", ""]
        for i, m in enumerate(top, 1):
            lines.append(_url_entry(i, m))
            lines.append("")
        lines.append("**Müll-eyeball:** muell_abs=? / muell_rate=?  ")
        lines.append("")

    return "\n".join(lines)


def _write_report(
    sections: list[str],
    summaries: list[dict],
    path: Path,
    total_ms: int,
) -> None:
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid   = [s for s in summaries if not s["skipped"]]
    skipped = [s for s in summaries if s["skipped"]]
    rsk_total = sum(s["rate_skip_count"] for s in summaries)

    hdr = _header_lines(ts, summaries, valid, skipped, total_ms, rsk_total)
    hdr += _summary_rows(summaries)
    hdr += _muell_aggregate_lines()

    path.write_text("\n\n---\n\n".join(["\n".join(hdr)] + sections), encoding="utf-8")


def _header_lines(ts: str, summaries: list[dict], valid: list[dict], skipped: list[dict], total_ms: int, rsk_total: int) -> list[str]:
    return [
        "# Pooling Strategy Comparison — Capped Pool (bead searxng-g82)",
        "",
        f"**Date:** {ts}  ",
        f"**Queries:** {len(summaries)} total / {len(valid)} valid / {len(skipped)} skipped  ",
        f"**Configs:** C1 Overlap-Count / C2 BM25 / C3 Cross-Encoder / C4 Embedding-Cosine  ",
        f"**Pool rule:** per-engine top-google_count results, dedup by URL  ",
        f"**GPU:** embedding port 8084 (Qwen3-Embedding-0.6B) / reranker port 8082 (Qwen3-Reranker-0.6B)  ",
        f"**Total wallclock:** {total_ms}ms ({total_ms / 1000:.1f}s)  ",
        f"**RATE_SKIP total (all queries, all engines):** {rsk_total}  ",
        f"**API failures after retry (C3 / C4):** {sum(s['c3_failed'] for s in summaries)} / {sum(s['c4_failed'] for s in summaries)}",
        "",
        "## Global Summary",
        "",
        "| # | Query | Cat | google_count | pool | RATE_SKIP | C1_ms | C2_ms | C3_ms | C4_ms |",
        "|---|-------|-----|--------------|------|-----------|-------|-------|-------|-------|",
    ]


def _summary_rows(summaries: list[dict]) -> list[str]:
    rows = []
    for i, s in enumerate(summaries, 1):
        flag = " ⚠SKIPPED" if s["skipped"] else ""
        flag += " C3_FAILED" if s["c3_failed"] else ""
        flag += " C4_FAILED" if s["c4_failed"] else ""
        rows.append(
            f"| {i} | {s['query'][:38]}{flag} | {s['category'][:10]} | {s['google_count']} "
            f"| {s['pool_size']} | {s['rate_skip_count']} "
            f"| {s['c1_ms']} | {s['c2_ms']} | {s['c3_ms']} | {s['c4_ms']} |"
        )
    return rows


def _muell_aggregate_lines() -> list[str]:
    return [
        "",
        "## Müll-Eyeball Aggregate (fill post-run)",
        "",
        "Conservative rule: count only unambiguously off-topic URLs. When in doubt → NOT Müll.",
        "",
        "| Config | muell_abs_total (sum/valid queries) | muell_rate_mean |",
        "|--------|-------------------------------------|-----------------|",
        "| C1 Overlap-Count | | |",
        "| C2 BM25 | | |",
        "| C3 Cross-Encoder | | |",
        "| C4 Embedding-Cosine | | |",
        "",
        "## Discriminating Queries (max(muell_abs) − min(muell_abs) > 2 across C1..C4)",
        "",
        "*(fill post-run — queries where ranking strategy choice visibly changes result quality)*",
        "",
    ]


if __name__ == "__main__":
    asyncio.run(run_probe())
