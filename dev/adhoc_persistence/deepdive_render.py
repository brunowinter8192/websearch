# INFRASTRUCTURE
from collections import Counter

from dev.adhoc_persistence.deepdive_assessment import (
    LIST_ORDER,
    SERVES_NO,
    SERVES_ORDER,
    SERVES_PARTIAL,
    SERVES_YES,
    type_counts,
)
from dev.adhoc_persistence.deepdive_candidates import DEV, RESEARCH, UNATTRIBUTED, strong
from dev.adhoc_persistence.deepdive_config import ERAS, LIST_EXCLUDED, LIST_QUALIFIES, LIST_SILENT, MIN_PAGES, STRONG_MIN_PAGES

PROJECT_PREFIX = "-Users-brunowinter2000-Documents-"
LIST_LABELS = {
    LIST_QUALIFIES: "list: qualifies",
    LIST_EXCLUDED: "list: excluded",
    LIST_SILENT: "list: silent",
}


# FUNCTIONS

def render_report(data: dict) -> str:
    sections = [
        render_header(data),
        render_summary(data),
        render_method(data),
        render_base(data),
        render_candidates(data),
        render_matrix(data),
        render_readings(data),
        render_qualifying(data),
        render_recurrence(data),
        render_deep_dives(data),
        render_ad_hoc_indexing(data),
        render_patch_decision(data),
        render_limits(data),
        render_appendix(data),
    ]
    return "\n\n".join(sections) + "\n"


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def short_project(project: str | None) -> str:
    if not project:
        return "-"
    return project.removeprefix(PROJECT_PREFIX).replace("--claude-worktrees-", "~")[:34]


def short_host_pages(pages: list[str]) -> str:
    return "<br>".join(page[:96] for page in pages)


def render_header(data: dict) -> str:
    meta = data["meta"]
    return (
        "# Deep dive rule measurement\n\n"
        f"Generated {meta['generated']} by `dev/adhoc_persistence/deepdive_rule_measurement.py`. "
        f"Scrape log window {meta['scrape_first'][:10]} .. {meta['scrape_last'][:10]}, "
        f"transcripts from {meta['transcripts_earliest'][:10]} ({meta['transcript_files']} files, {meta['transcript_sessions']} sessions with relevant lines)."
    )


