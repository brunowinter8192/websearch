# dev/engine_reduction/

## Role
Measurement scripts backing the engine reduction decision (keep openalex, cut the other specialised engines). Probes answer go/no-go questions per milestone; they do not touch `src/`.

## Public Interface
No `__init__.py` — not a package. The OpenAlex PDF probe is the sole entry point, run directly via `./venv/bin/python3`.

## Flow
Fixed set of real agent queries -> live OpenAlex API fetch per query -> per-query classification and eyeball rows -> markdown report in `01_reports/`.

## Modules

### openalex_pdf_probe.py (215 LOC)

**Purpose:** Measures how often an OpenAlex work carries a direct PDF URL versus landing page only versus none, over full page and top ten.
**Reads:** Live HTTP against the OpenAlex works API.
**Writes:** `01_reports/openalex_pdf_probe_<ts>.md`.
**Called by:** CLI only.
**Calls out:** `httpx`.

---

## State
None. Each run is self-contained; reports live in `01_reports/`.
