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

## Grundsätze

**Der Workflow liest nie die Textebene eines PDFs.**
- Jeder Worker überträgt Zeichen und Struktur allein aus den Seitenbildern, die er mit dem Read-Tool liest.
- Es gibt keinen Ankertext und keine Zählung von Zeichen gegen das PDF.

**Die Übertragung bleibt immer Sache der Worker.**
- Du schreibst nie eine Seite selbst ab, auch nicht, wenn Anthropic einen Worker blockt.

**Jeder Worker dieses Skills startet mit Haiku.**
- `MODEL_SELECTION_FILE=PDF_MODELS` steht vor jedem Spawn, beim Übertragungs-Worker wie beim Stichproben-Worker.
- Ein anderes Modell wird nie gestartet, auch nicht als letzter Versuch.

**Ein PDF wird ganz oder gar nicht indexiert.**
- Fehlt am Ende auch nur eine Seite, kommt das PDF nicht nach OUTPUT_DIR.
- Ein Markdown mit Lücken wird nie veröffentlicht.

---

## Formregeln

**Das fertige Markdown hat über alle Stücke hinweg dieselbe Form.**
- Der Prompt gibt jedem Worker die Formregeln mit.
- Jeder Worker sieht aber nur sein Stück, deshalb können die Stücke eines PDFs trotzdem voneinander abweichen.
- Du bist der Einzige, der alle Stücke sieht, die Einheitlichkeit über die Stücke hinweg ist deshalb deine Aufgabe.
- Die Formregeln sind der Maßstab der Formkontrolle in Step 3.

**Überschriften folgen der Gliederung des PDFs, nicht der Schriftgröße auf der Seite.**
- Der Titel des Werks steht als `#`, jedes Kapitel als `##`, jedes Unterkapitel als `###`, jede Ebene darunter als `####`.
- Derselbe Rang hat in allen Stücken dieselbe Ebene.
    - Beobachteter Fehler: Kapitel 1, 2, 6 und 7 standen als `#`, die Kapitel 3 bis 5 und 8 bis 11 als `##`.
- Hat das PDF kein Inhaltsverzeichnis, z. B. ein Aufsatz oder ein Foliensatz, steht der Titel als `#` und jeder Abschnitt oder jede Folienüberschrift als `##`.

**Ein Absatz, der über eine Seitengrenze läuft, bleibt ein Absatz.**
- Der Absatz steht vollständig auf der Seite, auf der er beginnt.
- Die Zeile `<!-- page N -->` der Folgeseite steht erst hinter seinem Ende, nie mitten in einem Satz.
    - Beobachteter Fehler: „…killed annually in the United States by“, dann der Seitenmarker, dann „terrorists…“.
- Dasselbe gilt an der Grenze zwischen zwei Stücken.

**Fußnoten haben in allen Stücken dasselbe Format.**
- Das Fußnotenzeichen im Text steht als `[^N]`.
- Der Fußnotentext steht als `[^N]: <Text>` am Ende der Seite, auf der er gedruckt ist.
- Nie eine angehängte Ziffer wie `dignity.1`, nie `<sup>14</sup>`.

**Anführungszeichen stehen so, wie sie gedruckt sind.**
- Gerade und typografische Anführungszeichen werden innerhalb eines PDFs nie gemischt.

**Jede Abbildung hat eine Beschreibung in einem festen Format.**
- Die Beschreibung ist ein eigener Absatz und steht nie mitten in einem Absatz des Fließtextes.
- Sie beginnt in allen Stücken mit `**Figure description (not source text):**`.
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

**Jeder Aufruf von WORKFLOW schreibt seine Ausgabe in eine Datei, lies sie danach vollständig.**
- Ein Aufruf, der scheitert, endet mit `FAILED` und nennt den Grund.

### Step 0 — PDFs festlegen

1. Frage den User nach den PDFs und der Collection, falls er sie nicht genannt hat.

2. Benenne jedes PDF nach seinem Inhalt und sortiere es in ein Projektverzeichnis unter PDF_DIR ein.
   - PDF_DIR hat ein Unterverzeichnis je Projekt, z. B. `PDF_DIR/wise2627/`.
   - Ist unklar, in welches Verzeichnis das PDF gehört, frag den User.
   - Muster: Autor + Titel + Jahr in PascalCase, nur Buchstaben, Ziffern und Unterstrich.
       - Beispiel: `CoenenbergKostenrechnungKostenanalyse_2016.pdf`, der STEM ist dann `CoenenbergKostenrechnungKostenanalyse_2016`.

