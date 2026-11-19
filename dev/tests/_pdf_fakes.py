# INFRASTRUCTURE
import json
from pathlib import Path

import pytest

LINES_PER_PAGE = 20


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
    body = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"] + [f"({escape(line)}) Tj T*" for line in lines] + ["ET"]
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


def worker_output(first: int, last: int) -> str:
    return "\n".join(f"<!-- page {number} -->\n\n" + "\n".join(page_lines(number)) + "\n" for number in range(first, last + 1))


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_manifest(batch_dir: Path) -> dict:
    return json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))


def write_pieces(batch_dir: Path) -> None:
    for piece in read_manifest(batch_dir)["pieces"]:
        (batch_dir / piece["output"]).write_text(worker_output(piece["from"], piece["to"]), encoding="utf-8")


@pytest.fixture
def conversion_log(monkeypatch, tmp_path):
    path = tmp_path / "logs" / "conversions.jsonl"
    monkeypatch.setenv("WEBSEARCH_CONVERSION_LOG_PATH", str(path))
    return path
