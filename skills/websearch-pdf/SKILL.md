---
name: websearch-pdf
description:
---

# PDF → MD → Index — Skill

## Pfade

- WEBSEARCH = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/websearch`
- WORKFLOW = `WEBSEARCH/venv/bin/python WEBSEARCH/cli.py pdf`
- PDF_MODELS = `WEBSEARCH/config/pdf_models.json`, legt `claude-haiku-5-5[1m]` als Worker-Modell fest.
- PDF_DIR = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf`
- OUTPUT_DIR = `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<COLLECTION>/`
- BATCH_DIR = `/tmp/pdf_<STEM>/`

---

## Workflow

**Step 1 bis 4 führst du für jedes PDF getrennt aus, Step 5 und 6 nur einmal am Ende für die ganze Collection.**
- Starte Step 5 erst, wenn alle PDFs Step 4 hinter sich haben.
- Nach Step 0 läuft der Skill ohne Rückfrage an den User bis zum Report in Step 6 durch.
- Scheitert ein PDF, notierst du es für den Report und machst mit den übrigen PDFs weiter.

### Step 0 — PDFs festlegen

1. Frage den User nach den PDFs und der Collection, falls er sie nicht genannt hat.

2. Benenne jedes PDF nach seinem Inhalt und sortiere es in ein Projektverzeichnis unter PDF_DIR ein.
   - PDF_DIR hat ein Unterverzeichnis je Projekt, z. B. `PDF_DIR/wise2627/`.
   - Ist unklar, in welches Verzeichnis das PDF gehört, frag den User.
   - Muster: Autor + Titel + Jahr in PascalCase, nur Buchstaben, Ziffern und Unterstrich.
       - Beispiel: `CoenenbergKostenrechnungKostenanalyse_2016.pdf`, der STEM ist dann `CoenenbergKostenrechnungKostenanalyse_2016`.

### Step 1 — Extraktion

**Rufe `extract` für jedes PDF nur ein einziges Mal auf.**
- `extract` löscht beim Start alle Dateien in BATCH_DIR, auch die fertigen Texte der Haiku-Worker.
- Ein zweiter Aufruf, nachdem Worker schon gelaufen sind, vernichtet also deren Arbeit.
- Hat das PDF keine Textebene, bricht `extract` mit Fehler ab. Notiere das für den Report und mach mit dem nächsten PDF weiter.

1. Rufe `extract` auf. Es teilt das PDF in Stapel zu je 50 Seiten und schreibt für jeden Stapel einen fertigen Prompt für einen Haiku-Worker nach BATCH_DIR.
   - Die Ausgabe landet in einer Datei, lies sie danach vollständig.

   ```bash
   WORKFLOW extract --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_extract.txt 2>&1
   ```

2. Lies `BATCH_DIR/manifest.json`. Dort stehen alle Stapel mit ihrem Seitenbereich, z. B. 1-50, 51-100, 101-150.
   - Zu jedem Stapel gibt es die Datei `BATCH_DIR/prompt_<von>-<bis>.md`, das ist der Prompt für seinen Worker.

### Step 2 — Haiku-Worker, einer pro Stapel

**Es laufen nie mehr als 20 Worker gleichzeitig.**
- `MODEL_SELECTION_FILE` vor dem Spawn sorgt dafür, dass der Worker mit Haiku statt mit Sonnet startet. Setze die Variable nur hier, bei allen anderen Workern nie.

