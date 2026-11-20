You correct the Markdown tables of one PDF against images of the tables. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}
Directory: {{DIR}}
Tables: {{IDS}}

For every table id there are two files in the directory:
- <id>.png: the table cropped at 200 dpi from the PDF page. This image is the ground truth.
- <id>_current.md: the same table as Markdown, produced automatically by a converter from the PDF text layer.

Steps:
1. Take the tables one after the other in the order listed above. For each table read <id>.png and <id>_current.md completely with the Read tool, then write <id>_fixed.md into the directory with the Write tool.
2. When every <id>_fixed.md is written, reply with one line per table: id, number of changes, anything unreadable or odd.

Rules:
- Correct only the content: every value, label, sign and footnote marker must match the image exactly. Compare cell by cell.
- Change nothing else. No italics, no bold, no indents, no &nbsp;, no added headings, no added captions, no added or removed text outside the table. Keep the markup of _current.md, such as <br> and <sup>, where the image agrees with it.
- Keep it a GitHub-flavored Markdown pipe table with every cell.
- Invent nothing. Do not add or infer any value that is not visible in the image. Write a cell or character you cannot read as [unreadable].
- If the image contains something that is not part of the table, leave it out of the table and report it.
- Change no file except the <id>_fixed.md files.
- Every file you write ends with a newline.
