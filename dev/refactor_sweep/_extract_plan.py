# INFRASTRUCTURE
import ast
import sys

from _layout_lib import expression_violations, statement_violations

BODY_INDENT = 4
SCOPE_TYPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
ASYNC_TYPES = (ast.Await, ast.AsyncFor, ast.AsyncWith)
FLOW_TYPES = (ast.Return, ast.Yield, ast.YieldFrom, ast.Global, ast.Nonlocal, ast.Delete)


# FUNCTIONS

def collect_loads(func: ast.AST) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    visit_loads(func, frozenset(), found)
    return found


def plan_block(stmts: list, defined_in: set, loads: dict, out: list, func: ast.AST) -> list:
    defined = set(defined_in)
    run: list = []
    snapshot: set = set()
    for stmt in stmts:
        if is_stdlib_import(stmt):
            close_run(run, snapshot, loads, out, func)
            run = []
            out.append(hoist_group(stmt))
        elif not statement_violations(stmt):
            close_run(run, snapshot, loads, out, func)
            run = []
            defined |= block_stores([stmt])
        elif isinstance(stmt, ast.If) and not expression_violations(stmt.test, True):
            close_run(run, snapshot, loads, out, func)
            run = []
            plan_block(stmt.body, defined, loads, out, func)
            plan_block(stmt.orelse, defined, loads, out, func)
            defined |= block_stores([stmt])
        else:
            if run and merge_key(run[-1]) is not None and merge_key(run[-1]) == merge_key(stmt):
                run.append(stmt)
            else:
                close_run(run, snapshot, loads, out, func)
                snapshot = set(defined)
                run = [stmt]
            defined |= block_stores([stmt])
    close_run(run, snapshot, loads, out, func)
    return out


def is_method_call(stmt: ast.stmt, attr: str) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == attr


def is_stdlib_import(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Import):
        return all(a.name.split(".")[0] in sys.stdlib_module_names for a in stmt.names)
    if isinstance(stmt, ast.ImportFrom):
        return stmt.level == 0 and (stmt.module or "").split(".")[0] in sys.stdlib_module_names
    return False


def close_run(run: list, snapshot: set, loads: dict, out: list, func: ast.AST) -> None:
    if run:
        out.append(make_group(run, snapshot, loads, func))


def hoist_group(stmt: ast.stmt) -> dict:
    return {"hoist": True, "stmts": [stmt], "start": stmt.lineno, "end": stmt.end_lineno, "col": stmt.col_offset, "manual": None}


def merge_key(stmt: ast.stmt) -> tuple | None:
    if is_print(stmt):
        return ("print",)
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return ("call", call_slug(stmt.value))
    return None


def make_group(run: list, snapshot: set, loads: dict, func: ast.AST) -> dict:
    start, end = run[0].lineno, run[-1].end_lineno
    stores = block_stores(run)
    used_after = {n for n in stores if any(line > end for line in loads.get(n, []))}
    read = names_loaded(run)
    params = sorted((n for n in (read | used_after) if n in snapshot), key=lambda n: first_line(n, run))
    returns = sorted(used_after, key=lambda n: first_line(n, run))
    return {
        "stmts": run,
        "start": start,
        "end": end,
        "col": run[0].col_offset,
        "async": any_async(run),
        "params": params,
        "returns": returns,
        "snapshot": snapshot,
        "manual": manual_reason(run, returns, snapshot, func),
    }


