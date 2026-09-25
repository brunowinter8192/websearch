# dev/agentic_discovery/

## Role
One-shot scripts removing UI chrome, navigation, and formatting artifacts from crawled markdown files before RAG indexing. Each script targets one domain or collection prefix and overwrites files in place. Not part of the production pipeline.

## Public Interface
No `__init__.py` — not a package. Each script is its own entry point, run directly via `./venv/bin/python`.

## Flow
Crawled markdown files in a sibling RAG project's document folders -> per-script domain-specific noise removal -> same files overwritten in place, source header comment preserved.

## Modules

### clean_web_searxng.py (228 LOC)

**Purpose:** Remove navigation chrome and formatting artifacts across all domain prefixes of the searxng RAG collection in one pass.
**Reads:** Markdown files of the searxng collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_anthropic.py (122 LOC)

**Purpose:** Fix formatting artifacts in crawled Anthropic docs pages.
**Reads:** Anthropic-prefixed files of the searxng collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_cookieyes.py (210 LOC)

**Purpose:** Remove UI chrome from cookieyes documentation pages.
**Reads:** Cookieyes-prefixed files of the searxng collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_onetrust.py (195 LOC)

**Purpose:** Remove UI chrome from OneTrust developer pages.
**Reads:** Onetrust-prefixed files of the searxng collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_Playwright.py (121 LOC)

**Purpose:** Remove Docusaurus chrome from Playwright docs pages.
**Reads:** Files of the separate Playwright collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_rag_docs.py (255 LOC)

**Purpose:** Remove site-generator chrome from Playwright, Crawl4AI, and Trafilatura docs in the searxng collection.
**Reads:** Files with those three prefixes.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

### clean_web_tor.py (134 LOC)

**Purpose:** Remove navigation chrome and UI widgets from Tor support pages.
**Reads:** Tor-prefixed files of the searxng collection.
**Writes:** Files overwritten in place.
**Called by:** CLI only.
**Calls out:** none.

---

## State
No shared state. Each script processes its own file set independently.
