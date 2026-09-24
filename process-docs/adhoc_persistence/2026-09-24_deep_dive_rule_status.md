# Deep-dive rule: not measurable yet (2026-09-24)

Orchestrator record. No code changed.

## Why the rule cannot be measured on 2026-09-24

The web-research skill tells an agent when to run a deep dive over a whole domain
(`discover_urls`, then scrape, then `index_scrapes`). The rule was set on 2026-09-20 as a
deliberate bias by domain type, not from measurement.

Measuring whether it fires on the right cases needs deep dives that actually happened. On
2026-09-24 `src/logs/cli.log*` (all rotated files back to 2026-08-31) contain zero `discover_urls`
calls. There is nothing to measure against.

## Owner change to the rule, uncommitted until this session

`skills/websearch-web-research/SKILL.md` carried an uncommitted owner edit on 2026-09-24:

- Before: "Ein Deep Dive haengt am Typ der Domain, nie an deinem Bedarf." plus the instruction to
  propose a deep dive at the smallest suspicion.
- After: "Mache einen Deep Dive wenn auch andere urls einer Domain fuer deine Fragestellung relevant
  sein koennten", keeping the domain-type lists as "meist infrage" / "meist nicht infrage", and
  dropping the smallest-suspicion line.

So the trigger moved from domain type alone to the relevance of further pages on the same domain,
with domain type as guidance. Any later measurement has to compare against this wording, not the
2026-09-20 one.

## How to measure once data exists

Count `discover_urls` records in `cli.log` per session and pair each with the preceding
`search_web` query and the seed domain. For each pair, classify the domain type from the skill's
lists and check whether the scraped pages were used afterwards (`index_scrapes` calls). A deep dive
on a "meist nicht infrage" type, or a documentation domain with no deep dive, are the two cases
that would say the rule misfires.
