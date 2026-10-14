# Deep dive rule measured against real agent sessions (2026-10-14)

Worker record. The skill is unchanged. Script, report and a patch file sit in `dev/adhoc_persistence/`. This entry holds what a successor needs to rerun, extend or question the measurement.

## Question and answer in one paragraph

Does the deep dive rule in `skills/websearch-web-research/SKILL.md` fire on the right cases? On 2026-10-14 the data cannot answer that for the 2026-10-11 text, because no research session ever ran under it: of 105 scrapes in research sessions, 33 fall into era E0, 35 into E1, 37 into E2, 0 into E3 or E4. What the data does show is how the list in the rule sorts the multi-page ad hoc cases that happened under older texts. Of 16 candidates (research session, at least 2 distinct pages of one host), 0 are documentation or manual hosts, 6 are excluded types (product, forum), 10 are hosts the list does not mention (all university or library sites). A deep dive would have served in 2 cases, partly in 3, not in 11. The 5 useful cases are on three hosts: `ub.uni-frankfurt.de`, `wiwi.uni-frankfurt.de`, `fragrantica.de`.

## Rule eras (by commit time of SKILL.md, UTC)

| Era | From | Text |
|---|---|---|
| E0 | start | Capture is the default, ad hoc scrape only when the user explicitly asks. No domain rule. |
| E1 | 2026-09-20 19:47 | Deep dive hangs on domain type; propose to the user at the smallest suspicion. |
| E2 | 2026-09-24 18:46 | Deep dive when other URLs of the domain could be relevant; propose to the user. |
| E3 | 2026-10-11 11:58 | Same trigger, proposal line dropped; the workflow section still asks the user. |
| E4 | 2026-10-14 16:37 | Same trigger, worker-only workflow with INFO_NEED. |

The plugin cache holds one overwritten version path, so the publish time of a text is not recoverable. The better evidence is the skill text injected into the session: the script reads it from the transcript and reports it as "Text seen". Example: session `f3816eda` started in E0 and ran into E1 by the clock, its injected text is E0.

## How the measurement works

1. Transcripts (`~/.claude/projects/*/*.jsonl`, earliest timestamp 2026-09-14, not the 2026-09-11 stated elsewhere) are read for Bash calls that invoke `scrape_url_chromium`, `discover_urls`, `index_scrapes`.
2. A scrape record joins a call when its normalized URL is in the call's URLs and its timestamp lies in `[tool_use - 30 s, tool_result + 30 s]`. Result: 118 of 158 records matched; 40 have no transcript: 33 before 2026-09-14, 7 mojeek search-page scrapes on 2026-09-17 from a dev test run outside any transcript call.
3. Sessions in a project directory of the websearch repo are **dev**, all others **research**. Dev sessions are an appendix only. Records without a match are **unattributed**.
4. Candidate: research session, one host, at least 2 distinct pages (3 or more shown as a second column). Grouping by registrable domain adds 0 candidates.
5. Objective facts per candidate: pages no drilldown offered in the 3 hours before the scrape ("navigated"), other research sessions that scraped the same host.
6. My judgment per candidate, two inputs in `deepdive_labels.json`: `need_multi` (did the question need several pages) and `stable` (yes, partly, no). `serves` is derived in `serves_of`: no if several pages were not needed or if the pages were neither navigated nor seen in another session; otherwise yes, partial or no by `stable`.
7. Host types are my hand labels. Types `docs`, `vendor_manual` count as the rule's positive list, `blog`, `news`, `forum`, `product`, `changelog`, `release_feed` as the negative list, everything else is "list silent".

## Observed cases (the ones the judgments rest on)

- `0e9319ff` wiwi (yes): dean's list criteria for master and bachelor, exam office FAQ, master download page. Examination regulations, stable for a semester.
- `c3d6ed15` ub (yes): off-campus access to licensed e-media, five pages, one reached by link.
- `adfd041c` ub (partial): seven pages for a permanent library desk; two login walls, two 404s from guessed URLs. The agent navigated blind, a URL map would have helped; registration dates perish.
- `f3816eda` ub (no): the question was the status of an application window and the page changed that same morning to "fully booked". A stale index would have answered wrongly.
- `c3d6ed15` dbis.ur.de and qis (no): query result pages of a database directory and a course catalogue. dbis returned 1 byte per page. Nothing a discovery lists.
- `79cb77e8` zalando, tumi, idealo (no): prices and stock are the answer.
- `adfd041c` and `79cb77e8` reddit (no): two threads on unrelated questions.
- `6224cb5d` three service sites (no): two pages each for one lookup, found as direct search hits.

The user's phrase "mach nochmal einen deep dive" in `79cb77e8` means thorough research, not the capture workflow. Do not count user or agent uses of the words as workflow starts.

## Reading of the rule on the same candidates

| Reading | Fires | yes | partial | no | Missed useful |
|---|---|---|---|---|---|
| A: list as a switch | 0 | 0 | 0 | 0 | 5 |
| B: sentence alone (several pages needed) | 13 | 2 | 3 | 8 | 0 |
| C: sentence plus perishable-content test | 8 | 2 | 3 | 3 | 0 |

The list filters 5 of the 11 useless cases (product, forum). It is silent on 4 of the 5 useful ones. Reading C removes zalando, tumi, dbis, qis and the ub status check without losing a useful case. Evidence level: 5 cases in 3 sessions, one rater, and `stable` is my own judgment, so C is not independent of the labels.

