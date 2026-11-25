---
name: websearch-pdf
description:
---

# PDF → MD → Index — Skill

## Pfade

- WEBSEARCH = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch`
- WORKFLOW = `WEBSEARCH/venv/bin/python WEBSEARCH/cli.py pdf`
- PDF_MODELS = `WEBSEARCH/config/pdf_models.json`
- PDF_DIR = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf`
- OUTPUT_DIR = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<COLLECTION>/`
- BATCH_DIR = `/tmp/pdf_<STEM>/`

---

## Workflow

**Step 1 bis 6 führst du für jedes PDF getrennt aus, Step 7 und 8 einmal am Ende für die ganze Collection.**
- Nach Step 0 läuft der Skill ohne Rückfrage an den User bis zum Report in Step 8 durch.
- Scheitert ein PDF, notierst du es für den Report und machst mit den übrigen PDFs weiter.

**Jeder Aufruf von WORKFLOW schreibt seine Ausgabe in eine Datei, lies sie danach vollständig.**
- Ein Aufruf, der scheitert, endet mit `FAILED` und nennt den Grund.

**Nach jedem `spawn` und jedem `send` folgt `worker-cli wait`.**

**Es laufen nie mehr als 20 Worker gleichzeitig, über alle PDFs gezählt.**

**Ein Worker, der idle ist und den `status` als `incomplete` meldet, bekommt seine fehlenden Dateien.**
- Prüfe zuerst, ob er geblockt wurde, wie in Step 3 beschrieben.

   ```bash
   worker-cli send pdf-<stem>-<worker> "Write the missing files: <Dateien aus status>"
   ```

**Endet `apply-outline` oder `assemble` mit `FAILED`, reparierst du die genannte Stelle selbst und rufst den Schritt erneut auf.**
- Der Ablauf steht unter "Reparatur nach FAILED".
- Du fragst den User dafür nicht.
- Lässt sich die Stelle nicht wahrheitsgemäß reparieren, geht das PDF auf den Bildweg.

**Endet `extract` mit `FAILED`, geht das PDF auf den Bildweg.**
- Der Ablauf steht unter "Bildweg".
- Du fragst den User dafür nicht.

### Reparatur nach FAILED

**Maßstab jeder Reparatur ist das Seitenbild, nicht die Prüfung.**
- Eine Reparatur ist wahrheitsgemäß, wenn die Datei danach dem Seitenbild entspricht.
- Eine Änderung, die nur die Prüfung zufriedenstellt und dem Seitenbild widerspricht, ist keine Reparatur.
- Die Prüflisten des Tools, zum Beispiel `*_missing.txt`, werden nie geändert oder gelöscht.

1. Lies die Meldung hinter `FAILED`. Sie nennt die Fehlerklasse, die Seite und die Datei.
2. Lies die genannte Datei und die Seite im PDF mit dem Read-Tool, bei einer Region zusätzlich `BATCH_DIR/<tables|figures>/<id>.png`.
3. Lege eine Kopie der Datei als `<Datei>.bak` an und korrigiere die Datei nach der Tabelle unten.
4. Rufe den gescheiterten Schritt erneut auf und lies die Ausgabe vollständig.
   - Nennt sie eine weitere Stelle, gehst du zurück zu 1.
5. Notiere jede Reparatur für den Report: PDF, Datei, was geändert wurde.

| Fehlerklasse | Beobachteter Fall | Reparatur |
|---|---|---|
| `heading_marks_changed` | `pages/p<n>_fixed.md` trägt eine Überschrift, die `pages/p<n>_outlined.md` nicht hat. Beobachtet beim Titel eines Inhaltsverzeichnisses. | Die Überschriftenzeichen der Datei werden an `p<n>_outlined.md` angeglichen. Steht der Text der Zeile schon an anderer Stelle der Seite, zum Beispiel in der Tabelle, wird die Zeile entfernt. Sonst bleibt er als normaler Absatz stehen. |
| `ambiguous_page_join` | Die letzte Fußnote der Seite endet im Druck ohne Satzzeichen, zum Beispiel auf einem Linktitel. | Endet die Fußnote laut Seitenbild auf dieser Seite, bekommt sie in `pages/p<n>_fixed.md` einen Punkt am Ende. Läuft sie laut Seitenbild auf der nächsten Seite weiter, bleibt sie unverändert. |
| `region_word_missing` | Der Ausschnitt der Region zeigt mehr als die Tabelle, zum Beispiel eine Quellenzeile oder eine Diagrammbeschriftung darüber. | Die fehlenden Wörter werden so in die `_fixed.md` der Region geschrieben, wie der Ausschnitt sie zeigt, an der Stelle, an der sie im Ausschnitt stehen. |

**Lässt sich eine Stelle nicht wahrheitsgemäß reparieren, geht das PDF auf den Bildweg.**
- Beobachteter Fall: Die Wortliste einer Tabelle hängt auch an einer Abbildung mit derselben Nummer, zum Beispiel an einem Logo, das die Wörter nicht zeigt.
- Stelle jede `.bak` dieses PDFs wieder her.
- Kille alle Worker dieses PDFs.
- Notiere das PDF, die Meldung und den Grund für den Report.
- Gehe nach "Bildweg" vor.

**Eine Fehlerklasse, die nicht in der Tabelle steht, behandelst du nach demselben Maßstab.**
- Notiere sie im Report als neue Fehlerklasse.

### Bildweg

**Der Bildweg ist der Fallback für ein PDF, an dem `extract` scheitert oder dessen Reparatur nicht wahrheitsgemäß möglich ist.**
- Beobachteter Fall: ein in PowerPoint gebautes Faktenblatt, jede Seite ein Dashboard aus Diagrammen, Karten, Quellenzeilen und einer großen Tabelle.
- Worker schreiben jede Seite aus dem Seitenbild als Markdown.
- Die Textschicht des PDFs prüft danach jedes Wort und jede Zahl.
- Der Bildweg ersetzt für dieses PDF Step 1 bis 6.
- IMG_DIR = `/tmp/pdfimg_<STEM>/`

**Der Bildweg setzt eine Textschicht voraus.**
- Liefert `pdftotext` für eine Seite mit sichtbarem Text keinen Text, wird das PDF nicht indexiert.
- Notiere das PDF und den Grund für den Report und mach mit dem nächsten PDF weiter.

1. Erzeuge je Seite ein Bild und die Textschicht.

   ```bash
   mkdir -p IMG_DIR/png IMG_DIR/txt IMG_DIR/md IMG_DIR/prompts
   pdftoppm -r 200 -png "PDF_DIR/<Projekt>/<STEM>.pdf" IMG_DIR/png/p
   pdftotext -f <n> -l <n> -layout "PDF_DIR/<Projekt>/<STEM>.pdf" IMG_DIR/txt/p<n>.txt
   ```

2. Schreibe je Seite einen Prompt nach `IMG_DIR/prompts/p<n>.md`.

   ```
   You are a WORKER. You convert exactly one PDF page to Markdown from its page image.

   Read these two files completely before you write anything:
   - IMG_DIR/png/p-<n>.png — the image of page <n>
   - IMG_DIR/txt/p<n>.txt — the text layer of the same page (output of pdftotext -layout)

   Write exactly one file: IMG_DIR/md/p<n>.md

   Rules:
   - The image decides what belongs together, the reading order, and which value stands in which row and column.
   - The text layer decides the characters: every word and every number you write is spelled exactly as in the text layer. Where image and text layer disagree on a character, the text layer wins.
   - Write every word and every number printed on the page. Nothing is summarized, nothing is added, nothing is rounded.
   - Headings become Markdown headings. Running text becomes paragraphs. A word hyphenated at a line end is joined.
   - A table becomes a Markdown pipe table: one row per printed row, one column per printed column. A header cell that spans several columns is repeated in each column it spans. Empty cells stay empty. N/A stays N/A.
   - A chart, map or diagram becomes one paragraph that starts with "**Figure description (not source text):**", names its title and lists every printed label together with its value, for example "Finland 20,8%". The source line of the chart follows as its own paragraph, word for word.
   - A logo becomes a one-sentence figure description.
   - The file contains no page number, no comment and no note about your work.

   Your file is checked automatically: every number in it must occur in the text layer, and every word and number of the text layer must occur in it.

   Do not edit any other file. Do not use any tool to fetch external information.
   When the file is written, reply with the single line: done p<n>
   ```

3. Starte je Seite einen Worker, alle direkt nacheinander.
   - Eine Seite je Worker, weil jede Seite unabhängig ist und ein Worker so genau ein Bild und eine Textschicht hält.
   - Die Grenze von 20 Workern gilt: Kille jeden Worker, dessen Datei `IMG_DIR/md/p<n>.md` existiert, und starte die nächste Seite.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-img-<n> IMG_DIR/prompts/p<n>.md
   ```

