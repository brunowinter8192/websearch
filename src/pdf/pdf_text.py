# INFRASTRUCTURE
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from src.pdf.report import WorkflowError

PAGES_LINE = re.compile(r"^Pages:\s+(\d+)\s*$", re.MULTILINE)
MAX_LATIN_CODEPOINT = 0x250


# FUNCTIONS
def pdf_page_count(pdf: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, check=True)
    match = PAGES_LINE.search(result.stdout.decode("utf-8", errors="replace"))
    if match is None:
        raise WorkflowError("unreadable_pdf", f"pdfinfo reports no page count for {pdf}")
    return int(match.group(1))


def pdftotext_range(pdf: Path, first_page: int, last_page: int) -> str:
    command = ["pdftotext", "-f", str(first_page), "-l", str(last_page), str(pdf), "-"]
    result = subprocess.run(command, capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="replace")


def latin_char_counts(text: str) -> Counter:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return Counter(ch for ch in normalized if ch.isalnum() and ord(ch) < MAX_LATIN_CODEPOINT)
