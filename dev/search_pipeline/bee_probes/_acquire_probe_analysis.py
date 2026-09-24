# INFRASTRUCTURE
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from _acquire_probe_canary import _pct


# FUNCTIONS

def _load_queries(path: Path, n: int | None) -> list[str]:
    qs = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return qs[:n] if n else qs


def _build_engine_summary(
    events: list[tuple[str, str, float]],
    all_statuses: dict[str, str],
) -> dict[str, dict]:
    by_eng: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for eng, evt, ts in events:
        by_eng[eng].append((evt, ts))

    summary = {}
    for eng in set(all_statuses) | set(by_eng):
        evts = by_eng.get(eng, [])
        enter_ts = next((ts for e, ts in evts if e == "enter"), None)
        exit_item = next(((e, ts) for e, ts in reversed(evts) if e.startswith("exit_")), None)
        exit_class = exit_item[0][len("exit_"):] if exit_item else "none"
        dur_ms = round((exit_item[1] - enter_ts) * 1000) if (enter_ts and exit_item) else None
        summary[eng] = {
            "status": all_statuses.get(eng, "—"),
            "entered": enter_ts is not None,
            "lock_granted": any(e == "lock_granted" for e, _ in evts),
            "lock_released": any(e == "lock_released" for e, _ in evts),
            "lock_stuck": any(e == "lock_stuck" for e, _ in evts),
            "exit_class": exit_class,
            "dur_ms": dur_ms,
        }
    return summary


def _discriminator(eng_summary: dict[str, dict]) -> str:
    rs = [d for d in eng_summary.values() if d["status"] == "RATE_SKIP"]
    if not rs:
        return "ok"
    n = len(rs)
    n_ent = sum(1 for d in rs if d["entered"])
    n_lg = sum(1 for d in rs if d["lock_granted"])
    n_ok = sum(1 for d in rs if d["exit_class"] == "ok")
    n_err = sum(1 for d in rs if d["exit_class"].startswith("err:"))
    if n_ent == 0:
        return "B"
    if n_ok == n:
        return "C"
    if n_lg == 0:
        return "A-lock"
    if n_err > 0:
        return "A-sleep"
    return f"mixed(ent={n_ent} lg={n_lg} ok={n_ok} err={n_err}/{n})"


def _dump_smoke(events: list, eng_summary: dict) -> None:
    print(f"  total events: {len(events)}", file=sys.stderr)
    for eng in sorted(eng_summary):
        d = eng_summary[eng]
        print(
            f"    {eng:<22} entered={d['entered']} lg={d['lock_granted']} "
            f"lr={d['lock_released']} ls={d['lock_stuck']} "
            f"exit={d['exit_class']:<22} dur={d['dur_ms']}ms",
            file=sys.stderr,
        )


def _agg_ratios(records: list[dict]) -> tuple:
    ratios_ent, ratios_lg, ratios_ok, ratios_err, durs = [], [], [], [], []
    for r in records:
        rs = [d for d in r["eng_summary"].values() if d["status"] == "RATE_SKIP"]
        n_rs = len(rs) or 1
        ratios_ent.append(sum(1 for d in rs if d["entered"]) / n_rs)
        ratios_lg.append(sum(1 for d in rs if d["lock_granted"]) / n_rs)
        ratios_ok.append(sum(1 for d in rs if d["exit_class"] == "ok") / n_rs)
        ratios_err.append(sum(1 for d in rs if d["exit_class"].startswith("err:")) / n_rs)
        durs += [d["dur_ms"] for d in rs if d["dur_ms"] is not None]
    mn = statistics.mean
    dp99: int | str = round(_pct(durs, 99)) if durs else "—"
    return (round(mn(ratios_ent), 2), round(mn(ratios_lg), 2),
            round(mn(ratios_ok), 2), round(mn(ratios_err), 2), dp99)
