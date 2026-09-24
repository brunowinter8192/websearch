# dev/news_pipeline/theblock/jhao104/patches/helper/

## Role
Overlay file for the vendored jhao104 proxy_pool clone: replaces upstream `helper/validator.py` so the validator chain checks Cloudflare pass on theblock.co. Touch it only to change that validator; it is not runnable on its own.

## Public Interface
No `__init__.py` — not a package. `jhao104/setup.sh` copies the file verbatim over the upstream clone; it imports upstream modules that exist only there.

## Flow
Upstream validator chain calls the registered validators per proxy -> format check, then the theblock sitemap fetch through the proxy -> pass or fail.

## Modules

### validator.py (86 LOC)

**Purpose:** Upstream validator with the theblock sitemap-index check registered as the only HTTP validator.
**Reads:** proxy candidates from the upstream pool; live theblock.co sitemap index.
**Writes:** nothing; returns booleans to the upstream chain.
**Called by:** upstream proxy_pool, after `jhao104/setup.sh` overlays it.
**Calls out:** `requests`, `curl_cffi`, upstream proxy_pool modules.

---

## State
No shared state beyond the upstream validator registry lists.
