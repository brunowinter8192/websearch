#!/usr/bin/env python3

# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines import google as google_engine
from src.search.engines import duckduckgo as duckduckgo_engine
from src.search.browser import close_browser

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

REPORT_DIR = SCRIPT_DIR / "md"

QUERIES = [
    "clean code",
    "design patterns",
    "tolkien lord of the rings",
    "dune frank herbert",
    "harry potter",
    "buddhism meditation",
    "cooking italian",
    "roman empire history",
    "nietzsche thus spoke zarathustra",
    "goethe faust",
    "kafka prozess",
    "deutsche geschichte",
]

SUFFIX = " book"

ENGINE_ORDER = [
    ("google",     google_engine),
    ("duckduckgo", duckduckgo_engine),
]

ENGINE_MAX = {
    "google":     100,
    "duckduckgo": 200,
}

BROWSER_SLEEP_S = 1.0
TOP_DOMAIN_LIMIT = 30
MIN_DOMAIN_COUNT = 2
TOP_PER_ENGINE = 15
MAX_SAMPLE_PATHS = 3
MAX_PATH_LEN = 80


# ORCHESTRATOR

async def run_probe() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    engines = [(name, engine_module) for name, engine_module in ENGINE_ORDER]

    all_runs: dict[str, list[dict]] = {}
    run_stats: dict[str, dict] = {name: {"total": 0, "errors": 0} for name, _ in ENGINE_ORDER}

    try:
        for qi, base_query in enumerate(QUERIES, 1):
            query = base_query + SUFFIX
            print(f"\n=== Q{qi}/{len(QUERIES)}: {query!r} ===", file=sys.stderr)
            run_results: list[dict] = []

            for i, (eng_name, engine) in enumerate(engines):
                max_r = ENGINE_MAX[eng_name]
                print(f"  {eng_name} ...", file=sys.stderr, end="", flush=True)

                t0 = time.monotonic()
                try:
                    results = (await engine.search_with_reason(query, "en", max_r))[0]
                    ms = round((time.monotonic() - t0) * 1000)
                    print(f" {len(results)} ({ms}ms)", file=sys.stderr)
                    run_stats[eng_name]["total"] += len(results)
                    for r in results:
                        run_results.append({
                            "engine":   eng_name,
                            "position": r.position,
                            "url":      r.url,
                        })
                except Exception as e:
                    ms = round((time.monotonic() - t0) * 1000)
                    print(f" ERROR {e} ({ms}ms)", file=sys.stderr)
                    run_stats[eng_name]["errors"] += 1

                if i < len(engines) - 1:
                    await asyncio.sleep(BROWSER_SLEEP_S)

            all_runs[base_query] = run_results
    finally:
        await close_browser()

    report_path = write_report(all_runs, run_stats, REPORT_DIR)
    print(f"\nReport: {report_path}", file=sys.stderr)


# FUNCTIONS

