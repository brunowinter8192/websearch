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

## Formregeln

**Das fertige Markdown hat über alle Stapel hinweg dieselbe Form.**
- Der Prompt gibt jedem Worker die Formregeln mit.
- Jeder Worker sieht aber nur seinen Stapel, deshalb können die Stapel eines PDFs trotzdem voneinander abweichen.
- Du bist der Einzige, der alle Stapel sieht, die Einheitlichkeit über die Stapel hinweg ist deshalb deine Aufgabe.
- Die Formregeln sind der Maßstab der Formkontrolle in Step 3.

**Überschriften folgen der Gliederung des PDFs, nicht der Schriftgröße auf der Seite.**
- Der Titel des Werks steht als `#`, jedes Kapitel als `##`, jedes Unterkapitel als `###`, jede Ebene darunter als `####`.
- Derselbe Rang hat in allen Stapeln dieselbe Ebene.
    - Beobachteter Fehler: Kapitel 1, 2, 6 und 7 standen als `#`, die Kapitel 3 bis 5 und 8 bis 11 als `##`.
- Hat das PDF kein Inhaltsverzeichnis, z. B. ein Aufsatz oder ein Foliensatz, steht der Titel als `#` und jeder Abschnitt oder jede Folienüberschrift als `##`.

**Ein Absatz, der über eine Seitengrenze läuft, bleibt ein Absatz.**
- Der Absatz steht vollständig auf der Seite, auf der er beginnt.
- Die Zeile `<!-- page N -->` der Folgeseite steht erst hinter seinem Ende, nie mitten in einem Satz.
    - Beobachteter Fehler: „…killed annually in the United States by“, dann der Seitenmarker, dann „terrorists…“.
- Dasselbe gilt an der Grenze zwischen zwei Stapeln.

**Fußnoten haben in allen Stapeln dasselbe Format.**
- Das Fußnotenzeichen im Text steht als `[^N]`.
- Der Fußnotentext steht als `[^N]: <Text>` am Ende der Seite, auf der er gedruckt ist.
- Nie eine angehängte Ziffer wie `dignity.1`, nie `<sup>14</sup>`.

**Anführungszeichen stehen so, wie sie gedruckt sind.**
- Gerade und typografische Anführungszeichen werden innerhalb eines PDFs nie gemischt.

**Jede Abbildung hat eine Beschreibung in einem festen Format.**
- Die Beschreibung ist ein eigener Absatz und steht nie mitten in einem Absatz des Fließtextes.
- Sie beginnt in allen Stapeln mit `**Figure description (not source text):**`.
    - Die Beschreibung stammt vom Worker und nicht vom Autor, sie darf deshalb nie als Zitat aus dem Werk gelesen werden.
- Die gedruckte Bildunterschrift bleibt normaler Text und steht direkt unter der Beschreibung.

**Im Markdown steht kein Verweis auf eine Bilddatei.**
- Der Workflow erzeugt keine Bilddateien, ein Verweis wie `![](img_p218_1.png)` zeigt deshalb ins Leere.
- An seiner Stelle steht die Beschreibung der Abbildung.

**Eine leere Seite ist kein Fund.**
- Eine Seite, die nur aus ihrer Zeile `<!-- page N -->` besteht, bleibt so stehen.

---

## Workflow

**Step 1 bis 6 führst du für jedes PDF getrennt aus, Step 7 und 8 nur einmal am Ende für die ganze Collection.**
- Starte Step 7 erst, wenn alle PDFs Step 6 hinter sich haben.
- Nach Step 0 läuft der Skill ohne Rückfrage an den User bis zum Report in Step 8 durch.
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
- `extract` löscht beim Start alle Dateien in BATCH_DIR, auch die fertigen Texte der Worker.
- Ein zweiter Aufruf, nachdem Worker schon gelaufen sind, vernichtet also deren Arbeit.

**`extract` entscheidet je PDF, ob es eine Textebene hat, und schreibt das als `mode` ins Manifest.**
- `mode` ist `text`, wenn das PDF eine Textebene hat. Der Worker bekommt dann zu den Seitenbildern einen Ankertext.
- `mode` ist `scan`, wenn das PDF keine Textebene hat. Der Worker liest dann nur die Seitenbilder und überträgt Zeichen und Struktur vom Bild, einen Ankertext gibt es nicht.
- Ein PDF hat immer genau einen `mode`, auch wenn nur einzelne Seiten gescannt sind.

