# INFRASTRUCTURE
import sys
import time
from collections import defaultdict
from pathlib import Path

from _branch_probe_instrument import _rl_mod


# FUNCTIONS

def _load_queries(path: Path, n: int | None) -> list[str]:
    qs = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return qs[:n] if n else qs


def _snapshot_limiters(qi: int) -> dict:
    now = time.monotonic()
    engines = {}
    for name, lim in _rl_mod._limiters.items():
        br = max(0.0, lim._backoff_until - now)
        tok_count = sum(1 for t in lim._tokens if now - t < lim._window_seconds)
        engines[name] = {
            "backoff_remaining_s": round(br, 2),
            "len_tokens": tok_count,
            "max_requests": lim._max_requests,
            "window_seconds": lim._window_seconds,
        }
    return {"qi": qi, "engines": engines}


def _build_engine_detail(
    events: list[tuple[str, str, float, float | None]],
    all_statuses: dict[str, str],
    snap: dict,
) -> dict[str, dict]:
    by_eng: dict[str, list[tuple[str, float, float | None]]] = defaultdict(list)
    for eng, evt, ts, wait in events:
        by_eng[eng].append((evt, ts, wait))

    detail = {}
    for eng in set(all_statuses) | set(by_eng):
        evts = by_eng.get(eng, [])
        enter_ts = next((ts for e, ts, _ in evts if e == "enter"), None)
        exit_item = next(((e, ts) for e, ts, _ in reversed(evts) if e.startswith("exit_")), None)
        exit_class = exit_item[0][len("exit_"):] if exit_item else "none"
        dur_ms = round((exit_item[1] - enter_ts) * 1000) if (enter_ts and exit_item) else None

        backoff_ev = next(((ts, w) for e, ts, w in evts if e == "backoff_sleep_attempt"), None)
        tokencap_ev = next(((ts, w) for e, ts, w in evts if e == "tokencap_sleep_attempt"), None)

        pre = snap["engines"].get(eng, {})
        detail[eng] = {
            "status": all_statuses.get(eng, "—"),
            "pre_backoff_remaining_s": pre.get("backoff_remaining_s", "?"),
            "pre_len_tokens": pre.get("len_tokens", "?"),
            "backoff_attempt": backoff_ev is not None,
            "backoff_wait_s": round(backoff_ev[1], 1) if backoff_ev else None,
            "tokencap_attempt": tokencap_ev is not None,
            "tokencap_wait_s": round(tokencap_ev[1], 1) if tokencap_ev else None,
            "exit_class": exit_class,
            "dur_ms": dur_ms,
        }
    return detail


def _query_discriminator(eng_detail: dict[str, dict]) -> str:
    rs = [d for d in eng_detail.values() if d["status"] == "RATE_SKIP"]
    if not rs:
        return "ok"
    n = len(rs)
    n_ba = sum(1 for d in rs if d["backoff_attempt"])
    n_tc = sum(1 for d in rs if d["tokencap_attempt"])
    n_ni = sum(1 for d in rs if not d["backoff_attempt"] and not d["tokencap_attempt"])
    if n_tc == n and n_ba == 0:
        return "tokencap"
    if n_ba == n and n_tc == 0:
        return "backoff"
    if n_ba > 0 and n_tc > 0:
        return f"mixed(ba={n_ba} tc={n_tc} ni={n_ni}/{n})"
    if n_ni == n:
        return "neither"
    return f"partial(ba={n_ba} tc={n_tc} ni={n_ni}/{n})"


def _dump_smoke(
    events: list[tuple[str, str, float, float | None]],
    eng_detail: dict[str, dict],
    snap: dict,
    backoff_immune: frozenset[str],
) -> None:
    print(f"  total events: {len(events)}", file=sys.stderr)
    for eng in sorted(eng_detail):
        d = eng_detail[eng]
        pre = snap["engines"].get(eng, {})
        imm = "(I)" if eng in backoff_immune else "   "
        print(
            f"    {eng:<22}{imm} pre_br={pre.get('backoff_remaining_s', '?'):>6}s "
            f"pre_tok={pre.get('len_tokens', '?')}  "
            f"backoff={d['backoff_attempt']} wait={d['backoff_wait_s']}  "
            f"tokencap={d['tokencap_attempt']} wait={d['tokencap_wait_s']}  "
            f"exit={d['exit_class']:<22} dur={d['dur_ms']}ms",
            file=sys.stderr,
        )