def render_summary(data: dict) -> str:
    m = data["meta"]
    cands = data["candidates"]
    yes_partial = [g for g in cands if g["serves"] in (SERVES_YES, SERVES_PARTIAL)]
    qualifying = data["qualifying"]
    unattributed_qualifying = [g for g in data["unattributed_candidates"] if g["list"] == LIST_QUALIFIES]
    domain, pick = data["reuse"]["domain"], data["reuse"]["pick"]
    lines = [
        "## Answer in short",
        "",
        f"- **Base.** {m['scrapes']} ad hoc scrape records; {m['matched']} matched to an agent transcript "
        f"({m['research_scrapes']} in research sessions, {m['dev_scrapes']} in sessions inside the websearch repo), "
        f"{m['unattributed']} without transcript.",
        f"- **The current rule never met a research session.** Research-session scrapes by era of the first scrape: "
        f"E0 {m['research_scrapes_e0']}, E1 {m['research_scrapes_e1']}, E2 {m['research_scrapes_e2']}, E3 or E4 {m['research_scrapes_e3_plus']}. "
        "Every behavior measured here happened under an older text. What the 2026-10-11 rule would have done is a counterfactual.",
        f"- **Candidates** (research session, at least {MIN_PAGES} distinct pages of one host): "
        f"{len(cands)} in {len({g['session'] for g in cands})} sessions on {len({g['host'] for g in cands})} hosts; "
        f"{len(strong(cands))} with at least {STRONG_MIN_PAGES} pages.",
        f"- **By the rule's list.** {count_list(cands, LIST_QUALIFIES)} qualifying type, {count_list(cands, LIST_EXCLUDED)} excluded type, "
        f"{count_list(cands, LIST_SILENT)} type the list does not mention (all of them {silent_types(cands)}).",
        f"- **Would a deep dive have served** (my judgment, see Method): yes {count_serves(cands, SERVES_YES)}, "
        f"partial {count_serves(cands, SERVES_PARTIAL)}, no {count_serves(cands, SERVES_NO)}.",
        "- **Where it would have served at least partly:** "
        + "; ".join(f"{g['session'][:8]} {g['host']} ({g['type']}, {LIST_LABELS[g['list']]}, {g['serves']})" for g in yes_partial) + ".",
        f"- **Reading of the list.** The list has no hit on the cases where a deep dive would have served: of the {len(yes_partial)}, "
        f"{sum(1 for g in yes_partial if g['list'] == LIST_SILENT)} are silent and {sum(1 for g in yes_partial if g['list'] == LIST_EXCLUDED)} excluded. "
        f"It does remove {count_serves_excluded(cands)} of the {count_serves(cands, SERVES_NO)} cases that would not have served.",
        f"- **The list's positive class is barely observed.** Research host-session pairs of a documentation or manual type: {len(qualifying)}, "
        f"{sum(1 for g in qualifying if len(g['pages']) == 1)} with a single page. "
        f"One unattributed cluster of a qualifying type exists ({', '.join(g['host'] for g in unattributed_qualifying) or 'none'}), without transcript."
        if unattributed_qualifying else
        f"- **The list's positive class is barely observed.** Research host-session pairs of a documentation or manual type: {len(qualifying)}.",
        f"- **Deep dives that happened.** {len(data['runs'])} pipe runs (2026-08-24 .. 2026-10-11), {domain['runs']} of domain scale and {pick['runs']} hand-picked captures. "
        f"{len(data['discover_fetches'])} distinct `discover_urls` fetches, none in a research session, none after an agent applied the rule; "
        "the only run with a recorded trigger of the capture skill is sre.google, started by the orchestrator on the owner's request.",
        f"- **Reuse of captured pages.** Domain-scale runs: {domain['retrieved']} documents of {domain['in_collection']} in the collection appeared in a rag-cli hit list "
        f"(one of the retrieval events is the orchestrator's own check of the sre.google capture). Hand-picked runs: {pick['retrieved']} of {pick['in_collection']}.",
        f"- **Agent behavior.** {m['research_sessions']} research sessions, {m['research_sessions_with_skill']} activated the web research skill. "
        f"Agent text containing \"deep dive\" in {m['research_sessions_with_mention']} of them ({format_mentions(m['mention_sessions'])}); "
        "none of these is a proposal of the capture workflow (read in the transcript).",
        "- Details, limits and the patch decision follow below.",
    ]
    return "\n".join(lines)


def silent_types(cands: list[dict]) -> str:
    return ", ".join(sorted({g["type"] for g in cands if g["list"] == LIST_SILENT}))


def count_serves_excluded(cands: list[dict]) -> int:
    return sum(1 for g in cands if g["list"] == LIST_EXCLUDED and g["serves"] == SERVES_NO)


def format_mentions(mention_sessions: list) -> str:
    return ", ".join(f"{session}: {count}" for session, count in mention_sessions) or "none"


def count_list(cands: list[dict], verdict: str) -> int:
    return sum(1 for g in cands if g["list"] == verdict)


def count_serves(cands: list[dict], serves: str) -> int:
    return sum(1 for g in cands if g["serves"] == serves)


