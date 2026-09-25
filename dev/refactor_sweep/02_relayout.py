#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import (
    DEF_TYPES,
    EXEMPT_FILES,
    FUNC_TYPES,
    IMPORT_TYPES,
    body_refs,
    definition_time_deps,
    guard_entry,
    has_future_annotations,
    invert_graph,
    late_statements,
    is_main_guard,
    list_dev_files,
    loaded_names,
    node_fingerprints,
    node_span,
    read_marker_lines,
    section_at,
    stray_comment_lines,
)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]


class RelayoutAbort(Exception):
    pass


# ORCHESTRATOR

def relayout_workflow() -> None:
    args = parse_args()
    files = select_files(args)
    outcomes = process_all(files, args.apply)
    print_outcomes(outcomes)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def select_files(args: argparse.Namespace) -> list[str]:
    if args.paths:
        return [p for p in args.paths if p not in EXEMPT_FILES]
    return [f for f in list_dev_files(PROJECT_ROOT) if f not in EXEMPT_FILES]


def process_all(files: list[str], apply: bool) -> list[tuple[str, str]]:
    return [process_file(rel, apply) for rel in files]


def process_file(rel: str, apply: bool) -> tuple[str, str]:
    path = PROJECT_ROOT / rel
    source = path.read_text(encoding="utf-8")
    try:
        new = relayout_source(source, rel)
        verify_equivalent(source, new)
    except RelayoutAbort as exc:
        return rel, f"ABORT {exc}"
    if new == source:
        return rel, "UNCHANGED"
    if apply:
        path.write_text(new, encoding="utf-8")
    return rel, "CHANGED"


def verify_equivalent(old: str, new: str) -> None:
    if node_fingerprints(old) != node_fingerprints(new):
        raise RelayoutAbort("fingerprint mismatch after relayout")


def relayout_source(source: str, rel: str) -> str:
    if "\r" in source:
        raise RelayoutAbort("carriage return in source")
    tree = ast.parse(source)
    lines = source.split("\n")
    plan = build_plan(tree, lines, rel)
    return assemble(plan)


def build_plan(tree: ast.Module, lines: list[str], rel: str) -> dict:
    body = tree.body
    spans = [node_span(n) for n in body]
    check_spans(spans, source_lines=lines)
    stray = stray_comment_lines("\n".join(lines), spans)
    if stray:
        raise RelayoutAbort(f"stray comment lines {stray[:3]}")
    guard = find_guard(body)
    infra = [n for n in body if not isinstance(n, DEF_TYPES) and not is_main_guard(n)]
    defs = collect_defs(body)
    future = has_future_annotations(tree)
    entry = resolve_entry(guard, defs, rel, "\n".join(lines))
    late = late_statements(infra, defs, future)
    early = [n for n in infra if n not in late]
    hoisted = hoist_classes(early, defs, future)
    infra_order = merge_hoisted(early, hoisted, defs, future)
    functions = [n for name, n in defs.items() if n not in hoisted and name != entry]
    order = order_functions(functions, defs, entry, future)
    return {
        "shebang": lines[0] if lines and lines[0].startswith("#!") else None,
        "lines": lines,
        "body": body,
        "infra": infra_order,
        "late": late,
        "orchestrator": defs.get(entry),
        "functions": order,
        "guard": guard,
    }


def check_spans(spans: list[tuple[int, int]], source_lines: list[str]) -> None:
    ordered = sorted(spans)
    for (s1, e1), (s2, e2) in zip(ordered, ordered[1:]):
        if s2 <= e1:
            raise RelayoutAbort(f"overlapping statements at line {s2}")


def find_guard(body: list[ast.stmt]) -> ast.If | None:
    guards = [n for n in body if is_main_guard(n)]
    if len(guards) > 1:
        raise RelayoutAbort("more than one main guard")
    if guards and body[-1] is not guards[0]:
        raise RelayoutAbort("statements after main guard")
    return guards[0] if guards else None


