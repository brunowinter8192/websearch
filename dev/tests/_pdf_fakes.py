# INFRASTRUCTURE
import json
from pathlib import Path

import pymupdf
import pytest

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 72
LINE_HEIGHT = 14
FONT_SIZE = 11
INDENT = 9


# FUNCTIONS
def write_pdf(path: Path, pages: list[list[tuple[float, str]]], toc: list[list] | None = None) -> Path:
    document = pymupdf.open()
    for rows in pages:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        for index, (x, text) in enumerate(rows):
            page.insert_text((x, 80 + index * LINE_HEIGHT), text, fontsize=FONT_SIZE)
    if toc:
        document.set_toc(toc)
    document.save(path)
    return path


def prose_rows(first_words: str, lines: int, indented: bool) -> list[tuple[float, str]]:
    rows = [(LEFT + (INDENT if indented else 0), f"{first_words} opens this paragraph with ordinary words")]
    rows += [(LEFT, f"and line {number} continues it with more ordinary words of text") for number in range(1, lines)]
    return rows


def rows_text(rows: list[tuple[float, str]]) -> str:
    return " ".join(text for _, text in rows)


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_manifest(batch_dir: Path) -> dict:
    return json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(batch_dir: Path, manifest: dict) -> None:
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def base_manifest(pages: int, stem: str = "Book", workers: list[dict] | None = None) -> dict:
    return {
        "run_id": "run0001",
        "ts_start": "2026-11-20T10:00:00.000000Z",
        "pdf": f"/data/{stem}.pdf",
        "pdf_sha256": "a" * 64,
        "stem": stem,
        "pages": pages,
        "worker_model": "claude-haiku-5-5[1m]",
        "tables": [],
        "figures": [],
        "headings": [],
        "workers": workers or [],
    }


def page_text(number: int) -> str:
    return f"Text {number}. Kostenrechnung Deckungsbeitrag Gemeinkosten auf Seite {number}."


def book_of(pages: int) -> str:
    return "\n\n".join(f"<!-- page {number} -->\n\n{page_text(number)}" for number in range(1, pages + 1)) + "\n"


def write_book_batch(batch_dir: Path, pages: int) -> Path:
    write_manifest(batch_dir, base_manifest(pages))
    (batch_dir / "Book.md").write_text(book_of(pages), encoding="utf-8")
    return batch_dir


@pytest.fixture
def conversion_log(monkeypatch, tmp_path):
    path = tmp_path / "logs" / "conversions.jsonl"
    monkeypatch.setenv("WEBSEARCH_CONVERSION_LOG_PATH", str(path))
    return path
