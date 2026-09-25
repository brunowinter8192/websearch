# INFRASTRUCTURE
from src.news.pipeline_support import (
    log_run_complete, master_list_path, persist_master_list, start_run, write_marker,
)
from src.news.platform import Platform


# ORCHESTRATOR

async def discover_only_workflow(platform: Platform) -> None:
    log = start_run(platform, "discover-only started")
    entries = await platform.discover()
    _log_discovered(log, entries)
    if platform.uses_master_list:
        persist_master_list(entries, master_list_path(platform), log)
    write_marker(platform.name, log)
    log_run_complete(log, platform, "discover-only complete")


# FUNCTIONS

def _log_discovered(log, entries: list[dict]) -> None:
    log.info(f"discover → {len(entries)} entries")
