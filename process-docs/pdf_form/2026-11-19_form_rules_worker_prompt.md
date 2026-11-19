# Form rules for converted PDFs (2026-11-19)

Area: pdf_form. Builds on the areas pdf_workflow (text mode) and pdf_scan (scan mode).

## What was decided

On 2026-11-19 the form of the converted Markdown became a fixed set of rules. The rules stand in two places:

- In the worker prompts `src/pdf/prompts/worker_prompt.md` and `src/pdf/prompts/scan_worker_prompt.md`, so every worker produces the form while it transcribes.
- In the skill `skills/websearch-pdf/SKILL.md` as section "Formregeln" plus a new Step 3 "Formkontrolle", so the orchestrator checks the batch files before `assemble`.

`src/pdf/prompts/control_prompt.md` got one line so the scan control worker does not report the new form as a deviation.

No Python module under `src/pdf/` was changed. `extract.py` and `assemble.py` behave as before.

## Observed weaknesses that triggered the change

A review of one converted book (Gigerenzer, several 50-page batches) listed these findings:

- Heading levels differed between batches. Chapters 1, 2, 6 and 7 were `#`, chapters 3 to 5 and 8 to 11 were `##`. Subchapters jumped between `##` and `###`.
- About 150 sentences were cut at a page boundary: the sentence stopped at the end of the page and continued after the `<!-- page N -->` line. Example: "…killed annually in the United States by", page marker, "terrorists…".
- Figure descriptions stood in the middle of a paragraph.
- Footnote marks were bare digits in the first half ("…dignity.1") and `<sup>14</sup>` in the second half.
- Straight and typographic quotation marks were mixed.
- Long "Figure description" blocks existed only from chapter 8 on.
- Three image links (`img_p218_1.png` and two more) pointed to files that do not exist.
- 15 empty pages. Harmless.
- Figure descriptions are written by the converter, not by the author. A reader could quote them as source text.

The same day, the four slide decks of the collection wise2627-reference showed the same pattern on a small scale. Each deck was converted by a different worker and each uses a different figure format: `[Figure: …]`, `**Figure:**`, `*Figure:*` and `*Figure: …*`. Slide titles are `##` in deck 3 and `#` in deck 4.

## Cause

Each worker sees only its own batch. Before 2026-11-19 the prompt said "Headings as Markdown headings, following the visual hierarchy". Every worker therefore built its own scale from the pages it saw. The prompt had no rule for footnotes, no fixed format for figure descriptions and no rule for a paragraph that crosses a page. The rule "Start each page with a line `<!-- page N -->`" forced the marker into the middle of a sentence.

## The rules and why each looks the way it does

- Headings: title `#`, chapter `##`, subchapter `###`, below `####`. Without a table of contents: title `#`, every section or slide title `##`. A fixed scale is the only thing two workers can agree on without seeing each other.
- `outline.md`: the orchestrator writes the outline of the PDF to `BATCH_DIR/outline.md` after `extract` (skill Step 1). The prompt tells the worker to read `outline.md` "in the directory of the output file". This wording avoids a new placeholder, so `extract.py` stayed untouched.
- Paragraph across a page: the paragraph stands completely on the page where it begins, the next page marker follows after its end. At a part-file boundary (a worker reads 20 pages per call) the worker leaves the unfinished paragraph out of the part it is writing and writes it at the start of the next part, before that part's first page marker. Reason: the concatenation command puts an empty line between two part files, so a paragraph split over two part files would become two paragraphs.
- Batch boundary: no worker sees both sides. The worker writes the unfinished paragraph as far as its last page goes. Joining is the orchestrator's job in the skill's Formkontrolle.
- Footnotes: mark `[^N]`, text `[^N]: …` at the end of the page where it is printed. Chosen because it cannot be confused with an ordinary number. The digit stays in the text, so the character count of `assemble` still sees it.
- Figures: own paragraph, fixed start `**Figure description (not source text):**`, caption as normal text below. The label answers the finding that descriptions could be quoted as source text.
- Image links are forbidden. Hypothesis, not verified: the links came from the liteparse anchor text and the worker copied them. The text prompt therefore says "also when the anchor text contains one".
- An empty page keeps only its page marker.

## What is verified and what is not

- Verified on 2026-11-19: the rendered prompts carry the rules in both modes (`dev/tests/test_pdf_worker_prompt.py`, new test), all 74 tests of the ten `test_pdf_*.py` files pass.
- Not verified: no PDF was converted with the new prompts on 2026-11-19. Whether Haiku follows the paragraph rule at part-file boundaries is unknown.
- Not verified: the grep patterns in the skill's Formkontrolle never ran on a real batch.
- Reasoned, not tested: the content check of `assemble` compares character counts per batch, not per page, so moving the tail of a paragraph to the previous page does not change the recall.

## Content filter blocks observed the same day

Two of twelve articles converted on 2026-11-19 never produced a batch file:

- Schelling 1981, "Economic Reasoning and the Ethics of Policy", mode text, 25 pages.
- Hayek 1939, "Freedom and the Economic System", mode scan, 23 pages.

Each was tried three times: once with the Haiku model from `config/pdf_models.json`, twice without `MODEL_SELECTION_FILE`. All six attempts ended with the single reply `API Error: Output blocked by content filtering policy`. No part file was written in any attempt, so the block hit the first write. The other ten articles of the same run, converted with the same prompt, passed. The cause is unknown; the message names none. The skill has a rule for a blocked worker in mode text only; a blocked worker in mode scan is not covered.
