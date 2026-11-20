You set the heading levels of one PDF. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}
Pages: {{PAGES}}
Output file: {{OUTPUT}}

The PDF was converted page by page to Markdown. Read completely with the Read tool:
- {{HEADINGS}}: every line the converter classified as a heading, with id, page and text. In the page files each one is replaced by a line <!-- HEADING <id> -->.
- {{BOOKMARKS}}: the bookmarks embedded in the PDF (level, title, page). Bookmarks can be incomplete or wrong: entries can be missing, and several entries can carry the same title. Use them only as a hint. The printed headings count.
- The page files {{PAGE_FILES}}, only to find headings the converter missed.

Heading rule:
- The level follows the outline of the work, not the font size: title of the work 1, chapter 2, subchapter 3, every level below 4. A work without a table of contents (article, slide deck): title 1, every section heading or slide title 2, every subsection 3, anything below 4.
- The same rank has the same level everywhere in the document.
- An entry of {{HEADINGS}} that is not a heading at all, for example a formula, a figure label or a publisher name, gets level 0.
- The wording of a heading stays exactly as printed. Do not fix spelling, do not change case, do not shorten.

Steps:
1. Read the files named above.
2. Write the output file with the Write tool in one call. It is a JSON object with two keys:
   - "headings": one entry per id of {{HEADINGS}}, in the same order: {"id": "<id>", "level": 0 to 4, "text": "<the heading wording without # marks>"}.
   - "missed": one entry per heading the converter missed: {"page": N, "line": "<the exact line as it appears in the page file>", "level": 1 to 4}. The line must match one line of the page file character for character. Never name a line that starts with <!--.
3. When the file is written, reply with the full outline as it will look, one heading per line with its # marks.

Change no file except the output file. The file ends with a newline.
