#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _layout_lib import EXEMPT_FILES, list_dev_files

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKERS = 16
TIMEOUT_S = 90
CHILD_FLAG = "--child"
SIMPLE = (str, int, float, bool, bytes, type(None))


# ORCHESTRATOR

def snapshot_workflow() -> None:
    args = parse_args()
    if args.child:
        run_child(Path(args.tree), args.child)
        return
    tree = Path(args.tree).resolve()
    files = _compute_files(tree)
    snapshots = collect_snapshots(tree, files)
    write_snapshots(Path(args.out), snapshots)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--child", default="")
    return parser.parse_args()


def run_child(tree: Path, rel: str) -> None:
    path = tree / rel
    sys.path.insert(0, str(tree))
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("snapshot_target", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        print(json.dumps({"status": "RAISED", "type": type(exc).__name__}))
        return
    print(json.dumps({"status": "OK", "names": snapshot_names(vars(module), str(tree))}, sort_keys=True))


def _compute_files(tree):
    files = [f for f in list_dev_files(PROJECT_ROOT) if (tree / f).exists()]
    return files


def collect_snapshots(tree: Path, files: list[str]) -> dict:
    targets = [f for f in files if f not in EXEMPT_FILES]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(lambda rel: run_parent(tree, rel), targets))
    return dict(zip(targets, results))


def write_snapshots(out: Path, snapshots: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshots, indent=1, sort_keys=True), encoding="utf-8")
    statuses = {}
    for snap in snapshots.values():
        statuses[snap["status"]] = statuses.get(snap["status"], 0) + 1
    print(statuses)


def snapshot_names(namespace: dict, root: str) -> dict:
    out = {}
    for name, value in namespace.items():
        if name.startswith("__") or name in ("snapshot_target",):
            continue
        out[name] = describe_value(value, root)
    return out


def run_parent(tree: Path, rel: str) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--tree", str(tree), CHILD_FLAG, rel],
            cwd=tree, capture_output=True, text=True, timeout=TIMEOUT_S, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    last = proc.stdout.strip().split("\n")[-1] if proc.stdout.strip() else ""
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return {"status": "NO_SNAPSHOT", "exit": proc.returncode}


def describe_value(value, root: str):
    if isinstance(value, SIMPLE):
        return normalise(repr(value), root)
    if isinstance(value, re.Pattern):
        return "re:" + value.pattern
    if isinstance(value, Path):
        return "path:" + normalise(str(value), root)
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [describe_value(v, root) for v in value]
        return [type(value).__name__, sorted(map(str, items)) if isinstance(value, (set, frozenset)) else items]
    if isinstance(value, dict):
        return ["dict", sorted((normalise(str(k), root), str(describe_value(v, root))) for k, v in value.items())]
    if callable(value):
        return "callable:" + getattr(value, "__name__", type(value).__name__)
    if type(value).__module__ == "builtins":
        return "builtin:" + type(value).__name__
    return "object:" + type(value).__name__


def normalise(text: str, root: str) -> str:
    return text.replace(root, "<ROOT>")


if __name__ == "__main__":
    snapshot_workflow()