1. Rufe `extract` auf. Es teilt das PDF in Stapel zu je 50 Seiten und schreibt für jeden Stapel einen fertigen Prompt für einen Worker nach BATCH_DIR.
   - Die Ausgabe landet in einer Datei, lies sie danach vollständig.

   ```bash
   WORKFLOW extract --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_extract.txt 2>&1
   ```

2. Lies `BATCH_DIR/manifest.json`. Dort stehen der `mode` und alle Stapel mit ihrem Seitenbereich, z. B. 1-50, 51-100, 101-150.
   - Zu jedem Stapel gibt es die Datei `BATCH_DIR/prompt_<von>-<bis>.md`, das ist der Prompt für seinen Worker.
   - Nur bei `mode` `scan` gibt es zusätzlich `BATCH_DIR/prompt_control.md`, das ist der Prompt für den Kontroll-Worker.
       - `extract` lost dafür 10 % der Seiten aus, zufällig über alle Stapel verteilt. Die ausgelosten Seiten stehen im Manifest unter `control_pages`.

3. Schreibe die Gliederung des PDFs nach `BATCH_DIR/outline.md`.
   - Die Quelle ist das Inhaltsverzeichnis des PDFs. Lies dazu die Seiten des Inhaltsverzeichnisses mit dem Read-Tool.
   - Je Zeile stehen die Ebene nach den Formregeln und der Wortlaut der Überschrift, z. B. `## 3 Risk and Uncertainty`.
   - Hat das PDF kein Inhaltsverzeichnis, steht in `outline.md` nur die Zeile mit dem Titel als `#` und der Satz `no table of contents, every section heading is ##`.
   - `outline.md` ist in Step 3 der Maßstab für die Überschriften aller Stapel.

### Step 2 — Übertragungs-Worker, einer pro Stapel

**Es laufen nie mehr als 20 Worker gleichzeitig.**
- `MODEL_SELECTION_FILE` vor dem Spawn sorgt dafür, dass der Worker mit Haiku statt mit Sonnet startet. Setze die Variable nur hier, bei allen anderen Workern nie.

**Ein fertiger Worker bleibt am Leben, bis sein Stapel die Formkontrolle in Step 3 bestanden hat.**
- Der Worker hat die Seiten seines Stapels noch im Kontext und kann seine Datei deshalb selbst korrigieren.
- Ein gekillter Worker kann das nicht mehr, dann bleibt die Korrektur an dir hängen.

