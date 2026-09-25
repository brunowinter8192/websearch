#!/usr/bin/env python3
# INFRASTRUCTURE
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _fixture_site import start_fixture_server, stop_fixture_server, ground_truth, seed_url

DEFAULT_PORT = 8935


# ORCHESTRATOR

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    fixture_site_server_workflow(args.port)


# FUNCTIONS

def fixture_site_server_workflow(port: int) -> None:
    server, thread, bound_port = start_fixture_server(port=port)
    print(f"Fixture serving on http://127.0.0.1:{bound_port}/", file=sys.stderr)
    print(f"Seed URL for discover_urls_workflow: {seed_url(bound_port)}", file=sys.stderr)
    print(json.dumps(ground_truth(), indent=2), file=sys.stderr)
    print("Ctrl+C to stop.", file=sys.stderr)
    try:
        while True:
            time.sleep(3600)
    finally:
        stop_fixture_server(server, thread)
        print("Fixture server stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
