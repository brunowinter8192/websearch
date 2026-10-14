# INFRASTRUCTURE
import json
import os
from pathlib import Path

from src.code_version import code_version
from src.log_janitor import maybe_prune_jsonl

DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "deep_dive_log.jsonl"


# FUNCTIONS

def log_deep_dive(record: dict) -> None:
    env = os.environ.get("WEBSEARCH_DEEP_DIVE_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({**record, "code_version": code_version()}, ensure_ascii=False) + "\n")
    maybe_prune_jsonl(log_path)
