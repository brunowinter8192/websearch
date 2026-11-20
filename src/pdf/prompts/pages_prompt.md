You correct the text of the PDF pages {{FROM}} to {{TO}} against their page images. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}

Each page was converted to Markdown automatically from the PDF text layer or by OCR. For each page N from {{FROM}} to {{TO}} there are two files:
- {{PNG_PATTERN}}: the full page rendered at 150 dpi. This image is the ground truth.
- {{MD_PATTERN}}: the Markdown of that page.

Steps:
1. Take the pages one after the other. For each page N read {{PNG_PATTERN}} and {{MD_PATTERN}} completely with the Read tool, then write {{FIXED_PATTERN}} with the Write tool.
2. When every page is written, reply with one line per page: page, number of changes, anything unreadable or odd.

{{FIXED_PATTERN}} is the page Markdown with only these corrections:
- Characters: every character must match the image. Wrong or broken characters, signs, accents and symbols are corrected. Check every number, date, name and abbreviation against the image.
- Formulas: a formula is written in LaTeX, inline as $...$, on its own line as $$...$$.
- Footnotes: the footnote marker in the text is written as [^N], the footnote text as [^N]: <text> at the end of the page on which it is printed. A note marked with a symbol such as * is written [^*]. Never a superscript like <sup>1</sup>, never an appended digit. Text that continues a footnote of the previous page has no marker: leave it where it is and add none.
- Paragraphs: a paragraph that is split inside the page, for example by a column break or a footnote block, is joined back into one paragraph. A word hyphenated at that break is joined. Two paragraphs stay separate where the image shows a new paragraph, for example by an indented first line.

Do not touch:
- Lines <!-- TABLE ... --> and <!-- FIGURE ... --> stay exactly as they are, at the same position.
- Lines starting with # stay exactly as they are.
- A paragraph that runs over to the next page or comes from the previous page stays split at the page boundary; another step joins it.
- Quotation marks stay as they are in the Markdown.
- Change nothing else: no added or removed text, no rewording, no italics, no bold, no indents, no headings. Never summarize, shorten or translate. Never write a Markdown image link.
- Invent nothing. If something in the image is unreadable, write [unreadable].

Change no file except the {{FIXED_PATTERN}} files of your pages. Every file you write ends with a newline.
