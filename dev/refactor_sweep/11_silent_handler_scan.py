#!/usr/bin/env python3
# INFRASTRUCTURE
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import EXEMPT_FILES, list_dev_files

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / "md" / "11_silent_handler_scan.md"
PROJECT_ROOT = SCRIPT_DIR.parents[1]
INTENDED_TYPES = {
    "asyncio.CancelledError": "task cancellation during cleanup",
    "asyncio.TimeoutError": "expected wait timeout as control flow",
    "asyncio.QueueEmpty": "queue drain loop end",
    "psutil.NoSuchProcess": "process exited between listing and access (race)",
    "psutil.AccessDenied": "process of another user (race)",
    "psutil.ZombieProcess": "process exited (race)",
    "psutil.Error": "process exited (race)",
}
INTENDED_FILES = {
    "dev/brave_return/verify_brave_pydoll_core.py": "verification script: the tripwire under test raising is the expected outcome and is reported through check()",
    "dev/mojeek_return/verify_mojeek_pydoll_core.py": "verification script: the tripwire under test raising is the expected outcome and is reported through check()",
}


# ORCHESTRATOR

def silent_scan_workflow() -> None:
    files = list_dev_files(PROJECT_ROOT)
    findings, intended = collect(files)
    write_report(render_report(findings, intended))
    print_summary(findings, intended)


# FUNCTIONS

def collect(files: list[str]) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    intended: list[str] = []
    for rel in files:
        if rel in EXEMPT_FILES:
            continue
        f, i = scan_file(rel)
        findings += f
        intended += i
    return findings, intended


def render_report(findings: list[str], intended: list[str]) -> str:
    lines = ["# 11_silent_handler_scan report", "", f"silent handlers without a trace: {len(findings)}", f"silent handlers left as intended: {len(intended)}", ""]
    lines += ["## Findings", ""] + [f"- {f}" for f in findings] + [""]
    lines += ["## Intended (exception type is the expected control flow)", ""] + [f"- {i}" for i in intended] + [""]
    lines += ["## Exempt files", ""] + [f"- `{f}`: {why}" for f, why in EXEMPT_FILES.items()] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(findings: list[str], intended: list[str]) -> None:
    print(f"findings={len(findings)} intended={len(intended)} report={REPORT_PATH}")


def scan_file(rel: str) -> tuple[list[str], list[str]]:
    tree = ast.parse((PROJECT_ROOT / rel).read_text(encoding="utf-8"))
    findings: list[str] = []
    intended: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and is_silent(node):
            classify(rel, node, findings, intended)
    return findings, intended


def is_silent(node: ast.ExceptHandler) -> bool:
    return all(is_trace_free(stmt) for stmt in node.body)


def classify(rel: str, node: ast.ExceptHandler, findings: list, intended: list) -> None:
    names = handler_names(node)
    label = f"{rel}:{node.lineno} except {','.join(names) or 'bare'}"
    if rel in INTENDED_FILES:
        intended.append(f"{label} ({INTENDED_FILES[rel]})")
        return
    if names and all(n in INTENDED_TYPES for n in names):
        intended.append(f"{label} ({INTENDED_TYPES[names[0]]})")
    else:
        findings.append(label)


def is_trace_free(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
        return True
    if isinstance(stmt, ast.Return):
        return stmt.value is None or is_constant_value(stmt.value)
    if isinstance(stmt, ast.Assign):
        return all(isinstance(t, ast.Name) for t in stmt.targets) and is_constant_value(stmt.value)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return ast.unparse(stmt.value.func).endswith("sleep")
    return False


def handler_names(node: ast.ExceptHandler) -> list[str]:
    if node.type is None:
        return []
    parts = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
    return [ast.unparse(p) for p in parts]


def is_constant_value(value: ast.AST) -> bool:
    if isinstance(value, ast.Constant):
        return True
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return all(isinstance(e, ast.Constant) for e in value.elts)
    return isinstance(value, ast.Dict) and not value.keys


if __name__ == "__main__":
    silent_scan_workflow()
