# INFRASTRUCTURE
from pathlib import Path

from src.pdf.manifest import load_manifest
from src.pdf.pieces import STATE_COMPLETE, STATE_INCOMPLETE, piece_state
from src.pdf.report import Report


# ORCHESTRATOR
def status_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    states = piece_states(manifest, batch_path)
    return Report(format_status(states), True)


# FUNCTIONS
def piece_states(manifest: dict, batch_dir: Path) -> list[tuple[dict, str, list[int]]]:
    pieces = sorted(manifest["pieces"], key=lambda piece: piece["from"])
    return [(piece, *piece_state(batch_dir, piece)) for piece in pieces]


def format_status(states: list[tuple[dict, str, list[int]]]) -> str:
    complete = sum(1 for _, state, _ in states if state == STATE_COMPLETE)
    lines = [f"pieces complete: {complete} of {len(states)}"]
    lines += [describe_piece(piece, state, missing) for piece, state, missing in states]
    return "\n".join(lines)


def describe_piece(piece: dict, state: str, missing: list[int]) -> str:
    line = f"  piece {piece['from']}-{piece['to']}: {state}"
    if state == STATE_INCOMPLETE:
        line += " (no page marker for pages " + " ".join(str(page) for page in missing) + ")"
    return line
