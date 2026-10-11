# INFRASTRUCTURE
import json
from pathlib import Path

import pytest

from src.pdf.extract import extract_workflow

LINES_PER_PAGE = 20
GIB = 1024 ** 3


# FUNCTIONS
def page_lines(number: int) -> list[str]:
    return [f"Kapitel {number} Zeile {line} Kostenrechnung Deckungsbeitrag Gemeinkosten" for line in range(1, LINES_PER_PAGE + 1)]


def write_pdf(path: Path, page_texts: list[list[str]]) -> Path:
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for lines in page_texts:
        stream = content_stream(lines)
        content_id = len(objects) + 2
        page_ids.append(len(objects) + 1)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    path.write_bytes(serialize(objects))
    return path


def content_stream(lines: list[str]) -> bytes:
    if not lines:
        return b""
    body = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"]
    body += [f"({escape(line)}) Tj T*" for line in lines]
    body.append("ET")
    return "\n".join(body).encode("latin-1")


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def serialize(objects: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def numbered_pages(count: int, blank: tuple[int, ...] = ()) -> list[list[str]]:
    return [[] if number in blank else page_lines(number) for number in range(1, count + 1)]


def worker_output(first: int, last: int, dropped_lines: int = 0, blank: tuple[int, ...] = ()) -> str:
    parts = []
    for number in range(first, last + 1):
        lines = [] if number in blank else page_lines(number)
        kept = lines[:len(lines) - dropped_lines] if lines else lines
        parts.append(f"<!-- page {number} -->\n\n" + "\n".join(kept) + "\n")
    return "\n".join(parts)


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_extract(pdf: Path, batch_dir: Path, monkeypatch, available_gb: float = 20.0):
    monkeypatch.setattr("src.pdf.extract.current_available_bytes", lambda: int(available_gb * GIB))
    return extract_workflow(str(pdf), str(batch_dir))


@pytest.fixture
def conversion_log(monkeypatch, tmp_path):
    path = tmp_path / "logs" / "conversions.jsonl"
    monkeypatch.setenv("WEBSEARCH_CONVERSION_LOG_PATH", str(path))
    return path