def collect_defs(body: list[ast.stmt]) -> dict[str, ast.AST]:
    defs: dict[str, ast.AST] = {}
    for node in body:
        if isinstance(node, DEF_TYPES):
            if node.name in defs:
                raise RelayoutAbort(f"duplicate definition {node.name}")
            defs[node.name] = node
    return defs


def resolve_entry(guard: ast.If | None, defs: dict, rel: str, source: str) -> str | None:
    if rel.startswith("dev/tests/"):
        return None
    entry = guard_entry(guard) if guard is not None else None
    if entry in defs and isinstance(defs[entry], FUNC_TYPES):
        return entry
    return existing_orchestrator(defs, source)


def existing_orchestrator(defs: dict, source: str) -> str | None:
    markers = read_marker_lines(source)
    found = [
        name for name, node in defs.items()
        if isinstance(node, FUNC_TYPES) and section_at(node_span(node)[0], markers) == "ORCHESTRATOR"
    ]
    return found[0] if len(found) == 1 else None


def hoist_classes(infra: list, defs: dict, future: bool) -> set:
    hoisted: set = set()
    for node in infra:
        for name in loaded_names([node]):
            if name in defs:
                request_hoist(defs, name, hoisted, future, node)
    return hoisted


def request_hoist(defs: dict, name: str, hoisted: set, future: bool, user: ast.AST) -> None:
    target = defs[name]
    if target in hoisted:
        return
    hoisted.add(target)
    for dep in definition_time_deps(target, set(defs), future):
        request_hoist(defs, dep, hoisted, future, target)


def merge_hoisted(infra: list, hoisted: set, defs: dict, future: bool) -> list:
    if not hoisted:
        return list(infra)
    placed: set = set()
    out: list = []
    for node in infra:
        for name in loaded_names([node]):
            if name in defs and defs[name] in hoisted:
                place_hoisted(defs[name], defs, hoisted, placed, out, future)
        out.append(node)
    return out


def place_hoisted(node: ast.AST, defs: dict, hoisted: set, placed: set, out: list, future: bool) -> None:
    if node in placed:
        return
    for dep in sorted(definition_time_deps(node, set(defs), future)):
        place_hoisted(defs[dep], defs, hoisted, placed, out, future)
    placed.add(node)
    out.append(node)


def order_functions(functions: list, defs: dict, entry: str | None, future: bool) -> list:
    names = [n.name for n in functions]
    index = {name: i for i, name in enumerate(names)}
    edges = {n.name: {c: line for c, line in body_refs(n, set(names)).items()} for n in functions}
    orch_refs = body_refs(defs[entry], set(names)) if entry else {}
    levels, dag_callers = compute_levels(names, edges)
    emitted = emit_by_level(names, index, levels, dag_callers, orch_refs, edges)
    ordered = [defs[n] for n in emitted]
    return fix_definition_time(ordered, set(defs), future)


def compute_levels(names: list[str], edges: dict) -> tuple[dict, dict]:
    index = {n: i for i, n in enumerate(names)}
    callers = invert_graph(edges)
    roots = [n for n in names if not (set(callers.get(n, {})) - {n})]
    state: dict[str, int] = {}
    dag: dict[str, list[str]] = {n: [] for n in names}
    post: list[str] = []
    for start in roots + [n for n in names if n not in roots]:
        if start not in state:
            visit(start, edges, index, state, dag, post)
    levels = {n: 0 for n in names}
    for n in reversed(post):
        for callee in dag[n]:
            levels[callee] = max(levels[callee], levels[n] + 1)
    dag_callers: dict[str, list[str]] = {n: [] for n in names}
    for n, callees in dag.items():
        for callee in callees:
            dag_callers[callee].append(n)
    return levels, dag_callers


def visit(node: str, edges: dict, index: dict, state: dict, dag: dict, post: list) -> None:
    state[node] = 1
    for callee in sorted(edges[node], key=lambda c: index[c]):
        if callee == node or state.get(callee) == 1:
            continue
        dag[node].append(callee)
        if callee not in state:
            visit(callee, edges, index, state, dag, post)
    state[node] = 2
    post.append(node)