1. Starte für jeden Stapel einen Worker, alle direkt nacheinander, aber nie mehr als 20 gleichzeitig.
   - `<von>` ist die erste Seite des Stapels, `<bis>` die letzte.
   - Starte einen Spawn erst, wenn der vorige zurückgekehrt ist, nie mehrere parallel im Hintergrund mit `&`.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<von> BATCH_DIR/prompt_<von>-<bis>.md
   ```

2. Ein Worker ist fertig, wenn er idle ist und seine Datei `BATCH_DIR/batch_<von>-<bis>.md` existiert.

3. Nur bei mehr als 20 Stapeln: Führe für jeden fertigen Stapel sofort Step 3 aus, kille seinen Worker und starte dann den nächsten Stapel, der noch keinen Worker hatte.

#### Ein Worker wird von Anthropic geblockt

**Einen geblockten Stapel teilst du in kleinere Stücke, jedes Stück bekommt einen eigenen Haiku-Worker.**
- Du erkennst den Block an drei Dingen zusammen: Der Worker ist idle, seine Datei `batch_<von>-<bis>.md` fehlt, und `worker-cli response pdf-<stem>-<von> 1` zeigt `API Error: Output blocked by content filtering policy`.
- Derselbe Stapel noch einmal oder ein anderes Modell hilft nicht.
    - Beobachtet: Zwei Aufsätze wurden je dreimal versucht, einmal mit Haiku und zweimal ohne `MODEL_SELECTION_FILE`, alle sechs Versuche wurden geblockt.
- Die Übertragung bleibt Sache der Worker, du schreibst einen geblockten Stapel nie selbst ab.

**Die Stücke werden in drei Stufen kleiner: 20 Seiten, dann 10 Seiten, dann 5 Seiten.**
- In jeder Stufe teilst du nur, was geblockt wurde. Ein Stück, dessen Datei existiert, bleibt wie es ist.
- Ist das geblockte Stück nicht größer als die Stückgröße der nächsten Stufe, überspringst du diese Stufe.
    - Beispiel: Ein geblockter Stapel von 18 Seiten beginnt mit Stücken zu 10 Seiten.
- Wird auch ein Stück von 5 Seiten geblockt, wird das PDF nicht indexiert. Notiere das PDF und die Seiten des Stücks für den Report.
- Es laufen auch hier nie mehr als 20 Worker gleichzeitig.

1. Kille den geblockten Worker.

2. Schreibe für jedes Stück den Prompt `BATCH_DIR/prompt_piece_<a>-<b>.md`, `<a>` ist die erste Seite des Stücks, `<b>` die letzte.
   - Der Prompt ist eine Kopie von `BATCH_DIR/prompt_<von>-<bis>.md` mit genau drei Änderungen, alles andere bleibt Wort für Wort gleich.
   - Die Zeile `Pages of this batch:` nennt `<a>-<b>`.
   - Die Zeile `Output file:` nennt `BATCH_DIR/piece_<a>-<b>.md`.
   - Unter `Steps:` stehen nur diese Schritte, die erste Zeile nur bei `mode` `text`:

   ```
   1. Read the anchor text file completely. It covers more pages than your piece, use only the pages <a>-<b>.
   2. Read the PDF pages <a>-<b> with the Read tool (pages parameter "<a>-<b>"), so you see every page as an image.
   3. Write the Markdown for the pages <a>-<b> to the output file with the Write tool in one call.
   4. When the file is written, reply with one line: done, number of pages written, and anything you could not transcribe.
   ```

3. Starte für jedes Stück einen Haiku-Worker.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-p<a> BATCH_DIR/prompt_piece_<a>-<b>.md
   ```

4. Ein Stück ist fertig, wenn sein Worker idle ist und `BATCH_DIR/piece_<a>-<b>.md` existiert. Ein geblocktes Stück geht in die nächste Stufe.

5. Sind alle Stücke des Stapels fertig, füge sie in der Reihenfolge der Seiten zur Datei des Stapels zusammen.

   ```bash
   cd BATCH_DIR && { cat piece_<a1>-<b1>.md; echo; cat piece_<a2>-<b2>.md; echo; cat piece_<a3>-<b3>.md; } > batch_<von>-<bis>.md
   ```

6. Für die Formkontrolle in Step 3 gilt jede Grenze zwischen zwei Stücken wie eine Grenze zwischen zwei Stapeln.
   - Kein Worker sieht beide Seiten der Grenze, einen Absatz über die Grenze fügst du selbst zusammen.
   - Die Funde eines Stücks schickst du an den Worker dieses Stücks, er korrigiert `piece_<a>-<b>.md`. Füge die Stücke danach erneut zusammen.

### Step 3 — Formkontrolle

**Die Formkontrolle läuft auf den Dateien `BATCH_DIR/batch_<von>-<bis>.md`, also vor dem Zusammenführen.**
- `assemble` liest genau diese Dateien, jede Korrektur dort landet deshalb im fertigen Markdown.
- `assemble` prüft nur den Inhalt, die Form prüft niemand außer dir.

1. Erzeuge die Prüfliste für alle Stapel des PDFs und lies sie vollständig.

   ```bash
   cd BATCH_DIR
   echo '== Überschriften =='; grep -n '^#' batch_*.md
   echo '== letzte Textzeile vor jedem Seitenmarker =='; grep -n -B2 '^<!-- page' batch_*.md
   echo '== Fußnoten nicht als [^N] =='; grep -n -E '<sup>|[[:alpha:].,;:!?”"’)][0-9]{1,3}([[:space:]]|$)' batch_*.md
   echo '== gerade Anführungszeichen =='; grep -c '"' batch_*.md
   echo '== typografische Anführungszeichen =='; grep -c '[„“”]' batch_*.md
   echo '== Abbildungen =='; grep -n -i -E 'figure|abbildung' batch_*.md
   echo '== Bildverweise =='; grep -n '!\[' batch_*.md
   ```

