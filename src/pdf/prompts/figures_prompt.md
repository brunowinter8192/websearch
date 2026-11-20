You describe the pictures of one PDF. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}
Directory: {{DIR}}
Pictures: {{IDS}}
Pictures with a missing-words file: {{MISSING_IDS}}

For every picture id there are two files in the directory:
- <id>.png: the picture cropped at 200 dpi from the PDF page.
- <id>_current.md: what a converter extracted for that area. It may be empty. Text in it can help you read labels.
- <id>_missing.txt, only for the pictures named as having a missing-words file: words that are printed in this picture but missing from <id>_current.md, one per line.

Steps:
1. Take the pictures one after the other in the order listed above. For each picture read <id>.png, <id>_current.md and, if named above, <id>_missing.txt completely with the Read tool, then write <id>_fixed.md into the directory with the Write tool.
2. When every <id>_fixed.md is written, reply with one line per picture: id and whether anything was unreadable.

Rules:
- <id>_fixed.md holds exactly one paragraph, and it starts with **Figure description (not source text):**
- Describe what the picture shows: the kind of picture, every label and every box text, the relations between the elements (arrows, groupings, hierarchy), axes with their labels and ranges, the legend, the overall course of each data series, and the clearly marked points such as maximum, minimum, start and end.
- Every word of <id>_missing.txt is printed in the picture and must appear in <id>_fixed.md where the description reaches the part of the image that shows it.
- Do not give a value for every single data point. Give a value only where it can be read reliably from the image.
- Describe only what is visible in the image. Invent nothing and add no interpretation from outside the image, such as where the picture stands in the document or what kind of publication element it is.
- Change nothing else: no italics, no indents, no headings, no caption. The printed caption already exists elsewhere in the document.
- Never write a Markdown image link such as ![](image.png).
- Change no file except the <id>_fixed.md files.
- Every file you write ends with a newline.
