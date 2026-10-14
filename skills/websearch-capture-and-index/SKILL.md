---
name: websearch-capture-and-index
description:
---

# Capture-and-Index — Skill

**Input aus dem Spawn-Prompt.**
- `SEED_URL` — die Einstiegsseite der Domain.
- `COLLECTION` — die Ziel-Collection.
- `INFO_NEED` — der Informationsbedarf des Main Agents, dein einziger Maßstab für Relevanz.

**Fehler werden in Step 6 gemeldet und stoppen den Ablauf nicht.**
- Führe den Ablauf bis zum Ende durch, es sei denn ein Fehler macht ein Weitermachen unmöglich.

## Step 1 — Discovery

1. Führe die Discovery gegen die Seed-URL aus.

   ```bash
   cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch
   ./venv/bin/python cli.py discover_urls "<seed_url>" --url-file /tmp/<domain>_urls.txt
   ```

## Step 2 — Cull

1. Filtere die Liste so weit es geht
   - Auf `platform.claude.com` hieß das: eine Sprache behalten, die Console-Routen streichen, die API-Referenz streichen. Aus 3571 Zeilen wurden 242.

2. Lies jede verbleibende Zeile vollständig

3. Behalte jede URL, die `INFO_NEED` dienen kann.
   - Bist du dir unsicher, ob eine URL dem `INFO_NEED` zuträglich ist, so lass sie weg.

4. Schreibe die behaltenen URLs nach `/tmp/<domain>_urls_culled.txt`.

## Step 3 — Scrape

1. Scrape die gefilterte Liste.

   ```bash
   cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch
   ./venv/bin/python -m src.crawler.pipe_scraper \
       --url-file <culled_url_file> \
       --output-dir /tmp/<domain>/ > /tmp/<domain>_scrape.log 2>&1
   ```

2. Geh idle, bis der Scrape fertig ist.
   - Polle nicht, du wirst benachrichtigt.

3. Hole die neuen Links aus den gescrapten Seiten.
   - pipe_scraper sammelt alle Links der gescrapten Seiten in `/tmp/<domain_underscored>_scrape_links.txt`.
      - Die Punkte im Domainnamen werden zu Unterstrichen, zum Beispiel `/tmp/docs_pytest_org_scrape_links.txt`.
   - Streiche daraus jede URL, die schon in der Discovery stand oder schon gescrapt wurde.

   ```bash
   cat /tmp/<domain>_urls.txt <culled_url_file> >> /tmp/<domain>_seen.txt
   comm -13 <(sort -u /tmp/<domain>_seen.txt) <(sort -u /tmp/<domain_underscored>_scrape_links.txt) > /tmp/<domain>_new_links.txt
   ```

4. Lies `/tmp/<domain>_new_links.txt` vollständig und behalte jede URL, die `INFO_NEED` dienen kann.

5. Gibt es behaltene neue URLs, schreibe sie in eine neue URL-Datei, scrape sie wie in 1 und wiederhole ab 3.
   - Sobald keine neue URL mehr behalten wird, geht es zu Step 4.

## Step 4 — Cleanup

**Der Cleanup räumt genau zwei Dinge ab.**
- Dateien von gescheiterten Scrapes.
- Verschmutzungen in den übrigen Dateien.

### Stage 1 — Gescheiterte Scrapes

**Eine extrem kleine Datei ist das deutlichste Zeichen für einen gescheiterten Scrape.**
- Beispiel: `test.com` lieferte eine Cloudflare-Sperrseite mit 506 Bytes statt des Inhalts.

1. Liste die Dateien in `/tmp/<domain>/` nach Größe, die kleinste zuerst.

   ```bash
   ls -lSr /tmp/<domain>/
   ```

2. Lies die Dateien von der kleinsten an, bis du auf echten Inhalt triffst.

3. Verschiebe jede Datei ohne echten Inhalt nach `/tmp/<domain>_failed/`.
   - Sie wird nicht indexiert und steht im Report von Step 6.

