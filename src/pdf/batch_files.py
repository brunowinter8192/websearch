# INFRASTRUCTURE
import json
import re
from pathlib import Path

from src.pdf.report import WorkflowError

PAGES_DIR = "pages"
PAGE_PNG_DIR = "page_png"
TABLES_DIR = "tables"
FIGURES_DIR = "figures"
FORMULAS_DIR = "formulas"
HEADINGS_FILE = "headings.json"
HEADINGS_FIXED_FILE = "headings_fixed.json"
BOOKMARKS_FILE = "bookmarks.json"
KIND_TABLE = "TABLE"
KIND_FIGURE = "FIGURE"
KIND_FORMULA = "FORMULA"
KIND_HEADING = "HEADING"
WORKER_OUTLINE = "outline"
BARE_PAGE_NUMBER = re.compile(r"\[?(\d+|[ivxlcdm]+)\]?", re.IGNORECASE)
PLACEHOLDER = re.compile(r"^<!-- (TABLE|FIGURE|FORMULA|HEADING) (\S+) -->$", re.MULTILINE)


# FUNCTIONS
def page_md(number: int | str) -> str:
    return f"{PAGES_DIR}/p{number}.md"


def outlined_md(number: int | str) -> str:
    return f"{PAGES_DIR}/p{number}_outlined.md"


def fixed_page_md(number: int | str) -> str:
    return f"{PAGES_DIR}/p{number}_fixed.md"


def page_png(number: int | str) -> str:
    return f"{PAGE_PNG_DIR}/p{number}.png"


def region_dir(kind: str) -> str:
    return {KIND_TABLE: TABLES_DIR, KIND_FIGURE: FIGURES_DIR, KIND_FORMULA: FORMULAS_DIR}[kind]


def region_png(kind: str, region_id: str) -> str:
    return f"{region_dir(kind)}/{region_id}.png"


def region_current(kind: str, region_id: str) -> str:
    return f"{region_dir(kind)}/{region_id}_current.md"


def region_fixed(kind: str, region_id: str) -> str:
    return f"{region_dir(kind)}/{region_id}_fixed.md"


def region_missing(kind: str, region_id: str) -> str:
    return f"{region_dir(kind)}/{region_id}_missing.txt"


def placeholder(kind: str, region_id: str) -> str:
    return f"<!-- {kind} {region_id} -->"


def placeholders(text: str) -> list[tuple[str, str]]:
    return [(match[1], match[2]) for match in PLACEHOLDER.finditer(text)]


def read_json(batch_dir: Path, name: str):
    path = batch_dir / name
    if not path.is_file():
        raise WorkflowError("file_missing", f"{path} does not exist")
    return json.loads(path.read_text(encoding="utf-8"))
