# INFRASTRUCTURE
from dev.kvp.kvp_config import (
    COLLECTION_NAME,
    ENGINE_BLOCKED,
    ENGINE_EMPTY_NO_SIGNAL,
    ENGINE_OK,
    ENGINE_RATE_SKIP,
    ENGINE_TRANSPORT_ERROR,
    MIN_ENGINES_OK,
    SCRAPE_USABLE,
    SILENT_SCRAPE_LABELS,
)

SCRAPE_COLUMNS = (SCRAPE_USABLE, "no_content", *SILENT_SCRAPE_LABELS)
ENGINE_COLUMNS = (ENGINE_OK, ENGINE_BLOCKED, ENGINE_EMPTY_NO_SIGNAL, ENGINE_TRANSPORT_ERROR, ENGINE_RATE_SKIP)
QUERY_PREVIEW_CHARS = 60


# FUNCTIONS

def render_report(meta: dict, data: dict, searches: list[dict], scrapes: list[dict], collection_items: list[dict], counter_check: list[dict]) -> str:
    sections = [
        _render_header(meta),
        _render_ad_hoc(data["ad_hoc"]),
        _render_deep_dive(data["deep_dive"]),
        _render_silent_scrapes(scrapes),
        _render_blocked_engine_runs(searches),
        _render_flagged_collection(collection_items),
        _render_counter_check(counter_check),
        _render_not_covered(),
    ]
    return "\n\n".join(sections) + "\n"


def _render_header(meta: dict) -> str:
    counts = ", ".join(f"{name}: {count}" for name, count in meta["counts"].items())
    lines = [
        "# KVP report",
        "",
        f"- Generated: {meta['generated']}",
        f"- Window: since {meta['since'] or 'beginning'} until {meta['until'] or 'now'}",
        f"- Log dir: `{meta['log_dir']}`",
        f"- Records in window: {counts}",
        "- All verdicts are derived offline by `dev/kvp/kvp_classify.py`; the production logs hold facts only.",
        "- `code_version` is stamped on records written after the M2 change; older records appear as `unversioned`.",
    ]
    return "\n".join(lines)


def _render_ad_hoc(ad_hoc: dict) -> str:
    return "\n\n".join([
        "## Ad hoc lane",
        _render_headline_by_version(ad_hoc),
        _render_engine_table(ad_hoc["all"]["engines"]),
        _render_block_rate_by_version(ad_hoc),
        _render_scrape_labels(ad_hoc),
        _render_relevance(ad_hoc),
    ])


def _render_headline_by_version(ad_hoc: dict) -> str:
    rows = []
    for name, group in ad_hoc.items():
        search, scrape, relevance = group["search"], group["scrape"], group["relevance"]
        rows.append([
            name, search["searches"],
            _ratio(search["at_least_min_ok"], search["searches"]),
            _ratio(search["searches_with_block"], search["searches"]),
            scrape["scrapes"],
            _ratio(scrape["usable"], scrape["scrapes"]),
            _ratio(scrape["silent"], scrape["scrapes"]),
            _ratio(relevance["searches_with_scrape"], relevance["searches"]),
        ])
    headers = ["code_version", "searches", f"searches with >= {MIN_ENGINES_OK} engines OK", "searches with a blocked engine",
               "scrapes", "usable-body rate", "silent-failure rate", "searches leading to a scrape"]
    return "### Headline indicators by code version (technical and relevance)\n\n" + _table(headers, rows)


def _render_engine_table(engines: dict) -> str:
    rows = []
    for engine, counts in engines.items():
        rows.append([engine, counts["runs"], *[counts[label] for label in ENGINE_COLUMNS], _ratio(counts[ENGINE_BLOCKED], counts["runs"])])
    headers = ["engine", "runs", *ENGINE_COLUMNS, "block rate"]
    return "### Engine runs, all versions\n\n`blocked` = EMPTY with a block signal; `empty_no_signal` = EMPTY without one (true empty or unexplained).\n\n" + _table(headers, rows)


def _render_block_rate_by_version(ad_hoc: dict) -> str:
    versions = [name for name in ad_hoc if name != "all"]
    engines = sorted(ad_hoc["all"]["engines"])
    rows = []
    for engine in engines:
        cells = []
        for version in versions:
            counts = ad_hoc[version]["engines"].get(engine)
            cells.append(_ratio(counts[ENGINE_BLOCKED], counts["runs"]) if counts else "-")
        rows.append([engine, *cells])
    return "### Block rate per engine by code version\n\n" + _table(["engine", *versions], rows)


def _render_scrape_labels(ad_hoc: dict) -> str:
    rows = [[name, group["scrape"]["scrapes"], *[group["scrape"]["by_label"].get(label, 0) for label in SCRAPE_COLUMNS]] for name, group in ad_hoc.items()]
    return "### Scrape verdicts by code version\n\n" + _table(["code_version", "scrapes", *SCRAPE_COLUMNS], rows)


def _render_relevance(ad_hoc: dict) -> str:
    rows = []
    for name, group in ad_hoc.items():
        relevance = group["relevance"]
        ranks = ", ".join(f"{rank}:{count}" for rank, count in relevance["rank_counts"].items()) or "-"
        rows.append([name, relevance["searches"], relevance["drilldowns"], relevance["searches_with_scrape"], relevance["attributed_scrapes"], ranks])
    headers = ["code_version", "searches", "drilldowns", "searches with scrape", "attributed scrapes", "rank of scraped URL (rank:count)"]
    return "### Relevance: click data\n\nA scrape is attributed to a drilldown list when its URL is in the list and it happened within 3 h after the drilldown.\n\n" + _table(headers, rows)


