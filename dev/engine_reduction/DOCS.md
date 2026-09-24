# dev/engine_reduction/

## Role
Measurement scripts backing the 14-engine-to-1-specialised-engine reduction decision (keep `openalex`, cut the other 7 non-general engines). Probes here answer specific go/no-go questions for each milestone of that reduction; they do not touch `src/`.

## Public Interface
No `__init__.py` — not a package. `openalex_pdf_probe.py` is the sole entry point, run directly via `./venv/bin/python3 dev/engine_reduction/openalex_pdf_probe.py`.

## Flow
`QUERIES` (7 real agent queries) -> `fetch_works` hits the OpenAlex API per query -> `classify`/`build_record`/`build_eyeball_rows` compute per-query counts and eyeball rows -> `write_report` emits `01_reports/openalex_pdf_probe_<ts>.md`.

## Modules

### openalex_pdf_probe.py (215 LOC)

**Purpose:** Milestone 1 measurement — for 7 real agent queries, how often does an OpenAlex work carry a direct PDF URL (`best_oa_location.pdf_url`) vs a landing page only vs no OA location, over the full 100-result page and over the top 10; plus a `type` breakdown of pdf_url-present works and an eyeball listing (title/type/chosen URL/pdf_url) for 2 queries.
**Reads:** none (live HTTP fetch against `https://api.openalex.org/works`, no `mailto`, no API key).
**Writes:** `01_reports/openalex_pdf_probe_<ts>.md`.
**Called by:** CLI only. `./venv/bin/python3 dev/engine_reduction/openalex_pdf_probe.py`.
**Calls out:** `httpx`. `_pick_url` is a dev-script-isolation inline copy of `src/search/engines/openalex.py::_pick_url` (ids.arxiv > doi > id) — not a shared import, matching the isolation convention of `dev/search_pipeline/25..31_*_probe.py`, so the probe keeps measuring even if `src/` changes underneath it later.

---

## State
No shared state; each run is self-contained. Report outputs live in `01_reports/` (readable reports), separate from any future data-dump folder, per the dev/ layout convention.
