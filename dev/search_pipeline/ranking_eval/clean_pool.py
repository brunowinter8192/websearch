#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
V2_DEFAULT = SCRIPT_DIR / "runs" / "value_eval_v2_20260523_000156"

MODES = ["general", "pdf", "books", "docs"]
QUERIES = [
    "transformer attention mechanism",
    "postgresql index types btree gin gist performance",
    "python asyncio event loop concurrency",
    "contrastive learning self-supervised representations",
]
DROP_ENGINES = {"google", "semantic_scholar"}

_BACKFILL: dict[str, list[dict]] = {
    "general_transformer_attention_mechanis": [
        {
            "url": "https://deeprevision.github.io/posts/001-transformer/",
            "rationale": (
                "'The Transformer Blueprint: A Holistic Guide to the Transformer Neural Network "
                "Architecture' — Lobsters-surfaced (pos=1, community quality signal), "
                "practitioner-grade implementation depth comparable to the dropped "
                "sebastianraschka.com self-attention tutorial. Primary technical guide "
                "covering attention mechanisms end-to-end."
            ),
        },
        {
            "url": "https://aman.ai/primers/ai/LLM/#overview",
            "rationale": (
                "Aman.ai AI Primers 'Overview of Large Language Models' — Lobsters-surfaced "
                "(pos=3), comprehensive reference covering attention mechanisms as core LLM "
                "architecture. Well-regarded in the ML practitioner community as authoritative "
                "explainer. Replaces the dropped ibm.com attention-mechanism overview."
            ),
        },
    ],
    "docs_contrastive_learning_self_supe": [
        {
            "url": "https://arxiv.org/pdf/2510.10572",
            "rationale": (
                "arXiv 2510.10572 'Understanding Self-supervised Contrastive Learning through "
                "Supervised ...' — primary research source directly on the query topic "
                "(DuckDuckGo pos=1). Replaces the dropped SemanticScholar Supervised "
                "Contrastive Learning paper with its underlying arXiv primary source."
            ),
        },
    ],
    "general_postgresql_index_types_btree_g": [
        {
            "url": "https://habr.com/ru/company/postgrespro/blog/441962/",
            "rationale": (
                "Habr/PostgresPro 'Indexes in PostgreSQL' — authored by PostgreSQL Pro "
                "(vendor documentation quality), Lobsters-surfaced (pos=1). Comprehensive "
                "technical reference covering all PostgreSQL index types (B-tree, GIN, GiST, "
                "Hash, BRIN) with performance trade-offs. Directly matches the query."
            ),
        },
    ],
    "pdf_postgresql_index_types_btree_g": [
        {
            "url": "https://habr.com/ru/company/postgrespro/blog/441962/",
            "rationale": (
                "Habr/PostgresPro 'Indexes in PostgreSQL' — authored by PostgreSQL Pro "
                "(vendor documentation quality), Lobsters-surfaced (pos=1). Replaces the "
                "dropped SemanticScholar intra-page indexing paper; directly covers "
                "PostgreSQL index type performance (B-tree, GIN, GiST) matching the query."
            ),
        },
    ],
}


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle cleanup — filter google+SS, backfill loss pairs")
    parser.add_argument("--v2-dir", default=None, help="v2 ts_dir path (default: value_eval_v2_20260523_000156)")
    args   = parser.parse_args()
    v2_dir = _compute_v2_dir(args)
    oracle_cleanup_workflow(v2_dir)


# FUNCTIONS

def _compute_v2_dir(args):
    v2_dir = Path(args.v2_dir) if args.v2_dir else V2_DEFAULT
    return v2_dir


def oracle_cleanup_workflow(v2_dir: Path) -> None:
    summary_rows: list[dict] = []
    for mode in MODES:
        for query in QUERIES:
            slug     = _query_slug(query)
            pair_key = f"{mode}_{slug}"
            row      = _process_pair(v2_dir, mode, query, slug, pair_key)
            summary_rows.append(row)
    _write_summary(v2_dir, summary_rows)
    print(v2_dir / "oracle_v3clean_summary.md")


def _query_slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")


