# INFRASTRUCTURE
from collections import defaultdict
from pathlib import Path

SNIPPET_CHARS = 200


# FUNCTIONS

def _build_sections(
    query: str, ts_display: str, google_count: int, pool: list[dict], engine_stats: dict, wall_ms: int,
    raw_results: list, url_engine_pos: dict, c1_top: list[dict], c2_scored: list, c3_scored: list,
    c4_scored: list, c1_ms: int, c2_ms: int, c3_ms: int, c4_ms: int, c3_failed: bool, c4_failed: bool,
) -> list[str]:
    return [
        _section_header(query, ts_display, google_count, pool, engine_stats, wall_ms),
        _section_per_engine(raw_results, engine_stats, google_count),
        _section_pool(pool, url_engine_pos),
        _section_configs(
            query, google_count, pool,
            c1_top, c2_scored, c3_scored, c4_scored,
            c1_ms, c2_ms, c3_ms, c4_ms, c3_failed, c4_failed,
        ),
        _section_matrix(pool, google_count, c1_top, c2_scored, c3_scored, c4_scored),
    ]


def _fmt_snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    return (text or "").strip().replace("\n", " ")[:n]


def _section_header(
    query: str,
    ts_display: str,
    google_count: int,
    pool: list[dict],
    engine_stats: dict,
    wall_ms: int,
) -> str:
    fired = ", ".join(
        f"{n} → {s['result_count']}"
        for n, s in sorted(engine_stats.items())
        if s["result_count"] > 0
    )
    n_engines = len(engine_stats)
    return "\n".join([
        "# Single-Query Pool Dump",
        "",
        f"**Query:** {query}  ",
        f"**Date:** {ts_display}  ",
        f"**google_count:** {google_count}  ",
        f"**Capped pool size:** {len(pool)} (after dedup across {n_engines} engines)  ",
        f"**Engines that fired:** {fired}  ",
        f"**Total wallclock:** {wall_ms}ms  ",
    ])


def _section_per_engine(
    raw_results: list,
    engine_stats: dict,
    google_count: int,
) -> str:
    by_engine: dict[str, list] = defaultdict(list)
    for r in raw_results:
        by_engine[r.engine].append(r)
    for eng in by_engine:
        by_engine[eng].sort(key=lambda r: r.position)

    lines = ["## Section 1 — Per-Engine Raw (capped to top-google_count per engine)", ""]
    for eng in sorted(by_engine.keys()):
        results = [r for r in by_engine[eng] if r.position <= google_count]
        note    = f"{len(results)} of {google_count}"
        if len(results) < google_count:
            note += f" (engine returned only {len(results)})"
        lines.append(f"### {eng} ({note})")
        lines.append("")
        for i, r in enumerate(results, 1):
            title   = (r.title or "").strip().replace("\n", " ")[:100]
            snippet = _fmt_snippet(r.snippet or "")
            lines.append(f"{i}. {r.url}")
            lines.append(f"   Title: {title}")
            lines.append(f"   Snippet: {snippet}")
        lines.append("")
    return "\n".join(lines)


def _section_pool(pool: list[dict], url_engine_pos: dict[str, dict[str, int]]) -> str:
    sorted_pool = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))
    lines = [f"## Section 2 — Capped Pool ({len(pool)} unique URLs after dedup)", ""]
    for i, m in enumerate(sorted_pool, 1):
        title   = (m.get("title") or "").strip().replace("\n", " ")[:100]
        snippet = _fmt_snippet(m.get("snippet") or "")
        ep      = url_engine_pos.get(m["url"], {})
        eng_str = ", ".join(
            f"{eng} (pos {ep.get(eng, '?')})"
            for eng in sorted(m["engines"])
        )
        lines.append(f"{i}. {m['url']}")
        lines.append(f"   Title: {title}")
        lines.append(f"   Snippet: {snippet}")
        lines.append(f"   engines: [{eng_str}]")
        lines.append(f"   min_position: {m['min_position']} | engine_count: {len(m['engines'])}")
        lines.append("")
    return "\n".join(lines)


