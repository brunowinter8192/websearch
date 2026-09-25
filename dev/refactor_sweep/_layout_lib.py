# INFRASTRUCTURE
import ast
import io
import subprocess
import tokenize
from collections import defaultdict
from pathlib import Path

MARKERS = ("INFRASTRUCTURE", "ORCHESTRATOR", "FUNCTIONS")
DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
IMPORT_TYPES = (ast.Import, ast.ImportFrom)
EXEMPT_FILES = {
    "dev/news_pipeline/theblock/jhao104/patches/helper/validator.py": (
        "verbatim overlay of the vendored upstream helper/validator.py: copied over the upstream clone by "
        "jhao104/setup.sh, must stay diffable against upstream, and its decorator registration at definition "
        "time (ProxyValidator.addPreValidator) pins the definition order"
    ),
}


# FUNCTIONS

def list_dev_files(root: Path) -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "dev", "*.py"], cwd=root, text=True)
    files = [f for f in out.split("\n") if f.endswith(".py") and f.startswith("dev/") and "/upstream/" not in f]
    return sorted(set(files))


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    return (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def has_future_annotations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(alias.name == "annotations" for alias in node.names):
                return True
    return False


def orchestrator_violations(func: ast.AST) -> list[str]:
    found: list[str] = []
    for stmt in func.body:
        found += statement_violations(stmt)
    return found


def build_reference_graph(defs: dict[str, ast.AST]) -> dict[str, dict[str, int]]:
    names = set(defs)
    return {name: body_refs(node, names) for name, node in defs.items()}


def invert_graph(graph: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    callers: dict[str, dict[str, int]] = defaultdict(dict)
    for caller, callees in graph.items():
        for callee, line in callees.items():
            callers[callee][caller] = line
    return callers


def node_fingerprints(source: str) -> list[str]:
    tree = ast.parse(source)
    return sorted(ast.dump(node) for node in tree.body)


def stray_comment_lines(source: str, spans: list[tuple[int, int]]) -> list[int]:
    stray = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        line = tok.start[0]
        text = tok.string.strip()
        if line == 1 and text.startswith("#!"):
            continue
        if text in {f"# {m}" for m in MARKERS}:
            continue
        if not any(start <= line <= end for start, end in spans):
            stray.append(line)
    return stray


def resolve_entry(guard: ast.If | None, defs: dict, rel: str, source: str) -> str | None:
    if rel.startswith("dev/tests/"):
        return None
    entry = guard_entry(guard) if guard is not None else None
    if entry in defs and isinstance(defs[entry], FUNC_TYPES):
        return entry
    return existing_orchestrator(defs, source)


def uses_unhoistable_definition(node: ast.AST, defs: dict, future: bool) -> bool:
    for name in loaded_names([node]):
        if name not in defs:
            continue
        target = defs[name]
        if not isinstance(target, ast.ClassDef) or not class_hoistable(target, defs, future):
            return True
    return False


def statement_violations(stmt: ast.stmt) -> list[str]:
    if isinstance(stmt, ast.Expr):
        return expression_violations(stmt.value, False)
    if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
        return expression_violations(stmt.value, False) if stmt.value is not None else []
    if isinstance(stmt, ast.Return):
        return expression_violations(stmt.value, False) if stmt.value is not None else []
    if isinstance(stmt, ast.If):
        found = expression_violations(stmt.test, True)
        for child in stmt.body + stmt.orelse:
            found += statement_violations(child)
        return found
    if isinstance(stmt, ast.Pass):
        return []
    if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call):
        return expression_violations(stmt.exc, False)
    return [type(stmt).__name__]


def body_refs(node: ast.AST, defined: set[str]) -> dict[str, int]:
    names = loaded_names([node])
    return {n: line for n, line in names.items() if n in defined and n != getattr(node, "name", None)}


def guard_entry(guard: ast.If) -> str | None:
    if len(guard.body) != 1:
        return None
    stmt = guard.body[0]
    if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call):
        call = stmt.exc
    elif isinstance(stmt, ast.Expr):
        call = stmt.value
    else:
        return None
    while isinstance(call, ast.Call):
        if isinstance(call.func, ast.Name) and call.func.id not in ("exit", "SystemExit"):
            return call.func.id
        if isinstance(call.func, ast.Attribute) and call.func.attr in ("run", "exit") and call.args:
            call = call.args[0]
            continue
        if isinstance(call.func, ast.Name) and call.args:
            call = call.args[0]
            continue
        return None
    return None


