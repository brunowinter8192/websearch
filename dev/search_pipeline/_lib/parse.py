# INFRASTRUCTURE
import ast
import re
from collections import defaultdict
from pathlib import Path

KNOWN_ENGINES = {
    "google", "duckduckgo", "mojeek", "lobsters",
    "google_scholar", "openalex", "crossref", "stack_exchange",
}


# FUNCTIONS

def parse_smoke_report(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict] = []
    state = {
        "query":   None,
        "record":  None,
        "counter": 0,
        "seen":    {},
        "pos":     defaultdict(int),
    }

    for line in lines:
        if _handle_query_header(line, state):
            continue
        if _handle_url_entry(line, state, records):
            continue
        if state["record"] is None:
            continue
        _apply_field_line(line, state["record"])

    if state["record"] is not None:
        records.append(state["record"])
    return records


def _handle_query_header(line: str, state: dict) -> bool:
    m = re.match(r'^## Q\d+: (.+)$', line)
    if not m:
        return False
    state["query"] = m.group(1).strip()
    if state["query"] not in state["seen"]:
        state["counter"] += 1
        state["seen"][state["query"]] = state["counter"]
    return True


def _handle_url_entry(line: str, state: dict, records: list[dict]) -> bool:
    m = re.match(r'^\d+\. \*\*\[([A-Z]+)\]\*\* (.+)$', line)
    if not m:
        return False
    if state["record"] is not None:
        records.append(state["record"])
    cls   = m.group(1)
    title = m.group(2).strip()
    qi    = state["seen"].get(state["query"], 0)
    state["pos"][state["query"]] += 1
    pos   = state["pos"][state["query"]]
    state["record"] = {
        "query":    state["query"],
        "class":    cls,
        "title":    title,
        "url":      None,
        "engines":  [],
        "source":   "",
        "display":  "",
        "og":       None,
        "meta":     None,
        "snippets": {},
        "_qi":      qi,
        "_pos":     pos,
    }
    return True


def _apply_field_line(line: str, record: dict) -> None:
    m = re.match(r'^\s+URL: (https?://\S+)', line)
    if m:
        record["url"] = m.group(1)
        return

    m = re.match(r'^\s+Engines: (.+)$', line)
    if m:
        record["engines"] = [e.strip() for e in m.group(1).split(",")]
        return

    m = re.match(r'^\s+source: (\S+) \| display: (.+)$', line)
    if m:
        record["source"]  = m.group(1)
        record["display"] = _repr_unquote(m.group(2))
        return

    m = re.match(r'^\s+og: (.*)', line)
    if m:
        rest = m.group(1)
        if ' | meta: ' in rest:
            og_part, meta_part = rest.split(' | meta: ', 1)
        else:
            og_part, meta_part = rest, "—"
        record["og"]   = None if og_part.strip()   == "—" else og_part.strip()
        record["meta"] = None if meta_part.strip() == "—" else meta_part.strip()
        return

    m = re.match(r'^\s+(\w+): (.+)$', line)
    if m:
        eng = m.group(1).lower()
        if eng in KNOWN_ENGINES:
            record["snippets"][eng] = _repr_unquote(m.group(2))


def _repr_unquote(s: str) -> str:
    s = s.strip()
    return ast.literal_eval(s)