def render_method(data: dict) -> str:
    era_rows = [[name, start or "-", end or "-", text] for name, start, end, text in ERAS]
    return "\n".join([
        "## Method",
        "",
        "- **Join.** Each `scrape_log.jsonl` record is matched to a `scrape_url_chromium` Bash call in a Claude Code transcript when the normalized URL "
        "is one of the call's URLs and the record timestamp lies between the call's `tool_use` timestamp minus 30 s and its `tool_result` timestamp plus 30 s.",
        "- **Session.** The transcript `sessionId`. A session counts as a **dev session** when its project directory belongs to the websearch repo "
        "(main checkout or a worktree). Those sessions are listed only in the appendix. Records without a transcript match are **unattributed** and never become candidates.",
        f"- **Candidate.** Research session, one host (the log's `domain`, `www.` stripped), at least {MIN_PAGES} distinct normalized URLs. Second column: at least {STRONG_MIN_PAGES}. "
        "Pages are counted whatever their verdict (login wall, 404 included), the usable count is shown next to it.",
        "- **Navigated pages.** Pages of the candidate that no `search_engine_drilldown` listed in the 3 hours before the scrape. The agent reached them by a link, a guessed URL or a URL the user gave.",
        "- **Other sessions.** Other research sessions in which the same host was scraped.",
        "- **Type and list verdict.** My hand label per host (`deepdive_labels.json`, all hosts listed in the appendix). "
        "Types `docs` and `vendor_manual` are *qualifies*, `blog`, `news`, `forum`, `product`, `changelog`, `release_feed` are *excluded*, everything else is *silent* (the rule's list does not mention it).",
        "- **Judgment.** Mine, single rater, from reading the transcript around the scrapes. Two inputs: *needed several pages* (did the question need more than one page of the host) and "
        "*stable* (yes, partly, no: does the needed content stay valid for months, or is it a price, stock, deadline, status or search result). "
        "*Serves* is derived: **no** if several pages were not needed or if the pages were neither navigated nor seen in another session; otherwise **yes** if stable, **partial** if partly stable, **no** if not stable.",
        "- **Rule text per session.** `Rule text seen` is read from the skill text injected into the session when there is one, otherwise `-`. `Era` is the era of the first scrape by commit time of `SKILL.md`.",
        "",
        table(["Era", "From (UTC)", "Until (UTC)", "Skill text"], era_rows),
    ])


def render_base(data: dict) -> str:
    m = data["meta"]
    kind_rows = [[kind, m["groups_by_kind"].get(kind, 0)] for kind in (RESEARCH, DEV, UNATTRIBUTED)]
    return "\n".join([
        "## Base of the measurement",
        "",
        table(["Kind", "Host-session groups"], kind_rows),
        "",
        f"- Research sessions with at least one scrape: {m['research_sessions']}. "
        f"Sessions that activated the web research skill: {m['research_sessions_with_skill']}. "
        f"Sessions with an agent text containing \"deep dive\": {m['research_sessions_with_mention']}.",
        f"- Research host-session groups with one page: {m['research_single_groups']}, with {MIN_PAGES} or more: {m['research_multi_groups']}.",
        f"- Grouping by registrable domain instead of host adds {len(data['registrable_extra'])} further candidates"
        + (": " + ", ".join(f"{g['host']} ({'+'.join(g['hosts'])})" for g in data['registrable_extra']) if data['registrable_extra'] else "") + ".",
    ])


def render_candidates(data: dict) -> str:
    rows = []
    for g in data["candidates"]:
        rows.append([
            g["session"][:8], short_project(g["project"]), g["first"][:10], g["era"], g["skill_text_era"] or "-",
            g["host"], g["type"], LIST_LABELS[g["list"]],
            f"{len(g['pages'])} ({len(g['usable_pages'])})", "x" if len(g["pages"]) >= STRONG_MIN_PAGES else "",
            len(g["navigated_pages"]), len(g["other_sessions"]),
            "yes" if g["judgment"]["need_multi"] else "no", g["judgment"]["stable"], g["serves"],
        ])
    notes = [f"- `{g['session'][:8]}:{g['host']}` ({g['serves']}): {g['judgment']['reason']}" for g in data["candidates"]]
    return "\n".join([
        "## Candidates: research sessions with several pages of one host",
        "",
        table(
            ["Session", "Project", "Date", "Era", "Text seen", "Host", "Type", "List", "Pages (usable)", f"{STRONG_MIN_PAGES}+",
             "Navigated", "Other sessions", "Needed several", "Stable", "Serves"],
            rows,
        ),
        "",
        "Reasons per row:",
        "",
        *notes,
    ])