def _process_pair(v2_dir: Path, mode: str, query: str, slug: str, pair_key: str) -> dict:
    pool_file   = next(v2_dir.glob(f"{pair_key}*_pool.json"),   None)
    oracle_file = next(v2_dir.glob(f"{pair_key}*_oracle.json"), None)
    if pool_file is None or oracle_file is None:
        return {"pair_key": pair_key, "error": "missing file"}

    pool_data   = json.loads(pool_file.read_text(encoding="utf-8"))
    oracle_data = json.loads(oracle_file.read_text(encoding="utf-8"))

    filtered_pool = filter_pool(pool_data["pool"], DROP_ENGINES)
    filtered_urls = {m["url"] for m in filtered_pool}

    original_picks = oracle_data["top_10"]
    surviving      = [p for p in original_picks if p["url"] in filtered_urls]
    lost           = [p for p in original_picks if p["url"] not in filtered_urls]

    backfill_specs = _BACKFILL.get(pair_key, [])
    backfill_picks = [
        {"rank": len(surviving) + i + 1, "url": spec["url"], "rationale": spec["rationale"]}
        for i, spec in enumerate(backfill_specs)
    ]

    top_10 = [{"rank": i + 1, "url": p["url"], "rationale": p["rationale"]}
              for i, p in enumerate(surviving)] + backfill_picks

    replacements = [
        {"replaced_url": lost_pick["url"], "new_url": bf["url"], "rationale": bf["rationale"]}
        for lost_pick, bf in zip(lost, backfill_picks)
    ]

    out = {
        "mode":             mode,
        "query":            query,
        "selection_method": oracle_data.get("selection_method", ""),
        "source":           "v3clean",
        "drop_engines":     sorted(DROP_ENGINES),
        "replacements":     replacements,
        "top_10":           top_10,
    }
    out_path = v2_dir / f"{pair_key}_oracle_v3clean.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "pair_key":       pair_key,
        "surviving":      len(surviving),
        "lost":           lost,
        "backfill_picks": backfill_picks,
        "top_10_count":   len(top_10),
    }


def _write_summary(v2_dir: Path, rows: list[dict]) -> None:
    loss_rows = [r for r in rows if "error" not in r and r["lost"]]

    lines = [
        "# Oracle v3clean Summary",
        "",
        f"**v2 ref:** `{v2_dir.name}`",
        f"**Drop engines:** {sorted(DROP_ENGINES)}",
        "",
        "## Loss Pairs — Backfill Detail",
        "",
    ]

    for r in loss_rows:
        lines += [f"### {r['pair_key']}", ""]
        lines.append("**Lost picks (google/semantic_scholar only):**")
        for p in r["lost"]:
            lines.append(f"- `{p['url']}`")
        lines.append("")
        lines.append("**Replacement picks:**")
        for bp in r["backfill_picks"]:
            lines.append(f"- rank {bp['rank']}: `{bp['url']}`")
            lines.append(f"  - {bp['rationale']}")
        lines.append("")

    lines += [
        "## All 16 Pairs — Survival Count",
        "",
        "| pair | surviving | lost | backfilled | top_10_count |",
        "|------|-----------|------|------------|--------------|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['pair_key']} | ERROR | — | — | — |")
        else:
            lines.append(
                f"| {r['pair_key']} | {r['surviving']} | {len(r['lost'])}"
                f" | {len(r['backfill_picks'])} | {r['top_10_count']} |"
            )

    lines.append("")
    (v2_dir / "oracle_v3clean_summary.md").write_text("\n".join(lines), encoding="utf-8")


def filter_pool(pool: list[dict], drop_engines: set[str]) -> list[dict]:
    result = []
    for entry in pool:
        remaining = [e for e in entry.get("engines", []) if e not in drop_engines]
        if not remaining:
            continue
        fe = dict(entry)
        fe["engines"]      = remaining
        fe["positions"]    = {e: p for e, p in entry.get("positions", {}).items()
                              if e not in drop_engines}
        fe["min_position"] = (min(fe["positions"].values())
                              if fe["positions"] else entry.get("min_position", 999))
        result.append(fe)
    return result


if __name__ == "__main__":
    main()