4. Prüfe jede Seite gegen die Textschicht, sobald alle Dateien `IMG_DIR/md/p<n>.md` existieren.

   ```bash
   python3 - IMG_DIR <<'EOF' > /tmp/pdf_<STEM>_imgcheck.txt 2>&1
   import re, sys, pathlib, unicodedata
   base = pathlib.Path(sys.argv[1])
   norm = lambda s: "".join(c for c in unicodedata.normalize("NFKC", s).casefold() if c.isalnum())
   nums = lambda s: set(re.findall(r"\d+(?:[.,]\d+)*", s))
   for txt in sorted(base.glob("txt/p*.txt"), key=lambda p: int(p.stem[1:])):
       md = (base / "md" / (txt.stem + ".md")).read_text(encoding="utf-8")
       layer = txt.read_text(encoding="utf-8")
       invented = sorted(nums(md) - nums(layer))
       lost_numbers = sorted(nums(layer) - nums(md))
       flat = norm(md)
       lost_words = sorted({w for w in layer.split() if len(norm(w)) > 2 and not norm(w).isdigit() and norm(w) not in flat})
       print(f"{txt.stem}: numbers not in text layer {invented} | numbers missing {lost_numbers} | words missing {lost_words}")
   EOF
   ```

   - Lies `/tmp/pdf_<STEM>_imgcheck.txt` vollständig.
   - Eine Zahl, die nicht in der Textschicht steht, ist ein Lesefehler.
   - Eine fehlende Zahl oder ein fehlendes Wort ist eine Auslassung, außer die Textschicht trennt das Wort am Zeilenende.
   - Schicke jede Seite mit Lesefehler oder Auslassung an ihren Worker zurück und prüfe erneut.

   ```bash
   worker-cli send pdf-<stem>-img-<n> "Your file fails the check. Numbers not in the text layer: <Liste>. Missing numbers: <Liste>. Missing words: <Liste>. Correct IMG_DIR/md/p<n>.md against image and text layer."
   ```

   - Scheitert eine Seite nach zwei Rücksendungen weiter, korrigierst du sie selbst mit dem Edit-Tool gegen das Seitenbild.

