# INFRASTRUCTURE
import json
from pathlib import Path

from src.pdf.batch_files import HEADINGS_FILE, HEADINGS_FIXED_FILE, REPAIR_PENDING, read_json

STATE_COMPLETE = "complete"
STATE_INCOMPLETE = "incomplete"


# FUNCTIONS
def worker_states(batch_dir: Path, manifest: dict) -> list[tuple[dict, str, list[str]]]:
    return [(worker, *worker_state(batch_dir, worker)) for worker in manifest["workers"]]


def worker_state(batch_dir: Path, worker: dict) -> tuple[str, list[str]]:
    missing = [name for name in worker["outputs"] if not output_complete(batch_dir, name)]
    return (STATE_INCOMPLETE, missing) if missing else (STATE_COMPLETE, [])


def output_complete(batch_dir: Path, name: str) -> bool:
    path = batch_dir / name
    if not path.is_file():
        return False
    if name == HEADINGS_FIXED_FILE:
        return outline_complete(batch_dir, path)
    return REPAIR_PENDING not in (line.strip() for line in path.read_text(encoding="utf-8").splitlines())


def outline_complete(batch_dir: Path, path: Path) -> bool:
    try:
        outline = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(outline, dict) or not isinstance(outline.get("headings"), list) or not isinstance(outline.get("missed"), list):
        return False
    given = {entry.get("id") for entry in outline["headings"] if isinstance(entry, dict)}
    return all(heading["id"] in given for heading in read_json(batch_dir, HEADINGS_FILE))


def format_unfinished(unfinished: list[tuple[dict, str, list[str]]]) -> list[str]:
    return [f"  {worker['name']}: incomplete (missing: {' '.join(missing)})" for worker, _, missing in unfinished]