def render_matrix(data: dict) -> str:
    cells = data["matrix"]
    rows = []
    for verdict in LIST_ORDER:
        rows.append([LIST_LABELS[verdict]] + [format_cell(cells.get((verdict, serves))) for serves in SERVES_ORDER])
    type_rows = [[host_type, LIST_LABELS[verdict], count] for (host_type, verdict), count in type_counts(data["candidates"])]
    return "\n".join([
        "## The rule's list against the judgment",
        "",
        f"Cell = candidates (of which with {STRONG_MIN_PAGES} or more pages).",
        "",
        table(["List verdict \\ deep dive would serve", *SERVES_ORDER], rows),
        "",
        "Reading: a *qualifies* row with *no* is a deep dive the list would trigger without use (false alarm). An *excluded* row with *yes* or *partial* is a deep dive the list would suppress although it would have served (miss). "
        "The *silent* row is where the list decides nothing and the sentence \"other URLs of the domain could be relevant\" has to carry the decision.",
        "",
        table(["Type", "List", "Candidates"], type_rows),
    ])


def render_readings(data: dict) -> str:
    rows = [
        [
            r["name"], r["fires"], r["fired_serves"].get(SERVES_YES, 0), r["fired_serves"].get(SERVES_PARTIAL, 0),
            r["fired_serves"].get(SERVES_NO, 0), r["missed_useful"],
        ]
        for r in data["readings"]
    ]
    return "\n".join([
        "## Three readings of the rule on the same candidates",
        "",
        "The 2026-10-11 rule is a sentence plus a list marked \"meist\". Three ways an agent could apply it, scored on the candidates above. "
        "Reading C is not the current rule; it shows what one added test would change. Its input (*stable*) is my own judgment, so reading C is not independent of the labels.",
        "",
        table(["Reading", "Fires", "of which yes", "of which partial", "of which no", "Missed (yes or partial, no fire)"], rows),
    ])


def format_cell(cell: list[int] | None) -> str:
    return "0" if not cell else f"{cell[0]} ({cell[1]})"


def render_qualifying(data: dict) -> str:
    rows = [
        [g["session"][:8], g["first"][:10], g["era"], g["host"], g["type"], len(g["pages"]), g["kind"], len(g["other_sessions"]), g["pages"][0][:90]]
        for g in sorted(data["qualifying"], key=lambda g: g["first"])
    ]
    return "\n".join([
        "## Documentation and manual hosts scraped ad hoc",
        "",
        "The rule's positive class. Every research host-session pair of a qualifying type:",
        "",
        table(["Session", "Date", "Era", "Host", "Type", "Pages", "Kind", "Other sessions", "Page"], rows),
        "",
        "A single page does not make a candidate. These rows say which sessions the rule's list would have asked about a deep dive, not that a deep dive would have served.",
    ])


def render_recurrence(data: dict) -> str:
    rows = [
        [r["host"], r["type"], LIST_LABELS[r["list"]], r["sessions"], r["pages"], len(r["repeated_pages"])]
        for r in data["recurring"]
    ]
    repeated = [f"- `{r['host']}`: " + ", ".join(p[:80] for p in r["repeated_pages"]) for r in data["recurring"] if r["repeated_pages"]]
    return "\n".join([
        "## Hosts that recur across research sessions",
        "",
        "Hosts scraped in at least two different research sessions. Repeated pages are pages scraped in two or more sessions, each time from scratch because nothing was persisted.",
        "",
        table(["Host", "Type", "List", "Sessions", "Distinct pages", "Pages in 2+ sessions"], rows),
        "",
        *repeated,
    ])


