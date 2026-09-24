# dev/search_pipeline/pdf_probes/

## Role
Three probes for the search-to-PDF download chain: classifying pooled URLs, following citation_pdf_url meta tags, and an end-to-end search-to-PDF regression run. Touch after `pdf_chain` changes; not for production download code.

## Public Interface
No `__init__.py`. Entry scripts `14_download_classify_probe.py`, `15_citation_pdf_followup.py`, `16_search_to_pdf_probe.py` run as `./venv/bin/python dev/search_pipeline/pdf_probes/<script>.py`.

## Flow
14 reads smoke and free-word reports from `../md/`, builds a tiered URL pool and sniff-classifies it; 15 re-fetches probe 14's HTML_HAS_PDF_LINK rows in two hops; 16 runs `search_web_workflow` and downloads real PDFs. Reports land in `../md/`.

## Modules

### 14_download_classify_probe.py (56 LOC)

**Purpose:** Download-classify probe entry point: builds the URL pool, classifies it by HTTP sniffing, and assembles the report.
**Reads:** newest `pipeline_smoke_*.md` and `free_word_injection_probe_*.md` from `../md/`.
**Writes:** `../md/download_classify_<ts>.md`, `../txt/pool_<ts>.txt`, `../txt/pool_doi_sample_<ts>.txt`.
**Called by:** CLI only.
**Calls out:** the three `_download_classify_probe_*` siblings.

### _download_classify_probe_classify.py (235 LOC)

**Purpose:** HTTP fetch and sniff concern: per-domain-capped async classification, Tier-1 transform, content-type, PDF-magic and paywall sniffing.
**Reads:** none (fetches URLs live).
**Writes:** none (returns result dicts; progress to stderr).
**Called by:** `14_download_classify_probe.py`, report sibling (constants).
**Calls out:** `httpx`.

### _download_classify_probe_pool.py (115 LOC)

**Purpose:** Pool-building concern: extracts, domain-tiers and doi.org-samples the URL pool from the two source reports.
**Reads:** report paths passed in.
**Writes:** `<data_dir>/pool_<ts>.txt`, `pool_doi_sample_<ts>.txt`.
**Called by:** `14_download_classify_probe.py`, report sibling.
**Calls out:** stdlib only.

### _download_classify_probe_report.py (243 LOC)

**Purpose:** Markdown report assembly for the download-classify probe, one builder per report section.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/download_classify_<ts>.md`.
**Called by:** `14_download_classify_probe.py`.
**Calls out:** pool and classify siblings.

### 15_citation_pdf_followup.py (263 LOC)

**Purpose:** Two-hop validation: re-GETs HTML_HAS_PDF_LINK URLs from probe 14, follows `citation_pdf_url`, classifies actual PDF delivery.
**Reads:** `../md/<SOURCE_REPORT>` (hardcoded), `../txt/<SOURCE_POOL>`.
**Writes:** `../md/citation_pdf_followup_<ts>.md`, `../txt/pool_has_pdf_link_<ts>.txt`.
**Called by:** CLI only.
**Calls out:** `httpx`, config and report siblings.

### _citation_pdf_followup_config.py (7 LOC)

**Purpose:** Constants shared by the citation follow-up entry and its report: source report name, concurrency, timeouts.
**Reads:** none.
**Writes:** none.
**Called by:** `15_citation_pdf_followup.py`, report sibling.
**Calls out:** stdlib only.

### _citation_pdf_followup_report.py (191 LOC)

**Purpose:** Markdown report assembly for the citation follow-up: metadata, per-domain tables, samples, per-URL detail.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/citation_pdf_followup_<ts>.md`.
**Called by:** `15_citation_pdf_followup.py`.
**Calls out:** config sibling.

### 16_search_to_pdf_probe.py (312 LOC)

**Purpose:** End-to-end search-to-PDF chain probe: workflow search, Tier-1/DIRECT/MULTI_STEP/BLACKLIST download chain, real PDFs saved.
**Reads:** queries as CLI positional args.
**Writes:** `../md/search_to_pdf_<ts>.md`, PDFs in `~/Downloads/`.
**Called by:** CLI only (`--top-n`).
**Calls out:** `src.scraper.pdf_chain`, `src.search.{browser,merge,result,search_web}`, `httpx`, config and report siblings.

### _search_to_pdf_probe_config.py (8 LOC)

**Purpose:** Constants shared by the search-to-PDF entry and its report: download dir, connection caps, timeout.
**Reads:** none.
**Writes:** none.
**Called by:** `16_search_to_pdf_probe.py`, report sibling.
**Calls out:** stdlib only.

### _search_to_pdf_probe_report.py (190 LOC)

**Purpose:** Markdown report assembly for the search-to-PDF probe: metadata, per-query tables, path distribution, highlights.
**Reads:** none (arguments only).
**Writes:** `<report_dir>/search_to_pdf_<ts>.md`.
**Called by:** `16_search_to_pdf_probe.py`.
**Calls out:** config sibling.

---

## State
none; each script keeps its state local.