def is_print(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "print"


def call_slug(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Attribute):
        base = fn.value.id.strip("_") if isinstance(fn.value, ast.Name) else ""
        return f"_{fn.attr.strip('_')}_{base}" if base else f"_{fn.attr.strip('_')}"
    if isinstance(fn, ast.Name):
        return f"_run_{fn.id.strip('_')}"
    return "_run_call"


def names_loaded(stmts: list) -> set[str]:
    found: dict[str, list[int]] = {}
    for stmt in stmts:
        visit_loads(stmt, frozenset(), found)
    return set(found)


def first_line(name: str, stmts: list) -> tuple:
    hits = [(n.lineno, n.col_offset) for s in stmts for n in ast.walk(s) if isinstance(n, ast.Name) and n.id == name]
    return min(hits) if hits else (10 ** 9, 0)


def manual_reason(run: list, returns: list, snapshot: set, func: ast.AST) -> str | None:
    for stmt in run:
        if contains_type(stmt, FLOW_TYPES):
            return "return, yield, global, nonlocal or del inside the block"
        if loose_loop_control(stmt, 0):
            return "break or continue leaves the block"
    if any_async(run) and not isinstance(func, ast.AsyncFunctionDef):
        return "async block in a sync function"
    for name in returns:
        if name not in snapshot and not directly_stored(run, name):
            return f"returned name {name} is only conditionally bound"
    if run[0].col_offset != BODY_INDENT and has_multiline_string(run):
        return "multi-line string in a block that needs re-indentation"
    return None


def visit_loads(node: ast.AST, shadow: frozenset, found: dict) -> None:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in shadow:
        found.setdefault(node.id, []).append(node.lineno)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        visit_for(node, shadow, found)
        return
    inner = shadow | scope_bindings(node)
    for child in ast.iter_child_nodes(node):
        visit_loads(child, inner, found)


def any_async(stmts: list) -> bool:
    return any(contains_type(s, ASYNC_TYPES) for s in stmts)


def loose_loop_control(node: ast.AST, depth: int) -> bool:
    if isinstance(node, (ast.Break, ast.Continue)):
        return depth == 0
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return False
    inner = depth + 1 if isinstance(node, (ast.For, ast.AsyncFor, ast.While)) else depth
    return any(loose_loop_control(c, inner) for c in ast.iter_child_nodes(node))


def directly_stored(run: list, name: str) -> bool:
    return any(definitely_binds(stmt, name) for stmt in run)


def has_multiline_string(run: list) -> bool:
    for stmt in run:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.Constant, ast.JoinedStr)) and node.lineno != node.end_lineno:
                if not isinstance(node, ast.Constant) or isinstance(node.value, (str, bytes)):
                    return True
    return False


def contains_type(node: ast.AST, types: tuple) -> bool:
    if isinstance(node, types):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
        return False
    return any(contains_type(c, types) for c in ast.iter_child_nodes(node))


def visit_for(node: ast.AST, shadow: frozenset, found: dict) -> None:
    bound = frozenset(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
    visit_loads(node.iter, shadow, found)
    for child in node.body + node.orelse:
        visit_loads(child, shadow | bound, found)


def scope_bindings(node: ast.AST) -> frozenset:
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return frozenset(n.id for g in node.generators for n in ast.walk(g.target) if isinstance(n, ast.Name))
    if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
        return frozenset(initial_defined(node))
    return frozenset()


def definitely_binds(stmt: ast.stmt, name: str) -> bool:
    if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return name in block_stores([stmt])
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        targets = {n.id for item in stmt.items if item.optional_vars for n in ast.walk(item.optional_vars) if isinstance(n, ast.Name)}
        return name in targets or any(definitely_binds(s, name) for s in stmt.body)
    if isinstance(stmt, ast.Try):
        if stmt.handlers:
            return any(definitely_binds(s, name) for s in stmt.finalbody)
        return any(definitely_binds(s, name) for s in stmt.body + stmt.finalbody)
    if isinstance(stmt, ast.If):
        return any(definitely_binds(s, name) for s in stmt.body) and any(definitely_binds(s, name) for s in stmt.orelse)
    return False


def block_stores(stmts: list) -> set[str]:
    found: set[str] = set()
    for stmt in stmts:
        walk_stores(stmt, found)
    return found


def initial_defined(func: ast.AST) -> set[str]:
    args = func.args
    every = args.posonlyargs + args.args + args.kwonlyargs + [a for a in (args.vararg, args.kwarg) if a]
    return {a.arg for a in every}


def walk_stores(node: ast.AST, found: set) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        found.add(node.name)
        return
    if isinstance(node, SCOPE_TYPES):
        return
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        found.add(node.id)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        found |= {(a.asname or a.name).split(".")[0] for a in node.names}
    for child in ast.iter_child_nodes(node):
        walk_stores(child, found)
