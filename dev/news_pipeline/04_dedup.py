#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

COLLECTION_DIR = Path(
    "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli"
    "/data/documents/coindesk"
)
OUTPUT_DIR = Path(__file__).parent / "04_json"
DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


# ORCHESTRATOR

def main():
    parser = argparse.ArgumentParser(
        description="CoinDesk dedup gate — filters discover JSON to URLs not yet in the RAG collection."
    )
    parser.add_argument(
        "--input", default=None,
        help="Path to discover_*.json (default: newest in 01_json/)"
    )
    _add_arguments(parser)
    args = parser.parse_args()
    input_path = _compute_input_path(args)
    dedup_workflow(input_path, Path(args.collection_dir))


# FUNCTIONS

def _add_arguments(parser):
    parser.add_argument(
        "--collection-dir", default=str(COLLECTION_DIR),
        help=f"RAG collection directory (default: {COLLECTION_DIR})"
    )


def _compute_input_path(args):
    input_path = Path(args.input) if args.input else pick_latest_input()
    return input_path


def dedup_workflow(input_path: Path, collection_dir: Path):
    entries = load_entries(input_path)
    print(f"Input : {input_path} ({len(entries)} entries)", file=sys.stderr)
    print(f"Collection dir: {collection_dir}", file=sys.stderr)

    new_entries, n_skipped = filter_new(entries, collection_dir)

    output_path = write_output(new_entries)
    print_summary(len(entries), n_skipped, len(new_entries), output_path)
    return output_path


def pick_latest_input() -> Path:
    input_dir = Path(__file__).parent / "01_json"
    candidates = sorted(input_dir.glob("discover_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No discover_*.json found in {input_dir}")
    return candidates[-1]


def load_entries(input_path: Path) -> list[dict]:
    return json.loads(input_path.read_text(encoding="utf-8"))


def filter_new(entries: list[dict], collection_dir: Path) -> tuple[list[dict], int]:
    new_entries = []
    n_skipped = 0
    for entry in entries:
        h = url_hash(entry["url"])
        pubdate = pub_date_str(entry)
        target = collection_dir / f"coindesk__{pubdate}__{h}.md"
        if target.exists():
            n_skipped += 1
        else:
            new_entries.append(entry)
    return new_entries, n_skipped


def write_output(entries: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_DIR / f"discover_filtered_{ts}.json"
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_summary(total: int, skipped: int, new: int, output_path: Path):
    print(f"Total input : {total}")
    print(f"Skipped (already indexed): {skipped}")
    print(f"New (to scrape): {new}")
    print(f"Output      : {output_path}")


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def pub_date_str(entry: dict) -> str:
    pub = entry.get("publication_date", "")
    if pub and len(pub) >= 10:
        return pub[:10]
    m = DATE_RE.search(entry.get("url", ""))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


if __name__ == "__main__":
    main()
