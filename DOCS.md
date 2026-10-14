# websearch/

## Role

CLI-driven web research toolkit for Claude Code. cli.py is the only root-level Python file, a thin argparse dispatcher wiring search, drilldown, scrape, discovery, indexing, the deep dive run record and PDF conversion into seven subcommands. Touch it to add or remove a subcommand or change global logging; workflow logic lives in src/search, src/scraper, src/crawler and src/pdf.

## Public Interface

No package init at this level. Entry path is `python cli.py <subcommand>`; nothing imports cli.py.

## Flow

File logging is configured as the first step of main, before argparse runs; no src module logs at import time. Arguments in via argparse. The chosen subcommand calls one workflow from src/search, src/scraper, src/crawler or src/pdf. Results leave as text on stdout; the discovery subcommand additionally writes a URL file on success. Logs go to a rotating file, never stderr.

## Modules

### cli.py (288 LOC)

**Purpose:** CLI entry point: main sets up rotating file logging and the browser at-exit cleanup, then dispatches the seven subcommands to their workflows in src/search, src/scraper, src/crawler and src/pdf.
**Reads:** CLI arguments, the disk cache of search pools (drilldown path).
**Writes:** the rotating CLI log under src/logs, stdout, the URL file of the discovery subcommand, and (through src/crawler) the discovery and closing records of the deep dive run log.
**Called by:** invoked directly as the CLI entry point; no importer.
**Calls out:** none.

## State

None. Each invocation is a fresh process; persistence lives in the packages it calls.
