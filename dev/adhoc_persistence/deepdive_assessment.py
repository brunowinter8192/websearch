# INFRASTRUCTURE
import json
from collections import Counter, defaultdict
from pathlib import Path

from dev.adhoc_persistence.deepdive_candidates import RESEARCH
from dev.adhoc_persistence.deepdive_config import (
    EXCLUDED_TYPES,
    LIST_EXCLUDED,
    LIST_QUALIFIES,
    LIST_SILENT,
    QUALIFYING_TYPES,
    STRONG_MIN_PAGES,
)

SERVES_YES = "yes"
SERVES_PARTIAL = "partial"
SERVES_NO = "no"
SERVES_ORDER = (SERVES_YES, SERVES_PARTIAL, SERVES_NO)
LIST_ORDER = (LIST_QUALIFIES, LIST_EXCLUDED, LIST_SILENT)
UNLABELLED = "unlabelled"


# FUNCTIONS

def load_labels(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_verdict(host_type: str) -> str:
    if host_type in QUALIFYING_TYPES:
        return LIST_QUALIFIES
    if host_type in EXCLUDED_TYPES:
        return LIST_EXCLUDED
    return LIST_SILENT


def annotate_groups(groups: list[dict], labels: dict) -> list[dict]:
    return [annotate_group(g, labels) for g in groups]


def annotate_group(group: dict, labels: dict) -> dict:
    host_type = labels["host_types"].get(group["host"], UNLABELLED)
    judgment = labels["judgments"].get(judgment_key(group))
    serves = serves_of(judgment, group) if judgment else None
    return {
        **group,
        "type": host_type,
        "list": list_verdict(host_type),
        "judgment": judgment,
        "serves": serves,
    }


def judgment_key(group: dict) -> str:
    return f"{(group['session'] or '')[:8]}:{group['host']}"


def serves_of(judgment: dict, group: dict) -> str:
    reachable = bool(group["navigated_pages"]) or bool(group["other_sessions"])
    if not (judgment["need_multi"] and reachable):
        return SERVES_NO
    return {"yes": SERVES_YES, "partly": SERVES_PARTIAL}.get(judgment["stable"], SERVES_NO)


def unlabelled_hosts(groups: list[dict]) -> list[str]:
    return sorted({g["host"] for g in groups if g["type"] == UNLABELLED})


def unjudged_candidates(candidate_groups: list[dict]) -> list[str]:
    return [judgment_key(g) for g in candidate_groups if g["judgment"] is None]


def matrix(candidate_groups: list[dict]) -> dict:
    cells: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for g in candidate_groups:
        cell = cells[(g["list"], g["serves"])]
        cell[0] += 1
        cell[1] += len(g["pages"]) >= STRONG_MIN_PAGES
    return dict(cells)


def type_counts(candidate_groups: list[dict]) -> list[tuple]:
    counter = Counter((g["type"], g["list"]) for g in candidate_groups)
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def research_groups(groups: list[dict]) -> list[dict]:
    return [g for g in groups if g["kind"] == RESEARCH]


def qualifying_singletons(groups: list[dict]) -> list[dict]:
    chosen = [g for g in research_groups(groups) if g["list"] == LIST_QUALIFIES and len(g["pages"]) == 1]
    return sorted(chosen, key=lambda g: g["first"])


def qualifying_groups(groups: list[dict]) -> list[dict]:
    return [g for g in research_groups(groups) if g["list"] == LIST_QUALIFIES]


def recurring_hosts(groups: list[dict]) -> list[dict]:
    by_host: dict[str, list[dict]] = defaultdict(list)
    for g in research_groups(groups):
        by_host[g["host"]].append(g)
    rows = [recurrence_row(host, members) for host, members in by_host.items() if len({m["session"] for m in members}) >= 2]
    return sorted(rows, key=lambda row: (-row["sessions"], row["host"]))


def recurrence_row(host: str, members: list[dict]) -> dict:
    page_sessions: dict[str, set] = defaultdict(set)
    for m in members:
        for page in m["pages"]:
            page_sessions[page].add(m["session"])
    return {
        "host": host,
        "type": members[0]["type"],
        "list": members[0]["list"],
        "sessions": len({m["session"] for m in members}),
        "pages": len(page_sessions),
        "repeated_pages": sorted(page for page, sessions in page_sessions.items() if len(sessions) >= 2),
    }


def readings(candidate_groups: list[dict]) -> list[dict]:
    rules = (
        ("A: the list as a switch (fires on qualifying types)", lambda g: g["list"] == LIST_QUALIFIES),
        ("B: the sentence alone (fires when several pages of the host were needed)", lambda g: g["judgment"]["need_multi"]),
        (
            "C: the sentence plus a perishable-content test (fires when several pages were needed and the content is not perishable)",
            lambda g: g["judgment"]["need_multi"] and g["judgment"]["stable"] != "no",
        ),
    )
    return [reading_row(name, test, candidate_groups) for name, test in rules]


def reading_row(name: str, test, candidate_groups: list[dict]) -> dict:
    fired = [g for g in candidate_groups if test(g)]
    silent = [g for g in candidate_groups if not test(g)]
    return {
        "name": name,
        "fires": len(fired),
        "fired_serves": Counter(g["serves"] for g in fired),
        "missed_useful": sum(1 for g in silent if g["serves"] in (SERVES_YES, SERVES_PARTIAL)),
    }
