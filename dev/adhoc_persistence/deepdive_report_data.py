# INFRASTRUCTURE
from collections import Counter
from datetime import datetime, timezone

from dev.adhoc_persistence.deepdive_assessment import (
    qualifying_groups,
    recurring_hosts,
    research_groups,
    matrix,
    readings,
)
from dev.adhoc_persistence.deepdive_candidates import DEV, RESEARCH, UNATTRIBUTED, candidates, era_at, registrable_only_candidates
from dev.adhoc_persistence.deepdive_config import DOMAIN_SCALE_MIN_URLS, MIN_PAGES
from dev.adhoc_persistence.deepdive_deepdives import fetching_discover_calls, index_calls
from dev.kvp.kvp_load import parse_ts

RULE_E3_START = "2026-10-11T11:58:39Z"


# FUNCTIONS

def build_report_data(joined: list[dict], groups: list[dict], facts: dict, runs: list[dict], labels: dict, rag_searches: list[dict]) -> dict:
    research_candidates = candidates(groups, RESEARCH)
    return {
        "meta": build_meta(joined, groups, facts),
        "candidates": research_candidates,
        "matrix": matrix(research_candidates),
        "readings": readings(research_candidates),
        "qualifying": qualifying_groups(groups),
        "recurring": recurring_hosts(groups),
        "registrable_extra": registrable_only_candidates(groups, RESEARCH),
        "runs": runs,
        "reuse": reuse_by_scale(runs),
        "domain_scale_min": DOMAIN_SCALE_MIN_URLS,
        "rag_first": min(s["ts"] for s in rag_searches),
        "discover_fetches": fetching_discover_calls(facts["calls"]["discover"], labels),
        "index_calls": index_calls(facts["calls"]["index"], labels),
        "dev_groups": [g for g in groups if g["kind"] == DEV],
        "unattributed_candidates": candidates(groups, UNATTRIBUTED),
        "host_types": labels["host_types"],
    }


def build_meta(joined: list[dict], groups: list[dict], facts: dict) -> dict:
    research = research_groups(groups)
    research_sessions = {g["session"] for g in research}
    sessions = facts["sessions"]
    kinds = Counter(g["kind"] for g in groups)
    scrape_kinds = Counter(kind_of_record(r, facts) for r in joined)
    research_records = [r for r in joined if kind_of_record(r, facts) == RESEARCH]
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scrape_first": min(r["ts"] for r in joined),
        "scrape_last": max(r["ts"] for r in joined),
        "transcripts_earliest": facts["earliest_ts"],
        "transcript_files": facts["files"],
        "transcript_sessions": len(sessions),
        "scrapes": len(joined),
        "matched": sum(1 for r in joined if r["call"]),
        "research_scrapes": scrape_kinds[RESEARCH],
        "dev_scrapes": scrape_kinds[DEV],
        "unattributed": scrape_kinds[UNATTRIBUTED],
        "groups_by_kind": dict(kinds),
        "research_sessions": len(research_sessions),
        "research_sessions_with_skill": sum(1 for s in research_sessions if sessions[s]["skill_loaded_ts"]),
        "research_sessions_with_mention": sum(1 for s in research_sessions if sessions[s]["agent_deep_dive_mentions"]),
        "research_single_groups": sum(1 for g in research if len(g["pages"]) < MIN_PAGES),
        "research_multi_groups": sum(1 for g in research if len(g["pages"]) >= MIN_PAGES),
        "research_scrapes_e3_plus": sum(1 for r in research_records if parse_ts(r["ts"]) >= parse_ts(RULE_E3_START)),
        "research_scrapes_e2": sum(1 for r in research_records if era_at(r["ts"]) == "E2"),
        "research_scrapes_e1": sum(1 for r in research_records if era_at(r["ts"]) == "E1"),
        "research_scrapes_e0": sum(1 for r in research_records if era_at(r["ts"]) == "E0"),
        "mention_sessions": sorted(
            (s[:8], sessions[s]["agent_deep_dive_mentions"]) for s in research_sessions if sessions[s]["agent_deep_dive_mentions"]
        ),
        "days_since_e3": (parse_ts(max(r["ts"] for r in joined)) - parse_ts(RULE_E3_START)).days,
        "dev_groups": kinds[DEV],
    }


def reuse_by_scale(runs: list[dict]) -> dict:
    rows = {}
    for scale, flag in (("domain", True), ("pick", False)):
        chosen = [r for r in runs if r["domain_scale"] is flag]
        rows[scale] = {
            "runs": len(chosen),
            "urls": sum(r["urls"] for r in chosen),
            "in_collection": sum(r["in_collection"] for r in chosen),
            "retrieved": sum(r["retrieved_documents"] for r in chosen),
        }
    return rows


def kind_of_record(record: dict, facts: dict) -> str:
    call = record["call"]
    if not call:
        return UNATTRIBUTED
    return DEV if "cli-websearch" in call["project"] else RESEARCH