5. Prüfe eine Stichprobe selbst gegen das PDF. Lies dazu die Seite mit dem Read-Tool.
   - Geprüft wird jede fünfte Seite, mindestens zwei Seiten, darunter jede Seite mit einer Tabelle über mehr als 20 Zeilen.
   - Die Textschicht prüft nur die Zeichen. Du prüfst, ob jeder Wert in der richtigen Zeile und Spalte steht.
   - Eine falsch zugeordnete Stelle korrigierst du selbst mit dem Edit-Tool.

6. Kille alle Worker dieses PDFs und setze die Seiten zusammen.

   ```bash
   for n in $(seq 1 <Seiten>); do printf '<!-- page %s -->\n\n' "$n"; cat IMG_DIR/md/p$n.md; printf '\n\n'; done > "<OUTPUT_DIR>/<STEM>.md"
   ```

7. Notiere für den Report: PDF, Bildweg, Zahl der Rücksendungen je Seite, geprüfte Seiten der Stichprobe und eigene Korrekturen.

### Step 0 — PDFs festlegen

1. Frage den User nach den PDFs und der Collection, falls er sie nicht genannt hat.
2. Benenne jedes PDF nach seinem Inhalt und sortiere es in ein Projektverzeichnis unter PDF_DIR ein.
   - Muster: Autor + Titel + Jahr in PascalCase, nur Buchstaben, Ziffern und Unterstrich.
       - Beispiel: `CoenenbergKostenrechnungKostenanalyse_2016.pdf`, der STEM ist `CoenenbergKostenrechnungKostenanalyse_2016`.
   - Ist unklar, in welches Verzeichnis das PDF gehört, frag den User.
