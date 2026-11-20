You repair the quality of already extracted Markdown pages of one PDF. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}

The text of these pages already exists. It was extracted from the PDF text layer or by OCR and is in the files below. Your job is only to fix extraction defects in that existing text. You are not asked to reproduce, retype or rewrite any content: the content is already there, and you stay as close to the existing text as you possibly can.

For each page N in {{PAGES}}:
- {{PNG_PATTERN}}: the page image. Use it only to decide what a damaged spot should be.
- {{FIXED_PATTERN}}: the extracted Markdown of the page. This is the file you repair, in place. Its first line is {{PENDING}}.

Typical defects: wrong or broken characters, and an old OCR layer that split single letters off as bold or italic markup, for example "distri **b** uti **on** o **f** the costs" (should be "distribution of the costs") or "opportunitie _s_ and" (should be "opportunities and").

How to work:
1. Take the pages one after the other. For each page N read {{PNG_PATTERN}} and {{FIXED_PATTERN}} with the Read tool.
2. Repair {{FIXED_PATTERN}} only with the Edit tool, one small edit at a time: each edit replaces a short damaged fragment by the repaired fragment. Never use the Write tool, never replace a whole paragraph or the whole file.
3. Fix only: letters split off by ** or _ markup, wrong characters, and footnote markers (write them as [^N], footnote text as [^N]: <text>).
4. Leave everything else exactly as it is: wording, order, paragraphs, lines starting with #, lines <!-- ... -->. Add nothing, remove no text, invent nothing. The only exception is step 5.
5. When a page is repaired, remove its first line {{PENDING}} with one last Edit, also when the page needed no repair. Only then go to the next page.

When every page is repaired, reply with one line per page: page and number of edits.
