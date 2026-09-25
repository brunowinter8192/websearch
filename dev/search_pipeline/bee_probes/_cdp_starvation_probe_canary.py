# INFRASTRUCTURE
import asyncio
import statistics
import time
from collections import defaultdict

COLD_START_SKIP_S = 5.0
CANARY_INTERVAL_S = 0.1

_canary_samples: list[tuple[float, float, int]] = []

PROBE_START: float = 0.0


# FUNCTIONS

def _start_probe_clock() -> None:
    global PROBE_START
    PROBE_START = time.monotonic()


async def _start_canary_monitor() -> tuple[asyncio.Event, asyncio.Task]:
    stop_canary = asyncio.Event()
    canary_task = asyncio.create_task(_canary_monitor(stop_canary))
    return stop_canary, canary_task


async def _stop_canary_monitor(stop_canary: asyncio.Event, canary_task: asyncio.Task) -> None:
    stop_canary.set()
    await canary_task


def _compute_stats(records: list[dict]) -> dict[str, dict]:
    cold_cutoff = PROBE_START + COLD_START_SKIP_S
    by_cat: dict[str, list[float]] = defaultdict(list)
    all_lat: list[float] = []
    cold_lat: list[float] = []

    for ts, lat, _ in _canary_samples:
        if ts < cold_cutoff:
            cold_lat.append(lat)
            continue
        cat = _sample_category(ts, records)
        by_cat[cat].append(lat)
        if cat != "between":
            all_lat.append(lat)

    def _stats(data: list[float]) -> dict:
        if not data:
            return {"n": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "mean": 0.0}
        return {
            "n": len(data),
            "p50": round(_pct(data, 50), 1),
            "p95": round(_pct(data, 95), 1),
            "p99": round(_pct(data, 99), 1),
            "max": round(max(data), 1),
            "mean": round(statistics.mean(data), 1),
        }

    return {
        "overall": _stats(all_lat),
        "normal": _stats(by_cat.get("normal", [])),
        "empty": _stats(by_cat.get("empty", [])),
        "zero_cascade": _stats(by_cat.get("zero_cascade", [])),
        "cold_start": _stats(cold_lat),
    }


async def _canary_monitor(stop: asyncio.Event) -> None:
    while not stop.is_set():
        t0 = time.monotonic()
        await asyncio.sleep(CANARY_INTERVAL_S)
        elapsed = time.monotonic() - t0
        latency_ms = max(0.0, (elapsed - CANARY_INTERVAL_S) * 1000)
        num_tasks = len(asyncio.all_tasks())
        _canary_samples.append((time.monotonic(), latency_ms, num_tasks))


def _sample_category(ts: float, records: list[dict]) -> str:
    for r in records:
        if r["t_start"] <= ts < r["t_end"]:
            return r["category"]
    return "between"


def _pct(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (k - lo) * (s[hi] - s[lo])
