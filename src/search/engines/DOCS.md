# src/search/engines/

## Role

Per-engine search implementations. Each module except base.py holds one engine subclass, either a pydoll Chrome-tab scraper or a direct httpx API client. Touch it to add or change an engine's parsing or rate-limit registration; the default engine set is chosen in src/search.

## Public Interface

`__init__.py` is empty. Consumers import engine classes by module path.

## Flow

Query in, engine-specific fetch (browser tab navigation with injected parse script, or HTTP call), parse, and a triple out: results, no verdict, and a diagnosis of observed facts. Each module registers a rate limiter at import; the fan-out in src/search acquires a token before calling the engine.

## Modules

### base.py (16 LOC)

**Purpose:** Abstract engine parent; the uniform triple-returning method is abstract and the plain search method only delegates.
**Reads:** none.
**Writes:** none.
**Called by:** every engine module (subclassed).
**Calls out:** src/search/result.py (type only).

### google.py (284 LOC)

**Purpose:** Google search via a Chrome tab with consent cookie, captcha detection and resolution of Google's goto redirect links.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** pydoll, curl_cffi, src/search/browser.py, src/search/document_status.py, src/search/selector_hits.py.

### duckduckgo.py (163 LOC)

**Purpose:** DuckDuckGo HTML-endpoint search via a Chrome tab with challenge-form detection and day-precision dates.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py.

### startpage.py (152 LOC)

**Purpose:** Startpage search via a Chrome tab using a two-step form flow to obtain the per-session token.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py.

### brave.py (238 LOC)

**Purpose:** Brave search via a Chrome tab, solving Brave's button challenge unattended when one is served.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py, src/search/selector_hits.py.

### bing.py (182 LOC)

**Purpose:** Bing search via a headed Chrome tab, unwrapping Bing's tracking redirect links and scanning for block markers.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py, src/search/selector_hits.py.

### yandex.py (161 LOC)

**Purpose:** Yandex search via a headed Chrome tab with captcha-redirect short-circuit and self-referential result filtering.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py, src/search/selector_hits.py.

### mojeek.py (204 LOC)

**Purpose:** Mojeek search via a Chrome tab that solves the site's proof-of-work challenge unattended within one wall-clock budget.
**Reads:** none (network only).
**Writes:** none.
**Called by:** src/search/search_web.py.
**Calls out:** src/search/browser.py, src/search/document_status.py.

### openalex.py (123 LOC)

**Purpose:** OpenAlex academic search via HTTP API with dates and open-access PDF links.
**Reads:** the optional OpenAlex API key environment variable.
**Writes:** none (network only).
**Called by:** src/search/search_web.py.
**Calls out:** httpx.

### scholar.py (99 LOC)

**Purpose:** Google Scholar search via HTTP; fully implemented but decoupled from the default engine pool.
**Reads:** none (network only).
**Writes:** none.
**Called by:** dev probe scripts only; not imported by production code (parked, not deleted).
**Calls out:** httpx, lxml.

## State

None. Engines are stateless per call; the only shared state is the limiter registry owned by src/search/rate_limiter.py.

Details, decisions and observed evidence: process-docs/search_pipeline, process-docs/marker_reflection, process-docs/mojeek_return, process-docs/engine_reduction and process-docs/refactor_sweep.
