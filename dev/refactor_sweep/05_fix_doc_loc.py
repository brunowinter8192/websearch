#!/usr/bin/env python3
# INFRASTRUCTURE
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEADING = re.compile(r"### (\S+\.(?:py|sh)) \(\d+ LOC\)")


# ORCHESTRATOR

def fix_workflow() -> None:
    docs = list_docs()
    changed = [fix_doc(doc) for doc in docs]
    print(f"docs={len(docs)} rewritten={sum(changed)}")


# FUNCTIONS

def list_docs() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "dev", "*DOCS.md"], cwd=PROJECT_ROOT, text=True)
    return [PROJECT_ROOT / f for f in out.split("\n") if f.endswith("DOCS.md") and f.startswith("dev/")]


def fix_doc(doc: Path) -> int:
    text = doc.read_text(encoding="utf-8")
    new = HEADING.sub(lambda m: heading_with_loc(doc.parent, m), text)
    if new == text:
        return 0
    doc.write_text(new, encoding="utf-8")
    return 1


def heading_with_loc(directory: Path, match: re.Match) -> str:
    target = directory / match.group(1)
    if not target.exists():
        return match.group(0)
    return f"### {match.group(1)} ({target.read_text(encoding='utf-8').count(chr(10))} LOC)"


if __name__ == "__main__":
    fix_workflow()
