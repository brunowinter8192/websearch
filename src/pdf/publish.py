# INFRASTRUCTURE
import os
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import NEW_PARAGRAPH, PARAGRAPH_LIMIT_BYTES
from src.pdf.conversion_log import append_record, build_end_record
from src.pdf.manifest import book_path, load_manifest
from src.pdf.report import Report, WorkflowError
from src.pdf.sample_runs import STATUS_OPEN, load_runs, loop_ended, sampled_pages

PARAGRAPH_SEPARATOR = re.compile(r"(\n{2,})")
SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+(?=\S)")
TABLE_RULE_CHARS = set("-: ")


# ORCHESTRATOR
def publish_workflow(batch_dir: str, out_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    runs = load_runs(batch_path)
    require_loop_ended(manifest, runs)
    split = split_long_paragraphs(book_path(batch_path, manifest).read_text(encoding="utf-8"))
    target = write_published(Path(out_dir), manifest, split.text)
    log_published(manifest, runs, target, split)
    return Report(format_summary(manifest, runs, target, split), True)


# FUNCTIONS
@dataclass(frozen=True)
class SplitResult:
    text: str
    paragraphs_split: int
    tables_split: int
    paragraphs_over_limit: int


def require_loop_ended(manifest: dict, runs: list[dict]) -> None:
    if not runs:
        raise WorkflowError("sampling_missing", "no sample run yet, open one with pdf sample")
    if runs[-1]["status"] == STATUS_OPEN:
        raise WorkflowError("run_open", f"sample run {runs[-1]['run']} is still open, close it with pdf sample-close")
    if not loop_ended(runs, manifest["pages"]):
        raise WorkflowError("loop_not_ended", f"sample run {runs[-1]['run']} applied corrections, open the next run with pdf sample")


def split_long_paragraphs(book: str) -> SplitResult:
    parts = PARAGRAPH_SEPARATOR.split(book)
    pieces = [split_paragraph(paragraph) for paragraph in parts[0::2]]
    rebuilt = [NEW_PARAGRAPH.join(chunks) for chunks in pieces]
    text = "".join(part for pair in zip(rebuilt, parts[1::2] + [""]) for part in pair)
    split = [(paragraph, chunks) for paragraph, chunks in zip(parts[0::2], pieces) if len(chunks) > 1]
    return SplitResult(
        text=text,
        paragraphs_split=len(split),
        tables_split=sum(1 for paragraph, _ in split if is_table(paragraph)),
        paragraphs_over_limit=sum(1 for chunks in pieces for chunk in chunks if size(chunk) > PARAGRAPH_LIMIT_BYTES),
    )


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def is_table(paragraph: str) -> bool:
    return paragraph.lstrip().startswith("|")


def split_paragraph(paragraph: str) -> list[str]:
    if size(paragraph) <= PARAGRAPH_LIMIT_BYTES:
        return [paragraph]
    if is_table(paragraph):
        return split_table(paragraph)
    return split_block(paragraph)


def split_table(paragraph: str) -> list[str]:
    lines = paragraph.split("\n")
    has_rule = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= TABLE_RULE_CHARS
    head = lines[:2] if has_rule else []
    blocks, current = [], list(head)
    for row in lines[len(head):]:
        if size("\n".join(current + [row])) > PARAGRAPH_LIMIT_BYTES and len(current) > len(head):
            blocks.append("\n".join(current))
            current = list(head)
        current.append(row)
    blocks.append("\n".join(current))
    return blocks


def split_block(paragraph: str) -> list[str]:
    lines = paragraph.split("\n")
    if len(lines) == 1:
        return split_line(paragraph)
    pieces = [piece for line in lines for piece in split_line(line)]
    return pack(pieces, "\n")


def split_line(line: str) -> list[str]:
    if size(line) <= PARAGRAPH_LIMIT_BYTES:
        return [line]
    sentences = []
    for sentence in SENTENCE_END.split(line):
        sentences += pack(sentence.split(" "), " ") if size(sentence) > PARAGRAPH_LIMIT_BYTES else [sentence]
    return pack(sentences, " ")


def pack(pieces: list[str], joiner: str) -> list[str]:
    chunks, current = [], ""
    for piece in pieces:
        candidate = f"{current}{joiner}{piece}" if current else piece
        if size(candidate) > PARAGRAPH_LIMIT_BYTES and current:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    chunks.append(current)
    return chunks


def write_published(out_dir: Path, manifest: dict, content: str) -> Path:
    target = out_dir / f"{manifest['stem']}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(content.rstrip("\n") + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target


def log_published(manifest: dict, runs: list[dict], target: Path, split: SplitResult) -> None:
    append_record(build_end_record(
        manifest["run_id"], manifest["ts_start"], "ok", None,
        md=str(target),
        pieces=[[piece["from"], piece["to"]] for piece in sorted(manifest["pieces"], key=lambda piece: piece["from"])],
        sample_runs=[{"run": run["run"], "pages": run["pages"], "applied": run["applied"], "rejected": run["rejected"]} for run in runs],
        **split_counts(split),
    ))


def split_counts(split: SplitResult) -> dict:
    return {
        "paragraphs_split": split.paragraphs_split,
        "tables_split": split.tables_split,
        "paragraphs_over_limit": split.paragraphs_over_limit,
    }


def format_summary(manifest: dict, runs: list[dict], target: Path, split: SplitResult) -> str:
    applied = sum(len(run["applied"]) for run in runs)
    return "\n".join([
        f"publish ok: {target}",
        f"sample runs: {len(runs)}, pages sampled: {len(sampled_pages(runs))} of {manifest['pages']}, corrections applied: {applied}",
        f"paragraphs split: {split.paragraphs_split} (tables: {split.tables_split}), "
        f"limit {PARAGRAPH_LIMIT_BYTES} bytes, left over the limit: {split.paragraphs_over_limit}",
    ])