2. Prüfe die Liste gegen die Formregeln.
   - Überschriften: Jede Überschrift hat die Ebene, die `outline.md` für ihren Rang nennt.
   - Seitenmarker: Die letzte Textzeile vor einem Seitenmarker endet mit einem Satzende. Endet sie mitten im Satz, läuft der Absatz über die Seitengrenze.
   - Fußnoten: Jeder Treffer ist ein Fußnotenzeichen im falschen Format oder eine gewöhnliche Zahl. Unterscheide das an der Stelle im Text.
   - Anführungszeichen: Haben beide Zählungen Treffer, sind die Zeichen gemischt.
   - Abbildungen: Jede Beschreibung ist ein eigener Absatz und beginnt mit `**Figure description (not source text):**`.
   - Bildverweise: Jeder Treffer ist ein Fund.

3. Schicke jedem Worker die Funde seines Stapels, er korrigiert seine Datei `batch_<von>-<bis>.md` selbst.
   - Nenne je Fund die Formregel im Wortlaut, die Zahl der Stellen und bis zu fünf Stellen mit Seite als Beispiel.
   - Nenne bei Überschriften den Pfad `BATCH_DIR/outline.md`.
   - Nach jedem `send` folgt ein `worker-cli wait`.

   ```bash
   worker-cli send pdf-<stem>-<von> "<Funde>"
   ```

4. Führe die Prüfliste nach der Korrektur genau ein weiteres Mal aus.
   - Es gibt eine einzige Korrekturrunde je Stapel.
   - Was danach noch abweicht, notierst du für den Report unter Funde der Formkontrolle.
   - Ein Fund der Formkontrolle verhindert die Indexierung nicht, das tut nur ein Fund am Inhalt.

5. Korrigiere selbst, was kein Worker korrigieren kann.
   - Ein Absatz, der vom letzten Blatt eines Stapels ins erste Blatt des nächsten läuft: Kein Worker sieht beide Stapel, füge den Absatz im vorderen Stapel zusammen.
   - Der Worker des Stapels lebt nicht mehr, z. B. nach einem Block durch Anthropic: Korrigiere die Datei mit dem Edit-Tool.

6. Kille jeden Worker, dessen Stapel die Formkontrolle hinter sich hat.

   ```bash
   worker-cli kill pdf-<stem>-<von>
   ```

### Step 4 — Kontroll-Worker, nur bei `mode` `scan`

