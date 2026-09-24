# dev/scrape_pipeline/05_paper_mode/

## Role
Standalone direct-PDF-download prototype — no prod imports, no Crawl4AI. Evaluates plain `requests`-based PDF acquisition as a baseline. PDF download is not a production feature — `scrape_url_chromium` rejects `.pdf` URLs and delegates download to the user (see root `DOCS.md` gotcha).

## Modules

### download.py (151 LOC)

**Purpose:** Takes `.pdf` URLs via positional args or `--input <smoke.md>` (parses all `.pdf` URLs across all queries). Downloads each via `requests.get(stream=True)` with Content-Type check. Filename resolution: Content-Disposition → URL basename → `download_<ts>.pdf`.
**Reads:** `--input <path-to-search-md>` or direct URL args.
**Writes:** `~/Downloads/` — downloaded PDFs; per-URL status table to stdout.
**Called by:** CLI only. `--overwrite` to re-download existing files.

## State
`pdf_test_urls.md` — 12-URL test inventory extracted from a `pipeline_smoke_20260506_003915.md` run. Columns: Q-Nr, URL, Status (hand-filled after test run). Hand-written input inventory, not script-generated.

## Gotchas
Observed failures (12-URL test run 2026-05-06): Springer (paywall → HTML redirect, not PDF); Academia.edu (HTTP 403). 10/12 ok.
