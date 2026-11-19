# INFRASTRUCTURE
import re
from pathlib import Path

from src.config import RESPLIT_PIECE_PAGES
from src.pdf.manifest import load_manifest, write_manifest
from src.pdf.pieces import plan_ranges, write_piece_prompt
from src.pdf.report import Report, WorkflowError

SPAN = re.compile(r"^(\d+)-(\d+)$")


# ORCHESTRATOR
def resplit_workflow(batch_dir: str, piece: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    blocked = require_blocked_piece(manifest, batch_path, piece)
    size = next_piece_pages(blocked)
    entries = write_sub_pieces(manifest, batch_path, blocked, size)
    replace_piece(manifest, batch_path, blocked, entries)
    return Report(format_summary(blocked, size, entries), True)


# FUNCTIONS
def require_blocked_piece(manifest: dict, batch_dir: Path, piece: str) -> dict:
    match = SPAN.match(piece)
    found = [entry for entry in manifest["pieces"] if match and (entry["from"], entry["to"]) == (int(match[1]), int(match[2]))]
    if not found:
        raise WorkflowError("piece_unknown", f"no piece {piece} in the manifest")
    if (batch_dir / found[0]["output"]).exists():
        raise WorkflowError("piece_finished", f"{found[0]['output']} exists, a finished piece is never split")
    return found[0]


def next_piece_pages(piece: dict) -> int:
    pages = piece["to"] - piece["from"] + 1
    smaller = [size for size in RESPLIT_PIECE_PAGES if size < pages]
    if not smaller:
        raise WorkflowError(
            "piece_minimal",
            f"piece {piece['from']}-{piece['to']} has {pages} pages, no piece size below it in {list(RESPLIT_PIECE_PAGES)}",
        )
    return max(smaller)


def write_sub_pieces(manifest: dict, batch_dir: Path, piece: dict, size: int) -> list[dict]:
    pdf = Path(manifest["pdf"])
    return [write_piece_prompt(pdf, batch_dir, first, last) for first, last in plan_ranges(piece["from"], piece["to"], size)]


def replace_piece(manifest: dict, batch_dir: Path, piece: dict, entries: list[dict]) -> None:
    kept = [entry for entry in manifest["pieces"] if entry is not piece]
    manifest["pieces"] = sorted(kept + entries, key=lambda entry: entry["from"])
    write_manifest(batch_dir, manifest)
    (batch_dir / piece["prompt"]).unlink(missing_ok=True)


def format_summary(piece: dict, size: int, entries: list[dict]) -> str:
    return "\n".join([
        f"resplit ok: piece {piece['from']}-{piece['to']} into {len(entries)} pieces of at most {size} pages",
        "prompts: " + " ".join(entry["prompt"] for entry in entries),
    ])
