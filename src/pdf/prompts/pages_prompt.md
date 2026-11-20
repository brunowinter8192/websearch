You repair the quality of the already extracted Markdown of the PDF pages {{FROM}} to {{TO}}. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}

The text of these pages already exists. It was extracted from the PDF text layer or by OCR and is in the files below. Your job is only to fix extraction defects in that existing text. You are not asked to reproduce, retype or rewrite any content: the content is already there, and you stay as close to the existing text as you possibly can.

For each page N from {{FROM}} to {{TO}} there are two files:
- {{PNG_PATTERN}}: the full page rendered at 150 dpi. Use it only to decide what a damaged spot should be.
- {{FIXED_PATTERN}}: the extracted Markdown of the page. This is the file you repair, in place. Its first line is {{PENDING}}.

How to work:
1. Take the pages one after the other. For each page N read {{PNG_PATTERN}} and {{FIXED_PATTERN}} completely with the Read tool.
2. Repair {{FIXED_PATTERN}} only with the Edit tool, one small edit at a time: each edit replaces a short damaged fragment by the repaired fragment. Never use the Write tool, never replace a whole paragraph or the whole file.
3. When the page is repaired, remove the line {{PENDING}} with one last Edit, also when the page needed no repair. This line is the only text you remove without replacing it. Only then go to the next page.
4. When every page is repaired, reply with one line per page: page, number of edits, anything unreadable or odd.

Defects you repair:
- Characters: every character must match the image. Wrong or broken characters, signs, accents and symbols are corrected. Check every number, date, name and abbreviation against the image. An old OCR text layer can split single letters off as bold or italic markup, for example "distri **b** uti **on** o **f** the costs" (should be "distribution of the costs") or "opportunitie _s_ and" (should be "opportunities and").
- Formulas: a formula inside a text line is written in LaTeX as $...$. A display formula that still stands as text on its own line is written as $$...$$.
- Footnotes: the footnote marker in the text is written as [^N], the footnote text as [^N]: <text> at the end of the page on which it is printed. A note marked with a symbol such as * is written [^*]. Never a superscript like <sup>1</sup>, never an appended digit. Text that continues a footnote of the previous page has no marker: leave it where it is and add none. A footnote text that stands before the end of the file is moved there: cut it with one edit and insert it after the last paragraph with a second edit.
- Heading lines (lines starting with #): every character after the # marks must match the image. Remove characters that are not printed in the image and bold or italic markers such as ** and _. Keep the # marks exactly as they are, never add or remove one.
- Paragraphs: a paragraph that is split inside the page, for example by a column break or a footnote block, is joined back into one paragraph. A word hyphenated at that break is joined. Two paragraphs stay separate where the image shows a new paragraph, for example by an indented first line: insert the empty line between them with an edit.

Do not touch:
- Lines <!-- TABLE ... -->, <!-- FIGURE ... --> and <!-- FORMULA ... --> stay exactly as they are, at the same position. A FORMULA line stands for a display formula that another step writes; do not write that formula again.
- Lines starting with # stay lines starting with the same # marks. Never turn a line into a heading or a heading into a plain line.
- A paragraph that runs over to the next page or comes from the previous page stays split at the page boundary; another step joins it.
- Quotation marks stay as they are in the Markdown.
- Change nothing else: no added or removed text, no rewording, no italics, no bold, no indents, no headings. Never summarize, shorten or translate. Never write a Markdown image link.
- Invent nothing. If something in the image is unreadable, write [unreadable].

Change no file except the {{FIXED_PATTERN}} files of your pages.
