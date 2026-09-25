#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import node_fingerprints

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
REPORT_PATH = SCRIPT_DIR / "md" / "03_ast_equivalence.md"


# ORCHESTRATOR

def equivalence_workflow() -> None:
    args = parse_args()
    base = resolve_base(args.base)
    files = changed_files(base)
    results = [compare_file(base, rel) for rel in files]
    write_report(render_report(base, results))
    print_summary(results)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="integration-merge-base")
    return parser.parse_args()


def resolve_base(base: str) -> str:
    if base != "integration-merge-base":
        return base
    return git("merge-base", "HEAD", "integration").strip()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True)


def changed_files(base: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=M", base, "--", "dev")
    return sorted(f for f in out.split("\n") if f.endswith(".py"))


def compare_file(base: str, rel: str) -> dict:
    old = git("show", f"{base}:{rel}")
    new = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    old_fp = node_fingerprints(old)
    new_fp = node_fingerprints(new)
    if old_fp == new_fp:
        return {"file": rel, "equal": True, "only_old": [], "only_new": []}
    only_old = sorted(set(old_fp) - set(new_fp))
    only_new = sorted(set(new_fp) - set(old_fp))
    return {"file": rel, "equal": False, "only_old": describe(old, only_old), "only_new": describe(new, only_new)}


def describe(source: str, fingerprints: list[str]) -> list[str]:
    wanted = set(fingerprints)
    names = []
    for node in ast.parse(source).body:
        if ast.dump(node) in wanted:
            names.append(getattr(node, "name", f"{type(node).__name__}@{node.lineno}"))
    return names


def render_report(base: str, results: list[dict]) -> str:
    equal = [r for r in results if r["equal"]]
    different = [r for r in results if not r["equal"]]
    lines = ["# 03_ast_equivalence report", "", f"base: {base}", ""]
    lines += [f"files compared: {len(results)}", f"top-level node multiset identical: {len(equal)}"]
    lines += [f"top-level node multiset differs: {len(different)}", ""]
    lines += ["## Files that differ", ""]
    for r in different:
        lines.append(f"### {r['file']}")
        lines.append("- only in base: " + ", ".join(r["only_old"]))
        lines.append("- only in current: " + ", ".join(r["only_new"]))
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    different = sum(1 for r in results if not r["equal"])
    print(f"compared={len(results)} differ={different} report={REPORT_PATH}")


if __name__ == "__main__":
    equivalence_workflow()
