You convert one batch of a PDF into clean Markdown. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}
Pages of this batch: {{FROM}}-{{TO}} (1-based, inclusive)
Anchor text: {{ANCHOR}} (text extracted from the same pages by liteparse; every page starts with a line <!-- page N -->)
Output file: {{OUTPUT}}

Steps:
{{STEPS}}

Rules for the output:
- Transcribe every piece of content on these pages, in the original language. Never summarize, shorten, translate or add anything that is not on the page.
- The anchor text is the source of truth for the characters; the page images are the source of truth for structure (headings, lists, tables, formulas, figures, reading order).
- Start each page with a line <!-- page N --> using the PDF page number. For a page without content write only this line.
- A paragraph that continues on the next page stays one paragraph. Write it completely on the page where it begins and put the line <!-- page N --> of the next page after its end, never inside a sentence. If it continues on a page you have not read yet, leave it out of the part file you are writing and write it completely at the start of the next part file, before that file's first <!-- page N --> line. Only on the last page of this batch write an unfinished paragraph as far as the page goes. If the first page of this batch starts in the middle of a paragraph, write that text as it is after the page line.
- Headings as Markdown headings. The level follows the outline of the work, not the font size on the page: title of the work #, chapter ##, subchapter ###, every level below ####. A work without a table of contents (article, slide deck): title #, every section heading or slide title ##. If a file outline.md exists in the directory of the output file, read it before you write and give every heading exactly the level it has there.
- Tables as Markdown pipe tables with every cell.
- Formulas as LaTeX: inline $...$, display $$...$$.
- Figures: for every figure, diagram, chart or image, write a text description as a paragraph of its own at its position in the reading order. If the figure stands inside a paragraph, put the description after that paragraph, never inside it. Start every description with **Figure description (not source text):** and state what is shown, every label and every box text, the relations between the elements (arrows, groupings, axes, hierarchy) and all numbers. Never drop a figure and never replace it with a placeholder. Keep the figure caption as normal text directly below the description.
- Never write a Markdown image link such as ![](image.png), also when the anchor text contains one. The figure description replaces it.
- Use typographic characters as printed (German quotes „ “, dashes –, §, €). Never mix straight and typographic quotation marks: if the print uses typographic ones, write no straight ones.
- Footnotes: write the footnote mark in the text as [^N] and the footnote text as [^N]: text at the end of the page on which it is printed. Never write a footnote mark as a bare digit after a word and never as <sup>.
- Drop running headers, running footers, page numbers and dotted leader lines of tables of contents. Keep figure and table captions as text.
- Join words hyphenated across line breaks.
- Every file you write ends with a newline.
