#!/usr/bin/env python3
# INFRASTRUCTURE
import asyncio
import logging
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from src.search.engines import google as google_engine
from src.search.engines import scholar as scholar_engine
from src.search.engines import duckduckgo as duckduckgo_engine
from src.search.engines import openalex as openalex_engine
from src.search.browser import close_browser

REPORT_DIR = SCRIPT_DIR / "md"

BASE_QUERIES = [
    "python asyncio",
    "tolkien hobbit",
    "sparse retrieval models",
]

VARIANTS = [
    ("baseline", ""),
    ("pdf",      " pdf"),
    ("book",     " book"),
]

ENGINE_ORDER = [
    ("google",         google_engine),
    ("google_scholar", scholar_engine),
    ("duckduckgo",     duckduckgo_engine),
    ("openalex",       openalex_engine),
]

ENGINE_MAX = {
    "google":         100,
    "google_scholar": 100,
    "duckduckgo":     200,
    "openalex":       200,
}

BROWSER_ENGINES = frozenset({"google", "google_scholar", "duckduckgo"})
BROWSER_SLEEP_S = 1.0
API_SLEEP_S = 0.5

PDF_HOSTS = frozenset({"arxiv.org", "doi.org", "dl.acm.org", "ieeexplore.ieee.org", "pmc.ncbi.nlm.nih.gov"})

BOOK_HOSTS = frozenset({"thalia.de", "openlibrary.org", "books.google.com", "goodreads.com",
                        "gutenberg.org", "doabooks.org", "hathitrust.org"})


# ORCHESTRATOR

async def run_probe() -> None:
    _configure_logging()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    engines = _compute_engines()
    run_stats = _compute_run_stats()

    all_runs = await _run_free_word_queries(engines, run_stats)

    report_path = write_report(all_runs, run_stats, REPORT_DIR)
    _print_report(report_path)


# FUNCTIONS

def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _compute_engines():
    engines = [(name, engine_module) for name, engine_module in ENGINE_ORDER]
    return engines


def _compute_run_stats():
    run_stats: dict[str, dict] = {name: {"total": 0, "errors": 0} for name, _ in ENGINE_ORDER}
    return run_stats


async def _run_free_word_queries(engines, run_stats):
    all_runs: dict[tuple[str, str], list[dict]] = {}
    try:
        for base_query in BASE_QUERIES:
            for vkey, suffix in VARIANTS:
                all_runs[(base_query, vkey)] = await _run_variant(base_query + suffix, vkey, engines, run_stats)
    finally:
        await close_browser()
    return all_runs


def write_report(all_runs: dict, run_stats: dict, report_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"free_word_injection_probe_{ts}.md"
    path.write_text("\n".join(_build_report(all_runs, run_stats, ts)), encoding="utf-8")
    return path


def _print_report(report_path):
    print(f"\nReport: {report_path}", file=sys.stderr)


async def _run_variant(query, vkey, engines, run_stats):
    print(f"\n=== {query!r} ({vkey}) ===", file=sys.stderr)
    run_results: list[dict] = []
    for i, (eng_name, engine) in enumerate(engines):
        await _query_engine(eng_name, engine, query, run_stats, run_results)
        if i < len(engines) - 1:
            await asyncio.sleep(_engine_sleep_s(eng_name))
    return run_results


def _build_report(all_runs: dict, run_stats: dict, ts: str) -> list[str]:
    lines = [
        f"# Free-Word Injection Probe — {ts}",
        "",
        "**Scope:** 3 queries × 3 variants (baseline / +pdf / +book) = 9 runs",
        "**Per-engine max_results:** Google=100, Scholar=100, SE=100; DDG/Mojeek/Lobsters/OpenAlex/CrossRef=200",
        "",
    ]
    lines += _url_listings(all_runs)
    lines += _domain_distribution(all_runs)
    lines += _summary_insights(all_runs)
    lines += _run_stats(all_runs, run_stats)
    return lines


async def _query_engine(eng_name, engine, query, run_stats, run_results) -> None:
    max_r = ENGINE_MAX[eng_name]
    print(f"  {eng_name} ...", file=sys.stderr, end="", flush=True)

    t0 = time.monotonic()
    try:
        results = (await engine.search_with_reason(query, "en", max_r))[0]
        ms = round((time.monotonic() - t0) * 1000)
        print(f" {len(results)} ({ms}ms)", file=sys.stderr)
        run_stats[eng_name]["total"] += len(results)
        _append_rows(run_results, eng_name, results)
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000)
        print(f" ERROR {e} ({ms}ms)", file=sys.stderr)
        run_stats[eng_name]["errors"] += 1


def _engine_sleep_s(eng_name):
    return BROWSER_SLEEP_S if eng_name in BROWSER_ENGINES else API_SLEEP_S


