# dev/scrape_pipeline/05_paper_mode/

## Role
Standalone direct-PDF-download prototype with no production imports, evaluating plain HTTP PDF acquisition as a baseline. PDF download is not a production feature; the scraper rejects PDF URLs.

## Public Interface
No `__init__.py` — not a package. The script is a CLI entry point run via `./venv/bin/python`.

## Flow
PDF URLs (arguments or parsed from a search smoke report) -> streamed download with content-type check -> files in the user's Downloads folder, status table to stdout.

## Modules

### download.py (156 LOC)

**Purpose:** Downloads PDF URLs with a content-type check and resolves filenames from headers or the URL.
**Reads:** URL arguments or a search smoke report via `--input`.
**Writes:** PDFs in `~/Downloads/`; status table to stdout.
**Called by:** CLI only.
**Calls out:** `requests`.

## State
`pdf_test_urls.md` is a hand-maintained 12-URL test inventory. Observed failures: process-docs area scrape_pipeline.
