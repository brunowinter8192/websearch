# INFRASTRUCTURE
import difflib

from src.config import NEW_PARAGRAPH
from src.pdf.coverage import normalized
from src.pdf.sample_runs import page_markers

KIND_CORRECTION = "correction"
KIND_DUPLICATE = "duplicate"
KIND_MIXED = "mixed"
TAG_INSERT = "insert"
TAG_EQUAL = "equal"


# FUNCTIONS
def judge_excerpts(book: str, changed: list[tuple[dict, str]]) -> list[tuple[dict, str, str, list[int]]]:
    judged = []
    for excerpt, edited in changed:
        kind, sources = excerpt_kind(book[:excerpt["start"]], excerpt, edited)
        judged.append((excerpt, edited, kind, sources))
    return judged


def excerpt_kind(book_before: str, excerpt: dict, edited: str) -> tuple[str, list[int]]:
    sources = [insertion_source(book_before, lines) if tag == TAG_INSERT else None for tag, lines in change_hunks(excerpt, edited)]
    found = [page for page in sources if page is not None]
    if not found:
        return KIND_CORRECTION, []
    if len(found) < len(sources):
        return KIND_MIXED, found
    return KIND_DUPLICATE, found


def change_hunks(excerpt: dict, edited: str) -> list[tuple[str, list[str]]]:
    before_lines = excerpt["original"].rstrip().split("\n")
    after_lines = edited.rstrip().split("\n")
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    return [(tag, after_lines[b_start:b_end]) for tag, _, _, b_start, b_end in matcher.get_opcodes() if tag != TAG_EQUAL]


def insertion_source(book_before: str, lines: list[str]) -> int | None:
    pages = [earlier_page_ending_with(book_before, block) for block in text_blocks(lines)]
    if not pages or None in pages:
        return None
    return pages[0]


def text_blocks(lines: list[str]) -> list[str]:
    blocks, current = [], []
    for line in lines + [""]:
        if line.strip():
            current.append(line)
        elif current:
            blocks.append(" ".join(current))
            current = []
    return blocks


def earlier_page_ending_with(book_before: str, block: str) -> int | None:
    tail = normalized(block)
    if not tail:
        return None
    bounds = page_markers(book_before) + [(0, len(book_before))]
    for (page, start), (_, end) in reversed(list(zip(bounds, bounds[1:]))):
        for paragraph in book_before[start:end].split(NEW_PARAGRAPH):
            whole = normalized(paragraph)
            if len(whole) > len(tail) and whole.endswith(tail):
                return page
    return None