### Step 1 — Aufteilen

**Rufe `split` für jedes PDF nur ein einziges Mal auf.**
- `split` löscht beim Start alle eigenen Dateien in BATCH_DIR, auch die fertigen Texte der Worker, alle Stichproben und `BATCH_DIR/blocked/`.
- Ein zweiter Aufruf, nachdem Worker schon gelaufen sind, vernichtet also deren Arbeit.

1. Rufe `split` auf. Es teilt das PDF in Stücke zu je 50 Seiten und schreibt für jedes Stück einen fertigen Prompt für einen Worker nach BATCH_DIR.
   - `split` braucht dafür nur die Seitenzahl des PDFs, es liest keine Seite.

   ```bash
   WORKFLOW split --pdf "PDF_DIR/<Projekt>/<STEM>.pdf" --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_split.txt 2>&1
   ```

2. Lies `BATCH_DIR/manifest.json`. Dort stehen alle Stücke mit ihrem Seitenbereich, z. B. 1-50, 51-100, 101-150.
   - Zu jedem Stück gibt es die Datei `BATCH_DIR/prompt_<a>-<b>.md`, das ist der Prompt für seinen Worker.
   - `<a>` ist die erste Seite des Stücks, `<b>` die letzte.
   - Der Worker schreibt seinen Text nach `BATCH_DIR/piece_<a>-<b>.md`.

3. Schreibe die Gliederung des PDFs nach `BATCH_DIR/outline.md`.
   - Die Quelle ist das Inhaltsverzeichnis des PDFs. Lies dazu die Seiten des Inhaltsverzeichnisses mit dem Read-Tool.
   - Je Zeile stehen die Ebene nach den Formregeln und der Wortlaut der Überschrift, z. B. `## 3 Risk and Uncertainty`.
   - Hat das PDF kein Inhaltsverzeichnis, steht in `outline.md` nur die Zeile mit dem Titel als `#` und der Satz `no table of contents, every section heading is ##`.
   - `outline.md` ist in Step 3 der Maßstab für die Überschriften aller Stücke.

### Step 2 — Übertragungs-Worker, einer pro Stück

**Es laufen nie mehr als 20 Worker gleichzeitig.**

**Ein fertiger Worker bleibt am Leben, bis sein Stück die Formkontrolle in Step 3 bestanden hat.**
- Der Worker hat die Seiten seines Stücks noch im Kontext und kann seine Datei deshalb selbst korrigieren.
- Ein gekillter Worker kann das nicht mehr, dann bleibt die Korrektur an dir hängen.

