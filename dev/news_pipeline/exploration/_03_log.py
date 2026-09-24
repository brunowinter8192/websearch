# INFRASTRUCTURE
from datetime import datetime, timezone


# FUNCTIONS

def write_log_header(log_fh, ts: str, cap_label: str) -> None:
    log_fh.write(f"# CoinDesk backfill — started {ts} — cap={cap_label}\n")
    log_fh.write("# timestamp                | click | total  | oldest     |  +new | btn            |    t(s)\n")
    log_fh.flush()


def write_log_line(
    log_fh, click_n: int, total: int, oldest: str,
    new_this: int, btn_state: str, elapsed: float,
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    line = (
        f"{ts} | click={click_n:5d} | total={total:6d} | oldest={oldest}"
        f" | +{new_this:4d} | {btn_state:<14} | {elapsed:6.1f}s\n"
    )
    log_fh.write(line)
    log_fh.flush()
