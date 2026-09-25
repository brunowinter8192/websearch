#!/usr/bin/env python3
# INFRASTRUCTURE
import hashlib
import json
from datetime import datetime
from pathlib import Path

SCRIPT_DIR      = Path(__file__).parent
SCOREBOARD_JSON = SCRIPT_DIR / "source_scoreboard.json"
SCOREBOARD_MD   = SCRIPT_DIR / "source_scoreboard.md"
FRESHNESS_LOG   = SCRIPT_DIR / "freshness_log.md"
SNAPSHOTS_DIR   = SCRIPT_DIR / "source_snapshots"

CF_RATE_MIN_N = 30


# ORCHESTRATOR

def update_and_flush(
    ts: datetime,
    source_results: list[dict],
    sample: list[tuple[str, str]],
    liveness_results: list[dict],
    neutral_alive: list[str],
    cf_passing: list[str],
    hp_to_sources: dict[str, set[str]],
) -> None:
    run_stats = compute_run_stats(
        source_results, sample, liveness_results,
        neutral_alive, cf_passing, hp_to_sources,
    )
    scoreboard = load_scoreboard()
    scoreboard = merge_scoreboard(scoreboard, run_stats, source_results, ts)
    save_scoreboard(scoreboard)
    render_scoreboard_md(scoreboard, ts)
    diffs = compute_freshness_diffs(source_results)
    save_snapshots(source_results, ts)
    append_freshness_log(diffs, ts)


# FUNCTIONS

def compute_run_stats(
    source_results: list[dict],
    sample: list[tuple[str, str]],
    liveness_results: list[dict],
    neutral_alive: list[str],
    cf_passing: list[str],
    hp_to_sources: dict[str, set[str]],
) -> dict[str, dict]:
    src_proxies: dict[str, set[str]] = {r["url"]: r["proxies"] for r in source_results}

    stats = _init_stats(src_proxies)

    _count_unique_latest(stats, src_proxies, hp_to_sources)

    _count_checked(stats, sample, hp_to_sources)

    _count_alive(stats, liveness_results, hp_to_sources)

    _count_proxy_urls(stats, neutral_alive, hp_to_sources, "cf_checked")

    _count_proxy_urls(stats, cf_passing, hp_to_sources, "cf_passed")

    return stats


def load_scoreboard() -> dict:
    if SCOREBOARD_JSON.exists():
        return json.loads(SCOREBOARD_JSON.read_text(encoding="utf-8"))
    return {}


def merge_scoreboard(
    scoreboard: dict,
    run_stats: dict[str, dict],
    source_results: list[dict],
    ts: datetime,
) -> dict:
    result = dict(scoreboard)
    bucket_map = {r["url"]: r["bucket"] for r in source_results}

    for url, s in run_stats.items():
        entry = result.get(url, {
            "bucket": bucket_map.get(url, "unknown"),
            "raw_unique": 0, "checked": 0, "alive": 0,
            "cf_checked": 0, "cf_passed": 0, "unique_latest": 0, "runs": 0,
        })
        entry["raw_unique"]    += s["raw_unique"]
        entry["checked"]       += s["checked"]
        entry["alive"]         += s["alive"]
        entry["cf_checked"]    += s["cf_checked"]
        entry["cf_passed"]     += s["cf_passed"]
        entry["unique_latest"]  = s["unique_latest"]
        entry["runs"]          += 1
        result[url] = entry

    result["_meta"] = {"last_updated": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}
    return result


