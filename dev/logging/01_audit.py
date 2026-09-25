#!/usr/bin/env python3
# INFRASTRUCTURE
import ast
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SRC_DIR = ROOT / "src"
REPORT_DIR = Path(__file__).parent / "md"
LEVELS = {"debug", "info", "warning", "error", "critical"}
MSG_LIMIT = 120


# ORCHESTRATOR

def audit_workflow() -> None:
    print(f"Scanning {SRC_DIR} ...", file=sys.stderr)
    records = _scan_src(SRC_DIR)
    print(f"Found {len(records)} logger call-sites.", file=sys.stderr)
    content = _render_report(records)
    out_path = _write_report(content)
    print(out_path)


# FUNCTIONS

def _scan_src(src_dir: Path) -> list[dict]:
    all_records: list[dict] = []
    for py_file in sorted(src_dir.rglob("*.py")):
        records = _scan_file(py_file)
        all_records.extend(records)
    return all_records


def _render_report(records: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# Logger Call-Site Audit — {ts}",
        f"\nSrc tree: `{SRC_DIR.relative_to(ROOT)}/`  ",
        f"Total call-sites found: **{len(records)}**\n",
        "| file:line | logger_obj | level | message_template |",
        "|---|---|---|---|",
    ]
    for r in records:
        cell_file = f"`{r['file']}:{r['lineno']}`"
        cell_obj = f"`{r['obj']}`"
        cell_level = r["level"].upper()
        cell_msg = r["msg"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {cell_file} | {cell_obj} | {cell_level} | {cell_msg} |")
    return "\n".join(lines) + "\n"


def _write_report(content: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts_file = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = REPORT_DIR / f"01_audit_{ts_file}.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _scan_file(filepath: Path) -> list[dict]:
    src_text = filepath.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src_text, filename=str(filepath))
    return _extract_calls(tree, src_text, filepath)


def _extract_calls(tree: ast.AST, src_text: str, filepath: Path) -> list[dict]:
    results = []
    src_lines = src_text.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        method = func.attr.lower()
        if method not in LEVELS:
            continue
        obj = func.value
        if isinstance(obj, ast.Name):
            obj_name = obj.id
        elif isinstance(obj, ast.Attribute):
            obj_name = ast.unparse(obj)
        else:
            obj_name = "?"

        lineno = node.lineno
        msg_template = ""
        if node.args:
            first_arg = node.args[0]
            try:
                msg_template = ast.unparse(first_arg)
            except Exception:
                msg_template = "<unparseable>"

        if len(msg_template) > MSG_LIMIT:
            msg_template = msg_template[: MSG_LIMIT - 3] + "..."

        results.append({
            "file": str(filepath.relative_to(ROOT)),
            "lineno": lineno,
            "obj": obj_name,
            "level": method,
            "msg": msg_template,
        })

    results.sort(key=lambda r: r["lineno"])
    return results


if __name__ == "__main__":
    audit_workflow()