1. Starte für jedes Stück einen Worker, alle direkt nacheinander, aber nie mehr als 20 gleichzeitig.
   - Starte einen Spawn erst, wenn der vorige zurückgekehrt ist, nie mehrere parallel im Hintergrund mit `&`.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-<a>-<b> BATCH_DIR/prompt_<a>-<b>.md
   ```

2. Ein Worker ist fertig, wenn er idle ist und `status` sein Stück als `complete` meldet.
   - `complete` heißt: Die Datei `BATCH_DIR/piece_<a>-<b>.md` enthält die Zeile `<!-- page N -->` jeder Seite des Stücks.
   - `incomplete` heißt: Die Datei existiert, aber Zeilen `<!-- page N -->` fehlen. `status` nennt die Seiten.
       - Beobachtet: Ein geblockter Worker hinterließ für das Stück 1-12 eine Datei mit den Seiten 1 bis 5, die Seiten 6 bis 12 fehlten.
   - `missing` heißt: Die Datei existiert nicht.

   ```bash
   WORKFLOW status --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_status.txt 2>&1
   ```

3. Nur bei mehr als 20 Stücken: Führe für jedes fertige Stück sofort Step 3 aus, kille seinen Worker und starte dann das nächste Stück, das noch keinen Worker hatte.

#### Ein Worker wird von Anthropic geblockt

**Ein geblocktes Stück teilst du mit `resplit` in kleinere Stücke, jedes kleinere Stück bekommt einen eigenen Haiku-Worker.**
- Du erkennst den Block an drei Dingen zusammen: Der Worker ist idle, `status` meldet sein Stück als `incomplete` oder `missing`, und `worker-cli response pdf-<stem>-<a>-<b> 1` zeigt `API Error: Output blocked by content filtering policy`.
- Dasselbe Stück noch einmal oder ein anderes Modell hilft nicht.
    - Beobachtet: Ein Aufsatz von 25 Seiten wurde mit Haiku in Stücken von 25, 20, 10, 5 und 2 Seiten geblockt und mit Opus in Stücken von 25 und 2 Seiten.

**Die Stücke werden in zwei Stufen kleiner: 20 Seiten, dann 10 Seiten. Kleiner wird nie geteilt.**
- `resplit` wählt die größte dieser Stückgrößen, die kleiner ist als das geblockte Stück.
    - Beispiel: Ein Stück von 50 Seiten wird zu 20, 20 und 10 Seiten, ein Stück von 18 Seiten zu 10 und 8 Seiten.
- Kleinere Stücke als 10 Seiten bringen nichts.
    - Beobachtet: Bei vier Aufsätzen wurden auch Stücke von 5, 2 und 1 Seite geblockt, kein Aufsatz wurde dadurch vollständig.
- `resplit` teilt nur das genannte Stück. Alle anderen Stücke bleiben im Manifest und auf der Platte, wie sie sind.
- `resplit` verweigert ein Stück, das `status` als `complete` meldet.
- Eine unvollständige Datei `piece_<a>-<b>.md` und übrig gebliebene Teildateien `part<n>_<a>-<b>.md` des geblockten Stücks legt `resplit` nach `BATCH_DIR/blocked/`. Es löscht keine davon.
    - Beobachtet: Ein geblockter Worker des Stücks 1-23 hinterließ `part1_1-23.md`.
- Hat das geblockte Stück 10 Seiten oder weniger, verweigert `resplit` die Teilung mit `piece_minimal`. Das PDF wird dann nicht indexiert.
    - Kille alle Worker dieses PDFs, auch die, die noch arbeiten.
    - Notiere das PDF und die Seiten des Stücks für den Report und mach mit dem nächsten PDF weiter.

1. Kille den geblockten Worker.

   ```bash
   worker-cli kill pdf-<stem>-<a>-<b>
   ```

2. Rufe `resplit` für das geblockte Stück auf. Es ersetzt das Stück im Manifest durch die kleineren Stücke, schreibt für jedes einen Prompt `BATCH_DIR/prompt_<a>-<b>.md`, löscht den Prompt des geblockten Stücks und nennt unter `set aside` die Dateien, die es nach `BATCH_DIR/blocked/` gelegt hat.

   ```bash
   WORKFLOW resplit --batch-dir BATCH_DIR --piece <a>-<b> > /tmp/pdf_<STEM>_resplit_<a>-<b>.txt 2>&1
   ```

3. Starte für jedes neue Stück einen Worker wie in Step 2.1. Ein Stück ist fertig wie in Step 2.2.

4. Wird ein neues Stück wieder geblockt, gehe für dieses Stück zurück zu 1.

### Step 3 — Formkontrolle

**Die Formkontrolle läuft auf den Dateien `BATCH_DIR/piece_<a>-<b>.md`, also vor dem Zusammenführen.**
- `merge` liest genau diese Dateien, jede Korrektur dort landet deshalb im zusammengeführten Markdown.
- Nach dem Start der Stichprobe in Step 5 verweigert `merge` einen neuen Lauf. Eine Korrektur an einer Datei `piece_<a>-<b>.md` nach Step 4 kommt also nie mehr im Markdown an.

1. Erzeuge die Prüfliste für alle Stücke des PDFs und lies sie vollständig.

   ```bash
   cd BATCH_DIR
   echo '== Überschriften =='; grep -n '^#' piece_*.md
   echo '== letzte Textzeile vor jedem Seitenmarker =='; grep -n -B2 '^<!-- page' piece_*.md
   echo '== Fußnoten nicht als [^N] =='; grep -n -E '<sup>|[[:alpha:].,;:!?”"’)][0-9]{1,3}([[:space:]]|$)' piece_*.md
   echo '== gerade Anführungszeichen =='; grep -c '"' piece_*.md
   echo '== typografische Anführungszeichen =='; grep -c '[„“”]' piece_*.md
   echo '== Abbildungen =='; grep -n -i -E 'figure|abbildung' piece_*.md
   echo '== Bildverweise =='; grep -n '!\[' piece_*.md
   ```

2. Prüfe die Liste gegen die Formregeln.
   - Überschriften: Jede Überschrift hat die Ebene, die `outline.md` für ihren Rang nennt.
   - Seitenmarker: Die letzte Textzeile vor einem Seitenmarker endet mit einem Satzende. Endet sie mitten im Satz, läuft der Absatz über die Seitengrenze.
   - Fußnoten: Jeder Treffer ist ein Fußnotenzeichen im falschen Format oder eine gewöhnliche Zahl. Unterscheide das an der Stelle im Text.
   - Anführungszeichen: Haben beide Zählungen Treffer, sind die Zeichen gemischt.
   - Abbildungen: Jede Beschreibung ist ein eigener Absatz und beginnt mit `**Figure description (not source text):**`.
   - Bildverweise: Jeder Treffer ist ein Fund.

3. Schicke jedem Worker die Funde seines Stücks, er korrigiert seine Datei `piece_<a>-<b>.md` selbst.
   - Nenne je Fund die Formregel im Wortlaut, die Zahl der Stellen und bis zu fünf Stellen mit Seite als Beispiel.
   - Nenne bei Überschriften den Pfad `BATCH_DIR/outline.md`.
   - Nach jedem `send` folgt ein `worker-cli wait`.

   ```bash
   worker-cli send pdf-<stem>-<a>-<b> "<Funde>"
   ```

4. Führe die Prüfliste nach der Korrektur genau ein weiteres Mal aus.
   - Es gibt eine einzige Korrekturrunde je Stück.
   - Was danach noch abweicht, notierst du für den Report unter Funde der Formkontrolle.
   - Ein Fund der Formkontrolle verhindert die Indexierung nicht.

5. Korrigiere selbst, was kein Worker korrigieren kann.
   - Ein Absatz, der vom letzten Blatt eines Stücks ins erste Blatt des nächsten läuft: Kein Worker sieht beide Stücke, füge den Absatz im vorderen Stück zusammen.
   - Der Worker des Stücks lebt nicht mehr: Korrigiere die Form der Datei mit dem Edit-Tool. Den Inhalt einer Seite schreibst du dabei nie selbst ab.

6. Kille jeden Worker, dessen Stück die Formkontrolle hinter sich hat.

   ```bash
   worker-cli kill pdf-<stem>-<a>-<b>
   ```

### Step 4 — Zusammenführen

**`merge` prüft nur, ob jedes Stück im Manifest `complete` ist wie in Step 2.2.**
- Ist auch nur ein Stück `incomplete` oder `missing`, schreibt `merge` nichts. Es nennt jedes fehlende Stück und bei jedem unvollständigen Stück die fehlenden Seiten.
- Den Text der Stücke prüft `merge` darüber hinaus nicht.
- Nennt `merge` ein Stück, dessen Worker noch lebt, schicke ihm die fehlenden Seiten, er ergänzt seine Datei. Lebt er nicht mehr, teile das Stück mit `resplit` wie in Step 2.

1. Rufe `merge` auf, sobald alle Stücke die Formkontrolle hinter sich haben. Es fügt alle Stücke in der Reihenfolge der Seiten zu `BATCH_DIR/<STEM>.md` zusammen, egal wie groß die einzelnen Stücke sind.
   - `BATCH_DIR/<STEM>.md` ist noch nicht das fertige Markdown. Nach OUTPUT_DIR kommt es erst in Step 6.

   ```bash
   WORKFLOW merge --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_merge.txt 2>&1
   ```

### Step 5 — Stichprobe

**Ein Stichproben-Worker prüft Seiten des zusammengeführten Markdowns gegen die Seitenbilder und korrigiert jeden Fehler selbst.**
- Jeder Lauf prüft 10 % der Seiten, zufällig gezogen aus den Seiten, die noch in keinem Lauf geprüft wurden.
- Findet ein Lauf etwas, folgt ein weiterer Lauf mit neuen Seiten.
- Die Schleife endet mit dem ersten Lauf, in dem keine Korrektur übernommen wird, spätestens wenn jede Seite einmal geprüft wurde.

**Der Worker korrigiert nie das Markdown selbst, sondern Ausschnitte daraus.**
- `sample` schneidet je geprüfter Seite einen Ausschnitt aus `BATCH_DIR/<STEM>.md` und legt ihn als `excerpt_<Seiten>.md` in `BATCH_DIR/samples/run_<k>/` ab, `<k>` ist die Nummer des Laufs.
- Der Ausschnitt beginnt mit der Seite vor der geprüften Seite, weil ein Absatz vollständig auf der Seite steht, auf der er beginnt.
- Erst `sample-close` schreibt die Korrekturen in `BATCH_DIR/<STEM>.md` zurück, und nur die, die du nicht verwirfst.

**Die Funde des Workers entscheiden nichts, das tust du.**
- Du prüfst jeden Fund und jede Korrektur gegen die Seite im PDF.

1. Öffne einen Lauf mit `sample`.
   - Die Ausgabe nennt die Nummer des Laufs, die gezogenen Seiten, die Ausschnitte und den Prompt `BATCH_DIR/samples/run_<k>/prompt.md`.

   ```bash
   WORKFLOW sample --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_<k>.txt 2>&1
   ```

2. Gib dem Stichproben-Worker den Lauf.
   - Lauf 1: Starte den Worker.

   ```bash
   MODEL_SELECTION_FILE=PDF_MODELS worker-cli spawn pdf-<stem>-sample BATCH_DIR/samples/run_1/prompt.md
   ```

   - Jeder weitere Lauf: Schicke dem Worker den neuen Prompt, danach `worker-cli wait`.

   ```bash
   worker-cli send pdf-<stem>-sample "Read BATCH_DIR/samples/run_<k>/prompt.md completely and follow it."
   ```

3. Der Lauf ist fertig, wenn der Worker idle ist und `BATCH_DIR/samples/run_<k>/findings.md` existiert.

4. Erzeuge den Bericht des Laufs mit `sample-report` und lies `BATCH_DIR/samples/run_<k>/report.md` vollständig.
   - Der Bericht nennt die geprüften Seiten, die Funde des Workers aus `findings.md` und jede Korrektur als Text vorher und nachher, je mit der Seite.
   - `sample-report` ändert nichts und darf beliebig oft laufen.

   ```bash
   WORKFLOW sample-report --batch-dir BATCH_DIR > /tmp/pdf_<STEM>_sample_report_<k>.txt 2>&1
   ```

5. Prüfe jede Korrektur gegen die Seite im PDF. Lies dazu die Seite mit dem Read-Tool.
   - Echt ist eine Korrektur, wenn der Text vorher wirklich vom Seitenbild abweicht und der Text nachher dem Seitenbild entspricht.
   - Die Korrektur folgt den Formregeln, z. B. eine nachgetragene Fußnote als `[^N]: <Text>`.
   - Ist eine Korrektur echt, aber selbst fehlerhaft, schicke dem Worker den Fund. Er korrigiert seinen Ausschnitt, danach erzeugst du den Bericht erneut.
   - Steht in `findings.md` ein Fund ohne Korrektur, prüfe ihn ebenso und schicke ihn dem Worker zur Korrektur.

6. Schließe den Lauf mit `sample-close`. Nenne mit `--reject` jede geprüfte Seite, deren Korrektur nicht echt ist.
   - Eine verworfene Korrektur landet nicht im Markdown und zählt nicht als Fund.
   - Ändert ein Ausschnitt eine Zeile `<!-- page N -->`, verweigert `sample-close` den Lauf. Verwirf diese Seite mit `--reject` oder lass den Worker die Zeile wiederherstellen.

   ```bash
   WORKFLOW sample-close --batch-dir BATCH_DIR [--reject <Seite> ...] > /tmp/pdf_<STEM>_sample_close_<k>.txt 2>&1
   ```

7. Die letzte Zeile der Ausgabe sagt, wie es weitergeht.
   - `loop continues`: Gehe zurück zu 1 und öffne den nächsten Lauf.
   - `loop ended`: Kille den Stichproben-Worker und gehe zu Step 6.

   ```bash
   worker-cli kill pdf-<stem>-sample
   ```

8. Notiere für den Report je Lauf die Zahl der geprüften Seiten und die übernommenen und verworfenen Korrekturen mit Seite.

### Step 6 — Veröffentlichen

**`publish` ist der einzige Weg nach OUTPUT_DIR.**
- `publish` verweigert, solange es keinen Lauf gibt, ein Lauf offen ist oder die Schleife aus Step 5 nicht beendet ist.
- Vor dem Schreiben teilt `publish` jeden zu langen Absatz in kürzere Absätze, auch die Absätze aus den Korrekturen der Stichprobe.

1. Rufe `publish` auf. Es schreibt das ganze Markdown als eine Datei `<OUTPUT_DIR>/<STEM>.md`.

   ```bash
   WORKFLOW publish --batch-dir BATCH_DIR --out-dir <OUTPUT_DIR> > /tmp/pdf_<STEM>_publish.txt 2>&1
   ```

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
   Geblockte Stücke: <PDF, Seiten, Stufe, oder "keine">
   Funde der Formkontrolle: <PDF, Formregel, Zahl der Stellen, oder "keine">
   Stichprobe: <PDF, Zahl der Läufe, geprüfte Seiten, übernommene und verworfene Korrekturen mit Seite>
   Fehler: <jeder Fehler aus allen Steps, oder "keine">
   ```

2. Geh idle.
