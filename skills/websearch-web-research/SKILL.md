---
name: websearch-web-research
description:
---

# Web Research — Skill

**Default = Permanent Capture Workflow.**
Assume permanent capture into RAG — always. Ad-hoc in-chat scraping only when the user EXPLICITLY asks for it. (PDF → MD conversion is a separate flow — see the `websearch-pdf` skill.)

Run via `websearch <command>` (in PATH), foreground — no `&`, no redirect.

## Commands

| Command | Args | Does |
|---|---|---|
| search_web | query (2–5 keywords) | Search: counts per engine |
| search_engine_drilldown | query --engine <name> | URLs for one engine from the prior search_web |
| scrape_url_chromium | url | Page → full markdown |

**One scrape lane, no per-call choice.**
It returns pruned markdown (PruningContentFilter). Page didn't come through → the returned content itself will show it (an error/block page, a 404); report that plainly, do not retry silently.

## Search Strategy

1. `search_web` for the engine breakdown. For a deep dive, fire 2–4 parallel calls with query variations.
2. `search_engine_drilldown` to get an engine's URLs — which engine(s) is your free choice, guided by the breakdown counts.
   - For papers and books, prefer drilling `openalex` — its entries carry a `PDF:` line with the direct full-text URL.
3. `scrape_url_chromium` the relevant URLs. PDFs and books: give the user the exact URLs from the search results — the user downloads them. Do not scrape a `.pdf` URL (it returns an error: the PDF must be downloaded by the user).

**Write the query in the language you want results in.**
The user-chat language does not apply here — a German conversation still gets English queries when English results are wanted.

---

## Permanent Capture Workflow

**Errors the worker reports do not stop the flow.**
- Carry it through to the end, unless an error is severe enough to make continuing impossible.

### Step 1 — Source

1. Ask the user for the target collection and propose `<current_project>-reference`.

2. Drill down to the seed URL via `search_web` → `search_engine_drilldown`.

3. Write the worker prompt to `/tmp/spawn-capture-<domain>.md`.

   ```markdown
   You are a WORKER.
   FIRST: activate the websearch-capture-and-index skill via Skill(skill="websearch-capture-and-index").
   SEED_URL: <seed url>
   ```

4. Spawn the worker.

   ```bash
   worker-cli spawn capture-<domain> /tmp/spawn-capture-<domain>.md <current_project_root> sonnet
   ```

**Insight**
- The worker runs discovery, reports the path of the full URL list, and goes idle.

### Step 2 — Cull Review

**Input, handed over by the worker.**
- `/tmp/<domain>_urls.txt` holds the full discovery list, one URL per line.

1. Shrink the list by pattern until the rest is readable in one pass. No judgment, pure matching.
   - On `platform.claude.com` that was: keep one language, drop the console routes, drop the API reference. 3571 lines became 242.

2. Read every remaining line in full, with the Read tool.

3. Write the kept URLs to `/tmp/<domain>_urls_culled.txt` yourself, and leave `/tmp/<domain>_urls.txt` untouched.

4. Confirm every kept URL appears in `/tmp/<domain>_urls.txt`.

   ```bash
   comm -23 <(sort /tmp/<domain>_urls_culled.txt) <(sort /tmp/<domain>_urls.txt)
   ```

5. Give the worker the go and name `/tmp/<domain>_urls_culled.txt` as the file to scrape.
   - Or tell the worker that nothing gets scraped anymore.

**Insight**
- The worker scrapes and hands you another txt of URLs, the ones it found on the scraped pages. Decide which of them get scraped, and treat any you keep exactly like the initial URLs in Step 2.
- Once nothing gets scraped anymore, the worker cleans the scraped content.

### Step 3 — Index

**Input, handed over by the worker.**
- `/tmp/<domain>/` holds the cleaned `.md` files.

1. Copy them into the collection directory.

   ```bash
   D=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<collection>
   mkdir -p $D && cp /tmp/<domain>/*.md $D/
   ```

2. Sample the copied files and confirm the noise the worker cut is gone.
   - Report leftover noise and stop.

3. Diff the domain's URLs in the collection against the full discovery list.

   ```bash
   grep -h -m1 '<!-- source:' $D/*.md | sed 's|.*source: ||;s| -->||' \
     | grep '^https://<domain>/' | sort > /tmp/<domain>_indexed_urls.txt
   comm -23 /tmp/<domain>_indexed_urls.txt <(sort /tmp/<domain>_urls.txt)
   ```

4. Show the user every URL the diff printed, and delete on their word.

   ```bash
   grep -l 'source: <url> -->' $D/*.md
   rag-cli delete --collection <collection> --document <file>
   ```

5. Index the collection.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <collection> > /tmp/<collection>_index.log 2>&1
   ```

6. Go idle once that command has been run, and never poll it.

7. Read `/tmp/<collection>_index.log` in full when the run has finished.

8. Tell the user every error, and nothing else.
   - The indexing errors from the log, plus everything the worker reported and everything you ran into yourself.
