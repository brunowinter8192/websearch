#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TIMEOUT_S = 60
VARIANTS = ([], ["--help"])
NORMALISERS = [
    (re.compile(r"\d{8}T\d{6}Z"), "<TS>"),
    (re.compile(r"\d{8}_\d{6}"), "<TS>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"), "<TS>"),
    (re.compile(r"\d+(\.\d+)?\s?(ms|s)\b"), "<DUR>"),
]


# ORCHESTRATOR

def run_compare_workflow() -> None:
    args = parse_args()
    scripts = read_list(Path(args.list))
    trees = [Path(args.base_tree).resolve(), Path(args.cur_tree).resolve()]
    base_results, cur_results = _run_pool(scripts, trees)
    verdicts = compare_results(scripts, base_results, cur_results)
    write_report(Path(args.out), verdicts)
    print_summary(verdicts)


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-tree", required=True)
    parser.add_argument("--cur-tree", required=True)
    parser.add_argument("--list", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def read_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def _run_pool(scripts, trees):
    with ThreadPoolExecutor(max_workers=2) as pool:
        base_results, cur_results = pool.map(lambda tree: run_tree(tree, scripts), trees)
    return base_results, cur_results


def compare_results(scripts: list[str], base: dict, cur: dict) -> list[dict]:
    verdicts = []
    for key in base:
        same = base[key] == cur[key]
        verdicts.append({"run": key, "same": same, "base": base[key], "cur": cur[key]})
    return verdicts


def write_report(out: Path, verdicts: list[dict]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    same = [v for v in verdicts if v["same"]]
    lines = ["# 08_run_compare report", "", f"runs: {len(verdicts)}", f"identical: {len(same)}", f"different: {len(verdicts) - len(same)}", ""]
    lines += ["## Runs", ""]
    for v in verdicts:
        lines.append(f"- {'SAME' if v['same'] else 'DIFF'} `{v['run']}` exit={v['base']['exit']}/{v['cur']['exit']} written={len(v['base']['written'])}/{len(v['cur']['written'])}")
    lines += ["", "## Differences", ""]
    for v in verdicts:
        if not v["same"]:
            lines += [f"### {v['run']}", "```", json.dumps({"base": v["base"], "cur": v["cur"]}, indent=1)[:3000], "```", ""]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(verdicts: list[dict]) -> None:
    diff = sum(1 for v in verdicts if not v["same"])
    print(f"runs={len(verdicts)} different={diff}")


def run_tree(tree: Path, scripts: list[str]) -> dict:
    home = tempfile.mkdtemp(prefix="run_compare_home_")
    results = {}
    for rel in scripts:
        for variant in VARIANTS:
            results[f"{rel} {' '.join(variant)}".strip()] = run_one(tree, rel, variant, home)
    return results


def run_one(tree: Path, rel: str, variant: list[str], home: str) -> dict:
    before = time.time()
    env = dict(os.environ, HOME=home, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(
            [sys.executable, str(tree / rel), *variant],
            cwd=tree, capture_output=True, text=True, timeout=TIMEOUT_S, env=env, stdin=subprocess.DEVNULL,
        )
        outcome = {"exit": proc.returncode, "out": normalise(proc.stdout, tree), "err": normalise(proc.stderr, tree)}
    except subprocess.TimeoutExpired:
        outcome = {"exit": "TIMEOUT", "out": "", "err": ""}
    outcome["written"] = written_files(tree, before)
    return outcome


def written_files(tree: Path, since: float) -> list[str]:
    found = []
    for path in (tree / "dev").rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.stat().st_mtime >= since:
            found.append(normalise(str(path.relative_to(tree)), tree))
    return sorted(found)


def normalise(text: str, tree: Path) -> str:
    text = text.replace(str(tree), "<ROOT>").replace(os.path.realpath(tree), "<ROOT>")
    text = re.sub(r"run_compare_home_\w+", "<HOME>", text)
    if "Traceback (most recent call last)" in text:
        text = "TRACEBACK " + [line for line in text.split("\n") if line.strip()][-1]
    for pattern, token in NORMALISERS:
        text = pattern.sub(token, text)
    return text


if __name__ == "__main__":
    run_compare_workflow()