def write_report(all_runs: dict, run_stats: dict, report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"books_probe_{ts}.md"
    path.write_text("\n".join(_build_report(all_runs, run_stats, ts)), encoding="utf-8")
    return path


def _build_report(all_runs: dict, run_stats: dict, ts: str) -> list[str]:
    lines = [
        f"# Books Domain Probe — {ts}",
        "",
        f"**Scope:** {len(QUERIES)} queries × 2 engines × +book = {len(QUERIES) * 2} runs",
        "**Engines:** google (max=100), duckduckgo (max=200)",
        "**Modifier:** free word `book` appended to each query (no operator)",
        "**Goal:** observe raw domain pool — no classification applied",
        "",
    ]
    lines += _section_url_listings(all_runs)
    lines += _section_global_domain_freq(all_runs)
    lines += _section_top_n_inspection(all_runs)
    lines += _section_per_engine_distribution(all_runs)
    lines += _section_run_stats(all_runs, run_stats)
    return lines


def _section_url_listings(all_runs: dict) -> list[str]:
    lines = ["## Per-Query URL Listings", ""]
    for qi, base_query in enumerate(QUERIES, 1):
        results = all_runs.get(base_query, [])
        full_q = f'"{base_query}{SUFFIX}"'
        lines += [
            f"### Q{qi}: {base_query}",
            "",
            f"#### +book — {full_q}",
            "",
            "| # | Engine | Pos | URL |",
            "|---|--------|----:|-----|",
        ]
        if results:
            for row_i, r in enumerate(results, 1):
                url = r["url"].replace("|", "%7C")
                lines.append(f"| {row_i} | {r['engine']} | {r['position']} | {url} |")
        else:
            lines.append("| — | — | — | (no results) |")
        lines.append("")
    return lines


def _section_global_domain_freq(all_runs: dict) -> list[str]:
    all_results = [r for results in all_runs.values() for r in results]
    eng_counters: dict[str, Counter] = {name: Counter() for name, _ in ENGINE_ORDER}
    query_presence: dict[str, set] = defaultdict(set)

    for base_query, results in all_runs.items():
        for r in results:
            d = _domain(r["url"])
            if not d:
                continue
            eng_counters[r["engine"]][d] += 1
            query_presence[d].add(base_query)

    total_counter: Counter = Counter()
    for ec in eng_counters.values():
        total_counter.update(ec)

    above_threshold = [(d, total_counter[d]) for d in total_counter if total_counter[d] >= MIN_DOMAIN_COUNT]
    above_threshold.sort(key=lambda x: x[1], reverse=True)
    singletons = sorted(d for d in total_counter if total_counter[d] < MIN_DOMAIN_COUNT)

    lines = ["## Global Domain Frequency Table", ""]
    lines += [
        f"Domains with count ≥ {MIN_DOMAIN_COUNT} across all {len(QUERIES)} queries and 2 engines.",
        "",
        "| Domain | Total | google | duckduckgo | # Queries |",
        "|--------|------:|------:|-----------:|----------:|",
    ]
    for d, total in above_threshold:
        g = eng_counters["google"][d]
        ddg = eng_counters["duckduckgo"][d]
        nq = len(query_presence[d])
        lines.append(f"| {d} | {total} | {g} | {ddg} | {nq} |")

    lines += [
        "",
        f"**Long tail (count = 1, {len(singletons)} domains):** " + (", ".join(singletons[:80]) if singletons else "none"),
        "",
    ]
    if len(singletons) > 80:
        lines.append(f"*(and {len(singletons) - 80} more)*")
        lines.append("")
    return lines


def _section_top_n_inspection(all_runs: dict) -> list[str]:
    all_results = [r for results in all_runs.values() for r in results]

    total_counter: Counter = Counter()
    domain_paths: dict[str, list[str]] = defaultdict(list)
    seen_paths: dict[str, set] = defaultdict(set)

    for r in all_results:
        d = _domain(r["url"])
        if not d:
            continue
        total_counter[d] += 1
        path = urlparse(r["url"]).path
        if path not in seen_paths[d]:
            seen_paths[d].add(path)
            domain_paths[d].append(path[:MAX_PATH_LEN])

    top = sorted(total_counter, key=lambda d: total_counter[d], reverse=True)[:TOP_DOMAIN_LIMIT]

    lines = [f"## Top-{TOP_DOMAIN_LIMIT} Domain Inspection", ""]
    lines += [
        "Sample paths are the first distinct URL paths seen for each domain across all queries.",
        "Paths truncated to 80 chars. Fewer than 3 shown when domain has fewer distinct paths.",
        "",
        "| Domain | Count | Sample Path 1 | Sample Path 2 | Sample Path 3 |",
        "|--------|------:|---------------|---------------|---------------|",
    ]
    for d in top:
        count = total_counter[d]
        paths = domain_paths[d][:MAX_SAMPLE_PATHS]
        row_paths = [f"`{p}`" if p else "`/`" for p in paths]
        while len(row_paths) < MAX_SAMPLE_PATHS:
            row_paths.append("—")
        lines.append(f"| {d} | {count} | {row_paths[0]} | {row_paths[1]} | {row_paths[2]} |")
    lines.append("")
    return lines


def _section_per_engine_distribution(all_runs: dict) -> list[str]:
    eng_counters: dict[str, Counter] = {name: Counter() for name, _ in ENGINE_ORDER}
    for results in all_runs.values():
        for r in results:
            d = _domain(r["url"])
            if d:
                eng_counters[r["engine"]][d] += 1

    lines = ["## Per-Engine Domain Distribution", ""]
    for eng_name, _ in ENGINE_ORDER:
        ec = eng_counters[eng_name]
        top = ec.most_common(TOP_PER_ENGINE)
        lines += [
            f"### {eng_name} — top {TOP_PER_ENGINE}",
            "",
            "| Domain | Count |",
            "|--------|------:|",
        ]
        for d, cnt in top:
            lines.append(f"| {d} | {cnt} |")
        lines.append("")
    return lines


def _section_run_stats(all_runs: dict, run_stats: dict) -> list[str]:
    lines = ["## Run Stats", ""]
    lines += [
        "| Engine | Total URLs | Mean / Query | Errors / Empties |",
        "|--------|----------:|-------------:|-----------------:|",
    ]
    for eng_name, _ in ENGINE_ORDER:
        total = run_stats[eng_name]["total"]
        errors = run_stats[eng_name]["errors"]
        empties = sum(
            1 for base_query, results in all_runs.items()
            if not any(r["engine"] == eng_name for r in results)
        )
        mean = round(total / len(QUERIES), 1) if QUERIES else 0
        lines.append(f"| {eng_name} | {total} | {mean} | {errors} errors / {empties} empties |")

    total_all = sum(len(v) for v in all_runs.values())
    lines += ["", f"**Total URLs collected:** {total_all}", ""]
    return lines


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


if __name__ == "__main__":
    asyncio.run(run_probe())