def render_deep_dives(data: dict) -> str:
    run_rows = [
        [r["run_id"], r["first"][:10], r["era"], r["host"], r["urls"], r["errors"], r["in_collection"], r["retrieved_documents"],
         "domain" if r["domain_scale"] else "pick", r["trigger"]]
        for r in data["runs"]
    ]
    retrieval_lines = [
        f"- `{r['run_id']}` {r['host']}: " + "; ".join(f"{ts} {collection}: {query}" for ts, collection, query in r["retrievals"])
        for r in data["runs"] if r["retrievals"]
    ]
    discover_rows = [[d["ts"][:19], d["session"], d["seed"], d["purpose"]] for d in data["discover_fetches"]]
    return "\n".join([
        "## Deep dives that happened",
        "",
        "Pipe runs from `pipe_scrape_log.jsonl`, grouped by `run_id`. *pick* = fewer than "
        f"{data['domain_scale_min']} URLs (a hand-picked capture), *domain* = at least that many. *In collection* = files in `websearch-pages` whose name derives from the run's URLs. "
        "*Retrieved* = of those URLs, documents that appeared in at least one rag-cli search hit list (search log starts "
        f"{data['rag_first'][:10]}).",
        "",
        table(["Run", "Date", "Era", "Host", "URLs", "Errors", "In collection", "Retrieved", "Scale", "Trigger"], run_rows),
        "",
        "Retrieval events:",
        "",
        *(retrieval_lines or ["- none"]),
        "",
        "`discover_urls` calls that fetched a seed URL (first call per session and seed; `--help` and grep are excluded). All sessions ran inside the websearch repo:",
        "",
        table(["Time (UTC)", "Session", "Seed", "Purpose"], discover_rows),
    ])


def render_ad_hoc_indexing(data: dict) -> str:
    rows = [
        [c["ts"][:16], c["session"], short_project(c["project"]), c["collection"], "<br>".join(u[:80] for u in c["urls"][:3]), c["purpose"]]
        for c in data["index_calls"]
    ]
    return "\n".join([
        "## Ad hoc indexing before it was removed",
        "",
        "`index_scrapes` calls in transcripts (ad hoc indexing left the web research skill on 2026-10-11). First call per session, collection and URL set.",
        "",
        table(["Time (UTC)", "Session", "Project", "Collection", "URLs (first 3)", "Purpose"], rows),
    ])


def render_patch_decision(data: dict) -> str:
    cands = data["candidates"]
    removed = [g for g in cands if g["judgment"]["need_multi"] and g["judgment"]["stable"] == "no"]
    institutions = [g for g in cands if g["type"] == "institution"]
    institutions_useful = [g for g in institutions if g["serves"] in (SERVES_YES, SERVES_PARTIAL)]
    removed_useful = [g for g in removed if g["serves"] in (SERVES_YES, SERVES_PARTIAL)]
    return "\n".join([
        "## Patch decision",
        "",
        "Patch file: `dev/adhoc_persistence/patch/deepdive_rule_perishable_content.patch` against `skills/websearch-web-research/SKILL.md`. The skill itself is unchanged. The patch applies with `git apply`.",
        "",
        f"- **Supported by the data: a perishable-content test.** Reading B fires on {data['readings'][1]['fires']} candidates, reading C on {data['readings'][2]['fires']}. "
        f"The {len(removed)} candidates removed are " + ", ".join(f"{g['session'][:8]}:{g['host']}" for g in removed)
        + f"; {len(removed_useful)} of them would have served. The observed mechanism is concrete: prices, stock, a registration status and dynamic search result pages were scraped page after page, and an index would have held them stale or empty. "
        f"Evidence level: {len(removed)} observed cases in {len({g['session'] for g in removed})} sessions, one rater, and the test input is my own judgment.",
        f"- **Not supported: adding institutions to the list of qualifying types.** {len(institutions)} candidates are institution hosts, {len(institutions_useful)} would have served. "
        "The type does not separate useful from useless cases; the perishable test and the question do. Not patched.",
        "- **Not testable: the documentation and manual side of the list.** No research session scraped more than one page of such a host, so neither a false alarm nor a miss was observed. Not patched.",
        "- **Not testable: the effect of the 2026-10-11 text on agent behavior.** No research session ran under it.",
    ])


