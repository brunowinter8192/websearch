# Autonomous deep dive, no ad hoc indexing, one web collection (2026-10-11)

Orchestrator record. Supersedes the ad hoc indexing decisions earlier in this area. No source code changed; the skills, the rag-cli data directory and a rules patch changed.

## Why

The owner's goal for this session: agents use websearch fully on their own and the owner only joins in meta and evaluation phases. Every point where a skill asked the user something blocked that.

The owner's reading of why no agent ever ran a deep dive (matches 2026-09-24 in this area: zero `discover_urls` calls in the logs): the workflow required talking to the user, and the agent saw roughly 90 lines of steps before starting. An agent that sees ten steps does not start.

## Decisions

1. **The ad hoc lane indexes nothing.** `index_scrapes` was removed from `websearch-web-research`. Reason given by the owner: web pages, unlike GitHub issues or Reddit posts, have no uniform format that makes deduplication easy, and every forced "index or not" decision by the agent is another decision it avoids. The CLI command `index_scrapes` still exists in the code as of 2026-10-11.
2. **The deep dive runs entirely in one worker.** The Main agent only finds the seed URL, writes an `INFO_NEED` (what question, why this domain) and spawns the worker. The worker decides on its own which URLs serve `INFO_NEED`, scrapes in rounds, cleans, indexes, and writes one fixed five-line report into the chat. All cull reviews and confirmations by the Main agent or the user were removed.
3. **Web content lives in one collection, `websearch-pages`.** `<project>-reference` collections hold only papers and books (MinerU output). Owner's reasons: no domain exists twice in different states across projects, and web documentation is more often useful across projects than papers are.

## Cleanup rules in the capture skill, as decided

- A scrape round's onward links matter because discovery misses pages. Observed 2026-10-11: `discover_urls` on `https://docs.pytest.org/en/stable/` returned 15 URLs, all version roots (`sitemap_declared=14`, seed 1); one scrape of the start page yielded 56 doc links. On `https://platform.claude.com/docs/en/home` it returned 3952 URLs in under 2 s.
- pipe_scraper writes the link file with dots replaced by underscores (`/tmp/docs_pytest_org_scrape_links.txt`), not under the dotted domain. The old skill text used the dotted name.
- New links are filtered against discovery plus every earlier round (`/tmp/<domain>_seen.txt`); filtering against discovery only would re-offer already scraped pages each round.
- The automatic deletion of collection files whose URL is not in this run's discovery was dropped: a second deep dive with a different `INFO_NEED` would delete the first one's pages.
- A polluted passage is cleaned if the pollution separates from the content, otherwise deleted whole (owner's rule; replaces "leave arguable noise in").
- Failed scrapes are found by reading the smallest files first. The sre.google run showed why there is no byte threshold: most files under 2.5 KB were landing pages of Google's PDF reports (e.g. "Incident Metrics in SRE"), real content, not failures.
- Waiting steps say "go idle, do not poll, you will be notified", because "wait until the log shows the summary line" invites polling.

## First run of the new capture skill (sre.google, 2026-10-11)

Deviation by prompt: indexing skipped, files left in /tmp for review. Result: 228 discovered, 205 kept, 205 scraped (204x200, 1x301), 90 new onward links of which 0 kept (slash variants and epub/mobi), 5 defect classes cleaned (site header, site footer, book sidebar, book footer, images). Spot checks of chapters, a podcast transcript and grep for cookie/subscribe residue found no leftover pollution.

Gaps seen in that run:
- The worker kept all 60 podcast transcripts because the skill says "keep when unsure".
- The report was a full page, not the five-line format.
- None of the run's numbers are logged anywhere persistent (see area `kvp`).

## Collection move

On 2026-10-11 every `.md` in a `*-reference` collection whose first lines contain `<!-- source: http` was treated as web content: 997 files, no file name collisions. They were copied to `rag-cli/data/documents/websearch-pages/` and deleted from their old collections with `rag-cli delete` (whole collection where all files were web: canvas, gh-cli, jobscraper, linkedin, mineru, reddit-cli `-reference`; per document in monitor-cc-reference (136 of 146), trading-reference (19 of 112), websearch-reference (365 of 371)). PDF-derived files never carry the source line. News collections (coindesk, theblock) and GitHub/Reddit collections were not touched.

The move carried along 13 platform.claude.com API pages consisting of bare "Loading..." lines that had never been indexed in the old collection (no `.json` sibling). Indexing made them searchable; they were deleted with `rag-cli delete` right after.

Final state on 2026-10-11: the 997 moved files indexed (17031 chunks, 0 errors), then the 205 sre.google files from the capture run (3222 chunks, 0 errors), minus the 13 placeholders: 1189 documents, 20164 chunks. A spot query "alerting on SLOs for low traffic services" restricted to `sre_google%` returned workbook chapter 5 at ranks 1-10 and a podcast transcript at rank 11.

## Rule proposal

`dev/kvp/patch/workers_rag_first.patch` against `~/.claude/shared-rules/main/workers.md`: RAG first before any websearch, gh-cli or reddit-cli call at any point of a cycle, with a table of which collection precedes which tool, and the reference collections always checked. Observation behind it: between 2026-09-18 and 2026-10-10 only 31 of 283 rag-cli searches went to a reference collection, and `websearch-pages` has never been searched.
