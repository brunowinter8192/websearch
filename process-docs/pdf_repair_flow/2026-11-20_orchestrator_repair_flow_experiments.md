# Orchestrator record: from image transcription to text layer repair (2026-11-20)

## Starting point

The image transcription flow (area pdf_image_flow) converted 17 SGSC PDFs for the collection wise2627-reference. 9 were indexed, 8 were not, all because Haiku workers were blocked with `API Error: Output blocked by content filtering policy`, also at the smallest piece size of 10 pages:
SchrageEwingCocoaIndustryChildLabour_2005, SchoutenGlasbergenLegitimacyRspo_2011, ConleyWilliamsGlobalBanksEquatorPrinciples_2011, WrightRwabizambugaVoluntaryCodesEquatorPrinciples_2006, ScholtensDamBankingOnTheEquator_2007, MouraChaddadCollectiveActionBonsucro_2012, HeilmayrDeforestationSpilloversRspo_2020, MeyersteinEffectivenessEquatorPrinciples_2011.

All 8 have a real text layer (checked with PyMuPDF, 3,000 to 7,000 characters per page).

The user's hypothesis: the filter blocks reproduction of content. A worker that repairs text which already exists should not be blocked. The test below confirmed this for one PDF.

## Decision: extract the text layer with a tool, let workers repair error classes

Search on GitHub (2026-11-20) split the candidates into two groups:
- Text layer readers without a model: pymupdf4llm, pdf_oxide, firecrawl/pdf-inspector, run-llama/liteparse, firecrawl/anydoc, opendataloader-pdf, markitdown.
- Model based (layout, tables, formulas): marker, docling, MinerU, olmocr, Dolphin, surya, PaddleOCR. MinerU had been dropped earlier because local models were slow and wrong.

pymupdf4llm 2.1 was chosen: built for PDF, and `page_chunks=True` returns per page a list of `page_boxes` with `class`, `bbox` and `pos` (offsets into the page markdown). This locates every table, picture, heading, page header and footer without a model.

Scholtens & Dam 2007, 22 pages, converted in about 5 seconds. Observed error classes:
1. Tables: torn column headers (`|Mo|del 1|`), a row label shifted by one row (Net interest margin), a rotated page-margin text read as an extra column (Appendix D).
2. Characters: every minus sign came out as U+FFFD; accents detached (`Socie´te´ Ge´ne´rale`).
3. Formula: `Ri ¼ a þ bRm þ error:` and classified as `section-header`.
4. Figures: only axis labels as text salad.
5. Running heads and page numbers inside paragraphs.
6. Paragraphs split at page and column boundaries (`gov-` / `ernance`).
7. Heading levels inconsistent; `(a) Descriptives ...` and three appendix titles not classified as headings.
8. Footnote markers as `<sup>1</sup>`.
9. No page markers.

Classes 5 and 9 are solved by the boxes alone (`page-header`, `page-footer` classes; one chunk per page).

## Worker experiments, all Haiku, none blocked

Single table (Table 1, page 9), PNG crop of the bbox at 200 dpi plus the markdown span: 30 changes, all correct against the image (27 minus signs, header, one row split). The worker also copied italics and indents from the image although only content was asked for; after an explicit "change nothing else" it removed them. Every later prompt carries that sentence.

The row `Net interest margin` in Table 1 is misaligned in the printed original itself; the worker kept it and reported it. Correct behaviour.

Figures: asked for values per data point, the worker misread single values by up to 0.06 (day 0: wrote -0.05, image about -0.09; day 10: wrote -0.06, image about -0.12). The course, axes, legend and peak were right. The prompt was changed to course plus clearly readable points only.

Full run (2026-11-20, batch in /tmp/pdfx_run): tables worker (9 tables), figures worker (7 pictures), outline worker, then 5 page workers of 5 pages each, then one sample worker. No block in any of the 9 workers.
- Outline worker used bookmarks plus page text. The PDF bookmarks were partly wrong: the three appendix entries B, C, D all carried the title of appendix A. The worker followed the printed text.
- Page workers: formula to LaTeX, footnotes to `[^N]` (an asterisk note became `[^*]`), accents, joins at column breaks. They differed on `‘‘ ’’` versus `“ ”`; normalized during assembly.
- Assembly by hand joined 7 paragraphs across page boundaries. Two paragraphs that continue after a full table or figure page (page 8 to 10, page 12 to 14) were not joined.
- Sample of 3 random pages (3, 7, 22): 2 findings. (a) Paragraph "The history of the EP ..." begins on page 3 but stood at the end of page 2. Cause: pymupdf4llm returned the continuation from page 2 and the new paragraph as one `text` box, so the boundary join carried the new paragraph along. (b) The ScienceDirect logo description contained "header logo" and "publisher banner", not visible in the image. Page 7 had no finding.

## OCR for scans

In PDF_DIR/wise2627 exactly one SGSC PDF has no text layer: HayekFreedomEconomicSystem_1939 (23 pages, each scan page shows two book pages). SchellingEconomicReasoningEthicsPolicy_1981 and BoatrightBusinessEthicsMistake_1999 are scans with an older OCR text layer. The Altmann slide decks have a full-page image per slide but also their own text.