3. Teile jedes PDF, dessen Seiten zwei Buchseiten nebeneinander zeigen.

   ```bash
   WORKFLOW split-spreads --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --out "/tmp/<STEM>_split.pdf" > /tmp/pdf_<STEM>_split.txt 2>&1
   ```

   - Meldet die Ausgabe `spreads=0`, bleibt das PDF, wie es ist.
   - Sonst ersetzt `/tmp/<STEM>_split.pdf` das PDF unter `PDF_DIR/<Projekt>/<STEM>.pdf`.

### Step 1 — Extrahieren

1. Rufe `extract` auf.

   ```bash
   WORKFLOW extract --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_extract.txt 2>&1
   ```

   - Endet `extract` mit `FAILED`, gehst du für dieses PDF nach "Bildweg" vor.

2. Lies `BATCH_DIR/manifest.json`. Dort steht jeder Worker dieses PDFs mit seinem Prompt:
   - `tables` — `BATCH_DIR/prompt_tables.md`, fehlt, wenn das PDF keine Tabelle hat.
   - `figures` — `BATCH_DIR/prompt_figures.md`, fehlt, wenn das PDF keine Abbildung hat.
   - `formulas` — `BATCH_DIR/prompt_formulas.md`, fehlt, wenn das PDF keine Formel hat.
   - `outline` — `BATCH_DIR/prompt_outline.md`.
   - `pages-<a>-<b>` — `BATCH_DIR/prompt_pages_<a>-<b>.md`, ein Prompt je Seitenbereich.

### Step 2 — Tabellen, Abbildungen, Formeln und Gliederung

**Hänge vor dem Start diesen Block an das Ende von `BATCH_DIR/prompt_figures.md` an.**

   ```
   Additional rules. They take precedence over the rules above.
   - A region that shows only printed text is written as that text, word for word, not as a figure description.
   - A region that shows a table is written as a Markdown pipe table, not as a figure description.
   - A blank to fill in is written as _____.
   ```

1. Starte die Worker `tables`, `figures`, `formulas` und `outline` direkt nacheinander.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<worker> BATCH_DIR/prompt_<worker>.md
   ```

2. Prüfe, welche Worker fertig sind.

   ```bash
   WORKFLOW status --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_status.txt 2>&1
   ```

3. Ist `outline` `complete`, setze die Gliederung in die Seiten ein und kille den Worker.

   ```bash
   WORKFLOW apply-outline --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_outline.txt 2>&1
   worker-cli kill pdf-<stem>-outline
   ```

   - Endet `apply-outline` mit `FAILED`, gehst du nach "Reparatur nach FAILED" vor.

### Step 3 — Seiten

**Starte die Seiten-Worker erst nach `apply-outline`.**

**Hänge vor dem Start diesen Block an das Ende jedes `BATCH_DIR/prompt_pages_<a>-<b>.md` an.**

   ```
   Additional corrections. They take precedence over "Change nothing else".
   - Reading order: the blocks of a page stand in the order in which the image is read. If the image shows two book pages side by side, all blocks of the left book page come first, then all blocks of the right book page, each from top to bottom. A heading line moves together with the block below it.
   - Tables: rows and columns that the image shows as a table or as a list in columns, and that stand as running text in the Markdown, are written as a Markdown pipe table. A line <!-- TABLE ... --> stays as it is.
   - Blanks: a blank to fill in is written as _____.
   - Running headers, running footers and page numbers of the print are removed.
   - Text that the image shows and the Markdown lacks is added, word for word.
   - Text that the image does not show is removed.
   ```

1. Starte für jeden Seitenbereich aus dem Manifest einen Worker, alle direkt nacheinander.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-pages-<a>-<b> BATCH_DIR/prompt_pages_<a>-<b>.md
   ```

