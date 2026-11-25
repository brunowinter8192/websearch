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

def batch(tmp_path, pages, tables=(), figures=(), formulas=(), running=()):
    batch_dir = tmp_path / "batch"
    outputs = [f"pages/p{number}_fixed.md" for number in range(1, len(pages) + 1)]
    workers = [{"name": "pages", "prompt": "prompt_pages.md", "outputs": outputs}]
    workers += [{"name": "tables", "prompt": "prompt_tables.md", "outputs": [f"tables/{name}_fixed.md" for name in tables]}]
    workers += [{"name": "figures", "prompt": "prompt_figures.md", "outputs": [f"figures/{name}_fixed.md" for name in figures]}]
    workers += [{"name": "formulas", "prompt": "prompt_formulas.md", "outputs": [f"formulas/{name}_fixed.md" for name in formulas]}]
    manifest = base_manifest(len(pages), workers=workers)
    manifest["tables"], manifest["figures"], manifest["formulas"] = list(tables), list(figures), list(formulas)
    manifest["running"] = list(running)
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


def test_an_open_footnote_whose_place_on_the_next_page_holds_no_text_still_fails_as_ambiguous(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "the extent of externalized\n\n[^1]: IFC uses a set of policies for\n",
        "costs or avoid conflicts.\n\n<!-- TABLE p2_0 -->\n\n[^2]: Source.\n",
    ], tables=("p2_0",))
    report = assemble_workflow(str(batch_dir))
    assert report.text == "assemble FAILED (ambiguous_page_join): page 1: its last footnote runs on, but page 2 has no text before its first footnote"


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


def test_a_word_listed_as_missing_for_a_table_must_appear_in_its_fixed_table(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, ["Table 1.\n\n<!-- TABLE p1_0 -->\n"], tables=("p1_0",))
    (batch_dir / "tables" / "p1_0_missing.txt").write_text("during\ndroughts\n")
    (batch_dir / "tables" / "p1_0_fixed.md").write_text("|a|b|\n|---|---|\n|in neighboring areas during|2|\n")
    report = assemble_workflow(str(batch_dir))
    assert report.text == (
        "assemble FAILED (region_word_missing): tables/p1_0_fixed.md lacks words printed in the region and listed in "
        "tables/p1_0_missing.txt: droughts"
    )
    assert read_log(conversion_log)[-1]["failure_class"] == "region_word_missing"
    (batch_dir / "tables" / "p1_0_fixed.md").write_text("|a|b|\n|---|---|\n|in neighboring areas<br>during droughts|2|\n")
    assert assemble_workflow(str(batch_dir)).ok


