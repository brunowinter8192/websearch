---
name: websearch-web-research
description:
---

# Web Research — Skill

**Der Standard ist der Permanent Capture Workflow.**
- Gehe immer von einem permanenten Capture nach RAG aus.
- Ein Ad-hoc-Scrape direkt im Chat passiert nur, wenn der Nutzer AUSDRÜCKLICH danach fragt.
- Die Umwandlung von PDF nach MD ist ein eigener Ablauf und steht im Skill `websearch-pdf`.

**Alles läuft über `websearch <command>`, das im PATH liegt, und zwar im Vordergrund.**
- Also ohne `&` und ohne Redirect.

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

**Der Einstieg in jede Recherche, danach entscheidest du selbst, welche Engine du ausklappst.**
- Für einen Deep-Dive feuerst du 2 bis 4 parallele Aufrufe mit Varianten der Query ab.

#### Input args

- `query` — 2 bis 5 Keywords, in Anführungszeichen.

#### Output

```
Engine breakdown for "dachziegel frostschaden erkennen":
  google               8
  duckduckgo           0
  mojeek               10
  openalex             0
  startpage            10
  brave                10
  bing                 10
  yandex               0
```

- Die Zahl ist die Menge der Treffer, die diese Engine beigesteuert hat.
- Eine 0 heißt, die Engine hat nichts geliefert, und nicht, dass es zu dieser Query nichts gibt.
- Das Ergebnis liegt im Cache, der Drilldown kostet also keinen zweiten Suchlauf.

### search_engine_drilldown

**Welche Engine du ausklappst, ist deine freie Wahl, geleitet von den Trefferzahlen.**
- Bei Papers und Büchern lohnt `openalex` zuerst, dessen Einträge tragen eine `PDF:`-Zeile mit der direkten URL zum Volltext.

#### Input args

- `query` — muss wörtlich der Query eines vorangegangenen `search_web` entsprechen.
- `--engine <name>` — `google`, `duckduckgo`, `mojeek`, `startpage`, `brave`, `bing`, `yandex` oder `openalex`.

#### Output

```
Results from brave for "dachziegel frostschaden erkennen"

1. Wie erkenne und verhindere ich Frostschäden am Dach?
   URL: https://www.dachdecker-spengler.com/wissenswertes/dachdeckerei/frostschaeden-am-dach/
   Snippet: Des Weiteren sind Ziegel aufgrund ihrer physischen Beschaffenheit nicht so massiv wie Dachsteine.
```

- `PDF:` erscheint nur, wo die Engine eine direkte Volltext-URL kennt, in der Praxis bei `openalex`.
- `Date:` erscheint nur, wo die Engine ein Datum liefert.
- Nennst du eine Engine, die für diese Query nichts im Cache hat, bekommst du die Liste der verfügbaren.

### scrape_url_chromium

**Es gibt genau eine Scrape-Lane, du wählst also nicht pro Aufruf.**

#### Input args

- `url` — eine einzelne URL.

#### Output

- Der vollständige Seiteninhalt als Markdown, ohne Längenbegrenzung.

**Scrape niemals eine `.pdf`-URL, das liefert einen Fehler.**
- Bei PDFs und Büchern gibst du dem Nutzer die exakten URLs aus den Suchergebnissen.
- Der Nutzer lädt sie selbst herunter.

---

## Permanent Capture Workflow

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
