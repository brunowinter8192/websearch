#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _extract_plan import (
    BODY_INDENT,
    block_stores,
    call_slug,
    initial_defined,
    is_method_call,
    is_print,
    plan_block,
    collect_loads,
)
from _layout_lib import (
    DEF_TYPES,
    EXEMPT_FILES,
    guard_entry,
    is_main_guard,
    list_dev_files,
    orchestrator_violations,
    resolve_entry,
)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]


# ORCHESTRATOR

def extract_workflow() -> None:
    args = parse_args()
    names = load_names(args.names)
    files = select_files(args)
    rows = collect_rows(files, names, args.apply)
    print_rows(rows, args.apply)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--names", default="")
    return parser.parse_args()


def load_names(path: str) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_files(args: argparse.Namespace) -> list[str]:
    if args.paths:
        return args.paths
    return [f for f in list_dev_files(PROJECT_ROOT) if f not in EXEMPT_FILES and not f.startswith("dev/tests/")]


def collect_rows(files: list[str], names: dict, apply: bool) -> list[str]:
    rows: list[str] = []
    for rel in files:
        rows += process_file(rel, names, apply)
    return rows


def print_rows(rows: list[str], apply: bool) -> None:
    for row in rows:
        print(row)
    print(f"rows={len(rows)} applied={apply}")


def first_called(stmts: list) -> str:
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id != "print":
                    return fn.id.strip("_")
                if isinstance(fn, ast.Attribute) and fn.attr not in ("append", "format", "join"):
                    return fn.attr.strip("_")
    return ""


def process_file(rel: str, names: dict, apply: bool) -> list[str]:
    path = PROJECT_ROOT / rel
    source = path.read_text(encoding="utf-8")
    try:
        lifted = lift_guard(source)
        new, rows = extract_source(lifted, rel, names)
    except ExtractAbort as exc:
        return [f"MANUAL {rel} :: {exc}"]
    if apply and new != source:
        path.write_text(new, encoding="utf-8")
    return rows