Comparison on Hayek page 5 (2026-11-20):
- pymupdf4llm with Tesseract 5.5.2: the two book pages mixed line by line ("assume an on lead to the suppression"). 26 s for 23 pages. Unusable.
- pymupdf4llm with RapidOCR 3.10 (`pip install rapidocr onnxruntime`, chosen automatically): reading order and columns correct, letter errors ("mcetings", "Sociely", "econonists", "r937"), one italic line destroyed ("Bre g B Band Hitler jugend" for "Balilla and Hitlerjugend"). 37 s.
- Apple Vision via ocrmac, page rendered at 200 dpi: 0.9 s per page, similar letter error rate ("lenst", "tbat", "Filler jugend"), returns lines with boxes but no layout integration into pymupdf4llm.
- `rapidtess_api` (RapidOCR detection plus Tesseract recognition) crashed: `TypeError: 'NoneType' object is not callable` in `rapidocr_391_backend.det_only`. Not pursued.

An independent benchmark of 22 engines (withinnoise.dev, October 2026) found every vision-language model clearly above every classic engine (best classic Surya 0.17 at 72.8 %, RapidOCR 66.2 %, Tesseract 67.8 %), and RapidOCR alternating lines on a two-column book. Those models need a GPU, which is the MinerU problem again. Our own Hayek result contradicts the column finding because pymupdf4llm does its own layout analysis before OCR.

Decision: RapidOCR inside pymupdf4llm. The remaining letter errors go to the page workers, who see the page image. Hypothesis, not yet tested: page workers repair OCR letter errors as reliably as they repaired the Scholtens characters.

## Skill

The skill was rewritten as workflow only: it says what the main agent does, nothing else. Form rules and explanations moved into the worker prompts generated by the tooling. The skill names commands `extract`, `status`, `apply-outline`, `assemble` that did not exist on 2026-11-20; the milestone after this record builds them.

A block in the new flow has not been observed. The skill therefore only aborts the PDF and reports it, without a resplit path.

## Inventory of PDFs on 2026-11-20

- Downloads: 15 PDFs not in PDF_DIR. New works: Baumol 1975 and 1991, Nozick 1998, Altmann 2025, Equator Principles EP4, Burritt 2010, Ruysschaert 2014, Contreras 2019, RSPO complaints brochure, Vorlesung Aufsichtsrat III (differs by content from the file of the same name in Documents/wise2627). Boatright, Friedman, Pies and Prakash exist in PDF_DIR, but the Downloads files differ by hash.
- Documents/wise2627: 36 symlinks into PDF_DIR, 46 real PDF files. 23 of them are also in PDF_DIR (duplicates), 23 are not in PDF_DIR at all (mostly LÜAG: AktG, DCGK 2022, LÜAG Skript komplett; COKA 2026 Handout; two ICD2 excerpts). 5 symlinks in LÜAG/Übungen/Übung_2 point to real files inside Documents/wise2627 instead of PDF_DIR.
- PDF_DIR has no duplicate files (by sha1).
- Of 93 PDFs in PDF_DIR/wise2627, 12 SGSC PDFs had no markdown in rag-cli documents (matched by file name only).

## Batch runs with the built tooling (2026-11-20, afternoon)

Batch 1: Hayek 1939 (scan), Moura Chaddad 2012, Conley Williams 2011, Heilmayr 2020, Contreras 2019. Batch 2: Scholtens 2007, Schouten 2011, Schrage 2005, Wright 2006, Meyerstein 2011 (234 pages, 50 workers, run in waves of 20). All ten indexed into wise2627-reference (338 + 797 chunks). Over 100 Haiku workers ran; none was blocked by the content filter. All eight PDFs blocked in the image transcription flow are now indexed.

Every PDF of batch 2 still needed a code change; each time a tripwire stopped the run before wrong text was produced. The fixes and their evidence are recorded by the workers in this area (formula worker, page join, coverage, second batch, Wright table notes, sample duplicates).

Orchestrator observations worth keeping:
- `MODEL_SELECTION_FILE` with a relative path is not found by worker-cli, which then silently spawns the default model (claude-sonnet-5) instead of Haiku. Observed once at the start of batch 1; the skill uses the absolute path.
- The first Hayek sample run reported no finding although the page images were contaminated by the inserted OCR text (footnote 16 written as [^1]). A sample run with no finding is only as good as the page images; the main agent found it by reading one page image itself.
- Three times the sampling worker "added" text that assemble had joined onto an earlier page (Heilmayr p9, Scholtens p10, plus the morning hand run). sample-close now rejects these itself.
- Outline results showed two defects that the later prompts fix but that remain in the published files: Heilmayr has its title twice (IOP cover sheet), Moura Chaddad headings keep `**` bold markers (its page workers ran before the heading rule).
- Meyerstein was published before the Wright fix; that fix adds a join 131->132 the published file lacks (text complete, paragraph split).
- Batch-level rotation of page workers was done with a throwaway script in /tmp that kills complete page workers and spawns the next incomplete ranges up to 20.