def save_scoreboard(scoreboard: dict) -> None:
    SCOREBOARD_JSON.write_text(
        json.dumps(scoreboard, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def render_scoreboard_md(scoreboard: dict, ts: datetime) -> None:
    entries = [(url, e) for url, e in scoreboard.items() if not url.startswith("_")]
    entries.sort(key=lambda x: _rank_score(x[1]), reverse=True)

    lines = [
        "# Proxy Source Scoreboard",
        "",
        f"Last updated: {ts.strftime('%Y-%m-%dT%H:%M:%SZ')}  |  "
        f"Sources tracked: {len(entries)}",
        "",
        f"**Rank score:** `cf_rate` if `cf_checked ≥ {CF_RATE_MIN_N}`, "
        "else `alive_rate × exclusivity` (unique_latest / raw_per_run).  ",
        "**CF-hits (abs):** absolute CF-passing count per source — early signal "
        "before cf_rate is statistically robust.",
        "",
        "| # | Source | Bucket | Raw/run | Alive% | CF-hits (abs) | CF% (n) | "
        "Unique%/run | Score | Runs |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for rank, (url, e) in enumerate(entries, 1):
        label       = _source_label(url)
        raw_per_run = e["raw_unique"] / e["runs"] if e["runs"] else 0.0
        alive_pct   = 100 * e["alive"] / e["checked"] if e["checked"] else 0.0
        cf_abs      = e["cf_passed"]
        cf_pct      = 100 * e["cf_passed"] / e["cf_checked"] if e["cf_checked"] else 0.0
        cf_n        = e["cf_checked"]
        uniq_pct    = 100 * e["unique_latest"] / raw_per_run if raw_per_run else 0.0
        score       = _rank_score(e)

        cf_abs_cell = str(cf_abs) if cf_abs > 0 else "—"
        cf_rt_cell  = f"{cf_pct:.1f}% ({cf_n})" if cf_n > 0 else f"— (0)"

        lines.append(
            f"| {rank} | `{label}` | {e['bucket']} | {raw_per_run:,.0f} | "
            f"{alive_pct:.1f}% | {cf_abs_cell} | {cf_rt_cell} | "
            f"{uniq_pct:.0f}% | {score:.4f} | {e['runs']} |"
        )

    lines.append("")
    SCOREBOARD_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Scoreboard → {SCOREBOARD_MD}")


def compute_freshness_diffs(source_results: list[dict]) -> list[dict]:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    diffs = []
    for r in source_results:
        if not r["ok"]:
            continue
        snap_path = SNAPSHOTS_DIR / f"{_source_id(r['url'])}.json"
        current   = r["proxies"]
        if snap_path.exists():
            prev  = set(json.loads(snap_path.read_text(encoding="utf-8"))["proxies"])
            new     = current - prev
            dropped = prev - current
        else:
            new     = set()
            dropped = set()
        diffs.append({
            "url": r["url"], "total": len(current),
            "new": len(new), "dropped": len(dropped),
        })
    return diffs


def save_snapshots(source_results: list[dict], ts: datetime) -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    for r in source_results:
        if not r["ok"]:
            continue
        snap_path = SNAPSHOTS_DIR / f"{_source_id(r['url'])}.json"
        snap_path.write_text(
            json.dumps({
                "url": r["url"],
                "ts":  ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "proxies": sorted(r["proxies"]),
            }, ensure_ascii=False),
            encoding="utf-8",
        )


def append_freshness_log(diffs: list[dict], ts: datetime) -> None:
    changed = [d for d in diffs if d["new"] > 0 or d["dropped"] > 0]

    lines = [f"## {ts.strftime('%Y-%m-%dT%H:%M:%SZ')}", ""]

    if not changed:
        lines += [
            "All sources unchanged since last snapshot "
            "(or first run — baseline snapshot set).",
            "",
        ]
    else:
        lines += [
            "| Source | Total | New | Dropped | New% |",
            "|---|---|---|---|---|",
        ]
        for d in sorted(changed, key=lambda x: x["new"], reverse=True):
            new_pct = 100 * d["new"] / d["total"] if d["total"] else 0.0
            lines.append(
                f"| `{_source_label(d['url'])}` | {d['total']:,} | "
                f"+{d['new']:,} | -{d['dropped']:,} | {new_pct:.1f}% |"
            )
        lines.append("")

    with FRESHNESS_LOG.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Freshness log → {FRESHNESS_LOG}")


def _init_stats(src_proxies: dict[str, set[str]]) -> dict[str, dict]:
    return {
        url: {"raw_unique": len(proxies), "checked": 0, "alive": 0,
              "cf_checked": 0, "cf_passed": 0, "unique_latest": 0}
        for url, proxies in src_proxies.items()
    }


def _count_unique_latest(
    stats: dict[str, dict],
    src_proxies: dict[str, set[str]],
    hp_to_sources: dict[str, set[str]],
) -> None:
    for url, proxies in src_proxies.items():
        stats[url]["unique_latest"] = sum(
            1 for hp in proxies if len(hp_to_sources.get(hp, set())) == 1
        )


def _count_checked(
    stats: dict[str, dict],
    sample: list[tuple[str, str]],
    hp_to_sources: dict[str, set[str]],
) -> None:
    for _proto, hp in sample:
        for src_url in hp_to_sources.get(hp, set()):
            if src_url in stats:
                stats[src_url]["checked"] += 1


def _count_alive(
    stats: dict[str, dict],
    liveness_results: list[dict],
    hp_to_sources: dict[str, set[str]],
) -> None:
    for r in liveness_results:
        if r["alive"]:
            for src_url in hp_to_sources.get(r["host_port"], set()):
                if src_url in stats:
                    stats[src_url]["alive"] += 1


def _count_proxy_urls(
    stats: dict[str, dict],
    proxy_urls: list[str],
    hp_to_sources: dict[str, set[str]],
    field: str,
) -> None:
    for purl in proxy_urls:
        hp = purl.split("://")[1]
        for src_url in hp_to_sources.get(hp, set()):
            if src_url in stats:
                stats[src_url][field] += 1


def _rank_score(entry: dict) -> float:
    if entry["cf_checked"] >= CF_RATE_MIN_N:
        return entry["cf_passed"] / entry["cf_checked"]
    alive_rate  = entry["alive"] / entry["checked"] if entry["checked"] else 0.0
    raw_per_run = entry["raw_unique"] / entry["runs"] if entry["runs"] else 1.0
    exclusivity = min(1.0, entry["unique_latest"] / raw_per_run) if raw_per_run else 0.0
    return alive_rate * exclusivity


def _source_label(url: str) -> str:
    if "proxyscrape.com" in url:
        return f"proxyscrape/{url.split('protocol=')[-1]}"
    parts = url.rstrip("/").split("/")
    return "/".join(parts[-3:]) if len(parts) >= 3 else url


def _source_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]