def existing_orchestrator(defs: dict, source: str) -> str | None:
    markers = read_marker_lines(source)
    found = [
        name for name, node in defs.items()
        if isinstance(node, FUNC_TYPES) and section_at(node_span(node)[0], markers) == "ORCHESTRATOR"
    ]
    return found[0] if len(found) == 1 else None


def class_hoistable(cls: ast.ClassDef, defs: dict, future: bool) -> bool:
    for dep in definition_time_deps(cls, set(defs), future):
        target = defs[dep]
        if not isinstance(target, ast.ClassDef) or not class_hoistable(target, defs, future):
            return False
    return True


def expression_violations(expr: ast.AST, condition: bool) -> list[str]:
    if isinstance(expr, (ast.Name, ast.Constant)):
        return []
    if isinstance(expr, ast.Call):
        found = expression_violations(expr.func, False)
        for arg in expr.args:
            found += expression_violations(arg, False)
        for kw in expr.keywords:
            found += expression_violations(kw.value, False)
        return found
    if isinstance(expr, (ast.Await, ast.Starred, ast.Attribute)):
        return expression_violations(expr.value, False)
    if isinstance(expr, ast.Subscript):
        return expression_violations(expr.value, False) + expression_violations(expr.slice, False)
    if isinstance(expr, (ast.Tuple, ast.List, ast.Set)):
        return [v for e in expr.elts for v in expression_violations(e, False)]
    if isinstance(expr, ast.Dict):
        parts = [k for k in expr.keys if k is not None] + list(expr.values)
        return [v for e in parts for v in expression_violations(e, False)]
    if condition:
        return condition_violations(expr)
    return [type(expr).__name__]


def read_marker_lines(source: str) -> list[tuple[int, str]]:
    found = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            name = tok.string.lstrip("# ").strip()
            if name in MARKERS and tok.string.strip() == f"# {name}":
                found.append((tok.start[0], name))
    return found


def section_at(lineno: int, markers: list[tuple[int, str]]) -> str | None:
    current = None
    for line, name in markers:
        if line < lineno:
            current = name
    return current


def node_span(node: ast.AST) -> tuple[int, int]:
    start = node.lineno
    for deco in getattr(node, "decorator_list", []):
        start = min(start, deco.lineno)
    return start, node.end_lineno


def definition_time_deps(node: ast.AST, defined: set[str], future_annotations: bool) -> set[str]:
    names = loaded_names(definition_time_parts(node, future_annotations))
    return {n for n in names if n in defined and n != getattr(node, "name", None)}


def loaded_names(nodes: list[ast.AST]) -> dict[str, int]:
    found: dict[str, int] = {}
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                found[sub.id] = min(found.get(sub.id, sub.lineno), sub.lineno)
    return found


def condition_violations(expr: ast.AST) -> list[str]:
    if isinstance(expr, ast.Compare):
        parts = [expr.left] + list(expr.comparators)
    elif isinstance(expr, ast.BoolOp):
        parts = list(expr.values)
    elif isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
        parts = [expr.operand]
    else:
        return [type(expr).__name__]
    return [v for e in parts for v in expression_violations(e, True)]


def definition_time_parts(node: ast.AST, future_annotations: bool) -> list[ast.AST]:
    if isinstance(node, FUNC_TYPES):
        return function_head_parts(node, future_annotations)
    parts = list(node.decorator_list) + list(node.bases) + [k.value for k in node.keywords]
    for stmt in node.body:
        if isinstance(stmt, FUNC_TYPES):
            parts += function_head_parts(stmt, future_annotations)
        else:
            parts.append(stmt)
    return parts


def function_head_parts(func: ast.AST, future_annotations: bool) -> list[ast.AST]:
    parts = list(func.decorator_list)
    args = func.args
    parts += list(args.defaults) + [d for d in args.kw_defaults if d is not None]
    if not future_annotations:
        every = args.posonlyargs + args.args + args.kwonlyargs + [a for a in (args.vararg, args.kwarg) if a]
        parts += [a.annotation for a in every if a.annotation is not None]
        if func.returns is not None:
            parts.append(func.returns)
    return parts
