# INFRASTRUCTURE
import re

import pytest

from dev.tests._pdf_fakes import base_manifest, conversion_log, read_log, write_manifest
from src.pdf.assemble import assemble_workflow
from src.pdf.report import WorkflowError

TABLE = "|a|b|\n|---|---|\n|1|2|"
FIGURE = "**Figure description (not source text):** Line chart of the CAR."
FORMULA = "$$R_i = \\alpha + \\beta R_m + \\text{error}.$$"


# FUNCTIONS

def batch(tmp_path, pages, tables=(), figures=(), formulas=()):
    batch_dir = tmp_path / "batch"
    outputs = [f"pages/p{number}_fixed.md" for number in range(1, len(pages) + 1)]
    workers = [{"name": "pages", "prompt": "prompt_pages.md", "outputs": outputs}]
    workers += [{"name": "tables", "prompt": "prompt_tables.md", "outputs": [f"tables/{name}_fixed.md" for name in tables]}]
    workers += [{"name": "figures", "prompt": "prompt_figures.md", "outputs": [f"figures/{name}_fixed.md" for name in figures]}]
    workers += [{"name": "formulas", "prompt": "prompt_formulas.md", "outputs": [f"formulas/{name}_fixed.md" for name in formulas]}]
    manifest = base_manifest(len(pages), workers=workers)
    manifest["tables"], manifest["figures"], manifest["formulas"] = list(tables), list(figures), list(formulas)
    write_manifest(batch_dir, manifest)
    for name in ("pages", "tables", "figures", "formulas"):
        (batch_dir / name).mkdir()
    for number, text in enumerate(pages, start=1):
        (batch_dir / "pages" / f"p{number}_outlined.md").write_text(text)
        (batch_dir / "pages" / f"p{number}_fixed.md").write_text(text)
    for name in tables:
        (batch_dir / "tables" / f"{name}_fixed.md").write_text(TABLE + "\n")
    for name in figures:
        (batch_dir / "figures" / f"{name}_fixed.md").write_text(FIGURE + "\n")
    for name in formulas:
        (batch_dir / "formulas" / f"{name}_fixed.md").write_text(FORMULA + "\n")
    return batch_dir


def book_pages(batch_dir):
    book = (batch_dir / "Book.md").read_text()
    parts = re.split(r"^<!-- page \d+ -->$", book, flags=re.MULTILINE)
    return [part.strip() for part in parts[1:]]


