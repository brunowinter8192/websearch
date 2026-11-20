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

### Step 0 — PDFs festlegen

1. Frage den User nach den PDFs und der Collection, falls er sie nicht genannt hat.
2. Benenne jedes PDF nach seinem Inhalt und sortiere es in ein Projektverzeichnis unter PDF_DIR ein.
   - Muster: Autor + Titel + Jahr in PascalCase, nur Buchstaben, Ziffern und Unterstrich.
       - Beispiel: `CoenenbergKostenrechnungKostenanalyse_2016.pdf`, der STEM ist `CoenenbergKostenrechnungKostenanalyse_2016`.
   - Ist unklar, in welches Verzeichnis das PDF gehört, frag den User.

### Step 1 — Extrahieren

1. Rufe `extract` auf.

   ```bash
   WORKFLOW extract --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_extract.txt 2>&1
   ```

2. Lies `BATCH_DIR/manifest.json`. Dort steht jeder Worker dieses PDFs mit seinem Prompt:
   - `tables` — `BATCH_DIR/prompt_tables.md`, fehlt, wenn das PDF keine Tabelle hat.
   - `figures` — `BATCH_DIR/prompt_figures.md`, fehlt, wenn das PDF keine Abbildung hat.
   - `outline` — `BATCH_DIR/prompt_outline.md`.
   - `pages-<a>-<b>` — `BATCH_DIR/prompt_pages_<a>-<b>.md`, ein Prompt je Seitenbereich.

### Step 2 — Tabellen, Abbildungen und Gliederung

1. Starte die Worker `tables`, `figures` und `outline` direkt nacheinander.

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

### Step 3 — Seiten

**Starte die Seiten-Worker erst nach `apply-outline`.**

**Es laufen nie mehr als 20 Worker gleichzeitig.**

1. Starte für jeden Seitenbereich aus dem Manifest einen Worker, alle direkt nacheinander.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-pages-<a>-<b> BATCH_DIR/prompt_pages_<a>-<b>.md
   ```

2. Rufe `status` auf, bis jeder Worker des PDFs `complete` ist.
   - `incomplete` nennt die Dateien, die noch fehlen.
   - Nur bei mehr als 20 Seitenbereichen: Kille jeden Worker, der `complete` ist, und starte den nächsten Seitenbereich.

#### Ein Worker wird von Anthropic geblockt

**Du erkennst den Block an zwei Dingen zusammen.**
- Der Worker ist idle, und `status` meldet ihn als `incomplete`.
- `worker-cli response pdf-<stem>-<worker> 1` zeigt `API Error: Output blocked by content filtering policy`.

1. Kille alle Worker dieses PDFs.
2. Notiere das PDF, den Worker und die fehlenden Dateien für den Report.
3. Mach mit dem nächsten PDF weiter.

### Step 4 — Zusammenführen

1. Rufe `assemble` auf, sobald jeder Worker `complete` ist.

   ```bash
   WORKFLOW assemble --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_assemble.txt 2>&1
   ```

2. Kille alle übrigen Worker dieses PDFs.

### Step 5 — Stichprobe

1. Öffne einen Lauf mit `sample`.

   ```bash
   WORKFLOW sample --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_<k>.txt 2>&1
   ```

2. Gib dem Stichproben-Worker den Lauf.
   - Lauf 1: Starte den Worker.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-sample BATCH_DIR/samples/run_1/prompt.md
   ```

   - Jeder weitere Lauf: Schicke dem Worker den neuen Prompt.

   ```bash
   worker-cli send pdf-<stem>-sample "Read BATCH_DIR/samples/run_<k>/prompt.md completely and follow it."
   ```

3. Der Lauf ist fertig, wenn der Worker idle ist und `BATCH_DIR/samples/run_<k>/findings.md` existiert.

4. Erzeuge den Bericht des Laufs und lies `BATCH_DIR/samples/run_<k>/report.md` vollständig.

   ```bash
   WORKFLOW sample-report --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_report_<k>.txt 2>&1
   ```

5. Prüfe jede Korrektur und jeden Fund gegen die Seite im PDF. Lies dazu die Seite mit dem Read-Tool.
   - Echt ist eine Korrektur, wenn der Text vorher vom Seitenbild abweicht und der Text nachher dem Seitenbild entspricht.
   - Ist eine Korrektur echt, aber selbst fehlerhaft, oder steht ein Fund ohne Korrektur in `findings.md`, schicke ihn dem Worker. Danach erzeugst du den Bericht erneut.

6. Schließe den Lauf. Nenne mit `--reject` jede Seite, deren Korrektur nicht echt ist.

   ```bash
   WORKFLOW sample-close --batch-dir BATCH_DIR [--reject <Seite> ...] > /tmp/pdf_<STEM>_sample_close_<k>.txt 2>&1
   ```

7. Die letzte Zeile der Ausgabe sagt, wie es weitergeht.
   - `loop continues`: Gehe zurück zu 1.
   - `loop ended`: Kille den Stichproben-Worker und gehe zu Step 6.

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

1. Schreibe den Report in diesem Format in den Chat.

   ```
   PDF-Konvertierung fertig
   Collection: <collection>
   Indexiert: <Zahl> PDFs, <Zahl> Chunks
   Nicht indexiert: <PDF mit Grund, oder "keine">
   Geblockte Worker: <PDF, Worker, oder "keine">
   Stichprobe: <PDF, Zahl der Läufe, geprüfte Seiten, übernommene und verworfene Korrekturen mit Seite>
   Fehler: <jeder Fehler aus allen Steps, oder "keine">
   ```

2. Geh idle.
