# INFRASTRUCTURE
from pathlib import Path

from src.pdf.manifest import load_manifest
from src.pdf.report import Report
from src.pdf.worker_outputs import STATE_COMPLETE, format_unfinished, worker_states


# ORCHESTRATOR
def status_workflow(batch_dir: str) -> Report:
    batch_path = Path(batch_dir)
    manifest = load_manifest(batch_path)
    states = worker_states(batch_path, manifest)
    return Report(format_status(states), True)


# FUNCTIONS
def format_status(states: list[tuple[dict, str, list[str]]]) -> str:
    complete = [worker for worker, state, _ in states if state == STATE_COMPLETE]
    lines = [f"workers complete: {len(complete)} of {len(states)}"]
    for worker, state, missing in states:
        lines += [f"  {worker['name']}: {state}"] if state == STATE_COMPLETE else format_unfinished([(worker, state, missing)])
    return "\n".join(lines)
