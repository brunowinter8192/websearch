# INFRASTRUCTURE
import json
import re
from pathlib import Path

from dev.adhoc_persistence.deepdive_config import (
    MEASURING_PROJECT_SUFFIX,
    PROPOSAL_MARKER,
    SKILL_TEXT_MARKERS,
    TOP_LEVEL_TRANSCRIPT_GLOB,
    WEB_RESEARCH_SKILL,
)

INVOCATION_PREFIX = r"(?:^|(?<!\\)[;&|(]\s*|\n\s*)(?:time\s+)?(?:\w+=\S+\s+)*(?:\S*python\S*\s+cli\.py|websearch)\s+"
COMMAND_KINDS = {
    "scrape": re.compile(INVOCATION_PREFIX + "scrape_url_chromium"),
    "discover": re.compile(INVOCATION_PREFIX + "discover_urls"),
    "index": re.compile(INVOCATION_PREFIX + "index_scrapes"),
}
COMMAND_SUBSTRINGS = ("scrape_url_chromium", "discover_urls", "index_scrapes")
QUOTED_URL_PATTERN = re.compile(r"[\"'](https?://[^\"']+)[\"']")
BARE_URL_PATTERN = re.compile(r"https?://[^\s\"'`;|&)<>]+")
DEEP_DIVE_MENTION = re.compile(r"deep[ -]?dive", re.IGNORECASE)
RELEVANT_LINE_MARKERS = COMMAND_SUBSTRINGS + (
    '"skill"',
    "tool_result",
    "deep dive",
    "deep-dive",
    "deepdive",
    "permanent capture",
)


# FUNCTIONS

def load_transcript_facts(root: Path) -> dict:
    calls: dict[str, list[dict]] = {kind: [] for kind in COMMAND_KINDS}
    sessions: dict[str, dict] = {}
    paths = sorted(p for p in root.glob(TOP_LEVEL_TRANSCRIPT_GLOB) if not p.parent.name.endswith(MEASURING_PROJECT_SUFFIX))
    for path in paths:
        facts = read_transcript_file(path)
        for kind in COMMAND_KINDS:
            calls[kind].extend(facts["calls"][kind])
        merge_sessions(sessions, facts["sessions"])
    return {"calls": calls, "sessions": sessions, "files": len(paths), "earliest_ts": min(stamp for stamp in map(first_timestamp, paths) if stamp)}


def read_transcript_file(path: Path) -> dict:
    uses: dict[str, dict] = {}
    ends: dict[str, str] = {}
    sessions: dict[str, dict] = {}
    for record in relevant_records(path):
        session_id = record.get("sessionId")
        if not session_id:
            continue
        session = sessions.setdefault(session_id, new_session(path, record["timestamp"]))
        session["last_ts"] = record["timestamp"]
        register_skill_facts(session, record)
        collect_uses_and_ends(record, path, uses, ends)
    return {"calls": finish_calls(uses, ends), "sessions": sessions}


def first_timestamp(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stamp = json.loads(line).get("timestamp")
            if stamp:
                return stamp
    return ""


def relevant_records(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            lowered = line.lower()
            if not any(marker in lowered for marker in RELEVANT_LINE_MARKERS):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "timestamp" in record:
                yield record


def new_session(path: Path, first_ts: str) -> dict:
    return {
        "first_relevant_ts": first_ts,
        "project": path.parent.name,
        "file": path.name,
        "skill_loaded_ts": None,
        "skill_text_era": None,
        "last_ts": None,
        "agent_deep_dive_mentions": 0,
    }


def merge_sessions(target: dict, incoming: dict) -> None:
    for session_id, session in incoming.items():
        target.setdefault(session_id, session)


def register_skill_facts(session: dict, record: dict) -> None:
    content = record.get("message", {}).get("content")
    if not isinstance(content, list):
        content = [{"type": "text", "text": content}] if isinstance(content, str) else []
    for block in content:
        if is_web_research_skill_use(block) and session["skill_loaded_ts"] is None:
            session["skill_loaded_ts"] = record["timestamp"]
    if record.get("type") == "user" and session["skill_text_era"] is None:
        session["skill_text_era"] = skill_text_era(user_text(content))
    if record.get("type") == "assistant":
        session["agent_deep_dive_mentions"] += sum(
            1 for block in content
            if isinstance(block, dict) and block.get("type") == "text" and DEEP_DIVE_MENTION.search(str(block.get("text")))
        )


def is_web_research_skill_use(block: dict) -> bool:
    return (
        isinstance(block, dict)
        and block.get("type") == "tool_use"
        and block.get("name") == "Skill"
        and block.get("input", {}).get("skill", "").endswith(WEB_RESEARCH_SKILL)
    )


def user_text(content: list) -> str:
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
        if block.get("type") == "tool_result":
            parts.append(tool_result_text(block.get("content")))
    return "\n".join(parts)


def tool_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return ""


def skill_text_era(text: str) -> str | None:
    for era, marker in SKILL_TEXT_MARKERS:
        if marker in text:
            return resolve_era(era, text)
    return None


def resolve_era(era: str, text: str) -> str:
    if era != "E2_E3":
        return era
    return "E2" if PROPOSAL_MARKER in text else "E3"


def collect_uses_and_ends(record: dict, path: Path, uses: dict, ends: dict) -> None:
    content = record.get("message", {}).get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use" and block.get("name") == "Bash":
            command = block.get("input", {}).get("command", "")
            if any(pattern.search(command) for pattern in COMMAND_KINDS.values()):
                uses[block["id"]] = build_call(record, path, command)
        if block.get("type") == "tool_result" and block.get("tool_use_id"):
            ends[block["tool_use_id"]] = record["timestamp"]


def build_call(record: dict, path: Path, command: str) -> dict:
    return {
        "session": record["sessionId"],
        "project": path.parent.name,
        "cwd": record.get("cwd"),
        "start": record["timestamp"],
        "end": None,
        "command": command,
        "urls": urls_in(command),
    }


def finish_calls(uses: dict, ends: dict) -> dict[str, list[dict]]:
    calls: dict[str, list[dict]] = {kind: [] for kind in COMMAND_KINDS}
    for tool_use_id, call in uses.items():
        call["end"] = ends.get(tool_use_id)
        for kind, pattern in COMMAND_KINDS.items():
            if pattern.search(call["command"]):
                calls[kind].append(call)
    return calls


def urls_in(command: str) -> list[str]:
    quoted = QUOTED_URL_PATTERN.findall(command)
    remainder = QUOTED_URL_PATTERN.sub(" ", command)
    return quoted + BARE_URL_PATTERN.findall(remainder)
