# INFRASTRUCTURE
import json
import time
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "06_output"
CHECKPOINT_FILE = OUTPUT_DIR / "checkpoint.json"


# FUNCTIONS

def save_checkpoint(call_num: int, last_id: str, last_date: str, year_counts: dict, total: int) -> None:
    data = {
        "call_num": call_num,
        "last_id": last_id,
        "last_date": last_date,
        "year_counts": dict(year_counts),
        "total_articles": total,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def log_checkpoint(log_fh, ok_calls: int, total_articles: int, oldest_date, last_date: str,
                    t_start: float, elapsed_vals: list, rewarm_count: int, fallback_count: int) -> None:
    wall = int(time.monotonic() - t_start)
    avg_el = round(sum(elapsed_vals[-50:]) / max(1, len(elapsed_vals[-50:])), 3)
    log(log_fh, (
        f"checkpoint call={ok_calls} articles={total_articles}"
        f" oldest={oldest_date} pivot={last_date[:10]}"
        f" wall={wall}s avg_elapsed={avg_el}s"
        f" rewarms={rewarm_count} fallbacks={fallback_count}"
    ))


def log(log_fh, msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_fh.write(line + "\n")
    log_fh.flush()