def render_limits(data: dict) -> str:
    m = data["meta"]
    return "\n".join([
        "## What the data can and cannot say",
        "",
        "**Can say**",
        "",
        f"- Which host types the agents' multi-page ad hoc scrapes fell on: {Counter(g['type'] for g in data['candidates']).most_common()}.",
        f"- That in the {m['research_sessions']} research sessions with an ad hoc scrape no agent proposed or started a deep dive: no `discover_urls`, no capture spawn, and the one session with the words \"deep dive\" in the agent's text does not propose the workflow. Pipe runs before {m['transcripts_earliest'][:10]} cannot be attributed.",
        "- Which candidate pairs a perishable-content test (price, stock, deadline, status, search result) would have removed: all `stable = no` rows.",
        "- That " + recurring_institution_sentence(data) + ", each time from scratch because nothing was persisted.",
        "",
        "**Cannot say**",
        "",
        f"- **Small N.** {len(data['candidates'])} candidates, {len({g['host'] for g in data['candidates']})} hosts, {len({g['session'] for g in data['candidates']})} sessions, one user. "
        "One host with many sessions (the university library, the economics department) dominates the positive cases. No percentage in this report is a rate with a usable interval.",
        f"- **The rule text changed on 2026-10-11.** The newest text (trigger by relevance, no user proposal, worker-only workflow) was in force for at most {m['days_since_e3']} days of data. "
        f"Of {m['research_scrapes']} research-session scrapes, {m['research_scrapes_e3_plus']} fall into era E3 or E4. Everything else was produced under texts that asked the agent to propose to the user, or under the capture-first text of E0.",
        "- **Counterfactual, not behavior.** The list verdict says what the list would label. It does not say what an agent would have done with the sentence \"other URLs of the domain could be relevant\"; the list is guidance (\"meist\"), not a switch.",
        "- **Skill delivery.** The era is taken from commit times of `SKILL.md`. When the plugin was published is not recorded; the injected skill text in the transcript (column *Text seen*) is the better evidence where present.",
        f"- **Transcript coverage.** Transcripts start {m['transcripts_earliest'][:10]}; {m['unattributed']} of {m['scrapes']} scrape records have no transcript and cannot be judged. "
        "Pipe runs before that date have no attributable trigger.",
        "- **Single rater.** Types and judgments are mine. Another reader could move rows; the labels file holds every input so any row can be changed and the report rerun.",
        "- **Question not asked of the agent.** The transcript shows what the agent did, not whether it considered a deep dive and dropped the idea.",
        f"- **Dev vs research.** The split is by project directory. {m['dev_groups']} host-session groups from the websearch repo are in the appendix and may contain real research done from that directory.",
    ])


def recurring_institution_sentence(data: dict) -> str:
    rows = [r for r in data["recurring"] if r["type"] == "institution"]
    parts = [f"`{r['host']}` was scraped in {r['sessions']} research sessions ({r['pages']} distinct pages, {len(r['repeated_pages'])} of them in 2 or more sessions)" for r in rows]
    return "; ".join(parts) if parts else "no institution host recurred"


def render_appendix(data: dict) -> str:
    dev_rows = [
        [g["session"][:8], short_project(g["project"]), g["first"][:10], g["host"], len(g["pages"]), g["scrapes"]]
        for g in sorted(data["dev_groups"], key=lambda g: g["first"])
    ]
    unattributed_rows = [
        [g["first"][:10], g["host"], g["type"], LIST_LABELS[g["list"]], len(g["pages"]), len(g["usable_pages"])]
        for g in data["unattributed_candidates"]
    ]
    host_rows = [[host, host_type] for host, host_type in sorted(data["host_types"].items())]
    return "\n".join([
        "## Appendix A: dev sessions (websearch repo directories)",
        "",
        table(["Session", "Project", "Date", "Host", "Pages", "Scrapes"], dev_rows),
        "",
        f"## Appendix B: unattributed clusters (host and day with at least {MIN_PAGES} pages, no transcript match)",
        "",
        table(["Date", "Host", "Type", "List", "Pages", "Usable"], unattributed_rows),
        "",
        "## Appendix C: host type labels",
        "",
        table(["Host", "Type"], host_rows),
    ])
