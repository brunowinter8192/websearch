#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import ast
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import DEF_TYPES, EXEMPT_FILES, FUNC_TYPES, is_main_guard, list_dev_files, resolve_entry, statement_violations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LITERAL_TYPES = (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set)
MAX_ROUNDS = 60


# ORCHESTRATOR

def sink_workflow() -> None:
    args = parse_args()
    files = select_files(args)
    rows = collect_rows(files, args.apply)
    print_rows(rows)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def select_files(args: argparse.Namespace) -> list[str]:
    if args.paths:
        return args.paths
    return [f for f in list_dev_files(PROJECT_ROOT) if f not in EXEMPT_FILES and not f.startswith("dev/tests/")]


def collect_rows(files: list[str], apply: bool) -> list[str]:
    rows: list[str] = []
    for rel in files:
        rows += process_file(rel, apply)
    return rows


def print_rows(rows: list[str]) -> None:
    for row in rows:
        print(row)
    print(f"rows={len(rows)}")


def process_file(rel: str, apply: bool) -> list[str]:
    path = PROJECT_ROOT / rel
    source = path.read_text(encoding="utf-8")
    rows: list[str] = []
    for _ in range(MAX_ROUNDS):
        new, row = sink_one(source, rel)
        if new is None:
            break
        rows.append(f"{rel}: {row}")
        source = new
    if rows and apply:
        path.write_text(source, encoding="utf-8")
    return rows


def sink_one(source: str, rel: str) -> tuple[str | None, str]:
    tree = ast.parse(source)
    guards = [n for n in tree.body if is_main_guard(n)]
    defs = {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}
    entry = resolve_entry(guards[0] if guards else None, defs, rel, source)
    if entry is None or entry not in defs:
        return None, ""
    for block in blocks_of(defs[entry].body):
        for index, stmt in enumerate(block):
            result = try_statement(source, tree, defs, defs[entry], block, index, stmt)
            if result is not None:
                return result
    return None, ""


def blocks_of(stmts: list) -> list[list]:
    found = [stmts]
    for stmt in stmts:
        if isinstance(stmt, ast.If):
            found += blocks_of(stmt.body) + blocks_of(stmt.orelse)
    return found


def try_statement(source: str, tree: ast.Module, defs: dict, func: ast.AST, block: list, index: int, stmt: ast.stmt):
    name = literal_target(stmt)
    if name is None:
        return None
    if name.isupper():
        return hoist_constant(source, tree, stmt, name)
    user_index = first_user(block, index, name)
    if user_index is None:
        return None
    user = block[user_index]
    if statement_violations(user):
        return move_literal(source, stmt, user, name) if user_index > index + 1 else None
    return push_into_helper(source, tree, defs, func, stmt, user, name)


def literal_target(stmt: ast.stmt) -> str | None:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        target, value = stmt.targets[0], stmt.value
    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        target, value = stmt.target, stmt.value
    else:
        return None
    return target.id if is_pure_literal(value) else None


def hoist_constant(source: str, tree: ast.Module, stmt: ast.stmt, name: str):
    if any(isinstance(n, ast.Name) and n.id == name for top in tree.body if not isinstance(top, DEF_TYPES) for n in ast.walk(top)):
        return None
    lines = source.split("\n")
    text = " ".join(lines[stmt.lineno - 1].split())
    del lines[stmt.lineno - 1:stmt.end_lineno]
    top_line = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
    lines[top_line:top_line] = ["", text]
    return "\n".join(lines), f"hoisted constant {name} to module level"


def first_user(block: list, index: int, name: str) -> int | None:
    for position in range(index + 1, len(block)):
        if uses_name(block[position], name):
            return position
    return None


def move_literal(source: str, stmt: ast.stmt, user: ast.stmt, name: str) -> tuple[str, str]:
    lines = source.split("\n")
    text = lines[stmt.lineno - 1:stmt.end_lineno]
    del lines[stmt.lineno - 1:stmt.end_lineno]
    insert_at = user.lineno - 1 - (stmt.end_lineno - stmt.lineno + 1)
    lines[insert_at:insert_at] = text
    return "\n".join(lines), f"moved {name} before its first impure user"


def push_into_helper(source: str, tree: ast.Module, defs: dict, func: ast.AST, stmt: ast.stmt, user: ast.stmt, name: str):
    call, targets = call_of(user)
    if call is None or not isinstance(call.func, ast.Name) or call.func.id not in defs:
        return None
    helper = defs[call.func.id]
    if not isinstance(helper, FUNC_TYPES) or reference_count(tree, helper.name) != 1:
        return None
    positions = [i for i, a in enumerate(call.args) if isinstance(a, ast.Name) and a.id == name]
    if len(positions) != 1 or loads_in(user, name) != 1 or call.keywords:
        return None
    if not single_trailing_return(helper) or len(helper.args.args) != len(call.args):
        return None
    needs_return = name not in targets and used_after(func, user, name)
    return rewrite_pair(source, stmt, user, call, targets, helper, positions[0], name, needs_return)


