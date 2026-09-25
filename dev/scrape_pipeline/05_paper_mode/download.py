#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import re
import sys
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path.home() / "Downloads"
CHUNK_SIZE = 8192


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description="Download .pdf URLs to ~/Downloads/. No prod imports."
    )
    parser.add_argument("urls", nargs="*", metavar="URL", help="Direct PDF URLs")
    parser.add_argument("--input", metavar="SMOKE_MD", help="Parse all .pdf URLs from a pipeline smoke report")
    parser.add_argument("--overwrite", action="store_true", help="Re-download if file already exists")
    args = parser.parse_args()

    if not args.input and not args.urls:
        parser.error("provide at least one URL or --input <smoke.md>")

    url_list: list[tuple[str, str]] = []

    if args.input:
        url_list.extend(parse_pdf_urls(args.input))

    _download_all(args, url_list)

    if not url_list:
        print("No PDF URLs to download.", file=sys.stderr)
        sys.exit(0)

    download_workflow(url_list, args.overwrite)


# FUNCTIONS

def parse_pdf_urls(input_path: str) -> list[tuple[str, str]]:
    lines = Path(input_path).read_text(encoding="utf-8").splitlines()
    q_label = "?"
    results = []
    skipped = 0
    for line in lines:
        m = re.match(r"^## (Q\d+):", line)
        if m:
            q_label = m.group(1)
            continue
        um = re.match(r"^\s+URL: (https?://\S+)$", line)
        if um:
            url = um.group(1)
            if url.endswith(".pdf"):
                results.append((q_label, url))
            else:
                skipped += 1
    print(f"(skipped {skipped} non-PDF URLs)", file=sys.stderr)
    return results


def _download_all(args, url_list):
    for url in args.urls:
        if not url.endswith(".pdf"):
            print(f"skipped: {url} — not a .pdf URL", file=sys.stderr)
        else:
            url_list.append(("—", url))


def download_workflow(urls: list[tuple[str, str]], overwrite: bool) -> None:
    print(f"PDFs to download: {len(urls)} → {OUTPUT_DIR}", file=sys.stderr)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, (q_label, url) in enumerate(urls, 1):
        status, detail = download_one(url, overwrite)
        rows.append((i, q_label, url, detail, status))
        indicator = "✓" if status == "ok" else "✗"
        print(f"  [{i:02d}/{len(urls)}] {indicator} {url[:80]}", file=sys.stderr)

    print_report(rows)


def download_one(url: str, overwrite: bool) -> tuple[str, str]:
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as e:
        return "failed", f"HTTP {e.response.status_code}"
    except requests.RequestException as e:
        return "failed", str(e)[:80]

    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        return "failed", f"not PDF (Content-Type: {content_type[:60]})"

    filename = extract_filename(response, url)
    filepath = OUTPUT_DIR / filename

    if filepath.exists() and not overwrite:
        return "skipped", f"exists: {filename}"

    try:
        write_pdf(response, filepath)
    except OSError as e:
        return "failed", f"write error: {e}"

    size_str = format_size(filepath.stat().st_size)
    return "ok", f"{filename} ({size_str})"


def print_report(rows: list[tuple]) -> None:
    print()
    print("| # | Q | URL | File / Reason | Status |")
    print("|---|---|-----|---------------|--------|")
    for i, q_label, url, detail, status in rows:
        url_s = url[:60] + ("…" if len(url) > 60 else "")
        print(f"| {i:2d} | {q_label} | {url_s} | {detail} | {status} |")


def extract_filename(response: requests.Response, url: str) -> str:
    cd = response.headers.get("Content-Disposition", "")
    if cd:
        m = re.search(r'filename[^;=\n]*=[\"\']?([^;\"\'\n]+)', cd)
        if m:
            name = m.group(1).strip()
            if name:
                return name

    path = url.split("?")[0].rstrip("/")
    basename = path.split("/")[-1]
    if basename and basename.lower().endswith(".pdf"):
        return basename

    return f"download_{int(time.time())}.pdf"


def write_pdf(response: requests.Response, filepath: Path) -> None:
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


if __name__ == "__main__":
    main()
