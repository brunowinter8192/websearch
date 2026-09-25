#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _02_depth import depth_workflow
from _02_quick import probe_workflow


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CoinDesk pagination probe — quick (5 clicks + HAR) or depth (ceiling finder)"
    )
    parser.add_argument(
        "--depth", action="store_true",
        help="Run ceiling-finder loop (up to 150 clicks, no HAR, coindesk-only net log)"
    )
    args = parser.parse_args()
    if args.depth:
        asyncio.run(depth_workflow())
    else:
        asyncio.run(probe_workflow())


if __name__ == "__main__":
    main()
