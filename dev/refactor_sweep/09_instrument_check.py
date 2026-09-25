#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import importlib
import json
import sys
from pathlib import Path


# ORCHESTRATOR

def instrument_check_workflow() -> None:
    args = parse_args()
    tree = Path(args.tree).resolve()
    prepare_paths(tree)
    result = run_check(args.probe)
    print(json.dumps(result, sort_keys=True))


# FUNCTIONS

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--probe", required=True, choices=["acquire", "branch", "cdp"])
    return parser.parse_args()


def prepare_paths(tree: Path) -> None:
    sys.path.insert(0, str(tree))
    sys.path.insert(0, str(tree / "dev" / "search_pipeline" / "bee_probes"))


def run_check(probe: str) -> dict:
    if probe == "cdp":
        return check_cdp()
    return check_rate_limiter(probe)


def check_cdp() -> dict:
    instrument = importlib.import_module("_cdp_starvation_probe_instrument")
    install_if_present(instrument, "install_process_msg_patch")
    handler = instrument._CH
    return {"patched": handler._process_single_message is instrument._patched_process_msg}


def install_if_present(module, name: str) -> None:
    if hasattr(module, name):
        getattr(module, name)()


def check_rate_limiter(probe: str) -> dict:
    instrument = importlib.import_module(f"_{probe}_probe_instrument")
    importlib.import_module("src.search.search_web")
    install_if_present(instrument, "install_instrument")
    limiters = instrument._rl_mod._limiters
    kinds = {name: type(lim._lock).__name__ for name, lim in sorted(limiters.items())}
    events = asyncio.run(acquire_once(limiters["bing"], instrument))
    return {"lock_types": kinds, "acquire_patched": limiters["bing"].acquire.__func__.__name__, "events": events}


async def acquire_once(limiter, instrument) -> list[list]:
    await limiter.acquire()
    return [[e[0], e[1]] for e in instrument._acq_events]


if __name__ == "__main__":
    instrument_check_workflow()
