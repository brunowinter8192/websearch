# INFRASTRUCTURE
import pytest

from dev.tests._pdf_fakes import conversion_log, numbered_pages, read_manifest, worker_output, write_pdf
from src.pdf.report import WorkflowError
from src.pdf.resplit import resplit_workflow
from src.pdf.split import split_workflow


# FUNCTIONS

@pytest.fixture
def split_dir(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Book.pdf", numbered_pages(85))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    return batch_dir


def spans(batch_dir):
    return [(piece["from"], piece["to"]) for piece in read_manifest(batch_dir)["pieces"]]


def test_blocked_fifty_page_piece_becomes_twenty_twenty_and_ten(split_dir):
    report = resplit_workflow(str(split_dir), "1-50")
    assert report.ok
    assert spans(split_dir) == [(1, 20), (21, 40), (41, 50), (51, 85)]
    assert not (split_dir / "prompt_1-50.md").exists()
    for span in ("1-20", "21-40", "41-50"):
        prompt = (split_dir / f"prompt_{span}.md").read_text()
        assert f"Output file: {split_dir / f'piece_{span}.md'}" in prompt
        assert f'pages parameter "{span}"' in prompt
    assert "prompts: prompt_1-20.md prompt_21-40.md prompt_41-50.md" in report.text


def assert_refused_as_minimal(batch_dir, piece):
    before = read_manifest(batch_dir)
    with pytest.raises(WorkflowError) as raised:
        resplit_workflow(str(batch_dir), piece)
    assert raised.value.failure_class == "piece_minimal"
    assert read_manifest(batch_dir) == before
    assert (batch_dir / f"prompt_{piece}.md").is_file()


def test_a_twenty_page_piece_becomes_two_ten_page_pieces_and_ten_pages_is_final(split_dir):
    resplit_workflow(str(split_dir), "1-50")
    report = resplit_workflow(str(split_dir), "1-20")
    assert "into 2 pieces of at most 10 pages" in report.text
    assert spans(split_dir)[:3] == [(1, 10), (11, 20), (21, 40)]
    for piece in ("1-10", "11-20", "41-50"):
        assert_refused_as_minimal(split_dir, piece)


def test_a_remainder_skips_the_sizes_it_is_not_larger_than(split_dir):
    resplit_workflow(str(split_dir), "51-85")
    assert spans(split_dir)[1:] == [(51, 70), (71, 85)]
    resplit_workflow(str(split_dir), "71-85")
    assert spans(split_dir)[2:] == [(71, 80), (81, 85)]
    for piece in ("71-80", "81-85"):
        assert_refused_as_minimal(split_dir, piece)


def test_an_eighteen_page_piece_becomes_ten_and_eight_and_the_eight_is_final(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Short.pdf", numbered_pages(18))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    resplit_workflow(str(batch_dir), "1-18")
    assert spans(batch_dir) == [(1, 10), (11, 18)]
    assert_refused_as_minimal(batch_dir, "11-18")


@pytest.mark.parametrize("name, pages, chain, final", [
    ("Schelling_1981", 25, ["1-25", "1-20"], [(1, 10), (11, 20), (21, 25)]),
    ("Jensen_2001", 17, ["1-17"], [(1, 10), (11, 17)]),
    ("Brennan_2012", 12, ["1-12"], [(1, 10), (11, 12)]),
    ("Hayek_1939", 23, ["1-23", "1-20"], [(1, 10), (11, 20), (21, 23)]),
])
def test_the_articles_blocked_on_2026_11_19_end_at_pieces_of_ten_pages_or_fewer(tmp_path, conversion_log, name, pages, chain, final):
    pdf = write_pdf(tmp_path / f"{name}.pdf", numbered_pages(pages))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    for piece in chain:
        assert resplit_workflow(str(batch_dir), piece).ok
    assert spans(batch_dir) == final
    for first, last in final:
        assert_refused_as_minimal(batch_dir, f"{first}-{last}")


def test_a_finished_piece_is_never_split(split_dir):
    (split_dir / "piece_1-50.md").write_text(worker_output(1, 50))
    with pytest.raises(WorkflowError) as raised:
        resplit_workflow(str(split_dir), "1-50")
    assert raised.value.failure_class == "piece_finished"
    assert spans(split_dir) == [(1, 50), (51, 85)]


def test_splitting_one_piece_leaves_finished_pieces_and_their_files_untouched(split_dir):
    finished = worker_output(1, 50)
    (split_dir / "piece_1-50.md").write_text(finished)
    before = read_manifest(split_dir)["pieces"][0]
    resplit_workflow(str(split_dir), "51-85")
    after = read_manifest(split_dir)
    assert after["pieces"][0] == before
    assert (split_dir / "piece_1-50.md").read_text() == finished
    assert (split_dir / "prompt_1-50.md").is_file()


def test_unknown_piece_is_refused(split_dir):
    for piece in ("1-40", "51", "abc"):
        with pytest.raises(WorkflowError) as raised:
            resplit_workflow(str(split_dir), piece)
        assert raised.value.failure_class == "piece_unknown"


def test_a_blocked_piece_with_an_incomplete_file_is_split_and_its_file_set_aside(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Brennan_2012.pdf", numbered_pages(12))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    left = worker_output(1, 4) + "\n<!-- page 5 -->\n\nThe difference between the\n"
    (batch_dir / "piece_1-12.md").write_text(left)
    report = resplit_workflow(str(batch_dir), "1-12")
    assert report.ok
    assert spans(batch_dir) == [(1, 10), (11, 12)]
    assert "set aside: blocked/piece_1-12.md" in report.text
    assert not (batch_dir / "piece_1-12.md").exists()
    assert (batch_dir / "blocked" / "piece_1-12.md").read_text() == left


def test_part_files_left_by_a_blocked_split_worker_are_set_aside(tmp_path, conversion_log):
    pdf = write_pdf(tmp_path / "Hayek_1939.pdf", numbered_pages(23))
    batch_dir = tmp_path / "batches"
    split_workflow(str(pdf), str(batch_dir))
    (batch_dir / "part1_1-23.md").write_text(worker_output(1, 20))
    report = resplit_workflow(str(batch_dir), "1-23")
    assert "set aside: blocked/part1_1-23.md" in report.text
    assert not (batch_dir / "part1_1-23.md").exists()
    assert (batch_dir / "blocked" / "part1_1-23.md").is_file()
    assert spans(batch_dir) == [(1, 20), (21, 23)]


def test_a_blocked_piece_without_any_file_sets_nothing_aside(split_dir):
    report = resplit_workflow(str(split_dir), "51-85")
    assert "set aside: none" in report.text
