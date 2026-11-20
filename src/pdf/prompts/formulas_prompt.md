You write the display formulas of one PDF as LaTeX from images of the formulas. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree.

PDF: {{PDF}}
Directory: {{DIR}}
Formulas: {{IDS}}

For every formula id there are two files in the directory:
- <id>.png: the formula cropped at 200 dpi from the PDF page. This image is the ground truth.
- <id>_current.md: what a converter extracted for that area. Its characters are often wrong or missing, for example ¼ for =, þ for +, ð and Þ for brackets, and subscripts written on the line. Use it only as a hint.

Steps:
1. Take the formulas one after the other in the order listed above. For each formula read <id>.png and <id>_current.md completely with the Read tool, then write <id>_fixed.md into the directory with the Write tool.
2. When every <id>_fixed.md is written, reply with one line per formula: id and anything unreadable or odd.

Rules:
- <id>_fixed.md holds exactly one line: the formula in LaTeX between $$ and $$, for example $$R_i = \alpha + \beta R_m + \text{error}.$$
- Write every symbol, subscript, superscript, fraction, sum, product, bracket and punctuation mark exactly as the image shows it. Words inside the formula go into \text{...}.
- A formula printed over several lines is written as one formula on one line.
- An equation number printed next to the formula, such as (1), is written at the end as \tag{1}.
- Invent nothing. Write a symbol you cannot read as \text{[unreadable]}.
- Change nothing else: no explanation, no heading, no text before or after the formula.
- Change no file except the <id>_fixed.md files.
- Every file you write ends with a newline.