1. Starte für jeden Stapel einen Haiku-Worker, alle direkt nacheinander, aber nie mehr als 20 gleichzeitig.
   - `<von>` ist die erste Seite des Stapels, `<bis>` die letzte.
   - Starte einen Spawn erst, wenn der vorige zurückgekehrt ist, nie mehrere parallel im Hintergrund mit `&`.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<von> BATCH_DIR/prompt_<von>-<bis>.md
   ```

2. Ein Worker ist fertig, wenn er idle ist und seine Datei `BATCH_DIR/batch_<von>-<bis>.md` existiert. Kille ihn dann.

   ```bash
   worker-cli kill pdf-<stem>-<von>
   ```

3. Nur bei mehr als 20 Stapeln: Starte für jeden beendeten Worker den nächsten Stapel, der noch keinen Worker hatte.

### Step 3 — Zusammenführen und Inhaltskontrolle

**`assemble` prüft jeden Stapel, bevor es etwas schreibt.**
- Es zählt die Buchstaben und Ziffern im Text des Workers und vergleicht sie mit dem Text, der im PDF selbst steckt. Fehlt zu viel, gilt der Stapel als gescheitert.
- Ein Stapel, zu dem es keine Datei `batch_<von>-<bis>.md` gibt, gilt ebenfalls als gescheitert.
- Ist auch nur ein Stapel gescheitert, schreibt `assemble` keine Datei nach OUTPUT_DIR und nennt in seiner Ausgabe die gescheiterten Stapel. 
- Vor dem Schreiben teilt `assemble` jeden zu langen Absatz in kürzere Absätze.

1. Rufe `assemble` auf. Sind alle Stapel in Ordnung, schreibt es das ganze Buch als eine Datei `<OUTPUT_DIR>/<STEM>.md`.
   - Die Ausgabe landet in einer Datei, lies sie danach vollständig.

   ```bash
   WORKFLOW assemble --batch-dir BATCH_DIR --out-dir <OUTPUT_DIR> > /tmp/pdf_<STEM>_assemble.txt 2>&1
   ```

2. Nennt `assemble` gescheiterte Stapel, finde für jeden Stapel selbst heraus, warum er gescheitert ist.
   - Vergleiche dazu `BATCH_DIR/batch_<von>-<bis>.md` mit denselben Seiten im PDF.
   - Fehlt im Text des Workers wirklich Inhalt, oder stimmt etwas mit dem PDF selbst nicht?
   - Beispiel: In einem PDF können zwei Textebenen übereinanderliegen. Dann zählt `assemble` denselben Text doppelt, obwohl der Text des Workers vollständig ist.

3. Entscheide danach, was zu tun ist.
   - Fehlt beim Worker wirklich Inhalt, bessere `BATCH_DIR/batch_<von>-<bis>.md` selbst aus, anhand derselben Seiten im PDF. Starte dafür keinen neuen Worker.
       - Rufe danach erneut `assemble` auf.
       - Scheitert `assemble` auch nach deiner Ausbesserung, wird das PDF nicht indexiert.
    - Blockt Anthropic den Worker, z. B. mit `API Error: Output blocked by content filtering policy`, übernimmst du den Stapel.
       - Entscheide, ob du ihn selbst 1:1 abschreibst.
       - Falls nein: Erzeuge `batch_<von>-<bis>.md` mit `pdftotext`, je Seite mit `<!-- page N -->` davor, und korrigiere anhand der Seitenbilder gezielt Erkennungsfehler, Überschriften, Zitate und Bildbeschreibungen.
       - Rufe danach erneut `assemble` auf.
 
### Step 4 — Stichprobe

1. Vergleiche je eine Stelle aus Anfang, Mitte und Ende von `<OUTPUT_DIR>/<STEM>.md` mit derselben Stelle im PDF.
   - Achte auf fehlende Absätze, erfundenen Text, zerbrochene Tabellen und Formeln, Abbildungen ohne Beschreibung.
       - Bei Funden entscheidest du, ob sie so gravierend sind, dass das PDF nicht indexiert werden kann.
       
### Step 5 — Index

1. Indexiere die Collection und geh idle, bis der Lauf fertig ist.
   - Polle nicht, du wirst benachrichtigt.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <COLLECTION> > /tmp/<COLLECTION>_index.log 2>&1
   ```

2. Lies `/tmp/<collection>_index.log` vollständig und notiere jeden Fehler für den Report.
   - Zum Beispiel eine Datei, die rag-cli nicht chunken oder embedden konnte.

### Step 6 — Report

1. Schreibe den Report in diesem Format in den Chat.

   ```
   PDF-Konvertierung fertig
   Collection: <collection>
   Indexiert: <Zahl> PDFs, <Zahl> Chunks
   Nicht indexiert: <PDF mit Grund, oder "keine">
   Funde der Stichprobe: <PDF, Seite, Fund, oder "keine">
   Fehler: <jeder Fehler aus allen Steps, oder "keine">
   ```

2. Geh idle.