2. Rufe `status` auf, bis jeder Worker des PDFs `complete` ist.
   - `incomplete` nennt die Dateien, die noch fehlen.
   - Erreichst du die Grenze von 20 Workern: Kille jeden Worker, der `complete` ist, und starte den nächsten Seitenbereich.

#### Ein Worker wird von Anthropic geblockt

**Du erkennst den Block an zwei Dingen zusammen.**
- Der Worker ist idle, und `status` meldet ihn als `incomplete`.
- `worker-cli response pdf-<stem>-<worker> 1` zeigt `API Error: Output blocked by content filtering policy`.

**Ein geblockter Seiten-Worker wird durch einen Fallback-Worker ersetzt, der die Seiten nur mit dem Edit-Tool repariert.**

1. Kille den geblockten Worker.
2. Bereite den Fallback vor und lies die Ausgabe vollständig.

   ```bash
   WORKFLOW fallback --batch-dir BATCH_DIR --worker <worker> > /tmp/pdf_<STEM>_fallback.txt 2>&1
   ```

3. Starte einen neuen Worker mit dem Fallback-Prompt.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<worker>-fallback BATCH_DIR/prompt_fallback_<worker>.md
   ```

4. Rufe `status` auf, bis `<worker>` `complete` ist.
   - Ist der Fallback-Worker idle und `<worker>` noch `incomplete`, schicke ihm die Dateien aus `status`.

   ```bash
   worker-cli send pdf-<stem>-<worker>-fallback "Repair these files as your prompt says: <Dateien aus status>"
   ```

5. Notiere das PDF und den Worker für den Report als geblockt und per Fallback repariert.

**Wird auch der Fallback-Worker geblockt, oder endet `fallback` mit `FAILED`, wird das PDF nicht indexiert.**
- Kille alle Worker dieses PDFs.
- Notiere das PDF, den Worker und die fehlenden Dateien für den Report.
- Mach mit dem nächsten PDF weiter.

### Step 4 — Zusammenführen

1. Rufe `assemble` auf, sobald jeder Worker `complete` ist.

   ```bash
   WORKFLOW assemble --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_assemble.txt 2>&1
   ```

   - Endet `assemble` mit `FAILED`, gehst du nach "Reparatur nach FAILED" vor.

2. Prüfe nach `assemble ok` die Zeile `page joins` der Ausgabe.
   - Jeder Eintrag mit `(footnote)` hängt Text der Folgeseite an eine Fußnote an.
   - Lies für jeden dieser Einträge die Fußnote im zusammengeführten Markdown und die Seite im PDF mit dem Read-Tool.
   - Beobachteter Fall: Eine Fußnote endet im Druck ohne Satzzeichen, und `assemble` hängt Fließtext der Folgeseite an sie an.
   - Endet die Fußnote laut Seitenbild auf ihrer Seite, bekommt sie in `pages/p<n>_fixed.md` einen Punkt am Ende, wie unter "Reparatur nach FAILED".
   - Rufe danach `assemble` erneut auf und prüfe die Zeile noch einmal.

3. Kille alle übrigen Worker dieses PDFs.

### Step 5 — Stichprobe

1. Öffne einen Lauf mit `sample`.

   ```bash
   WORKFLOW sample --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_<k>.txt 2>&1
   ```

2. Starte für jeden Teil des Laufs einen eigenen Worker, alle direkt nacheinander. Die Ausgabe von `sample` nennt die Teile unter `part prompts`.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-sample-<k>-<i> BATCH_DIR/samples/run_<k>/prompt_part_<i>.md
   ```

