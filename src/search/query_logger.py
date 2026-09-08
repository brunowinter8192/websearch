# INFRASTRUCTURE
import json
import logging
import os
from pathlib import Path

from src.log_janitor import maybe_prune_jsonl

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "src" / "logs" / "query_log.jsonl"


# FUNCTIONS

def log_query(record: dict) -> None:
    env = os.environ.get("WEBSEARCH_QUERY_LOG_PATH")
    log_path = Path(env) if env else DEFAULT_LOG_PATH
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        maybe_prune_jsonl(log_path)
    except Exception as e:
        logger.warning("query_log write failed: %s", e)
