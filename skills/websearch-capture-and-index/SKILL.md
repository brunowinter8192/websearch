---
name: websearch-capture-and-index
description:
---

# Capture-and-Index — Skill

**Mehrere Domains laufen nacheinander.**
- Nimm eine Domain durch Schritt 1 bis Schritt 4 und fange danach mit der nächsten wieder bei Schritt 1 an.

**Fehler werden in Schritt 4 gemeldet und niemals mitten im Capture behandelt.**

## Schritt 1 — Discovery

**Input, den der Main Agent mit dem Go benennt.**
- `<seed_url>` hält eine Seed-URL pro Domain.

1. Führe die Discovery gegen die Seed-URL aus.

   ```bash
   cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch
   ./venv/bin/python cli.py discover_urls "<seed_url>" --url-file /tmp/<domain>_urls.txt
   ```

2. 🛑 STOP und melde:
   - den absoluten Pfad von `/tmp/<domain>_urls.txt`, eine URL pro Zeile, als klickbaren Link

3. Geh idle.

## Schritt 2 — Scrape

**Input, den der Main Agent mit dem Go benennt.**
- `<culled_url_file>` hält die URLs, die gescrapet werden.

1. Scrape die zusammengestrichene Liste.

   ```bash
   cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch
   ./venv/bin/python -m src.crawler.pipe_scraper \
       --url-file <culled_url_file> \
       --output-dir /tmp/<domain>/ > /tmp/<domain>_scrape.log 2>&1
   ```

2. Geh idle, sobald dieses Command läuft.
   - Es geht von selbst in den Hintergrund, und `/tmp/<domain>_scrape.log` trägt seine Summary-Zeile, sobald es zurückkommt.

3. Teile die Link-Datei auf, die pipe_scraper geschrieben hat.

   ```bash
   comm -13 <(sort /tmp/<domain>_urls.txt) <(sort /tmp/<domain>_scrape_links.txt) > /tmp/<domain>_new_links.txt
   comm -12 <(sort /tmp/<domain>_urls.txt) <(sort /tmp/<domain>_scrape_links.txt) > /tmp/<domain>_known_links.txt
   ```

4. 🛑 STOP und melde:
   - den absoluten Pfad von `/tmp/<domain>/`, als klickbaren Link
   - den absoluten Pfad von `/tmp/<domain>_new_links.txt`, als klickbaren Link

5. Geh idle.
   - Der Main Agent liest die Dateien und entscheidet zwischen einer weiteren Scrape-Runde und Schritt 3.

## Schritt 3 — Cleanup

**Dieser Schritt startet, wenn der Main Agent sagt, dass es zu Schritt 3 geht, und in keinem anderen Moment.**

**Rauschen stehen zu lassen ist besser, als Inhalt herauszuschneiden.**
- Eine Passage, über die man streiten kann, bleibt drin.

**Eine Defektklasse nach der anderen, von Anfang bis Ende, bevor die nächste benannt wird.**

**Eine Datei, bei der es so aussieht als wäre der Scrape schiefgegangen, wandert in den Report von Schritt 4.**
- Beim Cleanup fällt so etwas auf, also notiere es im Vorbeigehen und mach mit dem Cleanup weiter.

### Stufe 1 — Stichprobe

1. Wähle eine `.md` aus `/tmp/<domain>/` und lies sie mit dem Read-Tool von vorne bis hinten, jede Zeile.

2. Benenne die Defektklassen, die du darin siehst.
   - Jede Klasse trägt den Anker, über den sie sich identifizieren lässt.

### Stufe 2 — Ein Skript pro Klasse

1. Schreibe `/tmp/clean_<class>_<domain>.py` in `python3`.
   - Der Dry-Run ist der Standard, `--apply` ist ein eigener, getrennter Lauf.

2. Lass das Skript zwei Dinge schreiben.
   - die bereinigten `.md`-Dateien, direkt an Ort und Stelle, und zwar nur unter `--apply`
   - `/tmp/cut_<class>_<domain>.md` mit jeder entfernten Passage im Wortlaut, und zwar immer, auch im Dry-Run

3. Gib `cut_` einen Block pro Passage, ohne irgendetwas drumherum.

   ```
   <filename>:<start_line>-<end_line>
   <the removed text, verbatim>
   ```

4. Lass es zuerst trocken laufen.
   - Die `.md`-Dateien bleiben unangetastet, bis Stufe 3 die Klasse freigibt.

### Stufe 3 — Lies was du geschnitten hast, dann wende es an

1. Lies `/tmp/cut_<class>_<domain>.md` mit dem Read-Tool, mit `offset` über die Datei gestuft.
   - Stufe so weit, bis du Passagen vom Anfang, aus der Mitte und vom Ende gesehen hast.

2. Behalte jede Passage, die du nicht als Rauschen einordnen kannst.
   - Verenge den Anker, lass erneut trocken laufen und lies erneut.

3. Sichere und wende an, sobald sich jede Passage als Rauschen liest.
   - Kopiere ganz `/tmp/<domain>/` nach `/tmp/<domain>_PRE_<class>_BACKUP/` und führe dann `--apply` aus.

### Stufe 4 — Verifiziere, dann nimm die nächste Klasse

1. Scanne die Klasse erneut über `/tmp/<domain>/` und erwarte null verbleibende Treffer.

2. Lies 10 bis 15 Zeilen aus der Mitte von zwei bereinigten Dateien.

3. Bestätige, dass jede Datei weiterhin ihre Zeile `<!-- source: URL -->` trägt.

4. Geh zu Stufe 1 für die nächste Klasse.

## Schritt 4 — Report

**Melde, dass das Cleanup fertig ist, und geh idle.**
- den absoluten Pfad von `/tmp/<domain>/`, wo die bereinigten `.md`-Dateien liegen, als klickbaren Link
- jeden Fehler jeder Art, über den du in allen vier Schritten gestolpert bist
