# INFRASTRUCTURE
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pydoll.connection.connection_handler import ConnectionHandler as _CH

_cdp_ts: list[float] = []
_orig_process_msg = _CH._process_single_message


async def _patched_process_msg(self, raw_message: str) -> None:
    _cdp_ts.append(time.monotonic())
    return await _orig_process_msg(self, raw_message)


_CH._process_single_message = _patched_process_msg

SLOW_CB_THRESHOLD_S = 0.05

_slow_cb_events: list[str] = []


# FUNCTIONS

def _install_asyncio_log_capture() -> None:
    class _SlowCBHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = self.format(record)
            if "Executing" in msg and "took" in msg:
                _slow_cb_events.append(msg)

    h = _SlowCBHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    aio_log = logging.getLogger("asyncio")
    aio_log.setLevel(logging.WARNING)
    aio_log.addHandler(h)