def is_pure_literal(node: ast.AST) -> bool:
    return all(isinstance(n, LITERAL_TYPES + (ast.Load,)) for n in ast.walk(node))


def uses_name(stmt: ast.stmt, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(stmt))


def call_of(stmt: ast.stmt):
    value = None
    targets: list[str] = []
    if isinstance(stmt, ast.Expr):
        value = stmt.value
    elif isinstance(stmt, ast.Assign):
        value = stmt.value
        target = stmt.targets[0]
        elements = target.elts if isinstance(target, ast.Tuple) else [target]
        if not all(isinstance(e, ast.Name) for e in elements) or len(stmt.targets) != 1:
            return None, []
        targets = [e.id for e in elements]
    if isinstance(value, ast.Await):
        value = value.value
    return (value, targets) if isinstance(value, ast.Call) else (None, [])


def reference_count(tree: ast.Module, name: str) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name)


def loads_in(stmt: ast.stmt, name: str) -> int:
    return sum(1 for n in ast.walk(stmt) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load))


def single_trailing_return(helper: ast.AST) -> bool:
    returns = [n for n in ast.walk(helper) if isinstance(n, ast.Return)]
    if not returns:
        return True
    last = helper.body[-1]
    return len(returns) == 1 and last is returns[0] and isinstance(last.value, (ast.Name, ast.Tuple))


def used_after(func: ast.AST, user: ast.stmt, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name and n.lineno > user.end_lineno for n in ast.walk(func))


def rewrite_pair(source, stmt, user, call, targets, helper, position, name, needs_return):
    param = helper.args.args[position].arg
    edits = []
    edits.append((stmt.lineno, stmt.end_lineno, []))
    edits.append(call_site_edit(user, call, targets, position, name, needs_return))
    edits += helper_edits(source, helper, stmt, param, position, needs_return)
    lines = source.split("\n")
    for start, end, text in sorted(edits, key=lambda e: e[0], reverse=True):
        lines[start - 1:end] = text
    return "\n".join(lines), f"pushed {name} into {helper.name}"


def call_site_edit(user, call, targets, position, name, needs_return):
    new_call = copy.deepcopy(call)
    del new_call.args[position]
    new_targets = targets + [name] if needs_return else targets
    value = ast.Await(value=new_call) if isinstance(user.value, ast.Await) else new_call
    if new_targets:
        left = new_targets[0] if len(new_targets) == 1 else "(" + ", ".join(new_targets) + ")"
        left = ", ".join(new_targets)
        text = f"{left} = {ast.unparse(value)}"
    else:
        text = ast.unparse(value)
    indent = " " * user.col_offset
    return (user.lineno, user.end_lineno, [indent + text])


def helper_edits(source: str, helper: ast.AST, stmt: ast.stmt, param: str, position: int, needs_return: bool) -> list:
    header_end = helper.body[0].lineno - 1
    header = copy.deepcopy(helper)
    del header.args.args[position]
    header.body = [ast.Pass()]
    header.decorator_list = []
    head_text = ast.unparse(header).split("\n")[0]
    decorators = [helper.decorator_list[0].lineno] if helper.decorator_list else []
    start = decorators[0] if decorators else helper.lineno
    init = [" " * 4 + rename_target(stmt, param)]
    edits = [(start, header_end, [head_text] + init)]
    if needs_return:
        edits += return_edits(helper, param)
    return edits


def rename_target(stmt: ast.stmt, param: str) -> str:
    clone = copy.deepcopy(stmt)
    if isinstance(clone, ast.Assign):
        clone.targets[0].id = param
    else:
        clone.target.id = param
    return ast.unparse(clone)


def return_edits(helper: ast.AST, param: str) -> list:
    last = helper.body[-1]
    if isinstance(last, ast.Return):
        values = list(last.value.elts) if isinstance(last.value, ast.Tuple) else [last.value]
        text = "return " + ", ".join([ast.unparse(v) for v in values] + [param])
        return [(last.lineno, last.end_lineno, [" " * 4 + text])]
    return [(helper.end_lineno + 1, helper.end_lineno, [" " * 4 + f"return {param}"])]


if __name__ == "__main__":
    sink_workflow()
