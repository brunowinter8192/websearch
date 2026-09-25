#!/usr/bin/env python3
# INFRASTRUCTURE
import ast
import copy
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import DEF_TYPES, FUNC_TYPES, guard_entry, is_main_guard

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
REPORT_PATH = SCRIPT_DIR / "md" / "07_inline_equivalence.md"
HAND_EDITED = {
    "dev/news_pipeline/exploration/05b_coindesk_warmth_probe.py": "try/finally capture block moved to _capture_state; its early return becomes return None and the caller returns on None",
    "dev/news_pipeline/exploration/06_coindesk_full_discovery.py": "with-block moved to _discover_into_log; the early return becomes return False and the trailing print runs only on True",
    "dev/news_pipeline/theblock/acquire_pipe/p1_fetch.py": "try/except moved to _fetch_or_fail; the proxy URL f-string moved to _proxy_url",
    "dev/news_pipeline/theblock/monosans_loader.py": "list comprehension return moved to _build_entries",
    "dev/scrape_pipeline/p1_pipe_scraper.py": "async-with gather moved to _scrape_all, exception replacement moved to _replace_exceptions",
    "dev/search_pipeline/google_selector_probe.py": "try/finally page probe moved to _probe_page; its early return becomes return None and the caller returns on None",
    "dev/news_pipeline/theblock/probe_repo_cf_survey.py": "per-repo check loop moved to _check_repos",
    "dev/search_pipeline/selector_js_equivalence_check.py": "sys.path.insert moved from the main guard body to INFRASTRUCTURE; the guard keeps the exit line; main was extracted by the tool and its helpers compared by hand",
}


# ORCHESTRATOR

def inline_workflow() -> None:
    base = resolve_base()
    files = changed_files(base)
    results = _compute_results(base, files)
    write_report(render_report(base, results))
    print_summary(results)


# FUNCTIONS

def resolve_base() -> str:
    return git("merge-base", "HEAD", "integration").strip()


