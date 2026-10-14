# INFRASTRUCTURE
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import psutil

PS_COMMAND = ["ps", "-axo", "pid=,time=,comm="]
PS_TIMEOUT_S = 5
PS_TIME_PATTERN = re.compile(r"^(\d+):(\d{2}(?:\.\d+)?)$")
TOP_PROCESS_COUNT = 3
LOAD_DECIMALS = 2
CPU_BUSY_DECIMALS = 1
CPU_SECONDS_DECIMALS = 2
ERROR_SAMPLE_CHARS = 80


# FUNCTIONS

def take_host_snapshot() -> dict:
    errors: list[str] = []
    return {
        "load_avg": _guarded(errors, "loadavg", os.getloadavg),
        "cpu": _guarded(errors, "cpu_times", psutil.cpu_times),
        "procs": _guarded(errors, "ps", lambda: parse_ps_output(read_ps_output(), errors)),
        "errors": errors,
    }


def host_facts_since(start: dict) -> dict:
    errors = list(start["errors"])
    end = take_host_snapshot()
    errors.extend(end["errors"])
    facts = {
        "cpu_count": os.cpu_count(),
        "load_avg_start": _rounded_load(start["load_avg"]),
        "cpu_busy_pct": _guarded(errors, "cpu_busy", lambda: cpu_busy_pct(start["cpu"], end["cpu"])),
        "top_cpu_processes": _guarded(errors, "top_processes", lambda: top_cpu_processes(start["procs"], end["procs"])),
    }
    return {**facts, "errors": list(dict.fromkeys(errors))}


def read_ps_output() -> str:
    completed = subprocess.run(PS_COMMAND, capture_output=True, text=True, timeout=PS_TIMEOUT_S, check=True)
    return completed.stdout


def parse_ps_output(output: str, errors: list[str]) -> dict[int, tuple[str, float]]:
    processes: dict[int, tuple[str, float]] = {}
    unparseable: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parsed = _parse_ps_line(line)
        if parsed is None:
            unparseable.append(line.strip()[:ERROR_SAMPLE_CHARS])
        else:
            processes[parsed[0]] = (parsed[1], parsed[2])
    if unparseable:
        errors.append(f"ps: {len(unparseable)} unparseable lines, first: {unparseable[0]!r}")
    return processes


def cpu_busy_pct(start, end) -> float | None:
    if start is None or end is None:
        return None
    total = sum(end) - sum(start)
    idle = end.idle - start.idle
    if total <= 0:
        return None
    return round((total - idle) / total * 100, CPU_BUSY_DECIMALS)


def top_cpu_processes(start: dict | None, end: dict | None) -> list[dict] | None:
    if start is None or end is None:
        return None
    own_pid = os.getpid()
    seconds: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for pid, (name, cpu_s) in end.items():
        if pid == own_pid:
            continue
        before = start.get(pid)
        delta = cpu_s - before[1] if before and before[0] == name else cpu_s
        if delta > 0:
            seconds[name] += delta
            counts[name] += 1
    ranked = sorted(seconds.items(), key=lambda item: -item[1])[:TOP_PROCESS_COUNT]
    return [{"name": name, "cpu_s": round(cpu_s, CPU_SECONDS_DECIMALS), "procs": counts[name]} for name, cpu_s in ranked]


def _guarded(errors: list[str], label: str, read):
    try:
        return read()
    except Exception as e:
        errors.append(f"{label}: {type(e).__name__}: {str(e)[:ERROR_SAMPLE_CHARS]}")
        return None


def _parse_ps_line(line: str) -> tuple[int, str, float] | None:
    parts = line.split(None, 2)
    if len(parts) != 3 or not parts[0].isdigit():
        return None
    match = PS_TIME_PATTERN.match(parts[1])
    if match is None:
        return None
    return int(parts[0]), Path(parts[2]).name, int(match.group(1)) * 60 + float(match.group(2))


def _rounded_load(load_avg) -> list[float] | None:
    return [round(value, LOAD_DECIMALS) for value in load_avg] if load_avg else None
