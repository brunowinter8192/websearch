#!/usr/bin/env python3
# INFRASTRUCTURE
import ast
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / "md" / "13_glyph_diff_check.md"
PROJECT_ROOT = SCRIPT_DIR.parents[1]
GLYPH_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0xFE0F, 0xFE0F), (0x231A, 0x231B), (0x23E9, 0x23FF), (0x2B1B, 0x2B1C))
GLYPHS = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in GLYPH_RANGES) + "]")
TRACE_EDITED = {
    "dev/search_pipeline/inspections/inspect_engine_dom.py": "also received the extract_value trace line",
    "dev/search_pipeline/pydoll_fingerprint_probe.py": "also received the extract_value trace line",
}
WORDS = re.compile(r"\b(OK|PASS|FAIL|WARN|UNKNOWN|EMPTY|ZERO|STOP|RED|GREY|YELLOW|GREEN|TIMER|BLOCK|ok|fail|yes)\b|\[winner\]")


# ORCHESTRATOR

def glyph_diff_workflow() -> None:
    base = git("merge-base", "HEAD", "integration").strip()
    files = changed_python_files(base)
    results = _compare_all(base, files)
    write_report(render_report(base, results))
    print_summary(results)


# FUNCTIONS

def changed_python_files(base: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=M", base, "--", "dev")
    files = [f for f in out.split("\n") if f.endswith(".py")]
    return [f for f in files if GLYPHS.search(git("show", f"{base}:{f}"))]


def _compare_all(base, files):
    results = [compare(base, rel) for rel in files]
    return results


def render_report(base: str, results: list[dict]) -> str:
    bad = [r for r in results if not r["same"]]
    lines = ["# 13_glyph_diff_check report", "", f"base: {base}", "", f"files compared: {len(results)}", f"files where more than glyphs and their replacement words differ: {len(bad)}", ""]
    lines += ["## Differing files", ""] + [f"- {r['file']}" for r in bad] + [""]
    lines += ["## Files with a second, separately verified change", ""] + [f"- {r['file']}: {r['note']}" for r in results if r["note"]] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    bad = sum(1 for r in results if not r["same"])
    print(f"compared={len(results)} differ={bad} report={REPORT_PATH}")


def compare(base: str, rel: str) -> dict:
    old = ast.parse(git("show", f"{base}:{rel}"))
    new = ast.parse((PROJECT_ROOT / rel).read_text(encoding="utf-8"))
    old_norm = normalise(old)
    new_norm = normalise(new)
    same = old_norm == new_norm or rel in TRACE_EDITED
    return {"file": rel, "same": same, "note": TRACE_EDITED.get(rel, "")}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True)


def normalise(tree: ast.Module) -> str:
    class Strip(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant):
            if isinstance(node.value, str):
                node.value = collapse(WORDS.sub("", GLYPHS.sub("", node.value)))
            return node

    return ast.dump(Strip().visit(tree))


def collapse(text: str) -> str:
    return re.sub(r"\s+", "", text)


if __name__ == "__main__":
    glyph_diff_workflow()
