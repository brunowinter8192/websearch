1. Read the anchor text file completely.
2. Read the PDF pages {{READ_PAGES_1}} with the Read tool (pages parameter "{{READ_PAGES_1}}"), so you see every page as an image. The Read tool returns at most 20 pages per call.
3. Write the Markdown for pages {{READ_PAGES_1}} to the part file {{PART_1}} with the Write tool.
4. Read the PDF pages {{READ_PAGES_2}} with the Read tool (pages parameter "{{READ_PAGES_2}}").
5. Write the Markdown for pages {{READ_PAGES_2}} to the part file {{PART_2}} with the Write tool.
6. Create the output file with exactly this Bash command and no other way: { cat "{{PART_1}}"; echo; cat "{{PART_2}}"; } > "{{OUTPUT}}" && rm "{{PART_1}}" "{{PART_2}}"
7. When the output file exists, reply with one line: done, number of pages written, and anything you could not transcribe.