1. Starte den Kontroll-Worker, sobald alle Stapel die Formkontrolle hinter sich haben und ihre Worker gekillt sind.
   - Es läuft ein einziger Kontroll-Worker für das ganze PDF.
   - Er liest für jede ausgeloste Seite das Seitenbild und vergleicht es mit dem Text des Übertragungs-Workers.
   - Er meldet je geprüfter Seite, ob der Text stimmt, und nennt jede Abweichung: fehlende Absätze, verlesene Zahlen, erfundenen Text, zerbrochene Tabellen.
   - Er stuft jede Abweichung als gravierend oder nicht gravierend ein und schreibt seinen Befund nach `BATCH_DIR/control.json`.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-control BATCH_DIR/prompt_control.md
   ```

2. Der Kontroll-Worker ist fertig, wenn er idle ist und `BATCH_DIR/control.json` existiert. Kille ihn dann.

   ```bash
   worker-cli kill pdf-<stem>-control
   ```

### Step 5 — Zusammenführen und Inhaltskontrolle

**`assemble` prüft jeden Stapel, bevor es etwas schreibt.**
- Ein Stapel, zu dem es keine Datei `batch_<von>-<bis>.md` gibt, gilt als gescheitert.
- Bei `mode` `text` zählt es die Buchstaben und Ziffern im Text des Workers und vergleicht sie mit dem Text, der im PDF selbst steckt. Fehlt zu viel, gilt der Stapel als gescheitert.
- Bei `mode` `scan` gibt es im PDF keinen Text zum Zählen. `assemble` wertet stattdessen den Befund des Kontroll-Workers in `BATCH_DIR/control.json` aus.
    - Fehlt `control.json` oder fehlt darin eine ausgeloste Seite, gilt die Kontrolle als gescheitert.
    - Hat auch nur eine geprüfte Seite einen gravierenden Fund, gilt die Kontrolle als gescheitert.
- Ist auch nur ein Stapel oder die Kontrolle gescheitert, schreibt `assemble` keine Datei nach OUTPUT_DIR und nennt in seiner Ausgabe die gescheiterten Stapel und die Seiten mit Funden.
- Vor dem Schreiben teilt `assemble` jeden zu langen Absatz in kürzere Absätze.

1. Rufe `assemble` auf. Sind alle Stapel in Ordnung, schreibt es das ganze Buch als eine Datei `<OUTPUT_DIR>/<STEM>.md`.
   - Die Ausgabe landet in einer Datei, lies sie danach vollständig.

   ```bash
   WORKFLOW assemble --batch-dir BATCH_DIR --out-dir <OUTPUT_DIR> > /tmp/pdf_<STEM>_assemble.txt 2>&1
   ```

2. Nur bei `mode` `scan`: Nennt `assemble` Seiten mit gravierenden Funden, wird das PDF nicht indexiert.
   - Notiere die Seiten und die Funde für den Report und mach mit dem nächsten PDF weiter.
   - Nicht gravierende Funde nennt `assemble` in seiner Ausgabe, notiere sie für den Report unter Funde der Stichprobe.

3. Nur bei `mode` `text`: Nennt `assemble` gescheiterte Stapel, finde für jeden Stapel selbst heraus, warum er gescheitert ist.
   - Vergleiche dazu `BATCH_DIR/batch_<von>-<bis>.md` mit denselben Seiten im PDF.
   - Fehlt im Text des Workers wirklich Inhalt, oder stimmt etwas mit dem PDF selbst nicht?
   - Beispiel: In einem PDF können zwei Textebenen übereinanderliegen. Dann zählt `assemble` denselben Text doppelt, obwohl der Text des Workers vollständig ist.

4. Nur bei `mode` `text`: Entscheide danach, was zu tun ist.
   - Fehlt beim Worker wirklich Inhalt, bessere `BATCH_DIR/batch_<von>-<bis>.md` selbst aus, anhand derselben Seiten im PDF. Starte dafür keinen neuen Worker.
       - Rufe danach erneut `assemble` auf.
       - Scheitert `assemble` auch nach deiner Ausbesserung, wird das PDF nicht indexiert.
   - Ein von Anthropic geblockter Worker gehört nicht hierher, ihn behandelst du in Step 2 mit kleineren Stücken.

### Step 6 — Stichprobe

1. Vergleiche je eine Stelle aus Anfang, Mitte und Ende von `<OUTPUT_DIR>/<STEM>.md` mit derselben Stelle im PDF.
   - Achte auf fehlende Absätze, erfundenen Text, zerbrochene Tabellen und Formeln, Abbildungen ohne Beschreibung.
       - Bei Funden entscheidest du, ob sie so gravierend sind, dass das PDF nicht indexiert werden kann.

### Step 7 — Index

1. Indexiere die Collection und geh idle, bis der Lauf fertig ist.
   - Polle nicht, du wirst benachrichtigt.

   ```bash
   PYTHONUNBUFFERED=1 rag-cli index --collection <COLLECTION> > /tmp/<COLLECTION>_index.log 2>&1
   ```

2. Lies `/tmp/<collection>_index.log` vollständig und notiere jeden Fehler für den Report.
   - Zum Beispiel eine Datei, die rag-cli nicht chunken oder embedden konnte.

### Step 8 — Report

1. Schreibe den Report in diesem Format in den Chat.

   ```
   PDF-Konvertierung fertig
   Collection: <collection>
   Indexiert: <Zahl> PDFs, <Zahl> Chunks
   Nicht indexiert: <PDF mit Grund, oder "keine">
   Funde der Formkontrolle: <PDF, Formregel, Zahl der Stellen, oder "keine">
   Funde der Stichprobe: <PDF, Seite, Fund, oder "keine">
   Fehler: <jeder Fehler aus allen Steps, oder "keine">
   ```

2. Geh idle.