def emit_by_level(names: list[str], index: dict, levels: dict, dag_callers: dict, orch_refs: dict, edges: dict) -> list[str]:
    position: dict[str, int] = {}
    out: list[str] = []
    for level in range(max(levels.values(), default=-1) + 1):
        members = [n for n in names if levels[n] == level]
        members.sort(key=lambda n: sort_key(n, index, dag_callers, orch_refs, position, edges))
        for n in members:
            position[n] = len(out)
            out.append(n)
    return out


def sort_key(name: str, index: dict, dag_callers: dict, orch_refs: dict, position: dict, edges: dict) -> tuple:
    candidates = [(position[c], edges[c][name]) for c in dag_callers[name] if c in position]
    if name in orch_refs:
        candidates.append((-1, orch_refs[name]))
    if candidates:
        first = min(candidates)
        return (0, first[0], first[1], index[name])
    return (1, 0, 0, index[name])


def fix_definition_time(ordered: list, defined: set, future: bool) -> list:
    by_name = {n.name: n for n in ordered}
    result = list(ordered)
    for _ in range(len(result) + 1):
        moved = False
        for pos, node in enumerate(result):
            for dep in definition_time_deps(node, defined, future):
                dep_node = by_name.get(dep)
                if dep_node is not None and result.index(dep_node) > pos:
                    result.remove(dep_node)
                    result.insert(pos, dep_node)
                    moved = True
                    break
            if moved:
                break
        if not moved:
            return result
    raise RelayoutAbort("definition-time dependency cycle")


def node_text(node: ast.AST, lines: list[str]) -> str:
    start, end = node_span(node)
    return "\n".join(lines[start - 1:end])


def infra_separator(prev: ast.AST, nxt: ast.AST, body: list) -> str:
    if isinstance(prev, DEF_TYPES) or isinstance(nxt, DEF_TYPES):
        return "\n\n\n"
    pi, ni = body.index(prev), body.index(nxt)
    if ni == pi + 1:
        gap = node_span(nxt)[0] - node_span(prev)[1] - 1
        return "\n" + "\n" * min(gap, 1)
    if isinstance(prev, IMPORT_TYPES) and isinstance(nxt, IMPORT_TYPES):
        return "\n"
    return "\n\n"


def infra_block(plan: dict, key: str) -> str:
    out = ""
    prev = None
    for node in plan[key]:
        if prev is not None:
            out += infra_separator(prev, node, plan["body"])
        out += node_text(node, plan["lines"])
        prev = node
    return out


def function_block(plan: dict) -> str:
    return "\n\n\n".join(node_text(n, plan["lines"]) for n in plan["functions"])


def assemble(plan: dict) -> str:
    sections = []
    if plan["infra"]:
        sections.append("# INFRASTRUCTURE\n" + infra_block(plan, "infra"))
    if plan["orchestrator"] is not None:
        sections.append("# ORCHESTRATOR\n\n" + node_text(plan["orchestrator"], plan["lines"]))
    if plan["functions"]:
        sections.append("# FUNCTIONS\n\n" + function_block(plan))
    if plan["late"]:
        sections.append(infra_block(plan, "late"))
    text = "\n\n\n".join(sections) + "\n"
    if plan["guard"] is not None:
        text += "\n\n" + node_text(plan["guard"], plan["lines"]) + "\n"
    if plan["shebang"]:
        text = plan["shebang"] + "\n" + text
    return text


def print_outcomes(outcomes: list[tuple[str, str]]) -> None:
    for rel, outcome in outcomes:
        if outcome != "UNCHANGED":
            print(f"{outcome}  {rel}")
    counts: dict[str, int] = {}
    for _, outcome in outcomes:
        key = outcome.split()[0]
        counts[key] = counts.get(key, 0) + 1
    print(counts)


if __name__ == "__main__":
    relayout_workflow()