def test_a_paragraph_running_over_the_page_is_completed_before_the_footnotes_of_its_page(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "## 1. INTRODUCTION \n\nHeal (2005, p. 393) defines CSR as ‘‘(. . .) taking actions which reduce the extent of externalized \n\n"
        "[^*]: We are very grateful to the editor. Final revision accepted: October 16, 2006.\n",
        "costs or avoid distributional conflicts.’’ Furthermore, we want to find out more.\n\nThe structure of this paper is as follows.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert report.ok
    assert "page joins: 1: 1->2(body)" in report.text
    first, second = book_pages(batch_dir)
    assert first.split("\n\n") == [
        "## 1. INTRODUCTION",
        "Heal (2005, p. 393) defines CSR as “(. . .) taking actions which reduce the extent of externalized "
        "costs or avoid distributional conflicts.” Furthermore, we want to find out more.",
        "[^*]: We are very grateful to the editor. Final revision accepted: October 16, 2006.",
    ]
    assert second == "The structure of this paper is as follows."
    assert (batch_dir / "Book.md").read_text().startswith("<!-- page 1 -->\n\n## 1. INTRODUCTION")


def test_a_new_paragraph_at_the_top_of_the_next_page_stays_on_that_page(tmp_path):
    batch_dir = batch(tmp_path, [
        "In high-impact projects, borrowers develop an EMP that addresses mitigation and monitoring of\n",
        "environmental and social risk. Adopters are required to report on an annual basis.[^2]\n\n"
        "The history of the EP is described by Esty, Knoop, and Sesia (2005).\n",
    ])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first.endswith("mitigation and monitoring of environmental and social risk. Adopters are required to report on an annual basis.[^2]")
    assert second == "The history of the EP is described by Esty, Knoop, and Sesia (2005)."


def test_a_word_hyphenated_over_the_page_boundary_is_joined_without_hyphen_and_space(tmp_path):
    batch_dir = batch(tmp_path, ["It may increase the ben-\n", "efits. Furthermore, apart from that.\n\n### (c) Governance issues\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "It may increase the benefits. Furthermore, apart from that."
    assert second == "### (c) Governance issues"


def test_a_footnote_running_over_the_page_takes_the_unmarked_continuation(tmp_path):
    batch_dir = batch(tmp_path, [
        "Further research will be needed to address these issues.\n\n## NOTES\n\n[^1]: IFC uses a set of policies for private sector\n",
        "projects. The safeguard policies provide guidance.\n\n[^2]: From March to May 2006, the EP banks engaged in a review.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "1->2(footnote)" in report.text
    first, second = book_pages(batch_dir)
    assert first.endswith("[^1]: IFC uses a set of policies for private sector projects. The safeguard policies provide guidance.")
    assert second == "[^2]: From March to May 2006, the EP banks engaged in a review."


def test_the_join_skips_a_page_of_table_caption_table_and_note_and_a_table_caption_and_note_on_the_next(tmp_path):
    batch_dir = batch(tmp_path, [
        "For the firm characteristics, we have the surprising\n",
        "Table 1. Descriptive statistics\n\n<!-- TABLE p2_0 -->\n\n(continued on next page)\n",
        "Table 1—continued\n\n<!-- TABLE p3_0 -->\n\nSource: Bankscope, Datastream.\n\nfinding that almost all attributes differ.\n\nNext paragraph.\n",
    ], tables=("p2_0", "p3_0"))
    report = assemble_workflow(str(batch_dir))
    assert "1->3(body)" in report.text
    first, second, third = book_pages(batch_dir)
    assert first == "For the firm characteristics, we have the surprising finding that almost all attributes differ."
    assert second == f"Table 1. Descriptive statistics\n\n{TABLE}\n\n(continued on next page)"
    assert third == f"Table 1—continued\n\n{TABLE}\n\nSource: Bankscope, Datastream.\n\nNext paragraph."


def test_the_join_skips_a_figure_and_its_caption(tmp_path):
    batch_dir = batch(tmp_path, [
        "the cumulative abnormal returns for the period of one day before the event\n",
        "<!-- FIGURE p2_0 -->\n\nFigure 3. Cumulative abnormal returns.\n\nuntil one day after the event.\n",
    ], figures=("p2_0",))
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "the cumulative abnormal returns for the period of one day before the event until one day after the event."
    assert second == f"{FIGURE}\n\nFigure 3. Cumulative abnormal returns."


def test_a_page_number_left_in_the_page_is_neither_joined_onto_nor_moved(tmp_path):
    batch_dir = batch(tmp_path, ["which reduce the extent of externalized\n\n1307\n", "iii\n\ncosts or avoid conflicts.\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "which reduce the extent of externalized costs or avoid conflicts.\n\n1307"
    assert second == "iii"


def test_a_finished_paragraph_and_a_heading_on_the_next_page_are_not_joined(tmp_path):
    batch_dir = batch(tmp_path, ["The model specification is linear:\n", "Here, Ri is the daily return.\n", "of the\n", "## REFERENCES\n\nmore text\n"])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 0: none" in report.text
    assert book_pages(batch_dir) == ["The model specification is linear:", "Here, Ri is the daily return.", "of the", "## REFERENCES\n\nmore text"]


def test_an_incomplete_worker_stops_assemble_with_the_missing_files_and_logs_it(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["a.\n", "b.\n"])
    (batch_dir / "pages" / "p2_fixed.md").unlink()
    report = assemble_workflow(str(batch_dir))
    assert not report.ok
    assert report.text.splitlines() == [
        "assemble FAILED (incomplete_worker): 1 of 4 workers incomplete, nothing written",
        "  pages: incomplete (missing: pages/p2_fixed.md)",
    ]
    assert not (batch_dir / "Book.md").exists()
    end = read_log(conversion_log)[-1]
    assert (end["outcome"], end["failure_class"]) == ("failed", "incomplete_worker")
    assert end["incomplete_workers"] == [{"name": "pages", "missing": ["pages/p2_fixed.md"]}]


def test_a_page_worker_that_dropped_a_table_placeholder_fails_assemble(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["Table 1.\n\n<!-- TABLE p1_0 -->\n"], tables=("p1_0",))
    (batch_dir / "pages" / "p1_fixed.md").write_text("Table 1.\n")
    report = assemble_workflow(str(batch_dir))
    assert not report.ok
    assert "assemble FAILED (placeholder_changed): page 1" in report.text and "TABLE p1_0" in report.text
    assert read_log(conversion_log)[-1]["failure_class"] == "placeholder_changed"


def test_assemble_before_apply_outline_fails(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["a.\n"])
    (batch_dir / "pages" / "p1_outlined.md").unlink()
    report = assemble_workflow(str(batch_dir))
    assert "assemble FAILED (outline_not_applied)" in report.text


def test_assemble_after_sampling_started_is_refused(tmp_path):
    batch_dir = batch(tmp_path, ["a.\n"])
    (batch_dir / "samples" / "run_1").mkdir(parents=True)
    (batch_dir / "samples" / "run_1" / "run.json").write_text('{"run": 1, "status": "open"}')
    with pytest.raises(WorkflowError) as raised:
        assemble_workflow(str(batch_dir))
    assert raised.value.failure_class == "sampling_started"


def test_a_formula_placeholder_is_replaced_by_the_written_formula(tmp_path):
    batch_dir = batch(tmp_path, ["The model specification is linear:\n\n<!-- FORMULA p1_0 -->\n\nHere, Ri is the daily return.\n"], formulas=("p1_0",))
    report = assemble_workflow(str(batch_dir))
    assert report.ok, report.text
    assert "formulas=1" in report.text
    assert book_pages(batch_dir) == [f"The model specification is linear:\n\n{FORMULA}\n\nHere, Ri is the daily return."]


def test_a_heading_line_with_corrected_characters_passes_and_a_changed_number_of_marks_fails(tmp_path, conversion_log):
    outlined = "## **1. Introduction**\n\nText.\n\n### Global Banks 542..575 Regulators?lapo_348\n"
    batch_dir = batch(tmp_path, [outlined])
    (batch_dir / "pages" / "p1_fixed.md").write_text("## 1. Introduction\n\nText.\n\n### Global Banks Regulators?\n")
    assert assemble_workflow(str(batch_dir)).ok
    assert book_pages(batch_dir) == ["## 1. Introduction\n\nText.\n\n### Global Banks Regulators?"]
    (batch_dir / "pages" / "p1_fixed.md").write_text("# 1. Introduction\n\nText.\n\n### Global Banks Regulators?\n")
    report = assemble_workflow(str(batch_dir))
    assert not report.ok
    assert report.text == (
        "assemble FAILED (heading_marks_changed): page 1: pages/p1_fixed.md has heading marks ['#', '###'], "
        "pages/p1_outlined.md has ['##', '###']"
    )
    assert read_log(conversion_log)[-1]["failure_class"] == "heading_marks_changed"


def test_an_open_paragraph_and_an_open_footnote_before_a_heading_on_the_next_page_are_not_joined(tmp_path):
    batch_dir = batch(tmp_path, [
        "We focus our analysis on one case study.\n\n_ISSN 1569-1829 print, DOI 10.3920/JCNS2012.x002_\n\n_13_\n\n"
        "[^1]: _Institute for International Trade Negotiations; pmoura@iconebrasil.org.br_\n\n"
        "[^2]: _University of Missouri, Columbia, MO 65211, USA; chaddadf@missouri.edu_\n",
        "## **2. Literature review**\n\nThe literature on MSIs is growing.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert report.ok, report.text
    assert "page joins: 0: none" in report.text


def test_an_italic_page_number_is_neither_joined_onto_nor_moved(tmp_path):
    batch_dir = batch(tmp_path, ["which reduce the extent of externalized\n\n_13_\n", "costs or avoid conflicts.\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first == "which reduce the extent of externalized costs or avoid conflicts.\n\n_13_"
    assert second == ""


def test_an_open_paragraph_and_an_open_footnote_with_a_continuation_still_fail_as_ambiguous(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["the extent of externalized\n\n[^1]: IFC uses a set of policies for\n", "costs or avoid conflicts.\n"])
    report = assemble_workflow(str(batch_dir))
    assert report.text == "assemble FAILED (ambiguous_page_join): page 1: its last paragraph and its last footnote both run on"


def test_a_reference_list_item_is_not_continued_by_the_next_item_but_a_footnote_is_continued_by_a_dash_line(tmp_path):
    batch_dir = batch(tmp_path, [
        "## References\n\n- [5] Andam K S 2008 Measuring the effectiveness _Proc. Natl Acad. Sci._ **105** 16089\n\n"
        "- [6] Jayachandran S 2017 Cash for carbon _Science_ **357** 267–73\n",
        "- [7] Alix-Garcia J M and Gibbs H K 2017 Forest conservation effects\n\n- [8] Pfaff A and Robalino J 2017 Spillovers\n",
        "## NOTES\n\n[^10]: Several recent decisions made it more difficult for plaintiffs to use the U.S. federal courts to sue\n",
        "- corporations for human rights abuses abroad under the 1798 Alien Tort Statute (Gibeaut 2011).\n\n## REFERENCES\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 3->4(footnote)" in report.text
    first, second, third, fourth = book_pages(batch_dir)
    assert first.endswith("- [6] Jayachandran S 2017 Cash for carbon _Science_ **357** 267–73")
    assert second.startswith("- [7] Alix-Garcia")
    assert third.split("\n\n")[0] == "## NOTES"
    assert third.split("\n\n")[1].startswith("[^10]: Several")
    assert third.endswith("to sue corporations for human rights abuses abroad under the 1798 Alien Tort Statute (Gibeaut 2011).")
    assert fourth == "## REFERENCES"


def test_caption_labels_their_titles_and_table_notes_are_skipped_and_a_page_of_only_tables_is_no_target(tmp_path):
    batch_dir = batch(tmp_path, [
        "For the average pairwise collaboration, adopters i tend to collaborate as the significantly lower average\n",
        "Table 2\n\nRegional distribution of adopters of the Equator Principles.\n\n<!-- TABLE p2_0 -->\n\n"
        "This distribution concerns our sample of lead arrangers.\n\nTable 3\n\nSummary statistics.\n\n<!-- TABLE p2_1 -->\n\n"
        "Unit of observation: pairwise collaborations.\n\n(%) for adopters – our measure for peer pressure – shows.\n",
        "Table 8\n\nAdoption of the Equator Principles using Cox regression models.\n\n<!-- TABLE p3_0 -->\n",
        "Table 8 (continued)\n\n<!-- TABLE p4_0 -->\n\nExponentiated coefficients.\n\n"
        "The variable Initial adopter takes the value of one.\n",
    ], tables=("p2_0", "p2_1", "p3_0", "p4_0"))
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 1->2(body)" in report.text
    first, second, third, fourth = book_pages(batch_dir)
    assert first == "For the average pairwise collaboration, adopters i tend to collaborate as the significantly lower average (%) for adopters – our measure for peer pressure – shows."
    assert second.endswith("Unit of observation: pairwise collaborations.")
    assert third == f"Table 8\n\nAdoption of the Equator Principles using Cox regression models.\n\n{TABLE}"
    assert fourth.endswith("The variable Initial adopter takes the value of one.")


def test_body_text_directly_before_a_table_without_caption_continues_the_page_before(tmp_path):
    batch_dir = batch(tmp_path, [
        "Research in bandwagon effects may shed\n",
        "some light to our findings. The initial group consists of 14 banks.\n\n<!-- TABLE p2_0 -->\n\n"
        "Table 7 presents the results from these additional analyses.\n\nTo determine the validity of our results, we perform a validation.\n",
    ], tables=("p2_0",))
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 1->2(body)" in report.text
    first, second = book_pages(batch_dir)
    assert first == "Research in bandwagon effects may shed some light to our findings. The initial group consists of 14 banks."
    assert second.startswith(f"{TABLE}\n\nTable 7 presents")


def test_lowercase_text_directly_after_a_table_continues_the_page_before(tmp_path):
    batch_dir = batch(tmp_path, [
        "However, where their non-certified concessions overlapped with the forest\n",
        "**Table 2.** Average partial effects of direct and indirect exposure.\n\n<!-- TABLE p2_0 -->\n\n"
        "estate, greater exposure to within-company certification was associated with reduced deforestation.\n\n"
        "### 4.3. Local market spillovers\n",
    ], tables=("p2_0",))
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 1->2(body)" in report.text
    first, second = book_pages(batch_dir)
    assert first.endswith("overlapped with the forest estate, greater exposure to within-company certification was associated with reduced deforestation.")
    assert second == f"**Table 2.** Average partial effects of direct and indirect exposure.\n\n{TABLE}\n\n### 4.3. Local market spillovers"


def test_a_paragraph_ending_in_a_semicolon_runs_on_past_a_captioned_table(tmp_path):
    batch_dir = batch(tmp_path, [
        "where $EP_j$ is a dummy variable equal to one if lead arranger j is an adopter and zero otherwise;\n",
        "Table 1\n\nVariable description.\n\n<!-- TABLE p2_0 -->\n\n"
        "$\\text{Concentration}_{ji}$ is the share of syndicated project finance loans.\n\nThe second key variable is Susceptibility.\n",
    ], tables=("p2_0",))
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 1->2(body)" in report.text
    first, _ = book_pages(batch_dir)
    assert first == "where $EP_j$ is a dummy variable equal to one if lead arranger j is an adopter and zero otherwise; $\\text{Concentration}_{ji}$ is the share of syndicated project finance loans."


def test_a_paragraph_and_a_footnote_both_running_on_take_the_first_paragraph_and_the_one_before_the_first_footnote(tmp_path):
    batch_dir = batch(tmp_path, [
        "how, if the central purpose of intervention is to be achieved, intervention must expand\n\n"
        "[^11]: \"I have no doubt that this statement will be contradicted, and, therefor, the nature of the needs\n",
        "until it becomes a comprehensive system of planning.[^12] But it is relevant.\n\n## III\n\n"
        "The wide popularity which the idea enjoys today.\n\n[19]\n\n"
        "that are to be satisfied. A more detailed examination must be reserved for another occasion.\n\n"
        "[^12]: Cf. L. V. Mises, Kritik des Interventionismus (Jena, 1929).\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 2: 1->2(body) 1->2(footnote)" in report.text
    first, second = book_pages(batch_dir)
    assert first.split("\n\n") == [
        "how, if the central purpose of intervention is to be achieved, intervention must expand until it becomes a comprehensive system of planning.[^12] But it is relevant.",
        "[^11]: \"I have no doubt that this statement will be contradicted, and, therefor, the nature of the needs that are to be satisfied. "
        "A more detailed examination must be reserved for another occasion.",
    ]
    assert second.split("\n\n") == [
        "## III", "The wide popularity which the idea enjoys today.", "[19]", "[^12]: Cf. L. V. Mises, Kritik des Interventionismus (Jena, 1929).",
    ]


def test_a_page_number_in_picture_text_markup_is_neither_joined_onto_nor_moved(tmp_path):
    markup = "<!-- Start of picture text -->\n[31]<br><!-- End of picture text -->"
    batch_dir = batch(tmp_path, [
        f"The creation of the common creed becomes an indis-\n\n{markup}\n\n[^17]: America Must Choose (New York, 1934).\n",
        "pensable instrument for the success of the planned system.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 1: 1->2(body)" in report.text
    first, second = book_pages(batch_dir)
    assert first == f"The creation of the common creed becomes an indispensable instrument for the success of the planned system.\n\n{markup}\n\n[^17]: America Must Choose (New York, 1934)."
    assert second == ""


@pytest.mark.parametrize("page_end, first_paragraph, second_page", [
    (
        "Banks have caused damage to people who did not trade financial instruments they did not understand,\n\n"
        "> Address correspondence to John M. Conley, Chapel Hill, NC 27599-3380.\n\n"
        "LAW & POLICY, Vol. 33, No. 4, October 2011 © 2011 The Authors Law & Policy © 2011 The University of Denver/Colorado Seminary\n\n"
        "ISSN 0265–8240\n",
        "Banks have caused damage to people who did not trade financial instruments they did not understand, "
        "and did not distribute risk in ways that were opaque.",
        "",
    ),
    (
        "View the article online for updates and enhancements.\n\n"
        "This content was downloaded from IP address 79.213.252.163 on 19/11/2026 at 22:09\n",
        "View the article online for updates and enhancements.",
        "and did not distribute risk in ways that were opaque.",
    ),
    (
        "It may well mean the destruction of everything.\n\n[PRINTED IN USA]\n",
        "It may well mean the destruction of everything.",
        "and did not distribute risk in ways that were opaque.",
    ),
])
def test_imprint_lines_at_the_end_of_a_page_are_no_join_target(tmp_path, page_end, first_paragraph, second_page):
    batch_dir = batch(tmp_path, [page_end, "and did not distribute risk in ways that were opaque.\n"])
    assemble_workflow(str(batch_dir))
    first, second = book_pages(batch_dir)
    assert first.split("\n\n")[0] == first_paragraph
    assert second == second_page
