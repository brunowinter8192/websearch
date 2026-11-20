# INFRASTRUCTURE
import re
import unicodedata

import pymupdf

from src.pdf.report import WorkflowError

COMMENT_OR_BREAK = re.compile(r"<br>|<!--.*?-->", re.DOTALL)
INLINE_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")
TOKEN_SEPARATOR = re.compile(r"[\s|]+")
HYPHENATED_WORD = re.compile(r"[^\W\d_]-$")
CONSUMED = "\x00"
MISSING_SAMPLE = 12
MODIFIER_LETTER = "Lm"
TEXT_REGION_KEYS = ("tables", "figures")
FORMULA_REGION_KEY = "formulas"


# FUNCTIONS
def require_coverage(document: pymupdf.Document, pages: list[dict]) -> None:
    dropped_texts = {normalized(text) for page in pages for _, text in page["dropped"]}
    for page in pages:
        if page["ocr"]:
            continue
        missing = missing_words(document[page["number"] - 1], page, dropped_texts)
        if missing:
            raise WorkflowError(
                "text_not_covered",
                f"page {page['number']}: {len(missing)} words of the PDF text layer are missing from the extracted page, "
                f"for example: {' '.join(missing[:MISSING_SAMPLE])}",
            )


def normalized(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in folded if char.isalnum() and unicodedata.category(char) != MODIFIER_LETTER)


def missing_words(source: pymupdf.Page, page: dict, dropped_texts: set[str]) -> list[str]:
    body, missing = [], []
    for word, center in layer_words(source, page, dropped_texts):
        kind, text = region_at(page, center)
        if kind is None:
            body.append(word)
        elif not region_covers(kind, text, word):
            missing.append(word)
    return missing + uncovered_body_words(body, output_tokens(page))


def layer_words(source: pymupdf.Page, page: dict, dropped_texts: set[str]) -> list[tuple[str, pymupdf.Point]]:
    dropped_rects = [pymupdf.Rect(bbox) for bbox, _ in page["dropped"]]
    lines: dict[tuple[int, int], list[tuple[str, pymupdf.Point]]] = {}
    for x0, y0, x1, y1, word, block, line, _ in source.get_text("words"):
        center = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if not any(rect.contains(center) for rect in dropped_rects):
            lines.setdefault((block, line), []).append((word, center))
    return [
        entry for words in lines.values()
        if normalized(" ".join(word for word, _ in words)) not in dropped_texts for entry in words
    ]


def region_at(page: dict, center: pymupdf.Point) -> tuple[str | None, str]:
    for key in (*TEXT_REGION_KEYS, FORMULA_REGION_KEY):
        for region in page[key]:
            if pymupdf.Rect(region["bbox"]).contains(center):
                return key, "".join(tokens_of([region["current"]]))
    return None, ""


def region_covers(kind: str, text: str, word: str) -> bool:
    if kind == FORMULA_REGION_KEY:
        return all(text.count(char) >= normalized(word).count(char) for char in set(normalized(word)))
    return normalized(word) in text


def output_tokens(page: dict) -> list[str]:
    regions = [region["current"] for key in (*TEXT_REGION_KEYS, FORMULA_REGION_KEY) for region in page[key]]
    return tokens_of([page["text"], *regions, *(heading["text"] for heading in page["headings"])])


def tokens_of(texts: list[str]) -> list[str]:
    text = INLINE_TAG.sub("", COMMENT_OR_BREAK.sub(" ", "\n".join(texts)))
    return [token for token in (normalized(raw) for raw in TOKEN_SEPARATOR.split(text)) if token]


def uncovered_body_words(words: list[str], tokens: list[str]) -> list[str]:
    used, rest = consume_exact(words, tokens)
    stream = "".join(CONSUMED if used[index] else token for index, token in enumerate(tokens))
    whole = "".join(tokens)
    missing = []
    for word in sorted(rest, key=lambda item: -len(normalized(item))):
        token = normalized(word)
        if token in stream:
            stream = stream.replace(token, CONSUMED, 1)
        elif token not in whole:
            missing.append(word)
    return missing


def consume_exact(words: list[str], tokens: list[str]) -> tuple[list[bool], list[str]]:
    positions: dict[str, list[int]] = {}
    for index, token in enumerate(tokens):
        positions.setdefault(token, []).append(index)
    used, rest, index = [False] * len(tokens), [], 0
    while index < len(words):
        token = normalized(words[index])
        joined = token + normalized(words[index + 1]) if index + 1 < len(words) and HYPHENATED_WORD.search(words[index]) else ""
        if joined and positions.get(joined):
            used[positions[joined].pop(0)] = True
            index += 2
            continue
        if token and positions.get(token):
            used[positions[token].pop(0)] = True
        elif token:
            rest.append(words[index])
        index += 1
    return used, rest
