# INFRASTRUCTURE
from pathlib import Path

from src.config import NEW_PARAGRAPH
from src.pdf.conversion_log import append_record, build_end_record, log_failure
from src.pdf.manifest import book_path, load_manifest
from src.pdf.pieces import STATE_COMPLETE, STATE_MISSING, piece_state
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import load_runs


# ORCHESTRATOR
def merge_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    require_no_sampling(batch_path)
    return merge_logged(manifest, batch_path)


# FUNCTIONS
def require_no_sampling(batch_dir: Path) -> None:
    if load_runs(batch_dir):
        raise WorkflowError("sampling_started", "sampling has started, a new merge would discard its corrections")


def merge_logged(manifest: dict, batch_dir: Path) -> Report:
    try:
        return merge_pieces(manifest, batch_dir)
    except Exception as error:
        failure_class = log_failure(manifest["run_id"], manifest["ts_start"], error, "merge_error")
        return Report(f"merge FAILED ({failure_class}): {error}", False)


def merge_pieces(manifest: dict, batch_dir: Path) -> Report:
    pieces = ordered_pieces(manifest)
    states = [(piece, *piece_state(batch_dir, piece)) for piece in pieces]
    unfinished = [entry for entry in states if entry[1] != STATE_COMPLETE]
    if unfinished:
        return report_unfinished(manifest, pieces, unfinished)
    return write_book(manifest, batch_dir, pieces)


def ordered_pieces(manifest: dict) -> list[dict]:
    pieces = sorted(manifest["pieces"], key=lambda piece: piece["from"])
    covered = [page for piece in pieces for page in range(piece["from"], piece["to"] + 1)]
    if covered != list(range(1, manifest["pages"] + 1)):
        raise WorkflowError("manifest_corrupt", "the pieces in the manifest do not cover every page exactly once")
    return pieces


def report_unfinished(manifest: dict, pieces: list[dict], unfinished: list[tuple[dict, str, list[int]]]) -> Report:
    missing = [piece for piece, state, _ in unfinished if state == STATE_MISSING]
    incomplete = [(piece, pages) for piece, state, pages in unfinished if state != STATE_MISSING]
    failure_class = "missing_piece" if missing else "incomplete_piece"
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], "failed", failure_class,
        missing_pieces=[{"from": piece["from"], "to": piece["to"]} for piece in missing],
        incomplete_pieces=[{"from": piece["from"], "to": piece["to"], "missing_pages": pages} for piece, pages in incomplete],
    ))
    lines = [f"merge FAILED ({failure_class}): {len(unfinished)} of {len(pieces)} pieces unfinished, nothing written"]
    lines += [f"  piece {piece['from']}-{piece['to']}: missing_file {piece['output']}" for piece in missing]
    lines += [
        f"  piece {piece['from']}-{piece['to']}: incomplete, no page marker for pages " + " ".join(str(page) for page in pages)
        for piece, pages in incomplete
    ]
    return Report("\n".join(lines), False)


def write_book(manifest: dict, batch_dir: Path, pieces: list[dict]) -> Report:
    text = NEW_PARAGRAPH.join((batch_dir / piece["output"]).read_text(encoding="utf-8").strip() for piece in pieces)
    target = book_path(batch_dir, manifest)
    target.write_text(text + "\n", encoding="utf-8")
    sizes = " ".join(f"{piece['from']}-{piece['to']}" for piece in pieces)
    return Report(f"merge ok: {target}\npages={manifest['pages']} pieces={len(pieces)}: {sizes}", True)
