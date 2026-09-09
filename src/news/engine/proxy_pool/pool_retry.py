# INFRASTRUCTURE

import time

_sleep   = time.sleep
_BACKOFF = (1, 2, 4, 8)


# FUNCTIONS

def fetch_with_retry(fn):
    last_exc = None
    for delay in (None, *_BACKOFF):
        if delay is not None:
            _sleep(delay)
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
    raise last_exc
