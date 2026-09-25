# INFRASTRUCTURE
import asyncio
import importlib
import json
import re
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

_scraper_mod = importlib.import_module("src.crawler.pipe_scraper")
scrape_urls_workflow = _scraper_mod.scrape_urls_workflow

URL_FILE = REPO_ROOT / "dev/news_pipeline/04_json/discover_filtered_20260607T195044Z.json"
OUTPUT_DIR = REPO_ROOT / "dev/news_pipeline/smoke_output/raw"
REVIEW_FILE = REPO_ROOT / "dev/news_pipeline/smoke_output/regwall_review.md"

REGWALL_MARKERS = [
    "sign up",
    "create a free account",
    "create an account",
    "already have an account",
    "subscribe",
    "register",
    "continue reading",
    "by signing up",
    "sign in to continue",
]


# ORCHESTRATOR

def main():
    urls = _load_urls(URL_FILE)
    _print_loaded_urls_from(urls)

    asyncio.run(scrape_urls_workflow(urls, OUTPUT_DIR))

    rows = _build_rows(urls, OUTPUT_DIR)
    _write_review(rows, REVIEW_FILE)
    _print_stdout_summary(rows, REVIEW_FILE)


# FUNCTIONS

def _load_urls(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item["url"] for item in data]


def _print_loaded_urls_from(urls):
    print(f"Loaded {len(urls)} URLs from {URL_FILE}", flush=True)


def _build_rows(urls: list[str], output_dir: Path) -> list[dict]:
    file_by_url: dict[str, Path] = {}
    for fpath in output_dir.glob("*.md"):
        text = fpath.read_text(encoding="utf-8", errors="replace")
        first_line = text.split("\n", 1)[0].strip()
        m = re.match(r"<!--\s*source:\s*(.+?)\s*-->", first_line)
        if m:
            file_by_url[m.group(1)] = fpath

    rows = []
    for url in urls:
        fpath = file_by_url.get(url)
        if fpath is None:
            rows.append({
                "url": url,
                "found": False,
                "bytes": 0,
                "lines": 0,
                "marker_hits": 0,
                "verdict": "MISSING",
                "content_lines": [],
            })
            continue

        text = fpath.read_text(encoding="utf-8", errors="replace")
        byte_count = len(text.encode("utf-8"))
        all_lines = text.splitlines()

        lower_text = text.lower()
        hits = sum(lower_text.count(marker) for marker in REGWALL_MARKERS)

        verdict = "REGWALL?" if (byte_count < 3000 or hits >= 3) else "article?"

        rows.append({
            "url": url,
            "found": True,
            "bytes": byte_count,
            "lines": len(all_lines),
            "marker_hits": hits,
            "verdict": verdict,
            "content_lines": all_lines,
        })
    return rows


def _write_review(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "# CoinDesk Prod Scrape — Regwall Review",
        "",
        "> verdict_hint: `REGWALL?` if bytes<3000 OR marker_hits≥3, else `article?`. Judge by eye on previews.",
        "",
        "## Summary Table",
        "",
        "| slug | bytes | lines | marker_hits | verdict_hint |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        slug = row["url"].rstrip("/").split("/")[-1][:60]
        parts.append(
            f"| {slug} | {row['bytes']} | {row['lines']} | {row['marker_hits']} | {row['verdict']} |"
        )

    parts += ["", "---", ""]

    for row in rows:
        parts.append(f"## {row['url']}")
        parts.append("")
        if not row["found"]:
            parts.append("**NO FILE — scrape produced no output for this URL (error or empty).**")
            parts.append("")
            continue
        parts.append(
            f"bytes: {row['bytes']} | lines: {row['lines']} "
            f"| marker_hits: {row['marker_hits']} | verdict_hint: {row['verdict']}"
        )
        parts.append("")
        preview = row["content_lines"][:50]
        parts.append("```")
        parts.extend(preview)
        parts.append("```")
        parts.append("")

    out_path.write_text("\n".join(parts), encoding="utf-8")


def _print_stdout_summary(rows: list[dict], review_path: Path) -> None:
    found = [r for r in rows if r["found"]]
    missing = [r for r in rows if not r["found"]]
    byte_vals = [r["bytes"] for r in found]

    ok_count = sum(1 for r in found if r["bytes"] >= 100)
    empty_count = sum(1 for r in found if r["bytes"] < 100)
    error_count = len(missing)
    regwall_count = sum(1 for r in rows if r["verdict"] == "REGWALL?")

    byte_min = min(byte_vals) if byte_vals else 0
    byte_max = max(byte_vals) if byte_vals else 0
    byte_median = int(statistics.median(byte_vals)) if byte_vals else 0

    print(f"\n=== SMOKE SUMMARY ===")
    print(f"ok (>=100 bytes): {ok_count}  |  empty (<100 bytes): {empty_count}  |  error/missing: {error_count}")
    print(f"bytes  min={byte_min}  median={byte_median}  max={byte_max}")
    print(f"REGWALL? (heuristic): {regwall_count}/{len(rows)}")
    print(f"Review: {review_path}")


if __name__ == "__main__":
    main()