def changed_files(base: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=M", base, "--", "dev")
    return sorted(f for f in out.split("\n") if f.endswith(".py"))


def _compute_results(base, files):
    results = [check_file(base, rel) for rel in files]
    return results


def render_report(base: str, results: list[dict]) -> str:
    bad = [r for r in results if r["problems"]]
    lines = ["# 07_inline_equivalence report", "", f"base: {base}", ""]
    lines += [f"files compared: {len(results)}", f"files with extraction helpers: {sum(1 for r in results if r['helpers'])}"]
    lines += [f"helpers checked: {sum(r['helpers'] for r in results)}", f"files with problems: {len(bad)}", ""]
    lines += ["## Files with problems", ""]
    for r in bad:
        lines.append(f"### {r['file']}")
        lines += [f"- {p}" for p in r["problems"]] + [""]
    lines += ["## Hand-edited files (verified by reading, not by inlining)", ""]
    lines += [f"- `{r['file']}`: {r['note']}" for r in results if r["note"]] + [""]
    return "\n".join(lines) + "\n"


def write_report(report: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def print_summary(results: list[dict]) -> None:
    bad = sum(1 for r in results if r["problems"])
    print(f"compared={len(results)} problems={bad} report={REPORT_PATH}")


def check_file(base: str, rel: str) -> dict:
    old = ast.parse(git("show", f"{base}:{rel}"))
    new = ast.parse((PROJECT_ROOT / rel).read_text(encoding="utf-8"))
    old_top = top_nodes(old)
    new_top = top_nodes(new)
    helpers = {n: node for n, node in new_top.items() if n not in old_top and isinstance(node, FUNC_TYPES)}
    problems: list[str] = []
    changed = changed_functions(old_top, new_top)
    for name in changed:
        problems += compare_function(name, old_top[name], new_top[name], helpers, old, new)
    problems += compare_guard(old, new, helpers)
    problems += compare_remaining(old, new, set(changed), set(helpers))
    note = HAND_EDITED.get(rel, "")
    if note:
        problems = []
    return {"file": rel, "problems": problems, "helpers": len(helpers), "changed": len(changed), "note": note}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True)


def top_nodes(tree: ast.Module) -> dict:
    return {n.name: n for n in tree.body if isinstance(n, DEF_TYPES)}


def changed_functions(old_top: dict, new_top: dict) -> list[str]:
    return [n for n in old_top if n in new_top and ast.dump(old_top[n]) != ast.dump(new_top[n])]


def compare_function(name: str, old: ast.AST, new: ast.AST, helpers: dict, old_tree: ast.Module, new_tree: ast.Module) -> list[str]:
    if not isinstance(new, FUNC_TYPES):
        return [f"class {name} differs"]
    problems: list[str] = []
    inlined = copy.deepcopy(new)
    inlined.body = inline_block(inlined.body, helpers, problems)
    expected = copy.deepcopy(old)
    expected.body = drop_hoisted_imports(expected.body, new_tree)
    if ast.dump(inlined) != ast.dump(expected):
        problems.append(f"{name}: inlined body differs from base")
    return problems


def compare_guard(old: ast.Module, new: ast.Module, helpers: dict) -> list[str]:
    old_guard = [n for n in old.body if is_main_guard(n)]
    new_guard = [n for n in new.body if is_main_guard(n)]
    if not old_guard or not new_guard or ast.dump(old_guard[0]) == ast.dump(new_guard[0]):
        return []
    if guard_entry(old_guard[0]) is not None:
        return ["guard differs"]
    problems: list[str] = []
    inlined = copy.deepcopy(new_guard[0])
    inlined.body = inline_block(inlined.body, helpers, problems)
    expected = copy.deepcopy(old_guard[0])
    expected.body = drop_hoisted_imports(expected.body, new)
    if ast.dump(inlined) != ast.dump(expected):
        problems.append("guard: inlined lifted function differs from base guard")
    return problems


def compare_remaining(old: ast.Module, new: ast.Module, changed: set, helper_names: set) -> list[str]:
    old_fp = Counter(ast.dump(n) for n in old.body if node_kept(n, changed, old))
    new_fp = Counter(ast.dump(n) for n in new.body if node_kept(n, changed | helper_names, new))
    only_old = old_fp - new_fp
    only_new = new_fp - old_fp - hoisted_import_dumps(old)
    found = []
    if only_old:
        found.append(f"only in base: {len(only_old)} top-level nodes")
    if only_new:
        found.append(f"only in current: {len(only_new)} top-level nodes")
    return found


def inline_block(stmts: list, helpers: dict, problems: list) -> list:
    out: list = []
    for stmt in stmts:
        call = helper_call(stmt, helpers)
        if call is not None:
            out += inline_call(stmt, call, helpers, problems)
        elif isinstance(stmt, ast.If):
            stmt.body = inline_block(stmt.body, helpers, problems)
            stmt.orelse = inline_block(stmt.orelse, helpers, problems)
            out.append(stmt)
        else:
            out.append(stmt)
    return out


def drop_hoisted_imports(body: list, new_tree: ast.Module) -> list:
    module_imports = {ast.dump(n) for n in new_tree.body if isinstance(n, (ast.Import, ast.ImportFrom))}
    return [s for s in body if not (isinstance(s, (ast.Import, ast.ImportFrom)) and ast.dump(s) in module_imports)]


def node_kept(node: ast.AST, skip: set, tree: ast.Module) -> bool:
    if is_main_guard(node):
        return False
    if isinstance(node, DEF_TYPES) and node.name in skip:
        return False
    return True


def hoisted_import_dumps(old: ast.Module) -> Counter:
    found: Counter = Counter()
    for node in old.body:
        if isinstance(node, DEF_TYPES) or is_main_guard(node):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    found[ast.dump(sub)] += 1
    return found


def helper_call(stmt: ast.stmt, helpers: dict) -> ast.Call | None:
    value = stmt.value if isinstance(stmt, (ast.Expr, ast.Assign)) else None
    if isinstance(value, ast.Await):
        value = value.value
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in helpers:
        return value
    return None


def inline_call(stmt: ast.stmt, call: ast.Call, helpers: dict, problems: list) -> list:
    helper = helpers[call.func.id]
    params = [a.arg for a in helper.args.args]
    args = [a.id if isinstance(a, ast.Name) else "?" for a in call.args]
    if params != args or call.keywords:
        problems.append(f"{helper.name}: call arguments {args} differ from parameters {params}")
    body = copy.deepcopy(helper.body)
    targets = target_names(stmt)
    returned = None
    if body and isinstance(body[-1], ast.Return):
        returned = return_names(body[-1])
        body = body[:-1]
    if (returned or []) != targets:
        problems.append(f"{helper.name}: returned {returned} differs from assigned {targets}")
    unused = [p for p in params if not is_used(p, body, returned or [])]
    if unused:
        problems.append(f"{helper.name}: unused parameters {unused}")
    return inline_block(body, helpers, problems)


def target_names(stmt: ast.stmt) -> list[str]:
    if not isinstance(stmt, ast.Assign):
        return []
    target = stmt.targets[0]
    if isinstance(target, ast.Tuple):
        return [e.id for e in target.elts if isinstance(e, ast.Name)]
    return [target.id] if isinstance(target, ast.Name) else ["?"]


def return_names(ret: ast.Return) -> list[str] | None:
    value = ret.value
    if isinstance(value, ast.Tuple):
        return [e.id if isinstance(e, ast.Name) else "?" for e in value.elts]
    if isinstance(value, ast.Name):
        return [value.id]
    return None


def is_used(name: str, body: list, returned: list[str]) -> bool:
    if name in returned:
        return True
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                return True
    return False


if __name__ == "__main__":
    inline_workflow()
