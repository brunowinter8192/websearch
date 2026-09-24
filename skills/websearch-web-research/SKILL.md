---
name: websearch-web-research
description:
---

# Web Research — Skill

**Mache einen Deep Dive wenn auch andere urls einer Domain für deine Fragestellung relevant sein könnten**
- Diese Domaintypen kommen für einen Deep Dive meist infrage:
   - Dokumentation einer Bibliothek, eines Frameworks oder einer API.
   - Handbuch oder Referenz eines Herstellers.
- Diese Typen kommen meist nicht infrage:
   - Blog, News, Forum, Produktseite, Changelog, Release Feed.
- Schlage dem User proaktiv einen Deep Dive vor.

**Schreibe die Query in der Sprache, in der du die Ergebnisse haben willst.**
- Die Sprache des Chats gilt hier nicht.
- Eine Unterhaltung auf Deutsch bekommt trotzdem englische Queries, wenn englische Ergebnisse gewünscht sind.

## Commands

| Vorgang | Command |
|---|---|
| Über alle Engines suchen und die Trefferzahlen sehen | `websearch search_web "<query>"` |
| Die URLs einer einzelnen Engine ausklappen | `websearch search_engine_drilldown "<query>" --engine <name>` |
| Eine Seite in vollständiges Markdown wandeln | `websearch scrape_url_chromium <url>` |
| Bereits gescrapete Seiten in eine Collection legen | `websearch index_scrapes <collection> <url> [<url> ...]` |

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

**Schau dir die URLs eines oder mehrerer Engines an**
- Solltest du feststellen, dass eine Engine auf deine Query keine brauchbaren Ergebnisse liefert, versuche IMMER eine kürzere Query in anderen Worten.

**PDF-URLs werden IMMER an den User zum Download gegeben**
- Bevorzuge PDFs vor anderen Webinhalten.
- Die `PDF:`-Zeile ist der einzige Weg zum Volltext, denn eine `.pdf`-URL lässt sich nicht scrapen.
- Der Nutzer lädt selbst, die Umwandlung nach Markdown steht im Skill `websearch-pdf`.

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

### index_scrapes

**Jede Seite, die du mit `scrape_url_chromium` gescrapet hast, liegt auf der Platte und ist direkt indexierbar**
- Sofern du den Inhalt der URL gelesen hast, stelle dir folgende Fragen:
    - Kann eine spätere Session vom Inhalt der Website profitieren?
    - Besteht bei der Website die Gefahr, dass sie in den nächsten 1 bis 2 Monaten überholt ist?
- NUR wenn die erste mit ja und die zweite mit nein zu beantworten ist, schlage dem User ein Indexieren der Website vor
    - Frage den Nutzer nach der Zielcollection, bevor du das Kommando aufrufst.

#### Input args

- `collection` — der Name der Ziel-Collection, die bereits existieren muss.
- `url` — eine oder mehrere URLs, die zuvor in dieser Session gescrapet wurden.

#### Output

```
indexed: https://example.com/a -> example_com_a.md (18365 bytes)
no sidecar found: https://example.com/b
failed: https://example.com/c (<Grund>)
```

- Die Bytezahl ist die Größe der abgelegten Datei.
- Eine auffällig kleine Datei ist meist eine Block- oder Fehlerseite und gehört nicht in die Collection.
   - Melde das dem Nutzer, statt es stillschweigend stehen zu lassen.
- Nennst du eine Collection, die es nicht gibt, bricht das Kommando ab und legt nichts an.

---

## Deep Dive Workflow

**Fehler, die der Worker meldet, stoppen den Ablauf nicht.**
- Führe den Ablauf bis zum Ende durch, es sei denn ein Fehler ist so schwer, dass ein Weitermachen unmöglich wird.

### Schritt 1 — Quelle

1. Frage den Nutzer nach der Ziel-Collection und schlage `<current_project>-reference` vor.

2. Steige über `search_web` und danach `search_engine_drilldown` zur Seed-URL hinab.

