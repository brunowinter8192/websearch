# INFRASTRUCTURE
import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from urllib.parse import urlparse

from dev.kvp.kvp_classify import (
    classify_collapse,
    classify_collection_file,
    classify_engine_run,
    classify_pipe_record,
    classify_scrape,
    find_duplicate_files,
)
from dev.kvp.kvp_config import (
    ATTRIBUTION_WINDOW_HOURS,
    COLLECTION_NAME,
    ENGINE_BLOCKED,
    ENGINE_EMPTY_NO_SIGNAL,
    ENGINE_OK,
    ENGINE_RATE_SKIP,
    ENGINE_TRANSPORT_ERROR,
    FOCUS_ENGINE,
    MIN_ENGINES_OK,
    PAGE_LOAD_TIMEOUT_REASON,
    SCRAPE_NO_CONTENT,
    SCRAPE_USABLE,
    SILENT_SCRAPE_LABELS,
)
from dev.kvp.kvp_load import parse_ts, version_of

ENGINE_LABELS = (ENGINE_OK, ENGINE_BLOCKED, ENGINE_EMPTY_NO_SIGNAL, ENGINE_TRANSPORT_ERROR, ENGINE_RATE_SKIP)


# FUNCTIONS

def classify_searches(summaries: list[dict]) -> list[dict]:
    return [
        {"record": s, "verdicts": {engine: classify_engine_run(stats) for engine, stats in s["engines"].items()}}
        for s in summaries
    ]


def classify_scrapes(scrapes: list[dict]) -> list[dict]:
    return [{"record": s, "verdict": classify_scrape(s, s["body"])} for s in scrapes]


def classify_pipe_records(records: list[dict]) -> list[dict]:
    return [{"record": r, "verdict": classify_pipe_record(r)} for r in records]


def classify_collection(files: list[dict]) -> list[dict]:
    duplicates = find_duplicate_files(files)
    return [{"file": f, "verdict": classify_collection_file(f["body"]) or duplicates.get(f["name"])} for f in files]


