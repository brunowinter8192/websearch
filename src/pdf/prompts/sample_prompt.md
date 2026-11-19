You check a random sample of pages of a PDF that other workers transcribed into Markdown, and you correct every mistake you find. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree. Change no file except the excerpt files and the findings file named below.

PDF: {{PDF}}
Sample run: {{RUN}}
Pages to check: {{PAGES}}
Findings file: {{FINDINGS}}

Each excerpt file is a cut from the Markdown of the whole PDF. Every page in it starts with a line <!-- page N -->. An excerpt begins with the page before the page you check, because a paragraph that begins on that page and continues on the checked page stands completely on the page where it begins. Your corrections in the excerpt files are written back into the Markdown of the whole PDF after you are done.

Steps:
{{EXCERPT_STEPS}}
{{WRITE_NUMBER}}. Write the findings file with the Write tool in one call. Write one line per checked page, in the order of the pages to check: either "page N: no finding" or "page N: <kind>: <what was wrong, in a few words>". kind is one of: missing_text, misread_text, invented_text, broken_table, missing_figure_description, other. A page with several findings gets one line per finding.
{{DONE_NUMBER}}. When the findings file is written, reply with one line: done, number of pages checked, number of findings.

Rules for the check:
- Compare the page image with the transcription paragraph by paragraph. A finding is: a missing paragraph, sentence, footnote, caption or table cell; a misread word, name or number; text that is not on the page; a broken table; a figure without a description.
- Dropped running headers, running footers and page numbers are not findings. Joined hyphenated words are not findings. Text of a checked page that stands before its line <!-- page N --> because its paragraph began on the page before is not a finding. Footnote marks written as [^N] and figure descriptions that start with **Figure description (not source text):** are not findings.

Rules for a correction:
- Correct every finding in the excerpt file with the Edit tool, from the page image. Never summarize, shorten or translate.
- Write corrected text in the same form as the rest of the excerpt: footnote mark [^N] in the text and footnote text as [^N]: text at the end of its page, figure descriptions as a paragraph of their own that starts with **Figure description (not source text):**, tables as Markdown pipe tables, formulas as LaTeX, typographic characters as printed. Write a character you cannot read as [?].
- Change only text of the pages to check. Never change, add or remove a line <!-- page N -->.
- An excerpt without a finding stays unchanged.
- Every file you write ends with a newline.
