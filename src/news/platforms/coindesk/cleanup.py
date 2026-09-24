# INFRASTRUCTURE
import logging
import re

logger = logging.getLogger(__name__)

_RE_MORE_FOR_YOU     = re.compile(r'^More For You\s*$')
_RE_MORE_FOR_YOU_H2  = re.compile(r'^## More For You')
_RE_PRIVACY          = re.compile(r'^## We Care About Your Privacy')
_RE_TAG_FOOTER       = re.compile(r'^(\[[^\]]+\]\([^)]+\)){2,}$')
_RE_TAG_LINE         = re.compile(r'^(\[[^\]]+\]\([^)]+\))+$')

_END_ANCHORS = [
    ("MORE_FOR_YOU",    _RE_MORE_FOR_YOU),
    ("MORE_FOR_YOU_H2", _RE_MORE_FOR_YOU_H2),
    ("PRIVACY",         _RE_PRIVACY),
    ("TAG_FOOTER",      _RE_TAG_FOOTER),
]

_RE_GOOGLE_BADGE = re.compile(r'\[Make\s*\]\(https://www\.google\.com/preferences/source')
_RE_DATE_BYLINE  = re.compile(r'^(?:Updated |Published )?[A-Z][a-z]+ \d{1,2}, \d{4},.*read$')
_RE_BYLINE       = re.compile(r'^By \[.*?\]\(.*?\)(?:[,|].*)?\s*$')
_RE_IMAGE        = re.compile(r'^!\[.*?\]\(.*?\)\s*$')
_RE_IMAGE_LINK   = re.compile(r'^\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$')
_RE_EMPTY_LINK   = re.compile(r'\[\]\(.*?\)')
_RE_INLINE_LINK  = re.compile(r'\[([^\]]+)\]\([^)]+\)')


# FUNCTIONS

def cleanup(raw_markdown: str, entry: dict) -> str:
    body_lines = raw_markdown.splitlines()

    start_idx = find_start_anchor(body_lines)
    if start_idx is None:
        logger.warning("coindesk cleanup: no H1 start anchor, body-less: %s", entry.get("url"))
        return ""

    end_idx, end_anchor = find_end_anchor(body_lines, start_idx)
    if end_anchor == "NONE":
        logger.warning("coindesk cleanup: no end anchor, kept tail to end of page: %s", entry.get("url"))
    extracted = body_lines[start_idx:end_idx]
    cleaned_lines, _, _, _ = clean_body(extracted)
    return "\n".join(cleaned_lines)


def find_start_anchor(body_lines: list[str]) -> int | None:
    for i, line in enumerate(body_lines):
        if line.startswith("# "):
            return i
    return None


def find_end_anchor(body_lines: list[str], start_idx: int) -> tuple[int, str]:
    for i in range(start_idx + 1, len(body_lines)):
        line = body_lines[i]
        for name, pattern in _END_ANCHORS:
            if pattern.match(line):
                return i, name
    return len(body_lines), "NONE"


def clean_body(lines: list[str]) -> tuple[list[str], int, int, int]:
    pass1, ws_strips, tag_strips = _strip_and_substitute_lines(lines)
    result, para_inserts = _normalize_paragraphs(pass1)

    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()

    return result, ws_strips, para_inserts, tag_strips


def _strip_and_substitute_lines(lines: list[str]) -> tuple[list[str], int, int]:
    pass1: list[str] = []
    ws_strips = 0
    tag_strips = 0
    for line in lines:
        if _RE_TAG_LINE.match(line):
            tag_strips += 1
            continue
        if _RE_GOOGLE_BADGE.search(line):
            continue
        if _RE_DATE_BYLINE.match(line):
            continue
        if _RE_BYLINE.match(line):
            continue
        if _RE_IMAGE.match(line) or _RE_IMAGE_LINK.match(line):
            continue
        line = _RE_EMPTY_LINK.sub("", line)
        line = _RE_INLINE_LINK.sub(r'\1', line)
        stripped = line.rstrip(" \t")
        if stripped != line:
            ws_strips += 1
        pass1.append(stripped)
    return pass1, ws_strips, tag_strips


def _normalize_paragraphs(pass1: list[str]) -> tuple[list[str], int]:
    result: list[str] = []
    para_inserts = 0
    blank_run = 0
    prev_was_body_para = False
    for line in pass1:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                result.append("")
            prev_was_body_para = False
        else:
            blank_run = 0
            is_body_para = not line.lstrip().startswith(("#", "*", "-"))
            if is_body_para and prev_was_body_para:
                if not result or result[-1].strip():
                    result.append("")
                    para_inserts += 1
            result.append(line)
            prev_was_body_para = is_body_para
    return result, para_inserts
