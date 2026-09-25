#!/usr/bin/env python3
# INFRASTRUCTURE
import ast
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import (
    DEF_TYPES,
    EXEMPT_FILES,
    FUNC_TYPES,
    MARKERS,
    build_reference_graph,
    definition_time_deps,
    guard_entry,
    has_future_annotations,
    invert_graph,
    late_statements,
    is_main_guard,
    list_dev_files,
    node_span,
    orchestrator_violations,
    read_marker_lines,
    section_at,
)

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / "md" / "01_layout_scan.md"
PROJECT_ROOT = SCRIPT_DIR.parents[1]


# ORCHESTRATOR

def scan_workflow() -> None:
    files = list_dev_files(PROJECT_ROOT)
    results = _analyse_all(files)
    report = render_report(results)
    write_report(report)
    print_summary(results)


# FUNCTIONS

def _analyse_all(files):
    results = [analyse_file(PROJECT_ROOT, rel) for rel in files]
    return results


def render_report(results: list[dict]) -> str:
    total = Counter()
    for r in results:
        for f in r["findings"]:
            total[f.split()[0]] += 1
    dirty = [r for r in results if r["findings"]]
    kinds = Counter(r["kind"] for r in results)
    lines = ["# 01_layout_scan report", ""]
    lines += [f"files scanned: {len(results)} ({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))})"]
    lines += [f"files with findings: {len(dirty)}", f"findings total: {sum(total.values())}", ""]
    lines += ["## Findings by code", ""] + [f"- {code}: {n}" for code, n in sorted(total.items())] + [""]
    lines += ["## Exempt files", ""]
    lines += [f"- `{r['file']}`: {r['reason']}" for r in results if r["kind"] == "EXEMPT"] + [""]
    lines += ["## Files", ""]
    for r in dirty:
        lines.append(f"### {r['file']} ({r['kind']})")
        lines += [f"- {f}" for f in r["findings"]] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    dirty = sum(1 for r in results if r["findings"])
    print(f"scanned={len(results)} files_with_findings={dirty} report={REPORT_PATH}")


def analyse_file(root: Path, rel: str) -> dict:
    if rel in EXEMPT_FILES:
        return {"file": rel, "kind": "EXEMPT", "findings": [], "reason": EXEMPT_FILES[rel]}
    source = (root / rel).read_text(encoding="utf-8")
    tree = ast.parse(source)
    markers = read_marker_lines(source)
    kind = classify_kind(rel, tree)
    findings = []
    findings += marker_order_findings(markers)
    findings += placement_findings(tree, markers)
    findings += entry_findings(tree, markers, kind)
    findings += stepdown_findings(tree, markers)
    return {"file": rel, "kind": kind, "findings": findings, "reason": ""}


def classify_kind(rel: str, tree: ast.Module) -> str:
    if rel.startswith("dev/tests/"):
        return "TEST"
    if any(is_main_guard(n) for n in tree.body):
        return "SCRIPT"
    return "LIB"


def marker_order_findings(markers: list[tuple[int, str]]) -> list[str]:
    names = [name for _, name in markers]
    found = []
    for name in MARKERS:
        if names.count(name) > 1:
            found.append(f"MARKER_DUPLICATE {name}")
    ranks = [MARKERS.index(n) for n in names]
    if ranks != sorted(ranks):
        found.append("MARKER_ORDER " + ",".join(names))
    return found


def placement_findings(tree: ast.Module, markers: list[tuple[int, str]]) -> list[str]:
    found = []
    defs = {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}
    infra = [n for n in tree.body if not isinstance(n, DEF_TYPES) and not is_main_guard(n)]
    late = late_statements(infra, defs, has_future_annotations(tree))
    for node in tree.body:
        if is_main_guard(node) or node in late:
            continue
        section = section_at(node_span(node)[0], markers)
        if isinstance(node, FUNC_TYPES):
            if section is None:
                found.append(f"NO_MARKER_FOR_DEF {node.name}")
            elif section == "INFRASTRUCTURE":
                found.append(f"FUNC_IN_INFRASTRUCTURE {node.name}")
        elif isinstance(node, ast.ClassDef):
            if section is None:
                found.append(f"NO_MARKER_FOR_DEF {node.name}")
        elif section != "INFRASTRUCTURE":
            found.append(f"STATEMENT_OUTSIDE_INFRASTRUCTURE line {node.lineno} section {section}")
    return found


def entry_findings(tree: ast.Module, markers: list[tuple[int, str]], kind: str) -> list[str]:
    defs = {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}
    orchestrators = [
        n for n in tree.body
        if isinstance(n, FUNC_TYPES) and section_at(node_span(n)[0], markers) == "ORCHESTRATOR"
    ]
    if kind == "TEST":
        return [f"ORCHESTRATOR_IN_TEST {n.name}" for n in orchestrators]
    if kind == "LIB":
        return orchestrator_shape_findings(orchestrators)
    return script_entry_findings(tree, defs, orchestrators)


def stepdown_findings(tree: ast.Module, markers: list[tuple[int, str]]) -> list[str]:
    defs = {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}
    order = {name: i for i, name in enumerate(defs)}
    graph = build_reference_graph(defs)
    callers = invert_graph(graph)
    future = has_future_annotations(tree)
    found = []
    for name, node in defs.items():
        users = set(callers.get(name, {}))
        if not users:
            continue
        if all(order[u] > order[name] for u in users):
            if is_pinned_by_definition_time(name, users, defs, future):
                continue
            found.append(f"STEPDOWN {name} defined above all callers {sorted(users)}")
    return found


def script_entry_findings(tree: ast.Module, defs: dict, orchestrators: list) -> list[str]:
    guard = [n for n in tree.body if is_main_guard(n)][0]
    entry = guard_entry(guard)
    if entry is None:
        return ["GUARD_LOGIC"]
    found = []
    if entry not in defs:
        return [f"GUARD_ENTRY_UNRESOLVED {entry}"]
    if defs[entry] not in orchestrators:
        found.append(f"ENTRY_NOT_ORCHESTRATOR {entry}")
    return found + orchestrator_shape_findings(orchestrators)


def is_pinned_by_definition_time(name: str, users: set, defs: dict, future: bool) -> bool:
    names = set(defs)
    return any(name in definition_time_deps(defs[u], names, future) for u in users)


def orchestrator_shape_findings(orchestrators: list) -> list[str]:
    found = []
    if len(orchestrators) > 1:
        found.append("ORCHESTRATOR_COUNT " + ",".join(n.name for n in orchestrators))
    for node in orchestrators:
        kinds = sorted(set(orchestrator_violations(node)))
        if kinds:
            found.append(f"ORCHESTRATOR_LOGIC {node.name} {','.join(kinds)}")
    return found


if __name__ == "__main__":
    scan_workflow()
