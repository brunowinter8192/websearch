# websearch/

## Role

CLI-driven web research toolkit for Claude Code. cli.py is the only root-level Python file, a thin argparse dispatcher wiring search, drilldown, scrape, discovery and indexing into five subcommands. Touch it to add or remove a subcommand or change global logging; workflow logic lives in src/search, src/scraper and src/crawler.

## Public Interface

No package init at this level. Entry path is `python cli.py <subcommand>`; nothing imports cli.py.

## Flow

Arguments in via argparse, after file logging is configured and before any src import. The chosen subcommand calls one workflow from src/search, src/scraper or src/crawler. Results leave as text on stdout; the discovery subcommand additionally writes a URL file on success. Logs go to a rotating file, never stderr.

## Modules

### cli.py (219 LOC)

**Purpose:** CLI entry point: sets up rotating file logging, then dispatches the five subcommands to their workflows in src/search, src/scraper and src/crawler.
**Reads:** CLI arguments, the disk cache of search pools (drilldown path).
**Writes:** the rotating CLI log under src/logs, stdout, and the URL file of the discovery subcommand.
**Called by:** invoked directly as the CLI entry point; no importer.
**Calls out:** none.

## State

None. Each invocation is a fresh process; persistence lives in the packages it calls.