## Patch decision

`dev/adhoc_persistence/patch/deepdive_rule_perishable_content.patch` adds one bold sentence with two bullets to the Deep Dive section: no deep dive when the needed content is perishable (price, stock, deadline, status, search result), also on domains that otherwise qualify. Checked with `git apply --check`.

Deliberately not patched:
- "Institution" as a third qualifying type. 10 institution candidates, 4 useful. The type does not separate the cases.
- Anything on the documentation side of the list. Only 1 research host-session pair of a documentation type exists (one page of `developer.apple.com`), so neither a false alarm nor a miss was observed. One unattributed cluster of a qualifying type exists (`faq.whatsapp.com`, 2 pages, 2026-09-13, no transcript).

## Deep dives that happened

10 pipe runs from 2026-08-24 to 2026-10-11, 4 of domain scale (at least 30 URLs): pytest 51, openalex 37, platform.claude.com 50, sre.google 205. The 6 others are hand-picked captures of 1 to 7 URLs.

- Triggers are recoverable for 3 runs only: the pytest run (agent-side, to ground a decision, documented in area `tests`), an orchestrator probe on 2026-10-10 (1 URL), and sre.google (owner request, started by the orchestrator, worker session `e02ad316`). Runs before 2026-09-14 have no transcript.
- Fetching `discover_urls` calls: 5, all in websearch-repo sessions (two live tests on 2026-09-24, the 2026-10-10 probe, the sre.google worker). The area note of 2026-09-24 saying zero calls is consistent: the first test calls came about 45 minutes after the commit of that note.
- No research session proposed or started a deep dive. The only agent text with "deep dive" (session `79cb77e8`, 2 mentions) refers to its own research write-up.
- Reuse: documents of the domain-scale runs that appeared in a rag-cli hit list: 4 of 310 in the collection, one of the hits being the orchestrator's own check of the sre.google capture. Hand-picked runs: 3 of 17 (three code.claude.com pages, retrieved in 4 searches between 2026-09-24 and 2026-09-26 from `monitor-cc-reference`). The rag-cli search log starts 2026-09-18, so earlier captures had 26 days of window.

## Ad hoc indexing

Before `index_scrapes` left the skill on 2026-10-11, three sessions used it on real research pages: `c5c3b4c1` (GitHub issue, Q&A), `ad72996d` (two blog posts), `dcb383a9` (a paper and an Apple documentation page, run from the websearch directory, hence classed dev). Single pages, no deep dive among them.

## Recurrence across sessions

`ub.uni-frankfurt.de` was scraped in 5 research sessions (14 distinct pages), `wiwi.uni-frankfurt.de` in 5 (11 pages). One page per host was scraped in two sessions. Nothing was persisted between sessions. This is the strongest observation in the data and it is about two hosts of one user.

## Mistakes to avoid

- Transcript directories begin with `-`; `grep` and `ls` treat them as options. Use `--`, or read with Python.
- A first regex took `;` and `|` as part of a URL and dropped a third of the joins. Chained commands are common (`websearch scrape_url_chromium A; websearch scrape_url_chromium B`); the second scrape starts after the call started, so the window must end at `tool_result`.
- Quoted URLs contain `&`. Extract quoted URLs first, then bare ones.
- An invocation pattern must not match `grep "websearch scrape_url_chromium\|websearch discover_urls"`. The `\|` in a grep alternation looks like a pipe. Observed in the kvp session; covered by a test.
- A URL example with brackets inside a command (`https://[^ )]*`) makes `urlsplit` raise `Invalid IPv6 URL`. Observed; covered by a test.
- Backgrounded commands (`... > file &`) end after 0.1 s; the later real scrape still joins because the window slack is 30 s and a later call carries the same URL.
- The measuring session itself writes commands with the very strings the script searches for (heredocs). The script skips project directories ending in `worktrees-deepdive51`. A successor in a different worktree has to change `MEASURING_PROJECT_SUFFIX`.
- Hook rules in this environment reject `dev/` scripts importing from `src/`; `url_to_filename` is therefore copied into `deepdive_deepdives.py`. If the original changes, the copy drifts.

## What the data cannot say (2026-10-14)

- Small N: 16 candidates, 6 sessions, 12 hosts, one user. The positive cases come from two hosts.
- No research session under the 2026-10-11 text. A rerun after a few weeks of E3 or E4 traffic is the real test; rerun the script and read the "Answer in short" block.
- The counterfactual says what the list would label, not what an agent does with the sentence.
- Single rater. Change a row in `deepdive_labels.json` and rerun.
- The research versus dev split is by project directory; real research done from the websearch directory lands in the appendix.
- Private content in the transcripts (credentials, personal topics) was not copied into the report or labels. Keep it that way.

## For whoever reruns it

- Run `./venv/bin/python -m dev.adhoc_persistence.deepdive_rule_measurement` from the repo root. A new candidate without a judgment entry makes the report raise a TypeError in the candidate table; add the key `<session first 8 chars>:<host>` with `need_multi`, `stable`, `reason`. New hosts need a `host_types` entry, otherwise they show as `unlabelled` and count as list silent.
- Numbers differ slightly from the KVP notes of the same days: 158 records (the log grew) and 118 matched (stricter invocation pattern) against 156 and 120.
