You check the transcription of a scanned PDF on a random sample of pages. Work alone, do not ask questions, do not commit anything, do not change any file in your worktree. Do not edit any batch file; you only read and judge.

PDF: {{PDF}}
Pages to check: {{CONTROL_PAGES}}
Batch files with the transcription (every page starts with a line <!-- page N -->): {{BATCH_FILES}}
Output file: {{OUTPUT}}

Steps:
1. Read every batch file listed above completely with the Read tool.
{{PAGE_STEPS}}
{{WRITE_NUMBER}}. Write your findings for every checked page to the output file with the Write tool in one call, as JSON in exactly this shape:

{
  "pdf": "{{PDF}}",
  "pages": [
    {
      "page": 4,
      "batch": "batch_1-50.md",
      "correct": false,
      "findings": [
        {"kind": "misread_number", "grave": true, "detail": "image: 1.234, text: 1.324"}
      ]
    }
  ]
}

{{DONE_NUMBER}}. When the file is written, reply with one line: done, number of pages checked, number of grave findings.

Rules for the check:
- For each page, locate its text in the batch file by the line <!-- page N -->. If that line is missing, locate the text by its content between the neighbouring pages and add a finding of kind marker_missing (not grave).
- Compare the page image with the transcription paragraph by paragraph. Name every deviation: missing paragraphs, misread numbers, misread words or names, invented text that is not on the page, broken tables (missing rows, cells or columns), missing figure descriptions.
- Dropped running headers, running footers and page numbers are not deviations. Joined hyphenated words are not deviations.
- kind is one of: missing_paragraph, misread_number, invented_text, broken_table, marker_missing, other.
- grave is true when the deviation changes the meaning or loses content a reader needs: a missing paragraph, a wrong number, a wrong name, invented sentences, a table that lost cells. grave is false for a typo without change of meaning, a wrong heading level, a missing marker, a formatting difference.
- detail quotes the image reading and the transcription reading in a few words.
- A page with no deviation has "correct": true and an empty findings list.
- Every checked page appears exactly once in pages. Never omit a page from the list above.
- Every file you write ends with a newline.
