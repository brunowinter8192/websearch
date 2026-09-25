# INFRASTRUCTURE
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
LOG_DIR     = SCRIPT_DIR / "probe_liveness_logs"
SWEEP_LOG   = LOG_DIR / "sweep_log.md"

DEAD_BUCKETS = [
    "connect_timeout", "read_timeout", "hard_timeout", "connection_refused",
    "proxy_handshake_error", "resolve_error", "tls_error",
    "http_non200", "bad_body", "unknown",
]


# FUNCTIONS

def print_console_summary(results: list[dict], concurrency: int, elapsed: float) -> None:
    alive = sum(1 for r in results if r["alive"])
    n     = len(results)
    dead  = n - alive
    tp    = n / elapsed if elapsed > 0 else 0

    histogram: dict[str, int] = defaultdict(int)
    for r in results:
        if not r["alive"]:
            histogram[r["bucket"]] += 1

    print(f"\n--- concurrency={concurrency}  elapsed={elapsed:.1f}s  throughput={tp:.0f}/s ---")
    print(f"  Alive: {alive:,}/{n:,}  ({100*alive/n:.1f}%)")
    if dead:
        print("  Dead reason histogram:")
        for bucket in DEAD_BUCKETS:
            count = histogram.get(bucket, 0)
            if count:
                print(f"    {bucket:<25} {count:>6,}  ({100*count/dead:.1f}% of dead)")


def append_sweep_log(
    results: list[dict],
    ts: datetime,
    mode: str,
    n: int,
    concurrency: int,
    connect_s: float,
    read_s: float,
    elapsed: float,
    skipped: int = 0,
) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    alive     = sum(1 for r in results if r["alive"])
    dead      = n - alive
    tp        = n / elapsed if elapsed > 0 else 0
    alive_pct = 100 * alive / n if n else 0

    histogram: dict[str, int] = defaultdict(int)
    for r in results:
        if not r["alive"]:
            histogram[r["bucket"]] += 1

    skipped_part = f" | skipped_fresh={skipped:,}" if skipped else ""
    lines = [
        "---",
        f"## {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} | {mode} | n={n:,}{skipped_part} | "
        f"concurrency={concurrency} | timeout={connect_s}s/{read_s}s",
        "",
        "| Wall-clock | Throughput | Alive | Alive% | Dead |",
        "|---|---|---|---|---|",
        f"| {elapsed:.1f}s | {tp:.0f}/s | {alive:,} | {alive_pct:.1f}% | {dead:,} |",
        "",
        "### Dead Reason Histogram",
        "",
        "| Reason | Count | % of dead |",
        "|---|---|---|",
    ]
    for bucket in DEAD_BUCKETS:
        count = histogram.get(bucket, 0)
        pct   = 100 * count / dead if dead else 0.0
        lines.append(f"| {bucket} | {count:,} | {pct:.1f}% |")
    lines.append("")

    with SWEEP_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nAppended sweep entry → {SWEEP_LOG}")


def write_unknown_log(results: list[dict], ts: datetime) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path     = LOG_DIR / f"unknown_errors_{ts.strftime('%Y%m%dT%H%M%SZ')}.log"
    unknowns = [r for r in results if r["bucket"] == "unknown"]
    with path.open("w", encoding="utf-8") as f:
        f.write(f"# Unknown errors — {ts.strftime('%Y-%m-%dT%H:%M:%SZ')} — {len(unknowns)} entries\n\n")
        for r in unknowns:
            f.write(
                f"proto={r['proto']}  {r['host_port']}  "
                f"elapsed={r['elapsed']:.2f}s  {r['detail']}\n"
            )
    print(f"  Unknown log ({len(unknowns)} entries) → {path}")
