# INFRASTRUCTURE
from dev.kvp.kvp_config import (
    DIVE_COMPLETE,
    DIVE_DISCOVERY_FAILED,
    DIVE_NO_CLOSING,
    DIVE_NO_DISCOVERY,
    UNKNOWN_HOST,
)
from dev.kvp.kvp_load import version_of


# FUNCTIONS

def dive_rows(records: list[dict], pipe_runs: list[dict]) -> list[dict]:
    failed_by_run = {run["run_id"]: run["failed"] for run in pipe_runs}
    return [_dive_row(dive, failed_by_run) for dive in group_dives(records)]


def group_dives(records: list[dict]) -> list[dict]:
    dives: list[dict] = []
    open_by_host: dict[str, dict] = {}
    for record in sorted(records, key=lambda r: r["ts"]):
        host = record.get("host") or UNKNOWN_HOST
        if record["record_type"] == "discovery":
            open_by_host[host] = _new_dive(host, dives, discovery=record)
            continue
        dive = open_by_host.get(host)
        if dive is None or dive["closing"] is not None:
            dive = open_by_host[host] = _new_dive(host, dives)
        if record["record_type"] == "scrape_round":
            dive["rounds"].append(record)
        else:
            dive["closing"] = record
    return dives


def _new_dive(host: str, dives: list[dict], discovery: dict | None = None) -> dict:
    dive = {"host": host, "discovery": discovery, "rounds": [], "closing": None}
    dives.append(dive)
    return dive


def _dive_row(dive: dict, failed_by_run: dict[str, int]) -> dict:
    discovery, closing, rounds = dive["discovery"], dive["closing"], dive["rounds"]
    records = [r for r in [discovery, closing, *rounds] if r]
    discovered_ok = discovery is not None and discovery["ok"]
    return {
        "first_ts": min(r["ts"] for r in records),
        "host": dive["host"],
        "versions": sorted({version_of(r) for r in records}),
        "state": _dive_state(discovery, closing),
        "discovered": discovery["total"] if discovered_ok else None,
        "by_source": discovery["by_source"] if discovered_ok else {},
        "failed_feeders": sorted(discovery["failed_feeders"]) if discovery else [],
        "kept": closing["kept"] if closing else None,
        "rounds": [r["urls_requested"] for r in rounds],
        "files_written": sum(r["files_written"] for r in rounds),
        "pipe_failed": sum(failed_by_run.get(r["run_id"], 0) for r in rounds),
        "failed_aside": closing["failed"]["count"] if closing else None,
        "cuts": {name: facts["passages"] for name, facts in closing["cuts"].items()} if closing else {},
        "work_files": closing["work_files"]["count"] if closing and closing["work_files"] else None,
        "copied": closing["collection_files"]["copied"] if closing and closing["collection_files"] else None,
        "indexed": closing["index"]["done"] if closing else None,
        "index_errors": len(closing["index"]["errors"]) if closing else None,
        "collection": closing["collection"] if closing else None,
        "info_need": closing["info_need"] if closing else None,
    }


def _dive_state(discovery: dict | None, closing: dict | None) -> str:
    if discovery is None:
        return DIVE_NO_DISCOVERY
    if not discovery["ok"]:
        return DIVE_DISCOVERY_FAILED
    return DIVE_COMPLETE if closing else DIVE_NO_CLOSING
