# INFRASTRUCTURE
import re
from collections import Counter, defaultdict
from pathlib import Path

from dev.adhoc_persistence.deepdive_candidates import DEV, RESEARCH, era_at
from dev.adhoc_persistence.deepdive_config import DEV_PROJECT_MARKER, DOMAIN_SCALE_MIN_URLS

FETCHING_DISCOVER = re.compile(r"discover_urls\s+[\"']?https?://")
COLLECTION_ARGUMENT = re.compile(r"index_scrapes\s+(\S+)")
FILENAME_SLUG_MAX_CHARS = 100


# FUNCTIONS

def build_runs(pipe_records: list[dict], collection_dir: Path, rag_searches: list[dict], labels: dict) -> list[dict]:
    stems = {path.name for path in collection_dir.glob("*.md")} if collection_dir.exists() else set()
    hits = retrieval_events(rag_searches)
    runs = [summarize_run(run_id, members, stems, hits, labels) for run_id, members in group_by_run(pipe_records).items()]
    return sorted(runs, key=lambda run: run["first"])


def group_by_run(pipe_records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in pipe_records:
        grouped[record["run_id"]].append(record)
    return grouped


def retrieval_events(rag_searches: list[dict]) -> dict[str, list[dict]]:
    events: dict[str, list[dict]] = defaultdict(list)
    for search in rag_searches:
        for document in {hit["document"] for hit in search["hits"]}:
            events[document].append({"ts": search["ts"], "collection": search["collection"], "query": search["query"]})
    return events


def summarize_run(run_id: str, members: list[dict], stems: set[str], hits: dict, labels: dict) -> dict:
    filenames = {url_to_filename(m["url"]) for m in members}
    retrieved = sorted(name for name in filenames if name in hits)
    first = min(m["ts"] for m in members)
    label = labels["runs"].get(run_id[:8], {})
    return {
        "run_id": run_id[:8],
        "first": first,
        "host": Counter(m["domain"] for m in members).most_common(1)[0][0],
        "urls": len(filenames),
        "errors": sum(1 for m in members if m.get("error")),
        "in_collection": len(filenames & stems),
        "retrieved_documents": len(retrieved),
        "retrievals": sorted({(e["ts"][:16], e["collection"], e["query"][:70]) for name in retrieved for e in hits[name]}),
        "era": era_at(first),
        "domain_scale": len(filenames) >= DOMAIN_SCALE_MIN_URLS,
        "trigger": label.get("trigger", "unlabelled"),
        "source": label.get("source", ""),
    }


def url_to_filename(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "_", url.split("://")[-1])
    slug = re.sub(r"_+", "_", slug).strip("_")[:FILENAME_SLUG_MAX_CHARS]
    return f"{slug}.md"


def fetching_discover_calls(calls: list[dict], labels: dict) -> list[dict]:
    rows = [
        {
            "ts": c["start"],
            "session": c["session"][:8],
            "project": c["project"],
            "kind": call_kind(c["project"]),
            "seed": c["urls"][0] if c["urls"] else "",
            "purpose": labels["sessions"].get(c["session"][:8], "unlabelled"),
        }
        for c in calls
        if FETCHING_DISCOVER.search(c["command"])
    ]
    return first_per_key(rows, lambda row: (row["session"], row["seed"]))


def first_per_key(rows: list[dict], key) -> list[dict]:
    seen: dict = {}
    for row in sorted(rows, key=lambda r: r["ts"]):
        seen.setdefault(key(row), row)
    return list(seen.values())


def call_kind(project: str) -> str:
    return DEV if DEV_PROJECT_MARKER in project else RESEARCH


def index_calls(calls: list[dict], labels: dict) -> list[dict]:
    rows = [
        {
            "ts": c["start"],
            "session": c["session"][:8],
            "project": c["project"],
            "kind": call_kind(c["project"]),
            "collection": collection_of(c["command"]),
            "urls": c["urls"],
            "purpose": labels["sessions"].get(c["session"][:8], "unlabelled"),
        }
        for c in calls
        if c["urls"]
    ]
    return first_per_key(rows, lambda row: (row["session"], row["collection"], tuple(row["urls"])))


def collection_of(command: str) -> str:
    match = COLLECTION_ARGUMENT.search(command)
    return match.group(1) if match else ""