3. Schreibe den Worker-Prompt nach `/tmp/spawn-capture-<domain>.md`.

   ```markdown
   You are a WORKER.
   FIRST: activate the websearch-capture-and-index skill via Skill(skill="websearch-capture-and-index").
   SEED_URL: <seed url>
   ```

4. Spawne den Worker.

   ```bash
   worker-cli spawn capture-<domain> /tmp/spawn-capture-<domain>.md <current_project_root> sonnet
   ```

**Hinweis**
- Der Worker führt die Discovery aus, meldet den Pfad der vollständigen URL-Liste und geht idle.

### Schritt 2 — Cull Review

**Input, den der Worker übergibt.**
- `/tmp/<domain>_urls.txt` hält die vollständige Discovery-Liste, eine URL pro Zeile.

1. Schrumpfe die Liste über Muster, bis der Rest in einem Durchgang lesbar ist. Das ist reines Matching und keine inhaltliche Beurteilung.
   - Auf `platform.claude.com` hieß das: eine Sprache behalten, die Console-Routen streichen, die API-Referenz streichen. Aus 3571 Zeilen wurden 242.

2. Lies jede verbleibende Zeile vollständig, mit dem Read-Tool.

3. Schreibe die behaltenen URLs selbst nach `/tmp/<domain>_urls_culled.txt` und lass `/tmp/<domain>_urls.txt` unangetastet.

4. Bestätige, dass jede behaltene URL auch in `/tmp/<domain>_urls.txt` steht.

   ```bash
   comm -23 <(sort /tmp/<domain>_urls_culled.txt) <(sort /tmp/<domain>_urls.txt)
   ```

5. Gib dem Worker das Go und nenne `/tmp/<domain>_urls_culled.txt` als die Datei, die gescrapet wird.
   - Oder sag dem Worker, dass nichts mehr gescrapet wird.

**Hinweis**
- Der Worker scrapet und übergibt dir eine weitere txt mit URLs, nämlich denen, die er auf den gescrapeten Seiten gefunden hat. Entscheide, welche davon gescrapet werden, und behandle jede behaltene genau wie die ursprünglichen URLs in Schritt 2.
- Sobald nichts mehr gescrapet wird, bereinigt der Worker die gescrapeten Inhalte.

### Schritt 3 — Index

**Input, den der Worker übergibt.**
- `/tmp/<domain>/` hält die bereinigten `.md`-Dateien.

1. Kopiere sie in das Verzeichnis der Collection.

   ```bash
   D=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<collection>
   mkdir -p $D && cp /tmp/<domain>/*.md $D/
   ```

2. Ziehe Stichproben aus den kopierten Dateien und bestätige, dass das vom Worker geschnittene Rauschen weg ist.
   - Melde übrig gebliebenes Rauschen und stoppe.

3. Diffe die URLs der Domain in der Collection gegen die vollständige Discovery-Liste.

   ```bash
   grep -h -m1 '<!-- source:' $D/*.md | sed 's|.*source: ||;s| -->||' \
     | grep '^https://<domain>/' | sort > /tmp/<domain>_indexed_urls.txt
   comm -23 /tmp/<domain>_indexed_urls.txt <(sort /tmp/<domain>_urls.txt)
   ```

4. Zeige dem Nutzer jede URL, die der Diff ausgegeben hat, und lösche auf sein Wort.

   ```bash
   grep -l 'source: <url> -->' $D/*.md
   rag-cli delete --collection <collection> --document <file>
   ```

5. Indexiere die Collection.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <collection> > /tmp/<collection>_index.log 2>&1
   ```

6. Geh idle, sobald dieses Command läuft, und polle es nie.

7. Lies `/tmp/<collection>_index.log` vollständig, sobald der Lauf beendet ist.

8. Nenne dem Nutzer jeden Fehler, und sonst nichts.
   - Das sind die Indexierungsfehler aus dem Log, alles was der Worker gemeldet hat und alles worüber du selbst gestolpert bist.
