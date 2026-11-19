# INFRASTRUCTURE
import pytest

from src.config import PIECE_PAGES
from src.pdf.pieces import plan_ranges
from src.pdf.split import PARALLEL_WORKERS


# FUNCTIONS

@pytest.mark.parametrize("pages, count, first, last", [
    (993, 20, (1, 50), (951, 993)),
    (1000, 20, (1, 50), (951, 1000)),
    (1001, 21, (1, 50), (1001, 1001)),
    (1050, 21, (1, 50), (1001, 1050)),
    (50, 1, (1, 50), (1, 50)),
    (51, 2, (1, 50), (51, 51)),
    (100, 2, (1, 50), (51, 100)),
])
def test_plan_ranges_covers_every_page_in_fifties(pages, count, first, last):
    pieces = plan_ranges(1, pages, PIECE_PAGES)
    assert len(pieces) == count
    assert pieces[0] == first
    assert pieces[-1] == last
    covered = [page for start, end in pieces for page in range(start, end + 1)]
    assert covered == list(range(1, pages + 1))


def test_plan_ranges_inside_a_piece_starts_at_its_first_page():
    assert plan_ranges(51, 100, 20) == [(51, 70), (71, 90), (91, 100)]


def test_a_book_of_one_thousand_pages_fits_one_wave_of_twenty_workers():
    assert PARALLEL_WORKERS == 20
    assert len(plan_ranges(1, 1000, PIECE_PAGES)) <= PARALLEL_WORKERS
    assert len(plan_ranges(1, 1001, PIECE_PAGES)) > PARALLEL_WORKERS