def _render_deep_dive(deep_dive: dict) -> str:
    return "\n\n".join([
        "## Deep dive lane",
        _render_runs(deep_dive["runs"]),
        _render_collection(deep_dive["collection"]),
        _render_usefulness(deep_dive["usefulness"]),
    ])


def _render_runs(runs: list[dict]) -> str:
    rows = [
        [r["run_id"][:8], r["first_ts"][:10], ", ".join(r["domains"]), ", ".join(r["versions"]), r["urls"], r["failed"], r["zero_byte"],
         _format_dict(r["statuses"]), r["wall_ms_median"], r["in_collection"], _ratio(r["in_collection"], r["urls"])]
        for r in sorted(runs, key=lambda r: r["first_ts"])
    ]
    headers = ["run", "date", "domains", "code_version", "URLs scraped", "failed", "zero-byte", "http statuses", "wall ms median", "present in collection", "survival"]
    note = "Discovered, kept, rounds, cleanup cuts and indexed counts are not recorded anywhere (open milestone M3). Survival reads the collection as it is at report time, not as of the window."
    return "### Technical and relevance per pipe run\n\n" + note + "\n\n" + _table(headers, rows)


def _render_collection(collection: dict) -> str:
    flagged = _format_dict(collection["flagged"]) or "none"
    return (
        f"### Collection `{COLLECTION_NAME}` (unwindowed state at report time)\n\n"
        f"- Files: {collection['files']}, indexed (`.json` sibling): {collection['indexed']}\n"
        f"- Flagged files by class: {flagged}"
    )


def _render_usefulness(usefulness: dict) -> str:
    if usefulness["searches"] == 0:
        head = f"Usefulness is undefined: 0 rag-cli searches on `{COLLECTION_NAME}` in the window."
    else:
        head = (f"{usefulness['searches']} rag-cli searches on `{COLLECTION_NAME}`; "
                f"{usefulness['retrieved']} of {usefulness['indexed']} indexed documents ({_ratio(usefulness['retrieved'], usefulness['indexed'])}) appear in a hit.")
    rows = [[domain, counts["indexed"], counts["retrieved"], _ratio(counts["retrieved"], counts["indexed"])] for domain, counts in usefulness["per_domain"].items()]
    return "### Usefulness: rag-cli retrieval\n\n" + head + "\n\n" + _table(["domain", "indexed", "retrieved", "share"], rows)


def _render_silent_scrapes(scrapes: list[dict]) -> str:
    silent = [s for s in scrapes if s["verdict"].label in SILENT_SCRAPE_LABELS]
    rows = [
        [s["record"]["ts"][:19], s["record"]["url"], s["record"].get("http_status"), s["record"].get("bytes_returned"), s["verdict"].label, s["verdict"].evidence, s["record"].get("content_path") or "-"]
        for s in sorted(silent, key=lambda s: s["record"]["ts"])
    ]
    return f"## Silent failures to check\n\n### Ad hoc scrapes ({len(silent)})\n\n" + _table(["ts", "url", "status", "bytes", "class", "evidence", "sidecar"], rows)


def _render_blocked_engine_runs(searches: list[dict]) -> str:
    rows = []
    for s in sorted(searches, key=lambda s: s["record"]["ts"]):
        for engine, verdict in s["verdicts"].items():
            if verdict.label == ENGINE_BLOCKED:
                rows.append([s["record"]["ts"][:19], engine, s["record"]["query"][:QUERY_PREVIEW_CHARS], verdict.evidence])
    return f"### Engine runs recorded as EMPTY with a block signal ({len(rows)})\n\n" + _table(["ts", "engine", "query", "signals"], rows)


def _render_flagged_collection(collection_items: list[dict]) -> str:
    rows = [[c["file"]["name"], c["verdict"].label, c["verdict"].evidence] for c in collection_items if c["verdict"]]
    return f"### Collection files (unwindowed) ({len(rows)})\n\n" + _table(["file", "class", "evidence"], rows)


def _render_counter_check(counter_check: list[dict]) -> str:
    rows = [
        [c["record"]["ts"][:19], c["record"]["url"], c["record"].get("http_status"), c["record"].get("crawl4ai_success"), c["record"].get("bytes_returned")]
        for c in sorted(counter_check, key=lambda c: c["record"]["ts"])
    ]
    note = "Scrapes classified usable although `crawl4ai_success` is false or the final status is 400 or higher. Check these for false negatives."
    return f"### Counter-check: marked failed or error status, classified usable ({len(rows)})\n\n{note}\n\n" + _table(["ts", "url", "status", "crawl4ai_success", "bytes"], rows)


def _render_not_covered() -> str:
    return (
        "## Not covered\n\n"
        "- Ad hoc usefulness (from transcripts) is out of scope.\n"
        "- Deep dive discovered, kept and indexed counts need the run record of M3.\n"
        "- The classification of EMPTY without a signal is open: the report cannot tell a true empty from an unexplained one."
    )


def _table(headers: list[str], rows: list[list]) -> str:
    if not rows:
        return "(none)"
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _ratio(part: int, whole: int) -> str:
    return f"{part}/{whole} ({part / whole * 100:.1f} %)" if whole else "-"


def _format_dict(values: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items())
