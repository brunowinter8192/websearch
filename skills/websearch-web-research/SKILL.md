---
name: websearch-web-research
description:
---

# Web Research — Skill

**Die Ad-hoc-Suche schließt eine Lücke jetzt und indexiert nichts.**
- Indexierte Inhalte entstehen ausschließlich über den Deep Dive.

**Schreibe die Query in der Sprache, in der du die Ergebnisse haben willst.**
- Die Sprache des Chats gilt hier nicht.
- Eine Unterhaltung auf Deutsch bekommt trotzdem englische Queries, wenn englische Ergebnisse gewünscht sind.

## Commands

| Vorgang | Command |
|---|---|
| Über alle Engines suchen und die Trefferzahlen sehen | `websearch search_web "<query>"` |
| Die URLs einer einzelnen Engine ausklappen | `websearch search_engine_drilldown "<query>" --engine <name>` |
| Eine Seite in vollständiges Markdown wandeln | `websearch scrape_url_chromium <url>` |

### search_web

#### Input args

- `query` — 2 bis 5 Keywords, in Anführungszeichen.

#### Output

```
Engine breakdown for "<query>":
  google               8
  duckduckgo           0
  mojeek               10
  openalex             0
  startpage            10
  brave                10
  bing                 10
  yandex               0
```

- Die Zahl ist die Menge der URLs, die diese Engine zurückgegeben hat.

### search_engine_drilldown

**Schau dir die URLs einer oder mehrerer Engines an**
- Solltest du feststellen, dass eine Engine auf deine Query keine brauchbaren Ergebnisse liefert, versuche IMMER eine kürzere Query in anderen Worten.

#### Input args

- `query` — muss wörtlich der Query eines vorangegangenen `search_web` entsprechen.
- `--engine <name>` — `google`, `duckduckgo`, `mojeek`, `startpage`, `brave`, `bing`, `yandex` oder `openalex`.

#### Output

```
Results from <engine> for "<query>"

1. <Titel der Seite>
   URL: https://example.com/a
   Snippet: <Textauszug der Seite>

2. <Titel des Papers>
   URL: https://example.com/b
   PDF: https://example.com/b.pdf
```

### scrape_url_chromium

#### Input args

- `url` — eine einzelne URL.

#### Output

- Der vollständige Seiteninhalt als Markdown, ohne Längenbegrenzung.

---

## Deep Dive

**Starte einen Deep Dive, wenn auch andere URLs einer Domain für deine Fragestellung relevant sein könnten.**
- Diese Domaintypen kommen für einen Deep Dive meist infrage:
   - Dokumentation einer Bibliothek, eines Frameworks oder einer API.
   - Handbuch oder Referenz eines Herstellers.
- Diese Typen kommen meist nicht infrage:
   - Blog, News, Forum, Produktseite, Changelog, Release Feed.

### Step 1 — Festlegen der Seed-URL

1. Vorarbeit: Gehe über `search_web` und danach `search_engine_drilldown` zur gewünschten Seed-URL.
    - Das kann schon im Rahmen eines Ad-hoc-Scrapes erfolgt sein.

### Step 2 — Worker spawnen und idle gehen

**Der Worker meldet sich, wenn alles indexiert ist.**
- Die Meldung nennt die Collection, die Zahl der indexierten Seiten und jeden Fehler.
- Ab dann findest du die Inhalte über `rag-cli search` in der Collection.

1. Schreibe den Worker-Prompt nach `/tmp/spawn-capture-<domain>.md`.

   ```markdown
   You are a WORKER.
   FIRST: activate the websearch-capture-and-index skill via Skill(skill="websearch-capture-and-index").
   SEED_URL: <seed url>
   COLLECTION: websearch-pages
   INFO_NEED: <welche Frage du beantworten willst und warum du dafür Inhalte dieser Domain brauchst>
   ```

2. Spawne den Worker und geh idle.

   ```bash
   worker-cli spawn capture-<domain> /tmp/spawn-capture-<domain>.md
   ```