def test_a_footnote_continuation_left_in_a_converter_footnote_box_is_joined_without_its_quote_mark(tmp_path):
    batch_dir = batch(tmp_path, [
        "may qualify as prohibited child labour under this Convention.[^14] Growing cocoa involves\n\n"
        "[^14]: For any type of work that is ‘likely to jeopardize the health, safety or morals of young\n",
        "long hours in the sun performing physically demanding work.\n\n### Trafficking in persons\n\n"
        "Ivorian law does not prohibit trafficking in persons.[^18]\n\n"
        "> persons’ the minimum age is 18 years also; ILO C138, art. 2.\n\n"
        "[^15]: Trafficking is not solely a child labour issue.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 2: 1->2(body) 1->2(footnote)" in report.text, report.text
    first, second = book_pages(batch_dir)
    assert first.split("\n\n") == [
        "may qualify as prohibited child labour under this Convention.[^14] Growing cocoa involves long hours in the sun performing physically demanding work.",
        "[^14]: For any type of work that is ‘likely to jeopardize the health, safety or morals of young persons’ the minimum age is 18 years also; ILO C138, art. 2.",
    ]
    assert second.split("\n\n") == [
        "### Trafficking in persons", "Ivorian law does not prohibit trafficking in persons.[^18]", "[^15]: Trafficking is not solely a child labour issue.",
    ]


def test_an_open_footnote_takes_the_lowercase_paragraph_before_the_first_footnote_of_the_next_page(tmp_path):
    batch_dir = batch(tmp_path, [
        "Ivorian law does not prohibit trafficking in persons.[^18]\n\n"
        "[^18]: At least nine traffickers were arrested in 2002; however, all anti-trafficking law\n",
        "## Response of the global cocoa industry\n\nBefore Congress voted, the cocoa industry announced an initiative ‘to\n\n"
        "enforcement efforts in Côte d’Ivoire have ceased since September 2002 (USDOS 2003).\n\n"
        "[^19]: Trade Act of 1930, § 307.\n",
        "address the workers’ rights issues recently identified’.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 2: 1->2(footnote) 2->3(body)" in report.text, report.text
    first, second, third = book_pages(batch_dir)
    assert first.endswith(
        "[^18]: At least nine traffickers were arrested in 2002; however, all anti-trafficking law "
        "enforcement efforts in Côte d’Ivoire have ceased since September 2002 (USDOS 2003)."
    )
    assert second.split("\n\n") == [
        "## Response of the global cocoa industry",
        "Before Congress voted, the cocoa industry announced an initiative ‘to address the workers’ rights issues recently identified’.",
        "[^19]: Trade Act of 1930, § 307.",
    ]
    assert third == ""


def test_a_running_footer_kept_on_page_one_is_no_join_target_even_reformatted_by_the_worker(tmp_path):
    batch_dir = batch(tmp_path, [
        "This case also demonstrates that pressure on consumer brands facilitates collaborative action.\n\nJCC 18 *Summer 2005*\n",
        "Reports of slave labour on cocoa farms surfaced as early as 1998.\n",
    ], running=("**JCC 18** _Summer 2005_",))
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 0: none" in report.text, report.text
    assert book_pages(batch_dir) == [
        "This case also demonstrates that pressure on consumer brands facilitates collaborative action.\n\nJCC 18 *Summer 2005*",
        "Reports of slave labour on cocoa farms surfaced as early as 1998.",
    ]


def test_a_paragraph_ending_in_an_email_address_is_closed(tmp_path):
    batch_dir = batch(tmp_path, [
        "**Anthony P. Ewing** is a lawyer.\n\n451 Walton Road, Maplewood, NJ 07040, USA\n\n! aewing@law.columbia.edu\n",
        "Reports of slave labour on cocoa farms surfaced as early as 1998.\n",
    ])
    report = assemble_workflow(str(batch_dir))
    assert "page joins: 0: none" in report.text, report.text
    assert book_pages(batch_dir)[1] == "Reports of slave labour on cocoa farms surfaced as early as 1998."


def joins_of(batch_dir):
    return assemble_workflow(str(batch_dir)).text.splitlines()[-1]


def test_a_closed_citation_note_and_a_next_page_without_footnotes_join_only_the_body(tmp_path):
    batch_dir = batch(tmp_path, [
        "(and this despite the signing in September 2007 of the United\n\n"
        "[^101]: The surveyed countries included: Papua New Guinea, Philippines, and Thailand. _See (Iocca 2010)_\n",
        "Nations Declaration on the Rights of Indigenous Peoples by 144 States) (Iocca 2010).\n\n### Summary\n\n"
        "The goal of this chapter has been to impress upon the reader the scope of the gap.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"
    first, _ = book_pages(batch_dir)
    assert first.endswith("[^101]: The surveyed countries included: Papua New Guinea, Philippines, and Thailand. _See (Iocca 2010)_")


def test_an_open_footnote_whose_only_candidate_is_the_body_continuation_is_not_joined(tmp_path):
    batch_dir = batch(tmp_path, [
        "the Committee on the Elimination of Racial Discrimination,[^67] the Inter-American\n\n"
        "[^67]: interests are taken without their informed consent.‖ [cite]\n",
        "Declaration on the Rights of Indigenous Peoples.  Following the Rio Declaration, numerous instruments followed.\n\n"
        "[^68]: The principle of prior informed consent has received widespread support.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"


def test_paragraphs_after_a_footnote_definition_belong_to_the_footnote(tmp_path):
    batch_dir = batch(tmp_path, [
        "The United States went so far as to withhold funding.[^102] This pressure led the Bank in 1984 to\n\n"
        "[^102]: As the Bank's own two decade review of its investment in infrastructure explains:\n\n"
        "The Bank is also often criticized for not being effective at listening to stakeholders.\n\n"
        "[^103]: In 1989, the Congress required analysis available to the general public for at\n",
        "elaborate further on its environmental policy in OMS 2.36.\n\n"
        "least 120 days prior to the approval date.\n\n[^104]: Bank 1987.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 2: 1->2(body) 1->2(footnote)"
    first, second = book_pages(batch_dir)
    assert first.split("\n\n")[0].endswith("led the Bank in 1984 to elaborate further on its environmental policy in OMS 2.36.")
    assert first.endswith("[^103]: In 1989, the Congress required analysis available to the general public for at least 120 days prior to the approval date.")
    assert second == "[^104]: Bank 1987."


def test_on_a_page_without_footnotes_the_paragraph_after_an_open_paragraph_continues_the_footnote(tmp_path):
    batch_dir = batch(tmp_path, [
        "Perhaps a more precise measure is the increase in contact.[^169]\n\n"
        "[^169]: Standard Chartered Bank, as well as Korea First Bank, a subsidiary of Standard\n",
        "While it is worth keeping in mind the distinction, there is a new normal now.\n\n"
        "To gather some data, respondents were asked; eleven banks said that these campaigns did pose risks to their\n\n"
        "Chartered, (also an EPFI) are in the syndicate for the Rapu Rapu project (_Id._).\n",
        "other business lines.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 2: 1->2(footnote) 2->3(body)"
    first, second, _ = book_pages(batch_dir)
    assert first.endswith("a subsidiary of Standard Chartered, (also an EPFI) are in the syndicate for the Rapu Rapu project (_Id._).")
    assert second.endswith("did pose risks to their other business lines.")


def test_an_open_footnote_does_not_take_an_uppercase_first_paragraph_of_the_next_page(tmp_path):
    batch_dir = batch(tmp_path, [
        "The declaration was adopted with 144 countries voting in its favor.\n\n"
        "[^72]: IFC sets out political and conceptual arguments for adopting the term\n",
        "The second Rio Declaration norm, the precautionary approach, is found in Principle 15.[^73]\n\n"
        "[^73]: Principle 15, Rio Declaration.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 0: none"


def test_a_body_continuation_skips_a_page_left_with_only_footnotes(tmp_path):
    batch_dir = batch(tmp_path, [
        "investors affected by investment have little to no recourse against the\n",
        "impacts of these investments.[^85] The agreements did not create obligations.[^86] Mann\n\n"
        "[^85]: A case in point is the dispute in El Salvador.\n\n"
        "[^86]: As Howard Mann observes, this mention falls short of explicit standards, it does link\n",
        "notes that several US agreements impose more extensive labor obligations.\n\n"
        "human rights to investment. _See_ Art. 7.2, Investment Agreement.\n\n[^87]: Freezing clauses.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 3: 1->2(body) 1->3(body) 2->3(footnote)"
    first, second, third = book_pages(batch_dir)
    assert first.endswith("did not create obligations.[^86] Mann notes that several US agreements impose more extensive labor obligations.")
    assert second.endswith("it does link human rights to investment. _See_ Art. 7.2, Investment Agreement.")
    assert third == "[^87]: Freezing clauses."


@pytest.mark.parametrize("page_end, next_start", [
    ("as a driver of ―compliance.‖", "Improvements, we said, are bought at a price."),
    ("measures to obstruct environmental measures (213).</mark>", "<mark>Indeed, the advent of impact assessment changed this."),
    ("analysis on the threat of reputational risk (Wright and Rwabizambuga 2006)", "Offering some evidence, my research shows this."),
    ("**<u>Panel B:  experience with external stakeholders – summary statistics</u>**", "**Panel C: measures** **<u>of implementation</u>**"),
])
def test_closing_quote_glyph_trailing_tag_citation_and_bold_title_end_a_paragraph(tmp_path, page_end, next_start):
    batch_dir = batch(tmp_path, [page_end + "\n", next_start + "\n"])
    assert joins_of(batch_dir) == "page joins: 0: none"


def test_an_open_paragraph_and_a_footnote_ending_in_a_url_join_only_the_body(tmp_path):
    batch_dir = batch(tmp_path, [
        "a monitoring procedure is missing.  Even fewer\n\n[^189]: Rodriguez, http://www.carbonsmart.co.uk/?q=webfm_send/2\n",
        "banks have established a monitoring and evaluation procedure (IFC 2007).\n\n### Outcome effectiveness\n\n"
        "The survey asked:  ―Have you ever had to call an event of default?‖  Of the reporting institutions, 83\n\n"
        "[^190]: _See_ Equator Principles.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"


def test_an_enumerated_item_is_not_continued_by_the_next_item(tmp_path):
    batch_dir = batch(tmp_path, [
        "(4) external effects of the regime on the industry (specifically on non-participating institutions);\n",
        "(5) governance of the regime (transparency of process, etc)\n\n(6) political legitimacy\n\n"
        "Particular emphasis will be placed on implementation.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 0: none"
    batch_dir = batch(tmp_path / "roman", [
        "vi) accept subscriptions and donations, invest or expend all monies belonging to the Association;\n",
        "vii) hold any monies of the Association in a deposit account;\n\nix) do all such other things as will further the above.\n",
    ])
    assert joins_of(batch_dir) == "page joins: 0: none"


def test_symbol_notes_and_a_notes_label_after_a_table_are_table_notes_and_the_body_runs_over_the_next_table(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "**TABLE 1** Top 10 Mandated Arrangers of Global Project Finance Loans\n\n<!-- TABLE p1_0 -->\n\n"
        "[^*]: Equator bank as of June 30, 2004.\n\n_Notes_: Data based on equal apportionment between mandated arrangers.\n\n"
        "as more financial institutions adopt them.\n\n"
        "For example, of the current financial institutions that have signed the statement on the environment and\n",
        "**TABLE 2** Top 10 Mandated Arrangers of Latin American Project Finance Loans\n\n<!-- TABLE p2_0 -->\n\n"
        "[^*]: Equator bank as of June 30, 2004.\n\n[^**]: Not formally an Equator bank, but the Equator Principles are based on the IFC’s policies.\n\n"
        "sustainable development, 72 percent are from Europe.[^46]\n\n[^46]: Source.\n",
    ], tables=("p1_0", "p2_0"))
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"
    first, second = book_pages(batch_dir)
    assert first.endswith("on the environment and sustainable development, 72 percent are from Europe.[^46]")
    assert second == (
        f"**TABLE 2** Top 10 Mandated Arrangers of Latin American Project Finance Loans\n\n{TABLE}\n\n"
        "[^*]: Equator bank as of June 30, 2004.\n\n[^**]: Not formally an Equator bank, but the Equator Principles are based on the IFC’s policies.\n\n"
        "[^46]: Source."
    )


def test_an_uppercase_continuation_after_a_table_followed_by_body_text_is_joined_and_the_body_after_it_runs_on(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "For example, the regional league table covering\n",
        "**TABLE 3** Top 10 Mandated Arrangers of African Project Finance Loans\n\n<!-- TABLE p2_0 -->\n\n"
        "[^*]: Equator bank as of June 30, 2004.\n\n**TABLE 4** Top 10 Mandated Arrangers of Asian Project Finance Loans\n\n"
        "<!-- TABLE p2_1 -->\n\nAfrica and the Middle East includes only five Western European banks (see Table 3).\n\n"
        "These distributions suggest that regional environments produce different incentives for firms to adopt\n",
        "voluntary codes of conduct.\n",
    ], tables=("p2_0", "p2_1"))
    assert joins_of(batch_dir) == "page joins: 2: 1->2(body) 2->3(body)"
    first, second, third = book_pages(batch_dir)
    assert first == "For example, the regional league table covering Africa and the Middle East includes only five Western European banks (see Table 3)."
    assert second.endswith(f"{TABLE}\n\nThese distributions suggest that regional environments produce different incentives for firms to adopt voluntary codes of conduct.")
    assert third == ""


def test_an_uppercase_last_paragraph_after_a_table_is_body_text(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "Table 7.1 – _Bank perception of extent of collective reputation_\n\n<!-- TABLE p1_0 -->\n\n"
        "As Table 7.1 illustrates, 47.8% of those who agreed on individual reputation disagree or disagreed\n",
        "strongly with the possibility of having a collective reputation.\n",
    ], tables=("p1_0",))
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"
    assert book_pages(batch_dir)[0].endswith("disagree or disagreed strongly with the possibility of having a collective reputation.")


def test_lowercase_text_directly_after_a_figure_continues_the_page_before(tmp_path, conversion_log):
    batch_dir = batch(tmp_path, [
        "the strategic incentives they produce for firms shed light on the wide\n",
        "**FIGURE 1** Governance Levels in Home Countries of Equator Banks\n\n<!-- FIGURE p2_0 -->\n\n"
        "and rapid uptake of the Equator Principles among financial institutions headquartered there.\n",
    ], figures=("p2_0",))
    assert joins_of(batch_dir) == "page joins: 1: 1->2(body)"
    first, second = book_pages(batch_dir)
    assert first.endswith("shed light on the wide and rapid uptake of the Equator Principles among financial institutions headquartered there.")
    assert second == f"**FIGURE 1** Governance Levels in Home Countries of Equator Banks\n\n{FIGURE}"


def test_heading_lines_moved_into_another_order_by_a_page_worker_pass_the_mark_check():
    from src.pdf.assemble import require_heading_marks_kept
    require_heading_marks_kept(1, "#### A\n\ntext\n\n### B\n", "### B\n\ntext\n\n#### A\n")
