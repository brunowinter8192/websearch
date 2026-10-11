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
- Start each page with a line <!-- page N --> using the PDF page number.
- Headings as Markdown headings, following the visual hierarchy.
- Tables as Markdown pipe tables with every cell.
- Formulas as LaTeX: inline $...$, display $$...$$.
- Figures: for every figure, diagram, chart or image, write a text description at its position in the reading order. State what is shown, every label and every box text, the relations between the elements (arrows, groupings, axes, hierarchy) and all numbers. Never drop a figure and never replace it with a placeholder. Keep the figure caption as text.
- Use typographic characters as printed (German quotes „ “, dashes –, §, €).
- Drop running headers, running footers, page numbers and dotted leader lines of tables of contents. Keep figure and table captions as text.
- Join words hyphenated across line breaks.
- Every file you write ends with a newline.
