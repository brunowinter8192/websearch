---
name: websearch-pdf
description:
---

# PDF → MD → Index — Skill

Dieser Ablauf ist interaktiv. Der NUTZER führt das Convert-Command aus, Claude macht NUR Benennung, Cleanup und Index.
EIN Command wandelt ALLE PDFs des Batches nacheinander um, jedes als ganzes Dokument,
über MinerU mit `vlm-auto-engine` (mlx).

## Pfade
- MINERU = `~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py`
- COLLECTION = `trading-reference`, der Standard, den du nur bestätigst wenn der Nutzer eine andere nennt
- OUTPUT_DIR = `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/documents/<COLLECTION>/`
- PDF_DIR = `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf/<Thema>/`, der etablierte PDF-Ablageort.
  `<Thema>` ist ein bestehender Unterordner (z.B. `RAG`, `Trading`, `wise2627`), der zur Collection passt;
  existiert keiner, lege einen passenden an.

## Regel
Das CONVERT-Command führt der NUTZER aus. Claude führt die Benennung, die Cleanup-Skripte und `rag-cli index` aus.

## Phase 0 — Benennung und Skip-Check (CLAUDE)
1. Vergib pro PDF einen STEM in PascalCase, ausschließlich alphanumerisch plus Unterstrich, also keine eckigen
   Klammern, keine runden Klammern, keine Punkte, keine Kommas und keine Leerzeichen. Benenne das Quell-PDF
   direkt an Ort und Stelle um nach `<STEM>.pdf`.
2. Kopiere jedes umbenannte PDF nach `<PDF_DIR>/<STEM>.pdf`. Das Convert-Command referenziert IMMER die
   Archiv-Pfade unter PDF_DIR, nie die Downloads.
3. Skip-Check: Wirf jedes PDF raus, zu dem es bereits `<OUTPUT_DIR>/<STEM>.md` gibt. Nur noch nicht umgewandelte
   PDFs gehen in das Command.
4. Das Backend ist immer `vlm-auto-engine` (mlx).

## Phase 1 — MinerU convert (der NUTZER führt aus, EIN Command für den ganzen Batch)
POSTE DAS COMMAND IM CHAT und schreibe es niemals in eine Datei. Es ist EIN Codeblock, der ALLE nicht
übersprungenen PDFs auflistet, jedes als ganzes Dokument, und drumherum steht nichts außer den Vorbehalten, die zählen:
```
mkdir -p <OUTPUT_DIR>
PYTHONUNBUFFERED=1 ~/Documents/ai/Mineru/venv/bin/python ~/Documents/ai/Mineru/workflow.py convert \
  --pdf "<PDF1>" "<PDF2>" "<PDF3>" ... \
  --out-dir <OUTPUT_DIR> 2>&1 | tee /tmp/<batch>_mineru.log
```
- Die Ausgabe ist eine flache `<OUTPUT_DIR>/<STEM>.md` pro PDF.
- Der NUTZER führt den Block aus und meldet, dass er fertig ist.

## Phase 2 — Cleanup (CLAUDE)
Laufe über jede `<OUTPUT_DIR>/<STEM>.md`. Prüfe ZUERST, zieh also Stichproben aus den Treffern, und strippe erst danach.

Erkennung und Aktion pro Klasse:
- **A — verlorene Formel (NICHT WIEDERHERSTELLBAR, also NICHT reinigen):** `??`, `` (U+FFFD), leere oder ein `?`
  enthaltende `<sub>` und `<sup>` (`<su[bp]>[[:space:]]*</su[bp]>|<su[bp]>[^<]*\?[^<]*</su[bp]>`), dazu
  `$$…$$`-Blöcke aus reinem Whitespace (auf `$$` splitten, die ungeraden Segmente prüfen). Jeder Treffer in A heißt,
  dass NICHT gereinigt wird.
  **Melde das Symbol und die Seite an den Nutzer.**
- **B — zerrissene Mathematik (WIEDERHERSTELLBAR, also Leerzeichen entfernen):** `_ {`, `^ {`, `\ [a-z]( [a-z])+`,
  dazu Läufe aus einzelnen Zeichen mit Leerzeichen `([A-Za-z] ){3,}[A-Za-z]`. Ziehe diese Läufe zu echten Tokens
  zusammen, also `\mathrm { a r g m i n }` zu `\mathrm{argmin}`. Die Invariante ist, dass die Anzahl der
  alphanumerischen Zeichen EXAKT gleich bleibt und die Wortanzahl sinkt.
- **C — Encoding (WIEDERHERSTELLBAR, also unescapen):** HTML-Entities
  `&(amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);` und Mojibake wie `Ã.` oder `â€`. Die Anzahl der Entities muss danach 0 sein.
- **D — Zeichenfehler im Fließtext:** ignorieren. Ist der Fließtext durchgängig zerschossen, behandle es wie A und melde es.
- **E — Backmatter (ZWINGEND STRIPPEN):** ab der ersten Überschrift
  References, Bibliography, Index, Symbols, Abbreviations oder Nomenclature in den letzten rund 40 Prozent bis EOF.
  Das gilt auch für einen Referenz-Lauf ohne Überschrift, bei dem die meisten nicht-leeren Zeilen auf
  `\(\d{4}[a-z]?\)` oder `^Surname, Init.` passen, sowie für einen Index-Lauf mit `,\s*\d+([–-]\d+)?`.
  Bestätige, dass 3 Zeilen über dem Schnitt echter Inhalt stehen. Schneide KEINE nummerierten Unterabschnitte mit
  Inhalt, deren Überschrift mit einer Ziffer beginnt, und keine Bibliographic Notes einzelner Kapitel.