### Stage 2 — Stichprobe der Verschmutzung

**Jede verschmutzte Passage wird entweder bereinigt oder komplett gelöscht.**
- Lässt sich die Verschmutzung vom Inhalt trennen, bereinige die Passage.
- Lässt sie sich nicht trennen, lösche die Passage komplett.

**Bearbeite eine Defektklasse nach der anderen**
- cleane zuerst alle mds vollständig in bezug auf eine klasse, bevor du mit der nächsten beginnst.

1. Wähle eine `.md` aus `/tmp/<domain>/` und lies sie mit dem Read-Tool von vorne bis hinten, jede Zeile.

2. Benenne die Defektklassen, die du darin siehst.
   - Jede Klasse trägt den Anker, über den sie sich identifizieren lässt.

### Stage 3 — Ein Skript pro Klasse

**Das Skript hat zwei Modi, Probelauf und echter Lauf.**
- Ohne Flag macht es einen Probelauf.
   - escschreibt nur auf, was es schneiden würde.
- Mit `--apply` macht es den echten Lauf.
   - Es schneidet die Passagen wirklich aus den `.md`-Dateien.

**In beiden Modi schreibt das Skript jede geschnittene Passage nach `/tmp/cut_<class>_<domain>.md`.**
- Ein Block pro Passage, ohne irgendetwas drumherum:

   ```
   <filename>:<start_line>-<end_line>
   <the removed text, verbatim>
   ```

1. Schreibe für die Defektklasse ein Python-Skript, das ihre Defekte aus allen `.md`-Dateien schneidet.
   - Das Skript liegt unter `/tmp/clean_<class>_<domain>.py`.

2. Starte den Probelauf.

### Stage 4 — Bewerte was du geschnitten hast

1. Lies `/tmp/cut_<class>_<domain>.md` mit dem Read-Tool, ggf. mit `offset`.
    - nimm Stichproben von dem war wirklich geschnitten werden würde.

2. Hat das Skript eine saubere Passage mitgeschnitten, passe das skritp an. 
   - Starte erneut den Probelauf und lies erneut.

3. Starte den echten Lauf, sobald jeder Schnitt nur Verschmutzung oder untrennbar verschmutzte Passagen trifft.
   - Kopiere vorher ganz `/tmp/<domain>/` als Sicherung nach `/tmp/<domain>_PRE_<class>_BACKUP/`.

### Stage 5 — Verifiziere, dann nimm die nächste Klasse

1. Suche den Anker der Klasse erneut in allen Dateien unter `/tmp/<domain>/`.
   - Gibt es noch Treffer, hat das Skript sie verfehlt.
   - Passe das Skript so an, dass es diese Treffer erfasst, und geh zurück zu Stage 4.

2. Bestätige, dass jede Datei weiterhin ihre Zeile `<!-- source: URL -->` trägt.

3. Geh zu Stage 2 für die nächste Klasse.

## Step 5 — Index

1. Kopiere die bereinigten Dateien in das Verzeichnis der Collection.

   ```bash
   D=~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<collection>
   mkdir -p $D && cp /tmp/<domain>/*.md $D/
   ```

2. Indexiere die Collection und geh idle, bis der Lauf fertig ist.
   - Polle nicht, du wirst benachrichtigt.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <collection> > /tmp/<collection>_index.log 2>&1
   ```

3. Lies `/tmp/<collection>_index.log` vollständig und notiere jeden Fehler für den Report.
   - Zum Beispiel eine Datei, die rag-cli nicht chunken oder embedden konnte.

## Step 6 — Report

1. Schreibe ausschließlich diese fünf Zeilen in den Chat, nichts davor und nichts danach.

   ```
   Deep Dive fertig: <domain>
   Collection: <collection>
   Indexiert: <Zahl> Seiten
   Gescheiterte Scrapes: <Dateien aus /tmp/<domain>_failed/ oder "keine">
   Fehler: <jeder Fehler aus allen Steps oder "keine">
   ```

2. Geh idle.