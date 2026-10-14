# Deep dive rule measurement

Generated 2026-10-14T21:21:16Z by `dev/adhoc_persistence/deepdive_rule_measurement.py`. Scrape log window 2026-09-06 .. 2026-10-14, transcripts from 2026-09-14 (482 files, 481 sessions with relevant lines).

## Answer in short

- **Base.** 158 ad hoc scrape records; 118 matched to an agent transcript (105 in research sessions, 13 in sessions inside the websearch repo), 40 without transcript.
- **The current rule never met a research session.** Research-session scrapes by era of the first scrape: E0 33, E1 35, E2 37, E3 or E4 0. Every behavior measured here happened under an older text. What the 2026-10-11 rule would have done is a counterfactual.
- **Candidates** (research session, at least 2 distinct pages of one host): 16 in 6 sessions on 12 hosts; 6 with at least 3 pages.
- **By the rule's list.** 0 qualifying type, 6 excluded type, 10 type the list does not mention (all of them institution).
- **Would a deep dive have served** (my judgment, see Method): yes 2, partial 3, no 11.
- **Where it would have served at least partly:** adfd041c fragrantica.de (product, list: excluded, partial); adfd041c ub.uni-frankfurt.de (institution, list: silent, partial); 0e9319ff wiwi.uni-frankfurt.de (institution, list: silent, yes); f3816eda wiwi.uni-frankfurt.de (institution, list: silent, partial); c3d6ed15 ub.uni-frankfurt.de (institution, list: silent, yes).
- **Reading of the list.** The list has no hit on the cases where a deep dive would have served: of the 5, 4 are silent and 1 excluded. It does remove 5 of the 11 cases that would not have served.
- **The list's positive class is barely observed.** Research host-session pairs of a documentation or manual type: 1, 1 with a single page. One unattributed cluster of a qualifying type exists (faq.whatsapp.com), without transcript.
- **Deep dives that happened.** 10 pipe runs (2026-08-24 .. 2026-10-11), 4 of domain scale and 6 hand-picked captures. 6 distinct `discover_urls` fetches, none in a research session, none after an agent applied the rule; the only run with a recorded trigger of the capture skill is sre.google, started by the orchestrator on the owner's request.
- **Reuse of captured pages.** Domain-scale runs: 4 documents of 310 in the collection appeared in a rag-cli hit list (one of the retrieval events is the orchestrator's own check of the sre.google capture). Hand-picked runs: 3 of 17.
- **Agent behavior.** 19 research sessions, 19 activated the web research skill. Agent text containing "deep dive" in 1 of them (79cb77e8: 2); none of these is a proposal of the capture workflow (read in the transcript).
- Details, limits and the patch decision follow below.

## Method

- **Join.** Each `scrape_log.jsonl` record is matched to a `scrape_url_chromium` Bash call in a Claude Code transcript when the normalized URL is one of the call's URLs and the record timestamp lies between the call's `tool_use` timestamp minus 30 s and its `tool_result` timestamp plus 30 s.
- **Session.** The transcript `sessionId`. A session counts as a **dev session** when its project directory belongs to the websearch repo (main checkout or a worktree). Those sessions are listed only in the appendix. Records without a transcript match are **unattributed** and never become candidates.
- **Candidate.** Research session, one host (the log's `domain`, `www.` stripped), at least 2 distinct normalized URLs. Second column: at least 3. Pages are counted whatever their verdict (login wall, 404 included), the usable count is shown next to it.
- **Navigated pages.** Pages of the candidate that no `search_engine_drilldown` listed in the 3 hours before the scrape. The agent reached them by a link, a guessed URL or a URL the user gave.
- **Other sessions.** Other research sessions in which the same host was scraped.
- **Type and list verdict.** My hand label per host (`deepdive_labels.json`, all hosts listed in the appendix). Types `docs` and `vendor_manual` are *qualifies*, `blog`, `news`, `forum`, `product`, `changelog`, `release_feed` are *excluded*, everything else is *silent* (the rule's list does not mention it).
- **Judgment.** Mine, single rater, from reading the transcript around the scrapes. Two inputs: *needed several pages* (did the question need more than one page of the host) and *stable* (yes, partly, no: does the needed content stay valid for months, or is it a price, stock, deadline, status or search result). *Serves* is derived: **no** if several pages were not needed or if the pages were neither navigated nor seen in another session; otherwise **yes** if stable, **partial** if partly stable, **no** if not stable.
- **Rule text per session.** `Rule text seen` is read from the skill text injected into the session when there is one, otherwise `-`. `Era` is the era of the first scrape by commit time of `SKILL.md`.

| Era | From (UTC) | Until (UTC) | Skill text |
|---|---|---|---|
| E0 | - | 2026-09-20T19:47:04Z | capture is the default, ad hoc scrape only on explicit user request; no domain rule |
| E1 | 2026-09-20T19:47:04Z | 2026-09-24T18:46:25Z | deep dive hangs on domain type, never on need; propose to the user at the smallest suspicion |
| E2 | 2026-09-24T18:46:25Z | 2026-10-11T11:58:39Z | deep dive when other URLs of the domain could be relevant; propose to the user |
| E3 | 2026-10-11T11:58:39Z | 2026-10-14T16:37:27Z | same trigger, proposal line dropped; workflow section still asks the user |
| E4 | 2026-10-14T16:37:27Z | - | same trigger, worker-only workflow with INFO_NEED, no user step |

## Base of the measurement

| Kind | Host-session groups |
|---|---|
| research | 72 |
| dev | 12 |
| unattributed | 23 |

- Research sessions with at least one scrape: 19. Sessions that activated the web research skill: 19. Sessions with an agent text containing "deep dive": 1.
- Research host-session groups with one page: 56, with 2 or more: 16.
- Grouping by registrable domain instead of host adds 0 further candidates.

## Candidates: research sessions with several pages of one host

| Session | Project | Date | Era | Text seen | Host | Type | List | Pages (usable) | 3+ | Navigated | Other sessions | Needed several | Stable | Serves |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| adfd041c | wise2627 | 2026-09-15 | E0 | E0 | reddit.com | forum | list: excluded | 2 (2) |  | 0 | 2 | no | yes | no |
| adfd041c | wise2627 | 2026-09-15 | E0 | E0 | fragrantica.de | product | list: excluded | 2 (2) |  | 1 | 0 | yes | partly | partial |
| adfd041c | wise2627 | 2026-09-15 | E0 | E0 | ub.uni-frankfurt.de | institution | list: silent | 7 (3) | x | 4 | 4 | yes | partly | partial |
| 0e9319ff | wise2627 | 2026-09-17 | E0 | E0 | wiwi.uni-frankfurt.de | institution | list: silent | 4 (4) | x | 1 | 4 | yes | yes | yes |
| f3816eda | wise2627 | 2026-09-21 | E1 | E0 | ub.uni-frankfurt.de | institution | list: silent | 2 (2) |  | 2 | 4 | yes | no | no |
| f3816eda | wise2627 | 2026-09-21 | E1 | E0 | wiwi.uni-frankfurt.de | institution | list: silent | 5 (5) | x | 4 | 4 | yes | partly | partial |
| c3d6ed15 | general | 2026-09-23 | E1 | E1 | ub.uni-frankfurt.de | institution | list: silent | 5 (5) | x | 1 | 4 | yes | yes | yes |
| c3d6ed15 | general | 2026-09-23 | E1 | E1 | dbis.ur.de | institution | list: silent | 2 (0) |  | 2 | 0 | yes | no | no |
| c3d6ed15 | general | 2026-09-23 | E1 | E1 | qis.server.uni-frankfurt.de | institution | list: silent | 4 (4) | x | 4 | 0 | yes | no | no |
| 79cb77e8 | general | 2026-09-26 | E2 | E2 | zalando.de | product | list: excluded | 4 (4) | x | 3 | 0 | yes | no | no |
| 79cb77e8 | general | 2026-09-26 | E2 | E2 | idealo.de | product | list: excluded | 2 (2) |  | 0 | 0 | no | no | no |
| 79cb77e8 | general | 2026-09-26 | E2 | E2 | reddit.com | forum | list: excluded | 2 (2) |  | 1 | 2 | no | yes | no |
| 79cb77e8 | general | 2026-09-26 | E2 | E2 | de.tumi.com | product | list: excluded | 2 (2) |  | 1 | 0 | yes | no | no |
| 6224cb5d | general | 2026-10-04 | E2 | E2 | uni-frankfurt.de | institution | list: silent | 2 (1) |  | 0 | 0 | yes | partly | no |
| 6224cb5d | general | 2026-10-04 | E2 | E2 | swffm.de | institution | list: silent | 2 (2) |  | 0 | 0 | yes | partly | no |
| 6224cb5d | general | 2026-10-04 | E2 | E2 | rz.uni-frankfurt.de | institution | list: silent | 2 (2) |  | 0 | 0 | yes | yes | no |

Reasons per row:

- `adfd041c:reddit.com` (no): Two threads for two unrelated questions (jeans cut, bath products) 76 minutes apart; no site structure involved.
- `adfd041c:fragrantica.de` (partial): Two perfume entries scraped to compare two named perfumes; ratings and votes drift, entry notes are stable. The second entry was not in a drilldown list.
- `adfd041c:ub.uni-frankfurt.de` (partial): How to get a permanent library desk: seven pages, two were login walls, two were 404 pages from guessed URLs (agent navigated blind). Application rules are stable, the registration dates are not. Host recurs in four other sessions.
- `0e9319ff:wiwi.uni-frankfurt.de` (yes): Dean's list criteria for master and bachelor, exam office FAQ, master download page: examination regulations, stable for a semester. Host recurs in four other sessions.
- `f3816eda:ub.uni-frankfurt.de` (no): Status check of an application window: the page was changed that same morning to 'fully booked'. Needs the live page, an indexed copy would be stale.
- `f3816eda:wiwi.uni-frankfurt.de` (partial): Five pages for several questions in one session: registration deadlines and news ticker (perishable), department structure (stable). Host recurs in four other sessions.
- `c3d6ed15:ub.uni-frankfurt.de` (yes): Off-campus access to licensed e-media: home, FAQ, e-book readme, virtual textbook collection, subject page. Access conditions are stable; one page was reached by link, not by search. Host recurs in four other sessions.
- `c3d6ed15:dbis.ur.de` (no): Two query result pages of a database directory (?q=JSTOR, ?q=Business+Source), both filtered to 1 byte. Dynamic search results, nothing a discovery can list.
- `c3d6ed15:qis.server.uni-frankfurt.de` (no): Four query variants of one course-catalogue search. Result pages of a dynamic search, not enumerable by discovery.
- `79cb77e8:zalando.de` (no): Four product and listing pages to find one shoe in one size; prices and stock are the answer and they are perishable.
- `79cb77e8:idealo.de` (no): Two price-comparison pages for two different products (shoe, bag) 58 minutes apart.
- `79cb77e8:reddit.com` (no): Two threads on two different bags. The user's phrase 'mach nochmal einen deep dive' means thorough research, not the capture workflow.
- `79cb77e8:de.tumi.com` (no): Category page and one product page, 47 minutes apart; model list and prices are the answer.
- `6224cb5d:uni-frankfurt.de` (no): Service page and its sub page for one contact lookup (sub page returned no content). Content of the question is personal and not named in this report.
- `6224cb5d:swffm.de` (no): Service page and its consultation-hours sub page for the same single lookup.
- `6224cb5d:rz.uni-frankfurt.de` (no): Campus software offer page and the install guide for it, both direct search hits; one lookup, answered by the two pages.

## The rule's list against the judgment

Cell = candidates (of which with 3 or more pages).

| List verdict \ deep dive would serve | yes | partial | no |
|---|---|---|---|
| list: qualifies | 0 | 0 | 0 |
| list: excluded | 0 | 1 (0) | 5 (1) |
| list: silent | 2 (2) | 2 (2) | 6 (1) |

Reading: a *qualifies* row with *no* is a deep dive the list would trigger without use (false alarm). An *excluded* row with *yes* or *partial* is a deep dive the list would suppress although it would have served (miss). The *silent* row is where the list decides nothing and the sentence "other URLs of the domain could be relevant" has to carry the decision.

| Type | List | Candidates |
|---|---|---|
| institution | list: silent | 10 |
| product | list: excluded | 4 |
| forum | list: excluded | 2 |

## Three readings of the rule on the same candidates

The 2026-10-11 rule is a sentence plus a list marked "meist". Three ways an agent could apply it, scored on the candidates above. Reading C is not the current rule; it shows what one added test would change. Its input (*stable*) is my own judgment, so reading C is not independent of the labels.

| Reading | Fires | of which yes | of which partial | of which no | Missed (yes or partial, no fire) |
|---|---|---|---|---|---|
| A: the list as a switch (fires on qualifying types) | 0 | 0 | 0 | 0 | 5 |
| B: the sentence alone (fires when several pages of the host were needed) | 13 | 2 | 3 | 8 | 0 |
| C: the sentence plus a perishable-content test (fires when several pages were needed and the content is not perishable) | 8 | 2 | 3 | 3 | 0 |

## Documentation and manual hosts scraped ad hoc

The rule's positive class. Every research host-session pair of a qualifying type:

| Session | Date | Era | Host | Type | Pages | Kind | Other sessions | Page |
|---|---|---|---|---|---|---|---|---|
| 8590dee4 | 2026-09-21 | E1 | developer.apple.com | docs | 1 | research | 0 | developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct/movetoac |

A single page does not make a candidate. These rows say which sessions the rule's list would have asked about a deep dive, not that a deep dive would have served.

## Hosts that recur across research sessions

Hosts scraped in at least two different research sessions. Repeated pages are pages scraped in two or more sessions, each time from scratch because nothing was persisted.

| Host | Type | List | Sessions | Distinct pages | Pages in 2+ sessions |
|---|---|---|---|---|---|
| github.com | forum | list: excluded | 5 | 5 | 0 |
| ub.uni-frankfurt.de | institution | list: silent | 5 | 14 | 1 |
| wiwi.uni-frankfurt.de | institution | list: silent | 5 | 11 | 1 |
| reddit.com | forum | list: excluded | 3 | 5 | 0 |
| amazon.de | product | list: excluded | 2 | 2 | 0 |
| packhacker.com | blog | list: excluded | 2 | 2 | 0 |
| stackoverflow.com | forum | list: excluded | 2 | 2 | 0 |

- `ub.uni-frankfurt.de`: ub.uni-frankfurt.de/benutzung/dauerarbeitsplaetze.html
- `wiwi.uni-frankfurt.de`: wiwi.uni-frankfurt.de/studium/pruefungsorganisation/downloads/master

## Deep dives that happened

Pipe runs from `pipe_scrape_log.jsonl`, grouped by `run_id`. *pick* = fewer than 30 URLs (a hand-picked capture), *domain* = at least that many. *In collection* = files in `websearch-pages` whose name derives from the run's URLs. *Retrieved* = of those URLs, documents that appeared in at least one rag-cli search hit list (search log starts 2026-09-18).

| Run | Date | Era | Host | URLs | Errors | In collection | Retrieved | Scale | Trigger |
|---|---|---|---|---|---|---|---|---|---|
| 34214881 | 2026-08-24 | E0 | docs.pytest.org | 51 | 0 | 51 | 0 | domain | agent-side capture to ground suite-relocation decisions; who asked is not recorded |
| 42d1a7e9 | 2026-08-25 | E0 | platform.claude.com | 7 | 0 | 7 | 0 | pick | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| eeb9128d | 2026-08-27 | E0 | platform.claude.com | 2 | 0 | 0 | 0 | pick | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| 575fabca | 2026-08-31 | E0 | scrapebadger.com | 6 | 0 | 6 | 0 | pick | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| 2527ff0b | 2026-09-02 | E0 | git-scm.com | 1 | 0 | 1 | 0 | pick | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| 9d949ee8 | 2026-09-03 | E0 | help.openalex.org | 37 | 0 | 37 | 0 | domain | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| cf4b5a19 | 2026-09-04 | E0 | code.claude.com | 3 | 0 | 3 | 3 | pick | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| 67554e80 | 2026-09-06 | E0 | platform.claude.com | 50 | 0 | 17 | 1 | domain | not recoverable, no transcript: the earliest transcript is from 2026-09-14 |
| cf205813 | 2026-10-10 | E2 | docs.pytest.org | 1 | 0 | 0 | 0 | pick | orchestrator probe while designing the capture skill, 1 URL, scraped to /tmp |
| 09dc0c1e | 2026-10-11 | E3 | sre.google | 205 | 0 | 205 | 3 | domain | owner request, started by the orchestrator via worker-cli spawn capture-sre-google |

Retrieval events:

- `cf4b5a19` code.claude.com: 2026-09-24T15:37 monitor-cc-reference: synchronized output mode 2026 flicker free redraw tmux; 2026-09-24T17:49 monitor-cc-reference: Ghostty AppleScript new window opens on current space; 2026-09-25T16:20 monitor-cc-reference: macOS process safe to kill essential daemons; 2026-09-26T10:30 monitor-cc-reference: PreToolUse hook exit code 2 blocks tool call and stderr is shown to Cl
- `67554e80` platform.claude.com: 2026-09-26T10:30 monitor-cc-reference: PreToolUse hook exit code 2 blocks tool call and stderr is shown to Cl
- `09dc0c1e` sre.google: 2026-10-11T19:36 websearch-pages: alerting on SLOs for low traffic services

`discover_urls` calls that fetched a seed URL (first call per session and seed; `--help` and grep are excluded). All sessions ran inside the websearch repo:

| Time (UTC) | Session | Seed | Purpose |
|---|---|---|---|
| 2026-09-24T19:30:35 | 43d27df6 | https://docs.python.org/3/ | worker live test of discovery behavior during a dev change |
| 2026-09-24T19:30:39 | 43d27df6 | https://platform.claude.com/docs | worker live test of discovery behavior during a dev change |
| 2026-09-24T19:34:17 | ae0071bd | https://docs.python.org/3/ | orchestrator live test of discovery behavior during a dev change |
| 2026-10-10T19:38:36 | 51731b00 | https://platform.claude.com/docs/en/home | orchestrator probing discover_urls while designing the capture skill; later spawned the sre.google worker on the owner's request |
| 2026-10-11T14:54:37 | e02ad316 | https://sre.google/ | capture worker for sre.google (the only run that followed the capture skill) |
| 2026-10-14T21:08:49 | 291fbe59 | https://sre.google/ | unlabelled |

## Ad hoc indexing before it was removed

`index_scrapes` calls in transcripts (ad hoc indexing left the web research skill on 2026-10-11). First call per session, collection and URL set.

| Time (UTC) | Session | Project | Collection | URLs (first 3) | Purpose |
|---|---|---|---|---|---|
| 2026-09-20T18:03 | 8599391e | ai-Meta-ClaudeCode-cli-websearch~a | websearch-reference | https://www.anthropic.com/news/claude-opus-4-5 | dev test of the index_scrapes command |
| 2026-09-20T22:47 | 8599391e | ai-Meta-ClaudeCode-cli-websearch~a | this-collection-does-not-exist-xyz | https://example.com | dev test of the index_scrapes command |
| 2026-09-24T14:04 | c5c3b4c1 | ai-canvas | canvas-reference | https://github.com/h0x91b/dev-3.0/issues/1786<br>https://stackoverflow.com/questions/59268831/how-to-make-font-in-canvas-smooth-j | agent indexed single research pages (GitHub issue, Q&A) for the canvas project |
| 2026-09-25T09:59 | dcb383a9 | ai-Meta-ClaudeCode-cli-websearch | trading-reference | https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003285<br>https://developer.apple.com/documentation/appkit/nsstackview | agent indexed single research pages (paper, Apple doc) while working from the websearch directory |
| 2026-09-25T10:00 | dcb383a9 | ai-Meta-ClaudeCode-cli-websearch | monitor-cc-reference | https://developer.apple.com/documentation/appkit/nsstackview | agent indexed single research pages (paper, Apple doc) while working from the websearch directory |
| 2026-09-25T10:30 | 1440c8ea | ai-Meta-ClaudeCode-cli-websearch~w | nonexistent_coll_wssrc | http://x.invalid<br>http://x.invalid<br>http://x.invalid/a.PDF | dev test of the index_scrapes command (nonexistent collection) |
| 2026-09-25T16:32 | ad72996d | ai-Monitor-CC | monitor-cc-reference | https://procxray.com/blog/mds-stores-high-cpu-mac<br>https://eclecticlight.co/2025/06/16/spotlight-search-can-be-blocked-by-extended- | agent indexed single research pages (two blog posts) for the monitor-cc project |

## Patch decision

Patch file: `dev/adhoc_persistence/patch/deepdive_rule_perishable_content.patch` against `skills/websearch-web-research/SKILL.md`. The skill itself is unchanged. The patch applies with `git apply`.

- **Supported by the data: a perishable-content test.** Reading B fires on 13 candidates, reading C on 8. The 5 candidates removed are f3816eda:ub.uni-frankfurt.de, c3d6ed15:dbis.ur.de, c3d6ed15:qis.server.uni-frankfurt.de, 79cb77e8:zalando.de, 79cb77e8:de.tumi.com; 0 of them would have served. The observed mechanism is concrete: prices, stock, a registration status and dynamic search result pages were scraped page after page, and an index would have held them stale or empty. Evidence level: 5 observed cases in 3 sessions, one rater, and the test input is my own judgment.
- **Not supported: adding institutions to the list of qualifying types.** 10 candidates are institution hosts, 4 would have served. The type does not separate useful from useless cases; the perishable test and the question do. Not patched.
- **Not testable: the documentation and manual side of the list.** No research session scraped more than one page of such a host, so neither a false alarm nor a miss was observed. Not patched.
- **Not testable: the effect of the 2026-10-11 text on agent behavior.** No research session ran under it.

## What the data can and cannot say

**Can say**

- Which host types the agents' multi-page ad hoc scrapes fell on: [('institution', 10), ('product', 4), ('forum', 2)].
- That in the 19 research sessions with an ad hoc scrape no agent proposed or started a deep dive: no `discover_urls`, no capture spawn, and the one session with the words "deep dive" in the agent's text does not propose the workflow. Pipe runs before 2026-09-14 cannot be attributed.
- Which candidate pairs a perishable-content test (price, stock, deadline, status, search result) would have removed: all `stable = no` rows.
- That `ub.uni-frankfurt.de` was scraped in 5 research sessions (14 distinct pages, 1 of them in 2 or more sessions); `wiwi.uni-frankfurt.de` was scraped in 5 research sessions (11 distinct pages, 1 of them in 2 or more sessions), each time from scratch because nothing was persisted.

**Cannot say**

- **Small N.** 16 candidates, 12 hosts, 6 sessions, one user. One host with many sessions (the university library, the economics department) dominates the positive cases. No percentage in this report is a rate with a usable interval.
- **The rule text changed on 2026-10-11.** The newest text (trigger by relevance, no user proposal, worker-only workflow) was in force for at most 3 days of data. Of 105 research-session scrapes, 0 fall into era E3 or E4. Everything else was produced under texts that asked the agent to propose to the user, or under the capture-first text of E0.
- **Counterfactual, not behavior.** The list verdict says what the list would label. It does not say what an agent would have done with the sentence "other URLs of the domain could be relevant"; the list is guidance ("meist"), not a switch.
- **Skill delivery.** The era is taken from commit times of `SKILL.md`. When the plugin was published is not recorded; the injected skill text in the transcript (column *Text seen*) is the better evidence where present.
- **Transcript coverage.** Transcripts start 2026-09-14; 40 of 158 scrape records have no transcript and cannot be judged. Pipe runs before that date have no attributable trigger.
- **Single rater.** Types and judgments are mine. Another reader could move rows; the labels file holds every input so any row can be changed and the report rerun.
- **Question not asked of the agent.** The transcript shows what the agent did, not whether it considered a deep dive and dropped the idea.
- **Dev vs research.** The split is by project directory. 12 host-session groups from the websearch repo are in the appendix and may contain real research done from that directory.

## Appendix A: dev sessions (websearch repo directories)

| Session | Project | Date | Host | Pages | Scrapes |
|---|---|---|---|---|---|
| ef1f471b | ai-Meta-ClaudeCode-cli-websearch | 2026-09-15 | anthropic.com | 1 | 1 |
| b0b53463 | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | mojeek.com | 1 | 1 |
| b0b53463 | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | altcha.org | 1 | 1 |
| 9265b52d | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | deepwiki.com | 1 | 1 |
| 9265b52d | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | altcha.org | 1 | 1 |
| 9265b52d | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | community.mojeek.com | 1 | 1 |
| 9265b52d | ai-Meta-ClaudeCode-cli-websearch | 2026-09-17 | gist.github.com | 1 | 1 |
| 7e8253c2 | ai-Meta-ClaudeCode-cli-websearch | 2026-09-18 | yandex.com | 1 | 1 |
| dcb383a9 | ai-Meta-ClaudeCode-cli-websearch | 2026-09-25 | journals.plos.org | 1 | 1 |
| dcb383a9 | ai-Meta-ClaudeCode-cli-websearch | 2026-09-25 | developer.apple.com | 1 | 1 |
| 51731b00 | ai-Meta-ClaudeCode-cli-websearch | 2026-10-11 | blog.crawlex.net | 1 | 1 |
| 51731b00 | ai-Meta-ClaudeCode-cli-websearch | 2026-10-14 | vorschriften.bgn-branchenwissen.de | 1 | 2 |

## Appendix B: unattributed clusters (host and day with at least 2 pages, no transcript match)

| Date | Host | Type | List | Pages | Usable |
|---|---|---|---|---|---|
| 2026-09-09 | otsuka-europe.com | company_site | list: silent | 3 | 3 |
| 2026-09-09 | aam2core-holding-ag.jobs.personio.com | job_posting | list: silent | 4 | 4 |
| 2026-09-12 | ub.uni-frankfurt.de | institution | list: silent | 6 | 2 |
| 2026-09-13 | faq.whatsapp.com | vendor_manual | list: qualifies | 2 | 2 |
| 2026-09-17 | mojeek.com | search_engine | list: silent | 2 | 1 |

## Appendix C: host type labels

| Host | Type |
|---|---|
| aam2core-holding-ag.jobs.personio.com | job_posting |
| aam2core.com | company_site |
| aboutamazon.de | news |
| academia.edu | paper |
| ai-act-service-desk.ec.europa.eu | authority |
| altcha.org | docs |
| amazon.de | product |
| anthropic.com | news |
| bfr.bund.de | authority |
| blog.crawlex.net | blog |
| claudecodecamp.com | blog |
| code.claude.com | docs |
| community.mojeek.com | forum |
| cosdna.com | product |
| dbis.ur.de | institution |
| de.tumi.com | product |
| deal-magazin.com | news |
| deepwiki.com | docs |
| deitel.com | product |
| developer.apple.com | docs |
| developers.cloudflare.com | docs |
| dm.de | product |
| docs.getbifrost.ai | changelog |
| docs.pytest.org | docs |
| ebay.de | product |
| eclecticlight.co | blog |
| einzelhandel.de | news |
| esquire.de | news |
| everysize.com | product |
| fachschaft.org | institution |
| faq.whatsapp.com | vendor_manual |
| footlocker.de | product |
| forum.cursor.com | forum |
| forums.raspberrypi.com | forum |
| fragrantica.de | product |
| geizhals.de | product |
| gist.github.com | code_host |
| git-scm.com | docs |
| github.blog | changelog |
| github.com | forum |
| h-ka.de | institution |
| help.openalex.org | docs |
| idealo.de | product |
| immobilienmanager.de | news |
| iz.de | news |
| jamesloper.com | blog |
| jobs.smartrecruiters.com | job_posting |
| journals.plos.org | paper |
| journals.sagepub.com | paper |
| lobste.rs | forum |
| macinternals.app | blog |
| mangofriseurbedarf.de | product |
| markenfactory.com | company_site |
| mojeek.com | search_engine |
| moodle.studiumdigitale.uni-frankfurt.de | institution |
| moquer.com | product |
| nick-liu.com | blog |
| notino.de | product |
| oceanwash.de | blog |
| otsuka-europe.com | company_site |
| otsuka.com | company_site |
| otsuka.de | company_site |
| packhacker.com | blog |
| platform.claude.com | docs |
| procxray.com | blog |
| qis.server.uni-frankfurt.de | institution |
| reddit.com | forum |
| reebok.eu | product |
| rz.uni-frankfurt.de | institution |
| sandqvist.com | product |
| scrapebadger.com | blog |
| scrapfly.io | blog |
| sre.google | vendor_manual |
| stackoverflow.com | forum |
| stern.de | news |
| superuser.com | forum |
| swffm.de | institution |
| techcrunch.com | news |
| thenorthface.com | product |
| theodorehq.com | blog |
| tk.de | company_site |
| trustpilot.com | forum |
| ub.uni-frankfurt.de | institution |
| uni-frankfurt.de | institution |
| vorschriften.bgn-branchenwissen.de | regulation_text |
| wetransco.de | blog |
| whitecase.com | news |
| wiwi-frankfurt.de | institution |
| wiwi.uni-frankfurt.de | institution |
| yandex.com | vendor_manual |
| zalando.de | product |
