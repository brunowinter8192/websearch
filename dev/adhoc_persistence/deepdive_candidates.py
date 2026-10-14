# INFRASTRUCTURE
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from dev.adhoc_persistence.deepdive_config import (
    DEV_PROJECT_MARKER,
    ERAS,
    MIN_PAGES,
    OFFER_WINDOW_HOURS,
    STRONG_MIN_PAGES,
)
from dev.adhoc_persistence.deepdive_join import normalize_url
from dev.kvp.kvp_classify import classify_scrape
from dev.kvp.kvp_config import SCRAPE_USABLE
from dev.kvp.kvp_load import load_window, parse_ts

UNATTRIBUTED = "unattributed"
RESEARCH = "research"
DEV = "dev"


# FUNCTIONS

def classify_records(records: list[dict]) -> list[dict]:
    return [{**r, "verdict": classify_scrape(r, r["body"]).label} for r in records]


def load_drilldowns(path: Path) -> list[dict]:
    return [r for r in load_window(path, None, None) if r["record_type"] == "drilldown"]


def mark_offered(records: list[dict], drilldowns: list[dict]) -> list[dict]:
    offers = [(parse_ts(d["ts"]), {normalize_url(u) for u in d["urls"]}) for d in drilldowns]
    return [{**r, "offered": was_offered(r, offers)} for r in records]


def was_offered(record: dict, offers: list[tuple]) -> bool:
    scraped_at = parse_ts(record["ts"])
    wanted = normalize_url(record["url"])
    window = timedelta(hours=OFFER_WINDOW_HOURS)
    return any(offered_at <= scraped_at <= offered_at + window and wanted in urls for offered_at, urls in offers)


def build_groups(joined: list[dict], sessions: dict) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for record in joined:
        buckets[group_key(record)].append(record)
    return [summarize_group(key, members, sessions) for key, members in buckets.items()]


def group_key(record: dict) -> tuple:
    call = record["call"]
    if call:
        return call["session"], record["domain"], None
    return None, record["domain"], record["ts"][:10]


def summarize_group(key: tuple, members: list[dict], sessions: dict) -> dict:
    session_id, host, day = key
    session = sessions.get(session_id, {}) if session_id else {}
    project = members[0]["call"]["project"] if session_id else None
    first = min(m["ts"] for m in members)
    return {
        "session": session_id,
        "project": project,
        "host": host,
        "registrable": registrable_domain(host),
        "day": day or first[:10],
        "pages": sorted({normalize_url(m["url"]) for m in members}),
        "usable_pages": sorted({normalize_url(m["url"]) for m in members if m["verdict"] == SCRAPE_USABLE}),
        "navigated_pages": sorted({normalize_url(m["url"]) for m in members if not m["offered"]}),
        "scrapes": len(members),
        "first": first,
        "last": max(m["ts"] for m in members),
        "era": era_at(first),
        "skill_loaded": bool(session.get("skill_loaded_ts")),
        "skill_text_era": session.get("skill_text_era"),
        "kind": kind_of(session_id, project),
    }


def add_recurrence(groups: list[dict]) -> list[dict]:
    return [{**g, **recurrence_of(g, groups)} for g in groups]


def recurrence_of(group: dict, groups: list[dict]) -> dict:
    others = [o for o in groups if o["host"] == group["host"] and o is not group and o["kind"] == RESEARCH]
    other_sessions = sorted({o["session"] for o in others if o["session"] != group["session"]})
    shared = sorted({page for o in others for page in o["pages"] if page in group["pages"] and o["session"] != group["session"]})
    return {"other_sessions": other_sessions, "shared_pages": shared}


def kind_of(session_id: str | None, project: str | None) -> str:
    if not session_id:
        return UNATTRIBUTED
    return DEV if DEV_PROJECT_MARKER in project else RESEARCH


def registrable_domain(host: str) -> str:
    return ".".join(host.split(".")[-2:])


def era_at(ts: str) -> str:
    moment = parse_ts(ts)
    for name, start, end, _ in ERAS:
        after_start = start is None or moment >= parse_ts(start)
        before_end = end is None or moment < parse_ts(end)
        if after_start and before_end:
            return name
    raise ValueError(f"no era for {ts}")


def candidates(groups: list[dict], kind: str, min_pages: int = MIN_PAGES) -> list[dict]:
    chosen = [g for g in groups if g["kind"] == kind and len(g["pages"]) >= min_pages]
    return sorted(chosen, key=lambda g: g["first"])


def strong(groups: list[dict]) -> list[dict]:
    return [g for g in groups if len(g["pages"]) >= STRONG_MIN_PAGES]


def registrable_only_candidates(groups: list[dict], kind: str) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for g in groups:
        if g["kind"] != kind:
            continue
        key = (g["session"], g["registrable"], g["day"] if g["session"] is None else None)
        bucket = merged.setdefault(key, {**g, "host": g["registrable"], "pages": set(), "hosts": set()})
        bucket["pages"].update(g["pages"])
        bucket["hosts"].add(g["host"])
    host_level = {(g["session"], g["host"]) for g in candidates(groups, kind)}
    extra = [
        {**b, "pages": sorted(b["pages"]), "hosts": sorted(b["hosts"])}
        for b in merged.values()
        if len(b["pages"]) >= MIN_PAGES and not any((b["session"], h) in host_level for h in b["hosts"])
    ]
    return sorted(extra, key=lambda g: g["first"])