3. Der Lauf ist fertig, wenn jeder Teil seine Datei `BATCH_DIR/samples/run_<k>/findings_part_<i>.md` geschrieben hat. Kille dann die Worker des Laufs.
   - Ein Worker, der länger als 15 Minuten an derselben Seite steht, wird gekillt und mit demselben Prompt neu gestartet.

4. Erzeuge den Bericht des Laufs und lies `BATCH_DIR/samples/run_<k>/report.md` vollständig.

   ```bash
   WORKFLOW sample-report --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_report_<k>.txt 2>&1
   ```

5. Prüfe jede Korrektur und jeden Fund gegen die Seite im PDF. Lies dazu die Seite mit dem Read-Tool.
   - Echt ist eine Korrektur, wenn der Text vorher vom Seitenbild abweicht und der Text nachher dem Seitenbild entspricht.
   - Ist eine Korrektur echt, aber selbst fehlerhaft, oder steht ein Fund ohne Korrektur im Bericht, korrigiere die Excerpt-Datei selbst mit dem Edit-Tool. Danach erzeugst du den Bericht erneut.
   - Eine Korrektur, die der Bericht mit `DUPLICATE` kennzeichnet, prüfst du nicht. `sample-close` verwirft sie selbst.
   - Steht bei einer Korrektur `WARNING: an inserted text already ends a paragraph`, nenne die Seite mit `--reject`.

6. Schließe den Lauf. Nenne mit `--reject` jede Seite, deren Korrektur nicht echt ist.

   ```bash
   WORKFLOW sample-close --batch-dir BATCH_DIR [--reject <Seite> ...] > /tmp/pdf_<STEM>_sample_close_<k>.txt 2>&1
   ```

7. Die letzte Zeile der Ausgabe sagt, wie es weitergeht.
   - `loop continues`: Gehe zurück zu 1.
   - `loop ended`: Gehe zu Step 6.

8. Notiere für den Report je Lauf die Zahl der geprüften Seiten und die übernommenen und verworfenen Korrekturen mit Seite.

### Step 6 — Veröffentlichen

1. Rufe `publish` auf.

   ```bash
   WORKFLOW publish --batch-dir BATCH_DIR --out-dir <OUTPUT_DIR> > /tmp/pdf_<STEM>_publish.txt 2>&1
   ```

### Step 7 — Index

1. Indexiere die Collection und geh idle, bis der Lauf fertig ist.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <COLLECTION> > /tmp/<COLLECTION>_index.log 2>&1
   ```

2. Lies `/tmp/<COLLECTION>_index.log` vollständig und notiere jeden Fehler für den Report.

### Step 8 — Report

1. Schreibe den Report in diesem Format in des wein Chat.

   ```
   PDF-Konvertierung fertig
   Collection: <collection>
   Indexiert: <Zahl> PDFs, <Zahl> Chunks
   Nicht indexiert: <PDF mit Grund, oder "keine">
   Geblockte Worker: <PDF, Worker, per Fallback repariert oder nicht indexiert, oder "keine">
   Reparaturen: <PDF, Datei, was geändert wurde, oder "keine">
   Bildweg: <PDF, Grund, Rücksendungen je Seite, geprüfte Seiten, eigene Korrekturen, oder "keine">
   Stichprobe: <PDF, Zahl der Läufe, geprüfte Seiten, übernommene und verworfene Korrekturen mit Seite>
   Fehler: <jeder Fehler aus allen Steps, oder "keine">
   ```

2. Geh idle.


