#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COLLECTION_DIR = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli"
    "/data/documents/coindesk"
)
COLLECTION_NAME = "coindesk"
INPUT_DIR = Path(__file__).parent / "03_data"
DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk publish — copy cleaned MDs to RAG collection and index."
    )
    _add_arguments(parser)
    parser.add_argument(
        "--skip-index", action="store_true", default=False,
        help="Copy files but skip rag-cli index (for testing)"
    )
    args = parser.parse_args()
    n_copied, n_chunks = publish_workflow(
        Path(args.input), Path(args.collection_dir), args.skip_index
    )
    _print_done_article_s(n_copied, n_chunks)


# FUNCTIONS

def _add_arguments(parser):
    parser.add_argument(
        "--input", default=str(INPUT_DIR),
        help=f"Directory of cleaned .md files + manifest.json (default: {INPUT_DIR})"
    )
    parser.add_argument(
        "--collection-dir", default=str(COLLECTION_DIR),
        help=f"RAG collection directory (default: {COLLECTION_DIR})"
    )


def publish_workflow(input_dir: Path, collection_dir: Path, skip_index: bool = False):
    manifest = load_manifest(input_dir)
    if not manifest:
        print("Manifest empty — nothing to publish.", file=sys.stderr)
        return 0, 0

    collection_dir.mkdir(parents=True, exist_ok=True)
    n_copied = copy_articles(manifest, input_dir, collection_dir)
    print(f"Copied: {n_copied} article(s) → {collection_dir}", file=sys.stderr)

    if skip_index:
        print("--skip-index set; skipping rag-cli index.", file=sys.stderr)
        return n_copied, 0

    indexed_files, indexed_chunks = run_rag_index(COLLECTION_NAME)
    print(f"Indexed: {indexed_files} file(s), {indexed_chunks} chunk(s).", file=sys.stderr)
    return n_copied, indexed_chunks


def _print_done_article_s(n_copied, n_chunks):
    print(f"Done: {n_copied} article(s) published, {n_chunks} chunk(s) indexed.")


def load_manifest(input_dir: Path) -> list[dict]:
    manifest_path = input_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"No manifest.json in {input_dir}", file=sys.stderr)
        return []
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def copy_articles(manifest: list[dict], input_dir: Path, collection_dir: Path) -> int:
    n_copied = 0
    for entry in manifest:
        h = entry.get("hash") or url_hash(entry.get("url", ""))
        pubdate = pub_date_str(entry)
        src = input_dir / f"{h}.md"
        dest = collection_dir / f"coindesk__{pubdate}__{h}.md"
        if not src.exists():
            print(f"  WARN: source not found: {src}", file=sys.stderr)
            continue
        shutil.copy2(src, dest)
        n_copied += 1
    return n_copied


def run_rag_index(collection: str) -> tuple[int, int]:
    result = subprocess.run(
        ["rag-cli", "index", "--collection", collection],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"rag-cli index failed (exit {result.returncode}):\n{result.stderr}"
        )
    return parse_index_result(result.stdout + result.stderr)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def pub_date_str(entry: dict) -> str:
    pub = entry.get("publication_date", "")
    if pub and len(pub) >= 10:
        return pub[:10]
    m = DATE_RE.search(entry.get("url", ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return "unknown"


def parse_index_result(output: str) -> tuple[int, int]:
    m = re.search(r"Done:\s*(\d+)\s*files?\s*indexed\s*\((\d+)\s*chunks?\)", output)
    if m:
        return int(m.group(1)), int(m.group(2))
    files_m = re.search(r"(\d+)\s*files?\s*indexed", output)
    chunks_m = re.search(r"\((\d+)\s*chunks?\)", output)
    files = int(files_m.group(1)) if files_m else 0
    chunks = int(chunks_m.group(1)) if chunks_m else 0
    return files, chunks


if __name__ == "__main__":
    main()
