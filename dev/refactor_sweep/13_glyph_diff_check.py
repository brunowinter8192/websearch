#!/usr/bin/env python3
# INFRASTRUCTURE
import difflib
import json
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / "md" / "13_glyph_diff_check.md"
TABLE_PATH = SCRIPT_DIR / "glyph_replacements.json"
PROJECT_ROOT = SCRIPT_DIR.parents[1]
GLYPH_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0xFE0F, 0xFE0F), (0x231A, 0x231B), (0x23E9, 0x23FF), (0x2B1B, 0x2B1C))
GLYPHS = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in GLYPH_RANGES) + "]")


# ORCHESTRATOR

def glyph_diff_workflow() -> None:
    base = git("merge-base", "HEAD", "integration").strip()
    table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    glyph_files = files_with_glyphs_at_base(base)
    results = _compare_all(base, table)
    problems = table_problems(table, glyph_files)
    write_report(render_report(base, results, problems))
    print_summary(results, problems)


# FUNCTIONS

def files_with_glyphs_at_base(base: str) -> set[str]:
    out = git("ls-tree", "-r", "--name-only", base, "--", "dev")
    return {f for f in out.split("\n") if f.endswith(".py") and GLYPHS.search(git("show", f"{base}:{f}"))}


def _compare_all(base: str, table: dict) -> list[dict]:
    return [compare(base, rel, pairs) for rel, pairs in sorted(table.items())]


def table_problems(table: dict, glyph_files: set[str]) -> list[str]:
    found = [f"{f}: has glyphs at base but no table entry" for f in sorted(glyph_files - set(table))]
    found += [f"{f}: table entry for a file without glyphs at base" for f in sorted(set(table) - glyph_files)]
    return found


def render_report(base: str, results: list[dict], problems: list[str]) -> str:
    bad = [r for r in results if not r["same"]]
    lines = ["# 13_glyph_diff_check report", "", f"base: {base}", "", f"files in the replacement table: {len(results)}"]
    lines += [f"replacement pairs: {sum(r['pairs'] for r in results)}", f"files where base plus the table differs from the current file: {len(bad)}", f"table problems: {len(problems)}", ""]
    lines += ["## Differing files", ""]
    for r in bad:
        lines += [f"### {r['file']}", "```"] + r["diff"] + ["```", ""]
    lines += ["## Table problems", ""] + [f"- {p}" for p in problems] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(results: list[dict], problems: list[str]) -> None:
    bad = sum(1 for r in results if not r["same"])
    print(f"compared={len(results)} differ={bad} table_problems={len(problems)} report={REPORT_PATH}")


def compare(base: str, rel: str, pairs: list) -> dict:
    expected = apply_pairs(git("show", f"{base}:{rel}"), pairs)
    current = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    return {"file": rel, "pairs": len(pairs), "same": expected == current, "diff": diff_excerpt(expected, current)}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True)


def apply_pairs(text: str, pairs: list) -> str:
    for old, new in pairs:
        if old not in text:
            raise ValueError(f"replacement fragment not found: {old[:60]!r}")
        text = text.replace(old, new)
    return text


def diff_excerpt(expected: str, current: str) -> list[str]:
    if expected == current:
        return []
    lines = difflib.unified_diff(expected.split("\n"), current.split("\n"), "base+table", "current", n=0, lineterm="")
    return list(lines)[:12]


if __name__ == "__main__":
    glyph_diff_workflow()
