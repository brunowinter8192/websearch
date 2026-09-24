# INFRASTRUCTURE
import re
from pathlib import Path

COMMENT_LINE_RE = re.compile(r"^<!--.*-->$")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
SENTENCE_END_CHARS = (".", "!", "?")


# FUNCTIONS

def is_token(word: str) -> bool:
    return any(ch.isalpha() or ch.isdigit() for ch in word)


def tokenize(text: str) -> list[str]:
    return [w for w in text.split() if is_token(w)]


def is_comment_line(line: str) -> bool:
    return bool(COMMENT_LINE_RE.match(line.strip()))


def is_heading_line(line: str) -> bool:
    return line.lstrip().startswith("#")


def contains_sentence_end(text: str) -> bool:
    return any(ch in text for ch in SENTENCE_END_CHARS)


def process_line(line: str) -> tuple[str, int]:
    no_images = IMAGE_RE.sub("", line)
    link_tokens = 0

    def _reduce_link(match: re.Match) -> str:
        nonlocal link_tokens
        link_text = match.group(1)
        link_tokens += len(tokenize(link_text))
        return link_text

    visible_text = LINK_RE.sub(_reduce_link, no_images)
    return visible_text, link_tokens


def read_blocks(path: Path) -> list[dict]:
    blocks = []
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue
            if is_comment_line(line):
                continue
            visible_text, link_tokens = process_line(line)
            num_words = len(tokenize(visible_text))
            if num_words == 0:
                continue
            blocks.append({
                "num_words": num_words,
                "link_tokens": link_tokens,
                "link_density": link_tokens / num_words,
                "char_len": len(visible_text),
                "is_heading": is_heading_line(line),
                "has_sentence_end": contains_sentence_end(visible_text),
            })
    return blocks
