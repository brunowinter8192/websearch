# dev/agentic_discovery/

## Role
One-shot scripts removing UI chrome, navigation, and formatting artifacts from website-crawled markdown files before RAG indexing. Each script targets a specific domain or collection prefix. Files are overwritten in-place; `<!-- source: URL -->` headers are preserved. Run from project root: `./venv/bin/python dev/agentic_discovery/<script>.py`.

## Public Interface
No `__init__.py` — not a package. Each script is its own entry point, run directly via `./venv/bin/python dev/agentic_discovery/<script>.py`.

## Flow
Crawled `*.md` files under `RAG/data/documents/<searxng|Playwright>/` (a sibling project, not part of this repo) -> per-script, per-domain noise removal (header/footer chrome, inline UI artifacts) -> same files overwritten in-place, `<!-- source: URL -->` comment preserved.

## Modules

### clean_web_searxng.py (285 LOC)

**Purpose:** Remove navigation chrome and formatting artifacts from the `searxng` RAG collection (2076 files across 12 domain prefixes: searxng, crawl4ai, playwright, tor, anthropic, trafilatura, onetrust, cookieyes, web, paper, sitemaps, cookiebot).
**Reads:** `*.md` files in `RAG/data/documents/searxng/` — all domain prefixes handled in one pass with per-domain header/footer strategies.
**Writes:** Files overwritten in-place with headers, footers, and inline artifacts removed.
**Called by:** CLI only.
**Calls out:** none (stdlib `re`, `pathlib`, `sys` only).

---

### clean_web_anthropic.py (120 LOC)

**Purpose:** Fix formatting artifacts in Anthropic (platform.claude.com/docs) crawled pages.
**Reads:** `anthropic__*.md` files in `RAG/data/documents/searxng/`.
**Writes:** Files overwritten in-place. Fixes: excessive blank lines after source comment → 1 blank; broken headings (`## \n<text>` → `## <text>`); concatenated card navigation links at end of file removed.
**Called by:** CLI only.
**Calls out:** none (stdlib `re`, `pathlib` only).

---

### clean_web_cookieyes.py (267 LOC)

**Purpose:** Remove UI chrome from cookieyes.com/documentation pages.
**Reads:** `cookieyes__*.md` files in `RAG/data/documents/searxng/`.
**Writes:** Files overwritten in-place. Removes: blank lines before first heading; "Search for:Search Button" line; breadcrumb navigation; "Was this article helpful?" block; G2 Rating Badges; newsletter subscribe block; "Related articles" link list.
**Called by:** CLI only.
**Calls out:** none (stdlib `re`, `pathlib` only).

---

### clean_web_onetrust.py (225 LOC)

**Purpose:** Remove UI chrome from developer.onetrust.com pages.
**Reads:** `onetrust__*.md` files in `RAG/data/documents/searxng/`.
**Writes:** Files overwritten in-place. Removes: leading blank lines before first heading; split heading artifacts (`# ` alone on a line); empty anchor links; footer navigation (Prev/Next links after `* * *` separator); trailing `* * *` separators; pagination markers (`N of M[](URL)` lines).
**Called by:** CLI only.
**Calls out:** none (stdlib `re`, `sys`, `pathlib` only).

---

### clean_web_Playwright.py (129 LOC)

**Purpose:** Remove Docusaurus chrome from Playwright docs pages (playwright.dev).
**Reads:** `*.md` files in `RAG/data/documents/Playwright/`.
**Writes:** Files overwritten in-place. Content sandwiched between first `# ` heading and first `[Previous ` / `[Next ` pagination link. Removes full sidebar nav, breadcrumb, "On this page" label, and footer sections (Learn/Community/More + copyright).
**Called by:** CLI only.
**Calls out:** none (stdlib `pathlib`, `re` only).

---

### clean_web_rag_docs.py (299 LOC)

**Purpose:** Remove site-generator chrome from Playwright, Crawl4AI, and Trafilatura docs in the RAG collection (`playwright__*`, `crawl4ai__*`, `trafilatura__*` files).
**Reads:** Files matching the three prefixes in `RAG/data/documents/searxng/`.
**Writes:** Files overwritten in-place. Per-domain fixes: Playwright — heading anchors; Crawl4AI — standalone `Copy` UI lines after code blocks, `#### On this page` / `> Feedback` footer blocks; Trafilatura — heading anchors, `[ previous X ][ next Y ]` nav lines, `On this page` TOC blocks.
**Called by:** CLI only.
**Calls out:** none (stdlib `pathlib`, `re` only).

---

### clean_web_tor.py (142 LOC)

**Purpose:** Remove navigation chrome and UI artifacts from support.torproject.org pages.
**Reads:** `tor__*.md` files in `RAG/data/documents/searxng/`.
**Writes:** Files overwritten in-place. Removes: footer block starting at Jobs link (social media links, Copyleft notice, trademark, onion image); "View for:" UI widget; "Expand all Collapse all" widget; leading blank lines before first heading (reduced to max 1).
**Called by:** CLI only.
**Calls out:** none (stdlib `re`, `pathlib` only).

---

## State
No module-level mutable state. Each script reads its own file set, processes files independently, and overwrites them in-place; nothing is shared across scripts or across files within a run.
