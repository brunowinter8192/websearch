# INFRASTRUCTURE
import json
from pathlib import Path

from src.config import MANIFEST_FILE_NAME
from src.pdf.report import WorkflowError


# FUNCTIONS
def load_manifest(batch_dir: Path) -> dict:
    path = batch_dir / MANIFEST_FILE_NAME
    if not path.is_file():
        raise WorkflowError("manifest_missing", f"no {MANIFEST_FILE_NAME} in {batch_dir}, run split first")
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(batch_dir: Path, manifest: dict) -> None:
    (batch_dir / MANIFEST_FILE_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def book_path(batch_dir: Path, manifest: dict) -> Path:
    return batch_dir / f"{manifest['stem']}.md"