def lift_guard(source: str) -> str:
    tree = ast.parse(source)
    guards = [n for n in tree.body if is_main_guard(n)]
    if not guards or guard_entry(guards[0]) is not None:
        return source
    guard = guards[0]
    defs = {n.name for n in tree.body if isinstance(n, DEF_TYPES)}
    stored = {n.id for s in guard.body for n in ast.walk(s) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    leaked = stored & loaded_in_defs(tree)
    if leaked:
        raise ExtractAbort(f"guard assigns module globals used by functions: {sorted(leaked)}")
    name = "main" if "main" not in defs else "run_main"
    if name in defs:
        raise ExtractAbort("no free name for the lifted guard function")
    lines = source.split("\n")
    body = "\n".join(lines[guard.body[0].lineno - 1:guard.end_lineno])
    replacement = f"def {name}() -> None:\n{body}\n\n\nif __name__ == \"__main__\":\n    {name}()"
    return "\n".join(lines[:guard.lineno - 1] + [replacement] + lines[guard.end_lineno:])


def extract_source(source: str, rel: str, names: dict) -> tuple[str, list[str]]:
    tree = ast.parse(source)
    guards = [n for n in tree.body if is_main_guard(n)]
    defs = {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}
    entry = resolve_entry(guards[0] if guards else None, defs, rel, source)
    if entry is None:
        return source, [f"NOENTRY {rel}"]
    func = defs[entry]
    if not orchestrator_violations(func):
        return source, []
    plan = plan_block(func.body, initial_defined(func), collect_loads(func), [], func)
    return apply_plan(source, rel, func, tree, plan, names, set(defs))


def loaded_in_defs(tree: ast.Module) -> set[str]:
    found = set()
    for node in tree.body:
        if isinstance(node, DEF_TYPES):
            local = block_stores([node]) | initial_defined_all(node)
            found |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - local
    return found


def apply_plan(source: str, rel: str, func: ast.AST, tree: ast.Module, plan: list, names: dict, taken: set) -> tuple[str, list[str]]:
    lines = source.split("\n")
    rows: list[str] = []
    helpers: list[str] = []
    chosen: list[str] = []
    for index, group in enumerate(plan):
        key = f"{rel}::{func.name}::{index}"
        if group["manual"]:
            raise ExtractAbort(f"{key} lines {group['start']}-{group['end']}: {group['manual']}")
        if group.get("hoist"):
            chosen.append("")
            rows.append(f"{key} -> HOIST ({group['start']}-{group['end']}) {snippet(group, lines)}")
            continue
        name = unique_name(names.get(key) or auto_name(group, func), taken)
        taken.add(name)
        chosen.append(name)
        rows.append(f"{key} -> {name} ({group['start']}-{group['end']}) {snippet(group, lines)}")
        helpers.append(build_helper(name, group, lines))
    hoisted = [g for g in plan if g.get("hoist")]
    removed = sum(g["end"] - g["start"] + 1 for g in hoisted)
    for index in reversed(range(len(plan))):
        group = plan[index]
        if group.get("hoist"):
            lines[group["start"] - 1:group["end"]] = []
        else:
            lines[group["start"] - 1:group["end"]] = [build_call(chosen[index], group)]
    insert_at = func.end_lineno - group_line_delta(plan) - removed
    if helpers:
        lines[insert_at:insert_at] = ["", ""] + "\n\n\n".join(helpers).split("\n")
    if hoisted:
        top = last_import_line(tree)
        lines[top:top] = [ast.get_source_segment(source, g["stmts"][0]) for g in hoisted]
    return "\n".join(lines), rows


class ExtractAbort(Exception):
    pass


def initial_defined_all(node: ast.AST) -> set[str]:
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            names |= initial_defined(sub)
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            names.add(sub.id)
    return names


def snippet(group: dict, lines: list[str]) -> str:
    return lines[group["start"] - 1].strip()[:70]


def unique_name(name: str, taken: set) -> str:
    candidate, n = name, 2
    while candidate in taken:
        candidate = f"{name}_{n}"
        n += 1
    return candidate


def auto_name(group: dict, func: ast.AST) -> str:
    first = group["stmts"][0]
    if isinstance(first, (ast.Assign, ast.AnnAssign)):
        return "_compute_" + target_slug(first.targets[0] if isinstance(first, ast.Assign) else first.target)
    if isinstance(first, ast.AugAssign):
        return "_update_" + target_slug(first.target)
    if is_method_call(first, "add_argument"):
        return "_add_arguments"
    if is_print(first):
        return "_print_" + print_slug(first)
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
        return call_slug(first.value)
    if isinstance(first, ast.Import):
        return "_import_" + first.names[0].name.split(".")[0]
    if isinstance(first, ast.ImportFrom):
        return "_import_" + (first.module or "names").split(".")[0]
    return "_run_" + block_hint([first])


def build_helper(name: str, group: dict, lines: list[str]) -> str:
    keyword = "async def" if group["async"] else "def"
    body = shift_lines(lines[group["start"] - 1:group["end"]], group["col"] - BODY_INDENT)
    ret = []
    if group["returns"]:
        ret = [" " * BODY_INDENT + "return " + ", ".join(group["returns"])]
    head = f"{keyword} {name}({', '.join(group['params'])}):"
    return "\n".join([head] + body + ret)


def build_call(name: str, group: dict) -> str:
    indent = " " * group["col"]
    target = ""
    if group["returns"]:
        target = ", ".join(group["returns"]) + " = "
    awaited = "await " if group["async"] else ""
    return f"{indent}{target}{awaited}{name}({', '.join(group['params'])})"


def group_line_delta(plan: list) -> int:
    return sum((g["end"] - g["start"]) for g in plan if not g.get("hoist"))


def last_import_line(tree: ast.Module) -> int:
    ends = [n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    return max(ends) if ends else 0


def target_slug(target: ast.AST) -> str:
    names = [n.id.strip("_") for n in ast.walk(target) if isinstance(n, ast.Name)]
    return "_".join(names) if names else "value"


def print_slug(stmt: ast.stmt) -> str:
    call = stmt.value
    text = ""
    if call.args and isinstance(call.args[0], ast.JoinedStr):
        text = "".join(v.value for v in call.args[0].values if isinstance(v, ast.Constant))
    elif call.args and isinstance(call.args[0], ast.Constant):
        text = str(call.args[0].value)
    words = re.findall(r"[a-z0-9]+", text.lower())[:3]
    return "_".join(words) if words else "line"


def block_hint(stmts: list) -> str:
    for stmt in stmts:
        for node in ast.walk(stmt):
            hint = node_hint(node)
            if hint:
                return hint
    return "block"


def shift_lines(block: list[str], delta: int) -> list[str]:
    if delta <= 0:
        return block
    prefix = " " * delta
    return [line[delta:] if line.startswith(prefix) else line for line in block]


def node_hint(node: ast.AST) -> str:
    if isinstance(node, (ast.For, ast.AsyncFor)):
        it = node.iter
        while isinstance(it, ast.Call) and it.args:
            it = it.args[0]
        return it.id.strip("_") if isinstance(it, ast.Name) else ""
    if isinstance(node, (ast.With, ast.AsyncWith)):
        var = node.items[0].optional_vars
        return var.id.strip("_") if isinstance(var, ast.Name) else ""
    if isinstance(node, ast.While):
        return "iterations"
    return ""


if __name__ == "__main__":
    extract_workflow()
