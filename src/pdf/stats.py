# INFRASTRUCTURE
from collections import Counter

from src.pdf.conversion_log import parse_timestamp, read_records
from src.pdf.report import Report, WorkflowError

SECONDS_PER_MINUTE = 60


# ORCHESTRATOR
def stats_workflow(since: str | None) -> Report:
    runs = group_runs(read_records(), since)
    return Report(format_stats(summarize(runs), since), True)


# FUNCTIONS
def group_runs(records: list[dict], since: str | None) -> list[dict]:
    runs: dict[str, dict] = {}
    for record in records:
        if record["record_type"] == "start":
            runs[record["run_id"]] = {"start": record, "ends": []}
        elif record["run_id"] in runs:
            runs[record["run_id"]]["ends"].append(record)
        else:
            raise WorkflowError("log_corrupt", f"end record without start record: {record['run_id']}")
    return [run for run in runs.values() if since is None or run["start"]["ts_start"][:10] >= since]


def summarize(runs: list[dict]) -> dict:
    finished = [run for run in runs if run["ends"]]
    final = [run["ends"][-1] for run in finished]
    return {
        "runs": len(runs),
        "ok": sum(1 for end in final if end["outcome"] == "ok"),
        "unfinished": len(runs) - len(finished),
        "failures": Counter(end["failure_class"] for end in final if end["outcome"] != "ok"),
        "recovered": sum(1 for run in finished if len(run["ends"]) > 1 and run["ends"][-1]["outcome"] == "ok"),
        "mean_pages": mean([run["start"]["pages"] for run in runs]),
        "mean_wall_s": mean([end["wall_s"] for end in final]),
        "configs": per_config(runs),
    }


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def per_config(runs: list[dict]) -> dict[str, tuple[int, int]]:
    configs: dict[str, tuple[int, int]] = {}
    for run in sorted(runs, key=lambda item: parse_timestamp(item["start"]["ts_start"])):
        total, ok = configs.get(run["start"]["config_hash"], (0, 0))
        succeeded = bool(run["ends"]) and run["ends"][-1]["outcome"] == "ok"
        configs[run["start"]["config_hash"]] = (total + 1, ok + int(succeeded))
    return configs


def format_stats(summary: dict, since: str | None) -> str:
    failed = sum(summary["failures"].values())
    lines = [
        f"pdf conversions since {since or 'the beginning'}",
        f"runs: {summary['runs']}  ok: {summary['ok']}  failed: {failed}  unfinished: {summary['unfinished']}",
        f"recovered by retry: {summary['recovered']}",
        "failures by reason: " + (", ".join(f"{name}={count}" for name, count in sorted(summary["failures"].items())) or "none"),
        f"mean pages: {format_number(summary['mean_pages'], 1)}",
        f"mean duration: {format_number(minutes(summary['mean_wall_s']), 1)} min",
    ]
    lines += [f"config {name}: {total} runs, {ok} ok" for name, (total, ok) in summary["configs"].items()]
    return "\n".join(lines)


def minutes(seconds: float | None) -> float | None:
    return None if seconds is None else seconds / SECONDS_PER_MINUTE


def format_number(value: float | None, digits: int) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"