def split_by_version(items: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[version_of(item["record"])].append(item)
    return dict(sorted(groups.items()))


def search_indicators(searches: list[dict]) -> dict:
    engines_ok = [sum(1 for v in s["verdicts"].values() if v.label == ENGINE_OK) for s in searches]
    total = len(searches)
    return {
        "searches": total,
        "at_least_one_ok": sum(1 for n in engines_ok if n >= 1),
        "at_least_min_ok": sum(1 for n in engines_ok if n >= MIN_ENGINES_OK),
        "zero_results": sum(1 for s in searches if _total_results(s["record"]) == 0),
        "blocked_runs": sum(1 for s in searches for v in s["verdicts"].values() if v.label == ENGINE_BLOCKED),
        "searches_with_block": sum(1 for s in searches if any(v.label == ENGINE_BLOCKED for v in s["verdicts"].values())),
        "engine_runs": sum(len(s["verdicts"]) for s in searches),
    }


def engine_indicators(searches: list[dict]) -> dict[str, dict]:
    per_engine: dict[str, Counter] = defaultdict(Counter)
    for s in searches:
        for engine, verdict in s["verdicts"].items():
            per_engine[engine]["runs"] += 1
            per_engine[engine][verdict.label] += 1
    return dict(sorted(per_engine.items()))


def focus_engine_indicators(searches: list[dict]) -> dict[str, dict]:
    groups = {"all": searches, **split_by_version(searches)}
    return {name: _focus_engine_row(group) for name, group in groups.items()}


def scrape_indicators(scrapes: list[dict]) -> dict:
    labels = Counter(item["verdict"].label for item in scrapes)
    total = len(scrapes)
    silent = sum(labels[label] for label in SILENT_SCRAPE_LABELS)
    return {
        "scrapes": total,
        "usable": labels[SCRAPE_USABLE],
        "silent": silent,
        "no_content": labels[SCRAPE_NO_CONTENT],
        "by_label": dict(sorted(labels.items())),
    }


def collapse_searches(searches: list[dict]) -> list[dict]:
    rows = []
    for search in searches:
        record, verdicts = search["record"], search["verdicts"]
        if sum(1 for v in verdicts.values() if v.label == ENGINE_OK) >= MIN_ENGINES_OK:
            continue
        rows.append(_collapse_row(record, verdicts))
    return sorted(rows, key=lambda row: row["ts"])


def scrape_counter_check(scrapes: list[dict]) -> list[dict]:
    return [
        item for item in scrapes
        if item["verdict"].label == SCRAPE_USABLE
        and (item["record"].get("crawl4ai_success") is False or (item["record"].get("http_status") or 0) >= 400)
    ]


def relevance_indicators(searches: list[dict], drilldowns: list[dict], scrapes: list[dict]) -> dict:
    keys = {s["record"]["search_key"] for s in searches}
    own_drilldowns = [d for d in drilldowns if d.get("search_key") in keys]
    hit_keys, ranks = _attribute_scrapes(own_drilldowns, scrapes)
    return {
        "searches": len(searches),
        "drilldowns": len(own_drilldowns),
        "searches_with_scrape": len(hit_keys),
        "rank_counts": dict(sorted(Counter(ranks).items())),
        "attributed_scrapes": len(ranks),
    }


def deep_dive_run_indicators(pipe_items: list[dict], collection_items: list[dict]) -> list[dict]:
    url_to_file = {normalize_url(c["file"]["source_url"]): c["file"]["name"] for c in collection_items if c["file"]["source_url"]}
    runs: dict[str, list[dict]] = defaultdict(list)
    for item in pipe_items:
        runs[item["record"]["run_id"]].append(item)
    return [_run_indicators(run_id, items, url_to_file) for run_id, items in runs.items()]


def collection_indicators(collection_items: list[dict]) -> dict:
    flagged = Counter(c["verdict"].label for c in collection_items if c["verdict"])
    return {
        "files": len(collection_items),
        "indexed": sum(1 for c in collection_items if c["file"]["indexed"]),
        "flagged": dict(sorted(flagged.items())),
    }


def usefulness_indicators(collection_items: list[dict], rag_searches: list[dict]) -> dict:
    searches = [s for s in rag_searches if s.get("collection") == COLLECTION_NAME]
    hit_documents = {h["document"] for s in searches for h in s.get("hits", [])}
    per_domain: dict[str, Counter] = defaultdict(Counter)
    for item in collection_items:
        if not item["file"]["indexed"]:
            continue
        domain = _domain_of(item["file"]["source_url"])
        per_domain[domain]["indexed"] += 1
        per_domain[domain]["retrieved"] += item["file"]["name"] in hit_documents
    return {
        "searches": len(searches),
        "indexed": sum(c["indexed"] for c in per_domain.values()),
        "retrieved": sum(c["retrieved"] for c in per_domain.values()),
        "per_domain": dict(sorted(per_domain.items(), key=lambda kv: -kv[1]["indexed"])),
    }


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{(parsed.hostname or '').lower()}{parsed.path.rstrip('/')}" + (f"?{parsed.query}" if parsed.query else "")


def _collapse_row(record: dict, verdicts: dict) -> dict:
    engines = record["engines"]
    completed = [stats["search_ms"] for stats in engines.values() if not stats["status"].startswith("TIMEOUT")]
    pattern = classify_collapse(engines)
    return {
        "ts": record["ts"],
        "version": version_of(record),
        "ok": sum(1 for v in verdicts.values() if v.label == ENGINE_OK),
        "wall_ms": record["total_wall_ms"],
        "overhead_ms": record["total_wall_ms"] - max(stats["search_ms"] for stats in engines.values()),
        "median_completed_ms": round(statistics.median(completed)) if completed else None,
        "pattern": pattern.label,
        "evidence": pattern.evidence,
        "host": record.get("host"),
    }


def _focus_engine_row(searches: list[dict]) -> dict:
    labels: Counter = Counter()
    ok_ms: list[int] = []
    for search in searches:
        stats = search["record"]["engines"].get(FOCUS_ENGINE)
        if stats is None:
            continue
        labels[_focus_label(stats, search["verdicts"][FOCUS_ENGINE].label)] += 1
        if stats["status"] == "OK":
            ok_ms.append(stats["search_ms"])
    ordered = sorted(ok_ms)
    return {
        "runs": sum(labels.values()),
        "labels": dict(labels),
        "ok_median_ms": round(statistics.median(ordered)) if ordered else None,
        "ok_p90_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))] if ordered else None,
    }


def _focus_label(stats: dict, verdict_label: str) -> str:
    if stats["status"] == "ERROR_BROWSER" and stats.get("drop_reason") == PAGE_LOAD_TIMEOUT_REASON:
        return "page_load_timeout"
    if stats["status"].startswith("TIMEOUT"):
        return "timeout"
    return verdict_label


def _total_results(record: dict) -> int:
    return sum(stats.get("result_count", 0) for stats in record["engines"].values())


def _attribute_scrapes(drilldowns: list[dict], scrapes: list[dict]) -> tuple[set[str], list[int]]:
    window = timedelta(hours=ATTRIBUTION_WINDOW_HOURS)
    prepared = [(parse_ts(d["ts"]), [normalize_url(u) for u in d["urls"]], d) for d in drilldowns]
    hit_keys: set[str] = set()
    ranks: list[int] = []
    for scrape in scrapes:
        scrape_ts, scrape_url = parse_ts(scrape["ts"]), normalize_url(scrape["url"])
        matches = [(ts, urls, d) for ts, urls, d in prepared if ts <= scrape_ts <= ts + window and scrape_url in urls]
        hit_keys.update(d["search_key"] for _, _, d in matches)
        if matches:
            ts, urls, _ = max(matches, key=lambda m: m[0])
            ranks.append(urls.index(scrape_url) + 1)
    return hit_keys, ranks


def _run_indicators(run_id: str, items: list[dict], url_to_file: dict[str, str]) -> dict:
    records = [i["record"] for i in items]
    in_collection = sum(1 for r in records if _record_in_collection(r, url_to_file))
    return {
        "run_id": run_id,
        "first_ts": min(r["ts"] for r in records),
        "domains": sorted({r["domain"] for r in records}),
        "versions": sorted({version_of(r) for r in records}),
        "urls": len(records),
        "failed": sum(1 for i in items if i["verdict"].label != SCRAPE_USABLE),
        "zero_byte": sum(1 for r in records if not r.get("bytes")),
        "statuses": dict(sorted(Counter(str(r.get("http_status")) for r in records).items())),
        "wall_ms_median": round(statistics.median(r["wall_ms"] for r in records)),
        "in_collection": in_collection,
    }


def _record_in_collection(record: dict, url_to_file: dict[str, str]) -> bool:
    candidates = [record["url"], record.get("landed_url")]
    return any(normalize_url(u) in url_to_file for u in candidates if u)


def _domain_of(url: str | None) -> str:
    return (urlparse(url).hostname or "unknown").removeprefix("www.") if url else "unknown"


def compute_report_data(
    searches: list[dict], scrapes: list[dict], drilldowns: list[dict], attribution_scrapes: list[dict],
    pipe_items: list[dict], collection_items: list[dict], rag_searches: list[dict],
) -> dict:
    search_groups, scrape_groups = split_by_version(searches), split_by_version(scrapes)
    groups = {"all": (searches, scrapes)}
    for version in sorted(set(search_groups) | set(scrape_groups)):
        groups[version] = (search_groups.get(version, []), scrape_groups.get(version, []))
    return {
        "ad_hoc": {
            name: {
                "search": search_indicators(group_searches),
                "engines": engine_indicators(group_searches),
                "scrape": scrape_indicators(group_scrapes),
                "relevance": relevance_indicators(group_searches, drilldowns, attribution_scrapes),
            }
            for name, (group_searches, group_scrapes) in groups.items()
        },
        "collapse": collapse_searches(searches),
        "focus_engine": focus_engine_indicators(searches),
        "deep_dive": {
            "runs": deep_dive_run_indicators(pipe_items, collection_items),
            "collection": collection_indicators(collection_items),
            "usefulness": usefulness_indicators(collection_items, rag_searches),
        },
    }