- **F — Tabellen-Markup (WIEDERHERSTELLBAR, also in Pipe-Text wandeln):** MinerU schreibt `<table>` als HTML, mit einem
  Markup-Anteil über 50 Prozent. Strippe die Tags, mache eine Zeile pro `</tr>`, trenne die Zellen mit `|`, lass den
  Inhalt unverändert und kürze nichts. Validiere, dass die Token-Menge des Zelltexts unverändert ist.
- **G — Image-Tags (ZWINGEND STRIPPEN):** `!\[[^\]]*\]\([^)]*\)`, entferne jeden Treffer. Wirf Zeilen weg, die durch das
  Entfernen leer werden, und ziehe 3 oder mehr aufeinanderfolgende Leerzeilen auf 1 zusammen. Scanne erneut, die Anzahl muss 0 sein.
- **H — Block-Rauschen (ZWINGEND STRIPPEN):** Läufe von 2 oder mehr nackten Fence-Zeilen, wobei eine Zeile aus
  optionalem Whitespace, 3 oder mehr Backticks und optionalem Whitespace besteht und sonst nichts. Entferne den ganzen
  Lauf. BEHALTE einzelne Fences und Opener mit Sprach-Tag, also ```` ```txt ```` und ```` ```csv ````.
  Bei Trennlinien gilt: Wenn auf der von Leerzeichen befreiten Zeile das häufigste Zeichen aus `=#-~*_.+` über
  70 Prozent aller Zeichen ausmacht UND die Länge mindestens 20 beträgt, entferne die Zeile. Scanne erneut, der längste
  Lauf nackter Fences muss 1 sein.
- **I — zusammengelaufene Tokens (BEDINGT, der Nutzer entscheidet):** Splitte an Whitespace und markiere Tokens ab
  46 Zeichen mit einem Alpha-Anteil über 0.7, wobei Tokens mit `\`, `http` oder `/` ausgenommen sind. Ist ein markiertes
  Token länger als 2000 Zeichen, STOPPE, liste dem Nutzer Dokument und Token und warte auf seine Entscheidung. Sind alle
  markierten Tokens höchstens 2000 Zeichen lang, lass sie stehen und strippe NICHT.
- **J — übergroße Passagen (ZWINGEND):** Scanne BEIDE Granularitäten und melde jeden Treffer mit Zeilennummer und den
  ersten 200 Zeichen:
  ```bash
  awk '{ if (length($0) > 1000) print NR, length($0) }' "$MD"                       # long lines
  awk 'BEGIN{RS="\n\n"} { gsub(/\n/," "); if (length($0) > 1000) print NR, length($0) }' "$MD"  # long blocks
  ```
  Klassifiziere jeden Treffer und handle danach:
  - **Lauf aus wiederholten Zeichen** (`(.)\1{39,}`) zieht auf 3 Zeichen zusammen:
    `re.sub(r"(.)\1{39,}", lambda m: m.group(1)*3, text)`.
  - **echter Fließtext, echte Tabelle oder echte Formel** bleibt stehen.
  Scanne erneut und melde die maximale Zeilenlänge und die maximale Blocklänge. Benenne jede verbleibende Passage über
  1000 Zeichen als echten Inhalt.

Fließtext-Fenster für jede md: Zieh 1 bis 2 Textzeilen aus dem mittleren Drittel, mit einer Länge über 70, beginnend mit
einem Buchstaben, mit mehr als 10 Leerzeichen und einem Alpha-Anteil über 0.78, und LIES sie. Ist der Text kohärent, ist
der Test bestanden. Ist er zerschossen, ist es Klasse A und du meldest es als nicht wiederherstellbar.

Skripte pro Problem: je ein `/tmp/fix_<issue>_<STEM>.py`, teste es an der Datei, scanne diese Klasse erneut auf 0 und
prüfe stichprobenartig 10 bis 15 Zeilen aus der Mitte. Erhalte den Quellinhalt, überschreibe direkt an Ort und Stelle und
sichere vorher nach `/tmp/backup_<STEM>.md`.

## Phase 3 — Index (CLAUDE)
```
rag-cli index --collection <COLLECTION>
```
Das läuft inkrementell und überspringt über den Hash. Es muss das EINZIGE Command in seinem Bash-Aufruf sein. Zuweisungen,
ein `cd` und ein Redirect dürfen dabeistehen, sonst nichts, und keine Command-Substitution.

Wenn es zurückkommt, LIES DIE AUSGABE VOLLSTÄNDIG, bevor du meldest oder diagnostizierst.
Der Fehler sitzt in der ERSTEN Zeile. Ein stehender Chunk-Zähler heißt, dass der Lauf BEENDET ist, und niemals dass er langsam ist.

Bei `HTTP 400 … exceeds the available context size` lässt du den Scan aus Klasse J erneut über das genannte Dokument
laufen, behebst den Fund und indexierst erneut.

Melde die Anzahl der indexierten Dateien und der Chunks. Bestätige, dass die Dokumente in der Collection liegen.