def _config_entries(label: str, ms: int, entries: list[tuple[dict, str]]) -> list[str]:
    lines = [f"### {label} — {ms}ms", ""]
    for i, (m, score_line) in enumerate(entries, 1):
        title   = (m.get("title") or "").strip().replace("\n", " ")[:100]
        snippet = _fmt_snippet(m.get("snippet") or "")
        engines = ", ".join(m.get("engines", []))
        lines += [
            f"{i}. {m['url']}",
            f"   Title: {title}",
            f"   Snippet: {snippet}",
            f"   engines: [{engines}]",
            score_line,
            "",
        ]
    return lines


def _section_configs(
    query: str,
    google_count: int,
    pool: list[dict],
    c1_top: list[dict],
    c2_scored: list[tuple[dict, float]],
    c3_scored: list[tuple[dict, float]],
    c4_scored: list[tuple[dict, float]],
    c1_ms: int,
    c2_ms: int,
    c3_ms: int,
    c4_ms: int,
    c3_failed: bool,
    c4_failed: bool,
) -> str:
    c1_entries = [(m, f"   engine_count: {len(m.get('engines', []))}") for m in c1_top]
    c2_entries = [(m, f"   bm25_score: {s:.4f}") for m, s in c2_scored]
    c3_entries = [(m, f"   rerank_score: {s:.4f}") for m, s in c3_scored]
    c4_entries = [(m, f"   cosine_sim: {s:.4f}") for m, s in c4_scored]

    lines = [f"## Section 3 — Top-{google_count} per Config", ""]
    lines += _config_entries("C1 — Overlap-Count (−n_engines, min_position)", c1_ms, c1_entries)
    lines += _config_entries("C2 — BM25 (k1=1.2, b=0.75, sw=on, title+snippet)", c2_ms, c2_entries)
    lines += _config_entries("C3 — Cross-Encoder (Qwen3-Reranker-0.6B, port 8082)" + (" — API FAILED after retry" if c3_failed else ""), c3_ms, c3_entries)
    lines += _config_entries("C4 — Embedding-Cosine (Qwen3-Embedding-0.6B, port 8084)" + (" — API FAILED after retry" if c4_failed else ""), c4_ms, c4_entries)
    return "\n".join(lines)


def _section_matrix(
    pool: list[dict],
    google_count: int,
    c1_top: list[dict],
    c2_scored: list[tuple[dict, float]],
    c3_scored: list[tuple[dict, float]],
    c4_scored: list[tuple[dict, float]],
) -> str:
    c1_rank = {m["url"]: i for i, m in enumerate(c1_top, 1)}
    c2_rank = {m["url"]: i for i, (m, _) in enumerate(c2_scored, 1)}
    c3_rank = {m["url"]: i for i, (m, _) in enumerate(c3_scored, 1)}
    c4_rank = {m["url"]: i for i, (m, _) in enumerate(c4_scored, 1)}

    all_top_n = (c1_rank, c2_rank, c3_rank, c4_rank)

    sorted_pool = sorted(pool, key=lambda m: (-len(m["engines"]), m["min_position"]))

    in_topn     = [m for m in sorted_pool if any(m["url"] in d for d in all_top_n)]
    not_in_topn = [m for m in sorted_pool if all(m["url"] not in d for d in all_top_n)]

    zero_configs = len(not_in_topn)
    consensus    = sum(
        1 for m in pool
        if all(m["url"] in d for d in all_top_n)
    )

    lines = [
        "## Section 4 — Comparison Matrix",
        "",
        f"Top-{google_count} per config. `—` = not in Top-{google_count} for that config.  ",
        f"Pool URLs in at least one Top-N: {len(in_topn)} | missed by all configs: {zero_configs} | in all 4 configs: {consensus}",
        "",
        "| URL (short) | engines | C1 rank | C2 rank | C3 rank | C4 rank |",
        "|---|---|---|---|---|---|",
    ]
    for m in in_topn + not_in_topn:
        url       = m["url"]
        url_short = (url[:50] + "…") if len(url) > 50 else url
        engines   = ",".join(sorted(m["engines"]))
        lines.append(
            f"| {url_short} | {engines} | {_rank_cell(c1_rank, url)} "
            f"| {_rank_cell(c2_rank, url)} | {_rank_cell(c3_rank, url)} | {_rank_cell(c4_rank, url)} |"
        )

    return "\n".join(lines)


def _rank_cell(d: dict, url: str) -> str:
    v = d.get(url)
    return str(v) if v is not None else "—"


def _write_report(sections: list[str], path: Path) -> None:
    path.write_text("\n\n---\n\n".join(sections), encoding="utf-8")
