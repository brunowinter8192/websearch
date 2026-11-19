# INFRASTRUCTURE
import re
from pathlib import Path

from src.pdf.templates import page_range, read_template, require_filled, substitute

READ_PAGES_LIMIT = 20
PAGE_MARKER = re.compile(r"^<!-- page (\d+) -->$", re.MULTILINE)
STATE_COMPLETE = "complete"
STATE_INCOMPLETE = "incomplete"
STATE_MISSING = "missing"


# FUNCTIONS
def plan_ranges(first: int, last: int, size: int) -> list[tuple[int, int]]:
    return [(start, min(start + size - 1, last)) for start in range(first, last + 1, size)]


def write_piece_prompt(pdf: Path, batch_dir: Path, first: int, last: int) -> dict:
    entry = piece_entry(first, last)
    (batch_dir / entry["prompt"]).write_text(render_prompt(pdf, batch_dir, entry), encoding="utf-8")
    return entry


def piece_entry(first: int, last: int) -> dict:
    span = f"{first}-{last}"
    chunks = plan_ranges(first, last, READ_PAGES_LIMIT)
    return {
        "from": first,
        "to": last,
        "prompt": f"prompt_{span}.md",
        "output": f"piece_{span}.md",
        "parts": [f"part{number}_{span}.md" for number in range(1, len(chunks) + 1)] if len(chunks) > 1 else [],
    }


def render_prompt(pdf: Path, batch_dir: Path, entry: dict) -> str:
    first, last = entry["from"], entry["to"]
    text = read_template("worker_prompt.md").replace("{{STEPS}}", build_steps(batch_dir, entry))
    values = {
        "PDF": str(pdf),
        "FROM": str(first),
        "TO": str(last),
        "OUTPUT": str(batch_dir / entry["output"]),
        "READ_PAGES": page_range(first, last),
    }
    return require_filled(substitute(text, values))


def build_steps(batch_dir: Path, entry: dict) -> str:
    if not entry["parts"]:
        return read_template("steps_single.md")
    chunks = plan_ranges(entry["from"], entry["to"], READ_PAGES_LIMIT)
    parts = [str(batch_dir / name) for name in entry["parts"]]
    blocks = [chunk_block(1 + 2 * number, chunk, part) for number, (chunk, part) in enumerate(zip(chunks, parts))]
    next_number = 1 + 2 * len(chunks)
    values = {
        "CHUNK_STEPS": "\n".join(blocks),
        "CAT_NUMBER": str(next_number),
        "CAT_COMMAND": cat_command(parts, str(batch_dir / entry["output"])),
        "DONE_NUMBER": str(next_number + 1),
    }
    return substitute(read_template("steps_split.md"), values)


def chunk_block(read_number: int, chunk: tuple[int, int], part: str) -> str:
    values = {
        "READ_NUMBER": str(read_number),
        "WRITE_NUMBER": str(read_number + 1),
        "CHUNK_PAGES": page_range(*chunk),
        "CHUNK_PART": part,
    }
    return substitute(read_template("chunk_steps.md").rstrip("\n"), values)


def cat_command(parts: list[str], output: str) -> str:
    joined = "; echo; ".join(f'cat "{part}"' for part in parts)
    removals = " ".join(f'"{part}"' for part in parts)
    return f'{{ {joined}; }} > "{output}" && rm {removals}'


def piece_state(batch_dir: Path, piece: dict) -> tuple[str, list[int]]:
    path = batch_dir / piece["output"]
    pages = list(range(piece["from"], piece["to"] + 1))
    if not path.is_file():
        return STATE_MISSING, pages
    found = {page for page, _ in page_markers(path.read_text(encoding="utf-8"))}
    missing = [page for page in pages if page not in found]
    return (STATE_INCOMPLETE, missing) if missing else (STATE_COMPLETE, [])


def page_markers(text: str) -> list[tuple[int, int]]:
    return [(int(match[1]), match.start()) for match in PAGE_MARKER.finditer(text)]