def _url_listings(all_runs: dict) -> list[str]:
    lines = ["## Per-Variant URL Listings", ""]
    for qi, bq in enumerate(BASE_QUERIES, 1):
        lines += [f"### Q{qi}: {bq}", ""]
        for vkey, suffix in VARIANTS:
            results = all_runs.get((bq, vkey), [])
            vlabel = "Baseline" if vkey == "baseline" else f"+{vkey}"
            full_q = f'"{bq}{suffix}"'
            lines += [
                f"#### {vlabel} — {full_q}",
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


def _domain_distribution(all_runs: dict) -> list[str]:
    lines = ["## Domain Distribution Comparison", ""]
    for qi, bq in enumerate(BASE_QUERIES, 1):
        sb = _stats(all_runs.get((bq, "baseline"), []))
        sp = _stats(all_runs.get((bq, "pdf"), []))
        sk = _stats(all_runs.get((bq, "book"), []))
        lines += [f"### Q{qi}: {bq}", ""]

        lines += [
            "| Metric | Baseline | +pdf | +book |",
            "|--------|----------|------|-------|",
            f"| Total URLs | {sb['total']} | {sp['total']} | {sk['total']} |",
            f"| PDF-relevant URLs | {sb['pdf_count']} | {sp['pdf_count']} | {sk['pdf_count']} |",
            f"| Book-domain URLs | {sb['book_count']} | {sp['book_count']} | {sk['book_count']} |",
            "",
        ]

        all_doms = set(sb["domains"]) | set(sp["domains"]) | set(sk["domains"])
        top15 = sorted(
            all_doms,
            key=lambda d: sb["domains"][d] + sp["domains"][d] + sk["domains"][d],
            reverse=True,
        )[:15]
        lines += [
            "**Top 15 domains by URL count:**",
            "",
            "| Domain | Baseline | +pdf | +book |",
            "|--------|----------|------|-------|",
        ]
        for d in top15:
            lines.append(f"| {d} | {sb['domains'][d]} | {sp['domains'][d]} | {sk['domains'][d]} |")

        new_pdf  = sorted(set(sp["domains"]) - set(sb["domains"]))
        new_book = sorted(set(sk["domains"]) - set(sb["domains"]))
        lines += [
            "",
            f"**New domains in +pdf vs baseline ({len(new_pdf)}):** " + (", ".join(new_pdf) if new_pdf else "none"),
            f"**New domains in +book vs baseline ({len(new_book)}):** " + (", ".join(new_book) if new_book else "none"),
            "",
        ]
    return lines


def _summary_insights(all_runs: dict) -> list[str]:
    lines = ["## Summary Insights", ""]
    candidates: list[tuple[int, str]] = []

    for bq in BASE_QUERIES:
        sb = _stats(all_runs.get((bq, "baseline"), []))
        sp = _stats(all_runs.get((bq, "pdf"), []))
        sk = _stats(all_runs.get((bq, "book"), []))

        for vlabel, s in [("+pdf", sp), ("+book", sk)]:
            pdf_d   = s["pdf_count"]  - sb["pdf_count"]
            book_d  = s["book_count"] - sb["book_count"]
            pool_d  = s["total"]      - sb["total"]
            magnitude = abs(pdf_d) + abs(book_d) + abs(pool_d)

            parts = []
            if pdf_d:
                parts.append(f"PDF-relevant {sb['pdf_count']}→{s['pdf_count']} ({'+' if pdf_d > 0 else ''}{pdf_d})")
            if book_d:
                parts.append(f"book-domain {sb['book_count']}→{s['book_count']} ({'+' if book_d > 0 else ''}{book_d})")
            if pool_d:
                parts.append(f"pool {sb['total']}→{s['total']} ({'+' if pool_d > 0 else ''}{pool_d})")
            if not parts:
                parts.append("no measurable density shift")

            bullet = f'**"{bq}" {vlabel}:** ' + "; ".join(parts)
            candidates.append((magnitude, bullet))

    candidates.sort(key=lambda x: x[0], reverse=True)
    bullets = [b for _, b in candidates[:5]]
    if not bullets:
        bullets = ["No significant density shifts detected across all query/variant combinations."]

    for b in bullets:
        lines.append(f"- {b}")
    lines.append("")
    return lines


def _run_stats(all_runs: dict, run_stats: dict) -> list[str]:
    lines = ["## Run Stats", ""]
    lines += [
        "| Engine | Total URLs | Mean / Run | Errors / Empties |",
        "|--------|----------:|-----------:|-----------------:|",
    ]
    for eng_name, _ in ENGINE_ORDER:
        total = run_stats[eng_name]["total"]
        errors = run_stats[eng_name]["errors"]
        empties = sum(
            1 for results in all_runs.values()
            if not any(r["engine"] == eng_name for r in results)
        )
        mean = round(total / len(all_runs), 1) if all_runs else 0
        lines.append(f"| {eng_name} | {total} | {mean} | {errors} errors / {empties} empties |")

    total_all = sum(len(v) for v in all_runs.values())
    lines += ["", f"**Total URLs collected:** {total_all}", ""]
    return lines


def _append_rows(run_results, eng_name, results) -> None:
    for r in results:
        run_results.append({
            "engine":   eng_name,
            "position": r.position,
            "url":      r.url,
            "title":    r.title,
        })


def _stats(results: list[dict]) -> dict:
    domains = Counter(_domain(r["url"]) for r in results if _domain(r["url"]))
    return {
        "total":      len(results),
        "pdf_count":  sum(1 for r in results if _is_pdf(r["url"])),
        "book_count": sum(1 for r in results if _is_book(r["url"])),
        "domains":    domains,
    }


def _is_pdf(url: str) -> bool:
    if urlparse(url).path.lower().endswith(".pdf"):
        return True
    d = _domain(url)
    return d in PDF_HOSTS or any(d.endswith("." + h) for h in PDF_HOSTS)


def _is_book(url: str) -> bool:
    d = _domain(url)
    if d in BOOK_HOSTS or any(d.endswith("." + h) for h in BOOK_HOSTS):
        return True
    u = url.lower()
    if "amazon." in d and "/dp/" in u:
        return True
    if d == "archive.org" and "/details/" in u:
        return True
    if d == "springer.com" and "/book/" in u:
        return True
    return d == "jstor.org"


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


if __name__ == "__main__":
    asyncio.run(run_probe())
